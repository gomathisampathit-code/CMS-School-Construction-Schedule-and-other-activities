"""Page 2 – Site attendance: who is working in the construction today."""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

import compat
import db

db.init_db()
STATUSES = ["Present", "Half day", "Absent", "Leave"]
ROLES = ["Mason", "Helper", "Bar bender", "Carpenter (centering)", "Electrician", "Plumber",
         "Painter", "Supervisor", "Site engineer", "Other"]

st.title("👷 Site Attendance")
st.caption("Mark who is working on site. Add people once in **Workers list**, then mark attendance every day.")

tab_today, tab_workers, tab_history = st.tabs(["✅ Daily attendance", "👥 Workers list", "📜 History"])


def workers_df(active_only=True):
    with db.conn() as c:
        q = "SELECT * FROM workers" + (" WHERE active=1" if active_only else "") + " ORDER BY name"
        return pd.DataFrame([dict(r) for r in c.execute(q).fetchall()],
                            columns=["id", "name", "role", "agency", "phone", "active"])


# ---------------------------------------------------------------- Workers list
with tab_workers:
    st.subheader("Workers list")
    w = workers_df(active_only=False)
    w_view = w.rename(columns={"name": "Name", "role": "Role", "agency": "Agency / Contractor",
                               "phone": "Phone", "active": "Active"})
    w_view["Active"] = w_view["Active"].astype(bool)
    edited_w = compat.data_editor(
        w_view, key="workers_editor", hide_index=True, num_rows="dynamic",
        column_order=["Name", "Role", "Agency / Contractor", "Phone", "Active"],
        column_config={
            "Name": st.column_config.TextColumn(required=True),
            "Role": st.column_config.SelectboxColumn(options=ROLES),
            "Active": st.column_config.CheckboxColumn(default=True,
                                                      help="Untick when the person has left the site"),
        },
    )
    st.caption("Add a row at the bottom to add a worker. Untick **Active** instead of deleting, "
               "so past attendance is kept.")
    if st.button("💾 Save workers list", type="primary"):
        with db.conn() as c:
            kept = set()
            for _, r in edited_w.iterrows():
                name = db.clean_text(r["Name"])
                if not name:
                    continue
                vals = (name, db.clean_text(r["Role"]), db.clean_text(r["Agency / Contractor"]),
                        db.clean_text(r["Phone"]), int(bool(r["Active"]) if not pd.isna(r["Active"]) else 1))
                wid = None if pd.isna(r.get("id")) else int(r["id"])
                if wid is not None:
                    c.execute("UPDATE workers SET name=?, role=?, agency=?, phone=?, active=? WHERE id=?", vals + (wid,))
                    kept.add(wid)
                else:
                    cur = c.execute("INSERT INTO workers (name, role, agency, phone, active) VALUES (?,?,?,?,?)", vals)
                    kept.add(cur.lastrowid)
            blocked = []
            for wid in set(w["id"].astype(int)) - kept:   # rows deleted in the table
                has_money = (c.execute("SELECT 1 FROM wage_payments WHERE worker_id=?", (wid,)).fetchone()
                             or c.execute("SELECT 1 FROM advances WHERE worker_id=?", (wid,)).fetchone())
                if has_money:
                    blocked.append(w.loc[w["id"] == wid, "name"].iloc[0])
                    continue
                c.execute("DELETE FROM attendance WHERE worker_id=?", (wid,))
                c.execute("DELETE FROM workers WHERE id=?", (wid,))
        if blocked:
            st.warning("Not deleted (wages / advances already recorded in Account): " + ", ".join(blocked)
                       + ". Untick **Active** instead.")
        st.success("Workers list saved.")
        if not blocked:
            st.rerun()

# ---------------------------------------------------------------- Daily attendance
with tab_today:
    att_date = st.date_input("Attendance date", value=date.today(), format="DD/MM/YYYY")
    st.subheader(f"{att_date:%A, %d %B %Y}")
    active = workers_df(active_only=True)
    if active.empty:
        st.info("No workers yet. Go to the **Workers list** tab and add the people working on site.")
    else:
        with db.conn() as c:
            saved = {r["worker_id"]: dict(r) for r in
                     c.execute("SELECT * FROM attendance WHERE att_date=?", (att_date.isoformat(),)).fetchall()}
        recs = []
        for _, r in active.iterrows():
            s = saved.get(int(r["id"]), {})
            recs.append({"ID": int(r["id"]), "Worker": r["name"], "Role": r["role"], "Agency": r["agency"],
                         "Status": s.get("status", "Absent" if saved else None),
                         "Remarks": s.get("remarks", "")})
        df = pd.DataFrame(recs)

        key = f"att_{att_date.isoformat()}"
        if st.button("Mark everyone present"):
            df["Status"] = "Present"
            st.session_state.pop(key, None)
            st.session_state["prefill_" + key] = df
        if "prefill_" + key in st.session_state:
            df = st.session_state["prefill_" + key]

        edited = compat.data_editor(
            df, key=key + ("_p" if "prefill_" + key in st.session_state else ""), hide_index=True,
            disabled=["ID", "Worker", "Role", "Agency"],
            column_order=["Worker", "Role", "Agency", "Status", "Remarks"],
            column_config={
                "Status": st.column_config.SelectboxColumn("Status ✏️", options=STATUSES),
                "Remarks": st.column_config.TextColumn("Remarks ✏️"),
            },
        )
        if st.button("💾 Save attendance", type="primary"):
            with db.conn() as c:
                for _, r in edited.iterrows():
                    status = r["Status"]
                    if status is None or pd.isna(status):
                        c.execute("DELETE FROM attendance WHERE att_date=? AND worker_id=?",
                                  (att_date.isoformat(), int(r["ID"])))
                        continue
                    c.execute(
                        "INSERT INTO attendance (att_date, worker_id, status, remarks) VALUES (?,?,?,?) "
                        "ON CONFLICT(att_date, worker_id) DO UPDATE SET status=excluded.status, remarks=excluded.remarks",
                        (att_date.isoformat(), int(r["ID"]), status, db.clean_text(r["Remarks"])))
            st.session_state.pop("prefill_" + key, None)
            st.success("Attendance saved.")
            st.rerun()

        # today's summary (from saved data)
        with db.conn() as c:
            summ = pd.DataFrame([dict(r) for r in c.execute(
                "SELECT w.name, w.role, w.agency, a.status FROM attendance a "
                "JOIN workers w ON w.id=a.worker_id WHERE a.att_date=?", (att_date.isoformat(),)).fetchall()])
        st.divider()
        if summ.empty:
            st.caption("Nothing saved for this date yet.")
        else:
            present = summ[summ["status"].isin(["Present", "Half day"])]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Working on site", len(present))
            c2.metric("Present", int((summ["status"] == "Present").sum()))
            c3.metric("Half day", int((summ["status"] == "Half day").sum()))
            c4.metric("Absent / leave", int(summ["status"].isin(["Absent", "Leave"]).sum()))
            if len(present):
                st.markdown("**Working on site – by role**")
                by_role = present.assign(role=present["role"].replace("", "(no role)")).groupby("role").size()
                compat.dataframe(by_role.rename("People").reset_index().rename(columns={"role": "Role"}),
                             hide_index=True, fit=True)

# ---------------------------------------------------------------- History
with tab_history:
    st.subheader("Attendance history")
    c1, c2 = st.columns(2)
    d_from = c1.date_input("From", value=date.today().replace(day=1), format="DD/MM/YYYY", key="h_from")
    d_to = c2.date_input("To", value=date.today(), format="DD/MM/YYYY", key="h_to")
    with db.conn() as c:
        hist = pd.DataFrame([dict(r) for r in c.execute(
            "SELECT a.att_date AS Date, w.name AS Worker, w.role AS Role, w.agency AS Agency, a.status AS Status, "
            "a.remarks AS Remarks FROM attendance a "
            "JOIN workers w ON w.id=a.worker_id WHERE a.att_date BETWEEN ? AND ? ORDER BY a.att_date DESC, w.name",
            (d_from.isoformat(), d_to.isoformat())).fetchall()])
    if hist.empty:
        st.info("No attendance saved in this period.")
    else:
        days = hist.groupby("Date")["Status"].apply(lambda s: int(s.isin(["Present", "Half day"]).sum()))
        st.markdown("**People working on site each day**")
        st.bar_chart(days.rename("People"))
        piv = hist.assign(Day=hist["Status"].map({"Present": 1, "Half day": 0.5}).fillna(0)) \
                  .groupby(["Worker", "Role"], as_index=False)["Day"].sum().rename(columns={"Day": "Days worked"})
        st.markdown("**Days worked per person**")
        compat.dataframe(piv.sort_values("Days worked", ascending=False), hide_index=True)
        st.markdown("**All records**")
        compat.dataframe(hist, hide_index=True)
        st.download_button("⬇️ Download as CSV", hist.to_csv(index=False).encode(),
                           file_name="attendance_history.csv", mime="text/csv")