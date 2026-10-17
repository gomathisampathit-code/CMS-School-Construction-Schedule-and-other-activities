# CMS School : Construction Schedule and other activities

A small site-management app (Streamlit + SQLite) with three pages:

| Page | What it does |
|---|---|
| **📅 Schedule** | Ground / First / Second floor activities with **planned** start–end. You enter the **actual** start and end dates. Actual dates and Status are free to enter (end date can be added later); delay in days is calculated. **You choose the status; remarks are for delays and only a reminder is shown. Includes a planned-vs-actual chart. 🟩 = concrete work. |
| **👷 Attendance** | Pick a date and mark who is working on site today (Present / Half day / Absent / Leave, in & out time). Add people once in *Workers list*. History tab shows days worked and daily headcount. |
| **💰 Account** *(admin only – Login ID `adminstar`)* | All the money details: **weekly wages every Saturday** from attendance × daily wage (with advances), **purchase expenses filtered by day / week / month / overall / custom dates**, other expenses, funds received & cash in hand, supplier payments and what is still owed, budget vs actual, and **Excel / CSV report downloads**. |
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

## Account page (admin)

- Opens only with **Login ID `adminstar`** and password (set in `auth.py`: `ADMIN_ID`, `ADMIN_PASSWORD`).
- First set each worker's **daily wage** in *Rates & Advances*. Then each Saturday open *Weekly Wages*, pick the Saturday, check the
  attendance grid, enter any advance to deduct, tick the workers and press **Record payment**.
- Pay week = Sunday to Saturday. Present = 1 day, Half day = 0.5 day.
- Download: every table has CSV / Excel buttons; the **Reports** tab gives one Excel file with all sheets.

## Password protection

- The first page asks for a password: **star123**.
- The password is written in `auth.py` (`PASSWORD = "star123"`). To change it, edit that line and restart the app.
- Use **🚪 Log out** in the left sidebar.
- This protects the app screen only. Anyone who can open the project folder can read `auth.py` or copy `cms_construction.db`, so keep the folder on a PC only you control.

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
