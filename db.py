"""SQLite storage + business rules for the CMS School construction app."""
import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "cms_construction.db"


FLOORS = ["Ground Floor", "First Floor", "Second Floor"]

# Cost heads used for budget vs actual (Account page)
HEADS = ["Labour (wages)", "Materials", "Equipment & tools", "Contractor / sub-contract",
         "Transport", "Site overheads", "Approvals & fees", "Miscellaneous"]
EXPENSE_HEADS = HEADS[2:]            # heads that can be chosen for "Other expenses"
PURCHASE_HEAD = {"Tools & Equipment": "Equipment & tools", "Labour / Contract": "Contractor / sub-contract"}

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
CREATE TABLE IF NOT EXISTS wage_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_end TEXT NOT NULL, worker_id INTEGER NOT NULL,
    days REAL, rate REAL, gross REAL, deduction REAL DEFAULT 0, net REAL, paid_on TEXT, remarks TEXT DEFAULT '',
    UNIQUE (week_end, worker_id)
);
CREATE TABLE IF NOT EXISTS advances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id INTEGER NOT NULL, adv_date TEXT NOT NULL, amount REAL NOT NULL, remarks TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS fund_receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rec_date TEXT, source TEXT DEFAULT '', amount REAL, mode TEXT DEFAULT '', ref TEXT DEFAULT '', remarks TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exp_date TEXT, head TEXT DEFAULT '', description TEXT DEFAULT '', paid_to TEXT DEFAULT '',
    amount REAL, mode TEXT DEFAULT '', ref TEXT DEFAULT '', remarks TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS supplier_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pay_date TEXT, supplier TEXT DEFAULT '', amount REAL, mode TEXT DEFAULT '', ref TEXT DEFAULT '', remarks TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS budgets (head TEXT PRIMARY KEY, amount REAL DEFAULT 0);
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
        wcols = [r["name"] for r in c.execute("PRAGMA table_info(workers)").fetchall()]
        if "daily_wage" not in wcols:
            c.execute("ALTER TABLE workers ADD COLUMN daily_wage REAL")
        for h in HEADS:
            c.execute("INSERT OR IGNORE INTO budgets (head, amount) VALUES (?, 0)", (h,))
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

    _seed_extra_activities()


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


# Activities added after the first release (inserted once into databases that already exist)
EXTRA_ACTIVITIES = [
    ("Ground Floor", "Door and windows fixing", date(2026, 12, 15), date(2026, 12, 20)),
    ("Ground Floor", "Inner plaster", date(2026, 12, 16), date(2026, 12, 30)),
]


def _insert_activity(c, floor, name, p_start, p_end, is_concrete=None):
    r = c.execute("SELECT value FROM settings WHERE key=?", (f"floor_start::{floor}",)).fetchone()
    fs = date.fromisoformat(r["value"]) if r else DEFAULT_FLOOR_START[floor]
    if is_concrete is None:
        is_concrete = _is_concrete(name)
    c.execute(
        "INSERT INTO activities (floor,seq,name,offset_days,duration_days,planned_start,planned_end,is_concrete)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (floor, 9999, name, (p_start - fs).days, (p_end - p_start).days + 1,
         p_start.isoformat(), p_end.isoformat(), int(is_concrete)))
    _resequence(c, floor)


def _resequence(c, floor):
    """Number the activities of a floor in order of planned start date."""
    ids = [r["id"] for r in c.execute(
        "SELECT id FROM activities WHERE floor=? ORDER BY planned_start, planned_end, seq, id", (floor,)).fetchall()]
    for i, aid in enumerate(ids, 1):
        c.execute("UPDATE activities SET seq=? WHERE id=?", (i, aid))


def add_activity(floor, name, p_start, p_end, is_concrete=None):
    with conn() as c:
        _insert_activity(c, floor, name.strip(), p_start, p_end, is_concrete)


def delete_activity(activity_id):
    with conn() as c:
        row = c.execute("SELECT floor FROM activities WHERE id=?", (activity_id,)).fetchone()
        c.execute("DELETE FROM activities WHERE id=?", (activity_id,))
        if row:
            _resequence(c, row["floor"])


def _seed_extra_activities():
    with conn() as c:
        if c.execute("SELECT 1 FROM settings WHERE key='extra_activities_v1'").fetchone():
            return
        for floor, name, ps, pe in EXTRA_ACTIVITIES:
            if not c.execute("SELECT 1 FROM activities WHERE floor=? AND name=?", (floor, name)).fetchone():
                _insert_activity(c, floor, name, ps, pe)
        c.execute("INSERT OR REPLACE INTO settings VALUES ('extra_activities_v1', '1')")


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
