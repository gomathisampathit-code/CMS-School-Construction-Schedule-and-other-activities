"""Permanent storage for the SQLite database.

Streamlit Community Cloud erases the app's disk whenever the app sleeps, restarts or is redeployed.
This module keeps a copy of cms_construction.db in a PRIVATE GitHub repository:
  * after every change the database file is uploaded (push)
  * when the app starts with no database file, the saved copy is downloaded (restore)

Set it up once in Streamlit Cloud -> Manage app -> Settings -> Secrets:

    [github_storage]
    token  = "github_pat_xxx"                  # fine-grained token: Contents = Read and write, ONLY the data repo
    repo   = "your-username/cms-construction-data"   # a separate PRIVATE repo (not the app repo)
    path   = "cms_construction.db"
    branch = "main"
"""
import base64
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import streamlit as st

import db

API = "https://api.github.com"
IST = timezone(timedelta(hours=5, minutes=30))
_state = {"sha": None, "last_ok": None, "last_error": None, "restored": False}
REQUIRED_TABLES = {"activities", "workers", "attendance", "purchases", "settings"}


# ---------------------------------------------------------------- configuration
def _cfg():
    try:
        s = st.secrets["github_storage"]
        return {"token": s["token"], "repo": s["repo"], "path": s.get("path", "cms_construction.db"),
                "branch": s.get("branch", "main")}
    except Exception:
        pass
    if os.environ.get("GH_STORAGE_TOKEN") and os.environ.get("GH_STORAGE_REPO"):
        return {"token": os.environ["GH_STORAGE_TOKEN"], "repo": os.environ["GH_STORAGE_REPO"],
                "path": os.environ.get("GH_STORAGE_PATH", "cms_construction.db"),
                "branch": os.environ.get("GH_STORAGE_BRANCH", "main")}
    return None


def enabled():
    return _cfg() is not None


def _headers(cfg, raw=False):
    return {"Authorization": f"Bearer {cfg['token']}",
            "Accept": "application/vnd.github.raw+json" if raw else "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}


def _url(cfg):
    return f"{API}/repos/{cfg['repo']}/contents/{cfg['path']}"


def _now():
    return datetime.now(IST)


# ---------------------------------------------------------------- download / upload
def fetch_remote():
    """Return the saved database bytes, or None if nothing has been saved yet. Raises on any other problem."""
    cfg = _cfg()
    r = requests.get(_url(cfg), headers=_headers(cfg), params={"ref": cfg["branch"]}, timeout=20)
    if r.status_code == 404:
        _state["sha"] = None
        return None
    r.raise_for_status()
    meta = r.json()
    _state["sha"] = meta["sha"]
    if meta.get("content"):
        return base64.b64decode(meta["content"])
    raw = requests.get(_url(cfg), headers=_headers(cfg, raw=True), params={"ref": cfg["branch"]}, timeout=60)
    raw.raise_for_status()
    return raw.content


def _refresh_sha(cfg):
    r = requests.get(_url(cfg), headers=_headers(cfg), params={"ref": cfg["branch"]}, timeout=20)
    _state["sha"] = r.json().get("sha") if r.status_code == 200 else None


def push():
    """Upload the current database file. Never raises - problems are shown in the sidebar."""
    cfg = _cfg()
    if not cfg or _state.get("block_push") or not db.DB_PATH.exists():
        return False
    try:
        content = base64.b64encode(db.DB_PATH.read_bytes()).decode()
        for _ in range(3):
            body = {"message": f"data update {_now():%d %b %Y %H:%M}", "content": content, "branch": cfg["branch"]}
            if _state["sha"]:
                body["sha"] = _state["sha"]
            r = requests.put(_url(cfg), headers=_headers(cfg), json=body, timeout=30)
            if r.status_code in (200, 201):
                _state["sha"] = r.json()["content"]["sha"]
                _state["last_ok"], _state["last_error"] = _now(), None
                return True
            if r.status_code in (409, 422):          # stale / missing sha -> look it up and retry
                _refresh_sha(cfg)
                continue
            r.raise_for_status()
        _state["last_error"] = "could not save after 3 tries"
    except Exception as e:                            # noqa: BLE001
        _state["last_error"] = str(e)[:200]
    return False


# ---------------------------------------------------------------- start-up
def restore_if_needed():
    """Call once at app start, before the database is opened.
    Returns None when fine, or an error message (the app should then stop to protect the saved data)."""
    if not enabled() or db.DB_PATH.exists():
        return None
    try:
        data = fetch_remote()
    except Exception as e:                            # noqa: BLE001
        _state["block_push"] = True                   # never overwrite the saved copy with an empty database
        _state["last_error"] = str(e)[:200]
        return str(e)[:300]
    _state["block_push"] = False
    if data:
        db.DB_PATH.write_bytes(data)
        _state["restored"] = True
    return None


def setup():
    """Hook: upload automatically after every change to the database."""
    db.after_write = push


# ---------------------------------------------------------------- manual backup / restore
def backup_bytes():
    return db.DB_PATH.read_bytes() if db.DB_PATH.exists() else b""


def restore_from_bytes(data: bytes):
    """Replace the database with an uploaded backup. Returns an error text, or None when done."""
    if not data.startswith(b"SQLite format 3"):
        return "This is not a database backup file."
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    try:
        c = sqlite3.connect(tmp_path)
        names = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        c.close()
    except Exception as e:                            # noqa: BLE001
        tmp_path.unlink(missing_ok=True)
        return f"Could not read the file: {e}"
    missing = REQUIRED_TABLES - names
    if missing:
        tmp_path.unlink(missing_ok=True)
        return "This backup is missing tables: " + ", ".join(sorted(missing))
    tmp_path.unlink(missing_ok=True)
    db.DB_PATH.write_bytes(data)
    db.init_db()                                      # bring an older backup up to the current structure
    _state["block_push"] = False
    push()
    return None


def status_text():
    if not enabled():
        return None
    if _state["last_error"]:
        return f"⚠️ Cloud save problem: {_state['last_error']}"
    if _state["last_ok"]:
        return f"☁️ Saved to cloud at {_state['last_ok']:%I:%M %p, %d %b}"
    if _state["restored"]:
        return "☁️ Data restored from cloud"
    return "☁️ Cloud backup is on"
