"""Password protection for the app (one shared password, stored only as a salted hash)."""
import hashlib
import hmac
import os
import time

import streamlit as st

import db

ITERATIONS = 200_000
MIN_LENGTH = 6
MAX_FAILS = 5          # wrong attempts before a short lock
LOCK_SECONDS = 60


# ---------------------------------------------------------------- storage
def _get(key, default=None):
    with db.conn() as c:
        r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default


def _set(key, value):
    with db.conn() as c:
        c.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, str(value)))


def _delete(key):
    with db.conn() as c:
        c.execute("DELETE FROM settings WHERE key=?", (key,))


def _hash(password, salt=None):
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def _verify(password, stored):
    try:
        salt_hex, digest_hex = stored.split("$")
        expected = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), ITERATIONS)
        return hmac.compare_digest(expected.hex(), digest_hex)
    except Exception:
        return False


def password_is_set():
    return bool(_get("password_hash"))


def set_password(new_password):
    _set("password_hash", _hash(new_password))
    _delete("fail_count")
    _delete("lock_until")


# ---------------------------------------------------------------- screens
def _title():
    st.markdown("## 🏗️ CMS School : Construction Schedule and other activities")


def _setup_screen():
    _title()
    st.info("First time: create a password for this app. You will need it every time you open the app.")
    with st.form("setup"):
        p1 = st.text_input("New password", type="password")
        p2 = st.text_input("Confirm password", type="password")
        if st.form_submit_button("Create password", type="primary"):
            if len(p1) < MIN_LENGTH:
                st.error(f"Password must be at least {MIN_LENGTH} characters.")
            elif p1 != p2:
                st.error("The two passwords do not match.")
            else:
                set_password(p1)
                st.session_state["authed"] = True
                st.rerun()
    st.stop()


def _login_screen():
    _title()
    lock_until = float(_get("lock_until", 0) or 0)
    wait = int(lock_until - time.time())
    with st.form("login"):
        pw = st.text_input("Password", type="password")
        go = st.form_submit_button("Log in", type="primary", disabled=wait > 0)
    if wait > 0:
        st.error(f"Too many wrong attempts. Try again in {wait} seconds.")
    elif go:
        if _verify(pw, _get("password_hash", "")):
            _delete("fail_count")
            _delete("lock_until")
            st.session_state["authed"] = True
            st.rerun()
        else:
            fails = int(_get("fail_count", 0) or 0) + 1
            if fails >= MAX_FAILS:
                _set("lock_until", time.time() + LOCK_SECONDS)
                _set("fail_count", 0)
                st.error(f"Wrong password. Locked for {LOCK_SECONDS} seconds.")
            else:
                _set("fail_count", fails)
                st.error(f"Wrong password. {MAX_FAILS - fails} attempt(s) left.")
    st.caption("Forgot the password? Run `python reset_password.py` on this computer, then open the app again.")
    st.stop()


# ---------------------------------------------------------------- public API
def require_login():
    """Call at the top of app.py. Stops the script until the user is logged in."""
    if st.session_state.get("authed"):
        return
    if not password_is_set():
        _setup_screen()
    _login_screen()


def sidebar_account():
    """Log-out button and change-password form for the sidebar."""
    with st.sidebar:
        st.divider()
        with st.expander("🔑 Change password"):
            with st.form("change_pw", clear_on_submit=True):
                old = st.text_input("Current password", type="password")
                new1 = st.text_input("New password", type="password")
                new2 = st.text_input("Confirm new password", type="password")
                if st.form_submit_button("Change password"):
                    if not _verify(old, _get("password_hash", "")):
                        st.error("Current password is wrong.")
                    elif len(new1) < MIN_LENGTH:
                        st.error(f"New password must be at least {MIN_LENGTH} characters.")
                    elif new1 != new2:
                        st.error("The new passwords do not match.")
                    else:
                        set_password(new1)
                        st.success("Password changed.")
        if st.button("🚪 Log out"):
            st.session_state.clear()
            st.rerun()
