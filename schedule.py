"""Page 1 – Construction schedule: planned dates, actual dates + status entered freely by the user, delay remarks."""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

import compat
import db
from gantt import make_chart

if not hasattr(db, "STATUS_OPTIONS"):
    st.error("Your `db.py` is the old version. Please replace **both** `db.py` and `views/schedule.py` with the new files, "
             "then restart the app.")
    st.stop()

db.init_db()
TODAY = date.today()

st.title("📅 Construction Schedule")
st.caption("Planned dates come from the plan. **Actual Start, Actual End and Status are free for you to enter** – "
           "put the start date on the day work starts, and the end date whenever it finishes (it can be filled in later). "
           "Add a remark when an activity is delayed.")


def load(floor):
    with db.conn() as c:
        rows = c.execute("SELECT * FROM activities WHERE floor=? ORDER BY seq", (floor,)).fetchall()
    return [dict(r) for r in rows]


def build_frame(rows):
    out = []
    for r in rows:
        ps, pe = db.to_date(r["planned_start"]), db.to_date(r["planned_end"])
        a_s, a_e = db.to_date(r["actual_start"]), db.to_date(r["actual_end"])
        status = r.get("status") if r.get("status") in db.STATUS_OPTIONS else db.derive_status(a_s, a_e)
        out.append({
            "ID": r["id"], "#": r["seq"],
            "Activity": ("🟩 " if r["is_concrete"] else "") + r["name"],
            "Planned Start": ps, "Planned End": pe,
            "Actual Start": a_s, "Actual End": a_e,
            "Status": status,
            "Delay (days)": db.delay_days(ps, pe, a_s, a_e, status, TODAY),
            "Remarks": r["remarks"] or "",
        })
    df = pd.DataFrame(out)
    for col in ["Planned Start", "Planned End", "Actual Start", "Actual End"]:
        df[col] = pd.to_datetime(df[col])
    return df


def chart_rows(rows, kind):
    out = []
    for r in rows:
        ps, pe = db.to_date(r["planned_start"]), db.to_date(r["planned_end"])
        a_s, a_e = db.to_date(r["actual_start"]), db.to_date(r["actual_end"])
        label = f'{r["seq"]}. {r["name"]}'
        if kind == "Planned":
            out.append({"label": label, "start": ps, "end": pe, "concrete": bool(r["is_concrete"])})
        elif a_s:
            end = a_e or max(TODAY, a_s)
            out.append({"label": label, "start": a_s, "end": max(end, a_s), "concrete": bool(r["is_concrete"]),
                        "suffix": "" if a_e else "  – in progress"})
    return out


def live_rows(edited, base_rows):
    """Yield (name, row, status, delay) from what is currently typed in the table."""
    by_id = {r["id"]: r for r in base_rows}
    for _, row in edited.iterrows():
        base = by_id[int(row["ID"])]
        a_s, a_e = db.to_date(row["Actual Start"]), db.to_date(row["Actual End"])
        status = db.sync_status(row["Status"], a_s, a_e)
        ps, pe = db.to_date(base["planned_start"]), db.to_date(base["planned_end"])
        yield f'{base["seq"]}. {base["name"]}', row, status, db.delay_days(ps, pe, a_s, a_e, status, TODAY)


def date_errors(edited, base_rows):
    """Only one thing blocks saving: an end date earlier than the start date."""
    errs = []
    for name, row, _, _ in live_rows(edited, base_rows):
        a_s, a_e = db.to_date(row["Actual Start"]), db.to_date(row["Actual End"])
        if a_s and a_e and a_e < a_s:
            errs.append(f"**{name}**: Actual End is before Actual Start.")
    return errs


def remark_reminders(edited, base_rows):
    return [name for name, row, status, delay in live_rows(edited, base_rows)
            if delay > 0 and status != "On hold" and not db.clean_text(row["Remarks"])]


def save(edited, base_rows):
    with db.conn() as c:
        for name, row, status, _ in live_rows(edited, base_rows):
            c.execute("UPDATE activities SET actual_start=?, actual_end=?, status=?, remarks=? WHERE id=?",
                      (db.iso(row["Actual Start"]), db.iso(row["Actual End"]), status,
                       db.clean_text(row["Remarks"]), int(row["ID"])))


tabs = st.tabs(db.FLOORS)
for floor, tab in zip(db.FLOORS, tabs):
    with tab:
        rows = load(floor)
        df = build_frame(rows)

        done = int((df["Status"] == "Completed").sum())
        running = int((df["Status"] == "In progress").sum())
        delayed = int((df["Delay (days)"] > 0).sum())
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Activities", len(df))
        m2.metric("Completed", done)
        m3.metric("In progress", running)
        m4.metric("Delayed", delayed)
        st.progress(done / len(df), text=f"{done / len(df):.0%} of activities completed")

        start = db.get_floor_start(floor)
        end = df["Planned End"].max().date()
        st.markdown(f"**Planned:** {start:%a %d %b %Y} → {end:%a %d %b %Y}  &nbsp;·&nbsp; 🟩 = concrete work")

        edited = compat.data_editor(
            df, key=f"editor_{floor}", hide_index=True,
            disabled=["ID", "#", "Activity", "Planned Start", "Planned End", "Delay (days)"],
            column_order=["#", "Activity", "Planned Start", "Planned End", "Actual Start", "Actual End",
                          "Status", "Delay (days)", "Remarks"],
            column_config={
                "#": st.column_config.NumberColumn(width="small"),
                "Activity": st.column_config.TextColumn(width="medium"),
                "Planned Start": st.column_config.DateColumn(format="ddd DD MMM YYYY"),
                "Planned End": st.column_config.DateColumn(format="ddd DD MMM YYYY"),
                "Actual Start": st.column_config.DateColumn("Actual Start ✏️", format="ddd DD MMM YYYY",
                                                            help="Enter on the day the work starts"),
                "Actual End": st.column_config.DateColumn("Actual End ✏️", format="ddd DD MMM YYYY",
                                                          help="Enter when the work finishes – can be filled in later"),
                "Status": st.column_config.SelectboxColumn("Status ✏️", options=db.STATUS_OPTIONS, required=True,
                                                           help="Choose any status. Adding an Actual End sets it to Completed."),
                "Delay (days)": st.column_config.NumberColumn(width="small",
                                                              help="Calculated: how many days later than planned"),
                "Remarks": st.column_config.TextColumn("Remarks (if delayed) ✏️", width="large",
                                                       help="Reason for the delay"),
            },
            height=min(35 * (len(df) + 1) + 3, 900),
        )

        errs = date_errors(edited, rows)
        for e in errs:
            st.error(e)
        if st.button("💾 Save", type="primary", key=f"save_{floor}", disabled=bool(errs)):
            save(edited, rows)
            st.success("Saved.")
            st.rerun()

        need = remark_reminders(edited, rows)
        if need:
            st.warning("Delayed – don't forget to add a remark for: " + ", ".join(need))

        with st.expander("📊 Bar chart (one block per day)"):
            kind = st.radio("Show", ["Planned", "Actual"], horizontal=True, key=f"kind_{floor}")
            crows = chart_rows(rows, kind)
            if not crows:
                st.info("No actual start dates entered yet.")
            else:
                st.pyplot(make_chart(f"CMS School – Barchant : {floor} – {kind} Schedule", crows,
                                     "Green = concrete work · each block = one day"))

        with st.expander("⚙️ Change planned floor start date"):
            st.caption("This re-plans the floor: every planned date moves by the same number of days. "
                       "Actual dates, status and remarks are not touched.")
            new_start = st.date_input("New planned start", value=start, key=f"fs_{floor}")
            if st.button("Re-plan this floor", key=f"replan_{floor}"):
                db.set_floor_start(floor, new_start)
                st.success("Planned dates updated.")
                st.rerun()

        st.download_button("⬇️ Download as CSV", df.drop(columns=["ID"]).to_csv(index=False).encode(),
                           file_name=f"{floor.replace(' ', '_')}_schedule.csv", mime="text/csv",
                           key=f"dl_{floor}")
