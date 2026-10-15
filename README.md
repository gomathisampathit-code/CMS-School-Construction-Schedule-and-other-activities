# CMS School : Construction Schedule and other activities

A small site-management app (Streamlit + SQLite) with three pages:

| Page | What it does |
|---|---|
| **📅 Schedule** | Ground / First / Second floor activities with **planned** start–end. You enter the **actual** start and end dates. Actual dates and Status are free to enter (end date can be added later); delay in days is calculated. **You choose the status; remarks are for delays and only a reminder is shown. Includes a planned-vs-actual chart. 🟩 = concrete work. |
| **👷 Attendance** | Pick a date and mark who is working on site today (Present / Half day / Absent / Leave, in & out time). Add people once in *Workers list*. History tab shows days worked and daily headcount. |
| **🛒 Purchasing** | Purchase register with item, supplier, quantity, rate, amount, **order date, expected delivery date, received date**, status and bill no. Overdue deliveries are flagged. |

## Run it in Visual Studio Code

1. Install **Python 3.10+** and VS Code with the **Python** extension.
2. In VS Code: **File → Open Folder…** and choose this folder (`cms_construction_app`).
3. Open the terminal (**Terminal → New Terminal**) and run:

   ```
   python -m venv .venv
   .venv\Scripts\activate          # Windows   (Mac/Linux: source .venv/bin/activate)
   pip install -r requirements.txt
   streamlit run app.py
   ```
4. The app opens in your browser at http://localhost:8501.
   (Or press **F5** in VS Code and choose *Run CMS Construction App*.)

## Notes

- Data is stored in `cms_construction.db` (created on first run) in this folder. **Back up this file** to keep your data.
- First-floor and second-floor planned dates are *assumptions* (14 days curing after the previous slab).
  Change them on the Schedule page → **⚙️ Change planned floor start date** → *Re-plan this floor*.
- Delay rule: Completed late = actual end after planned end. In progress = delayed if started late or the planned
  end has passed. Not started = delayed once the planned start date has passed.
- To let several people use it on the site Wi-Fi, run `streamlit run app.py --server.address 0.0.0.0`
  and open `http://<your-PC-IP>:8501` on their phones. (SQLite suits one site office; for many simultaneous
  editors, move to a shared database.)
- Files: `app.py` (menu), `db.py` (database and delay rules), `views/schedule.py`, `views/attendance.py`, `views/purchasing.py`.
