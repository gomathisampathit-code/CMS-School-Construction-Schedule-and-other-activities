"""SQLite storage + business rules for the CMS School construction app."""
import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "cms_construction.db"

FLOORS = ["Ground Floor", "First Floor", "Second Floor"]

# Default planned start of each floor. First/Second floor dates are ASSUMPTIONS
# (14-day curing after the previous roof slab) - change them on the Schedule page.
DEFAULT_FLOOR_START = {
    "Ground Floor": date(2026, 10, 12),
    "First Floor": date(2026, 12, 14),
    "Second Floor": date(2027, 1, 25),
}

# (activity, start offset in days from floor start, duration in days)
GROUND = [
    ("Earth Work", 0, 2), ("PCC 1:4:8", 2, 3), ("Bar Bending", 3, 2),
    ("RCC Footing Concrete", 5, 2), ("Pedestal Centering", 7, 2), ("Pedestal RCC", 8, 2),
    ("Plinth Beam Earthwork", 10, 2), ("Plinth Beam PCC", 11, 2), ("Plinth Beam Bar Bending", 11, 2),
    ("Centering", 12, 3), ("Concrete (Plinth Beam)", 14, 2), ("Earth Filling & Levelling", 16, 4),
    ("Super Structure Column", 21, 3), ("RCC Concrete", 22, 3), ("Brickwork – Sill Level", 24, 8),
    ("Lintel Level", 30, 5), ("Lintel Centering", 34, 3), ("Bar Bending (Lintel)", 35, 3),
    ("Lintel RCC", 38, 1), ("Brickwork above Lintel", 39, 4), ("Centering Roof", 44, 4),
    ("Bar Bending (Roof)", 46, 3), ("Roof Concrete", 49, 1),
]
UPPER = [
    ("Super Structure Column", 0, 3), ("RCC Concrete", 1, 3), ("Brickwork – Sill Level", 3, 8),
    ("Lintel Level", 9, 5), ("Lintel Centering", 13, 3), ("Bar Bending (Lintel)", 14, 3),
    ("Lintel RCC", 17, 1), ("Brickwork above Lintel", 18, 4), ("Centering Roof", 23, 4),
    ("Bar Bending (Roof)", 25, 3), ("Roof Concrete", 28, 1),
]
TEMPLATES = {"Ground Floor": GROUND, "First Floor": UPPER, "Second Floor": UPPER}

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    floor TEXT NOT NULL, seq INTEGER NOT NULL, name TEXT NOT NULL,
    offset_days INTEGER NOT NULL, duration_days INTEGER NOT NULL,
    planned_start TEXT NOT NULL, planned_end TEXT NOT NULL,
    actual_start TEXT, actual_end TEXT, remarks TEXT DEFAULT '', is_concrete INTEGER DEFAULT 0,
    status TEXT
);
CREATE TABLE IF NOT EXISTS workers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL, role TEXT DEFAULT '', agency TEXT DEFAULT '', phone TEXT DEFAULT '',
    active INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    att_date TEXT NOT NULL, worker_id INTEGER NOT NULL,
    status TEXT NOT NULL, in_time TEXT, out_time TEXT, remarks TEXT DEFAULT '',
    UNIQUE (att_date, worker_id)
);
CREATE TABLE IF NOT EXISTS purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item TEXT NOT NULL, category TEXT DEFAULT '', quantity REAL, unit TEXT DEFAULT '',
    supplier TEXT DEFAULT '', rate REAL, amount REAL,
    order_date TEXT, expected_date TEXT, received_date TEXT,
    status TEXT DEFAULT 'Ordered', bill_no TEXT DEFAULT '', remarks TEXT DEFAULT ''
);
"""


@contextmanager
def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def _is_concrete(name: str) -> int:
    return int("Concrete" in name or "RCC" in name)


def init_db():
    with conn() as c:
        c.executescript(SCHEMA)
        cols = [r["name"] for r in c.execute("PRAGMA table_info(activities)").fetchall()]
        if "status" not in cols:                      # database created by an older version
            c.execute("ALTER TABLE activities ADD COLUMN status TEXT")
        if c.execute("SELECT COUNT(*) FROM activities").fetchone()[0] == 0:
            for floor in FLOORS:
                start = DEFAULT_FLOOR_START[floor]
                c.execute("INSERT OR REPLACE INTO settings VALUES (?,?)",
                          (f"floor_start::{floor}", start.isoformat()))
                for i, (name, off, dur) in enumerate(TEMPLATES[floor], 1):
                    ps = start + timedelta(days=off)
                    pe = ps + timedelta(days=dur - 1)
                    c.execute(
                        "INSERT INTO activities (floor,seq,name,offset_days,duration_days,planned_start,planned_end,is_concrete)"
                        " VALUES (?,?,?,?,?,?,?,?)",
                        (floor, i, name, off, dur, ps.isoformat(), pe.isoformat(), _is_concrete(name)))


# ---------------------------------------------------------------- helpers
def to_date(v):
    """Convert str / Timestamp / date / NaT / None -> date or None."""
    if v is None or v == "":
        return None
    try:
        import pandas as pd
        if pd.isna(v):
            return None
        if isinstance(v, pd.Timestamp):
            return v.date()
    except Exception:
        pass
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


def iso(v):
    d = to_date(v)
    return d.isoformat() if d else None


def clean_text(v):
    if v is None:
        return ""
    try:
        import pandas as pd
        if pd.isna(v):
            return ""
    except Exception:
        pass
    return str(v).strip()


# ---------------------------------------------------------------- schedule rules
STATUS_OPTIONS = ["Not started", "In progress", "Completed", "On hold"]


def derive_status(a_start, a_end):
    return "Completed" if a_end else ("In progress" if a_start else "Not started")


def sync_status(status, a_start, a_end):
    """The user chooses the status freely. Only obvious gaps are filled in:
    an actual end date -> Completed, an actual start date -> In progress."""
    status = status if status in STATUS_OPTIONS else derive_status(a_start, a_end)
    if a_end and status in ("Not started", "In progress"):
        return "Completed"
    if a_start and status == "Not started":
        return "In progress"
    return status


def delay_days(p_start, p_end, a_start, a_end, status, today=None):
    """Delay in days (0 = on time). Information only - it never blocks saving."""
    today = today or date.today()
    if status == "Completed" and a_end:
        d = (a_end - p_end).days
    elif a_start:
        d = max((a_start - p_start).days, (today - p_end).days if (today > p_end and status != "On hold") else 0)
    elif status == "Not started" and today > p_start:
        d = (today - p_start).days
    else:
        d = 0
    return max(d, 0)


def get_floor_start(floor):
    with conn() as c:
        r = c.execute("SELECT value FROM settings WHERE key=?", (f"floor_start::{floor}",)).fetchone()
    return date.fromisoformat(r["value"]) if r else DEFAULT_FLOOR_START[floor]


def set_floor_start(floor, new_start: date):
    """Re-plan a floor: shift every planned date using the stored offsets."""
    with conn() as c:
        c.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (f"floor_start::{floor}", new_start.isoformat()))
        for r in c.execute("SELECT id, offset_days, duration_days FROM activities WHERE floor=?", (floor,)).fetchall():
            ps = new_start + timedelta(days=r["offset_days"])
            pe = ps + timedelta(days=r["duration_days"] - 1)
            c.execute("UPDATE activities SET planned_start=?, planned_end=? WHERE id=?",
                      (ps.isoformat(), pe.isoformat(), r["id"]))
