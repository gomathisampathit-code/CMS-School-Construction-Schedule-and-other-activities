"""Page 1 – Construction schedule: planned dates, actual dates + status entered freely by the user, delay remarks."""
import importlib
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

import compat
import db
import finance
import gantt

# Streamlit can keep an older copy of db.py in memory after the file is replaced - reload it if functions are missing
if not (hasattr(db, "STATUS_OPTIONS") and hasattr(db, "add_activity")):
    importlib.reload(db)
if not (hasattr(db, "STATUS_OPTIONS") and hasattr(db, "add_activity")):
    st.error("The `db.py` that the app is loading is the OLD version.\n\n"
             f"File in use: `{getattr(db, '__file__', '?')}`\n\n"
             "Open that exact file and check it contains `def add_activity`. If not, replace it with the new `db.py`, "
             "then stop the app (Ctrl+C) and run `streamlit run app.py` again. "
             "On Streamlit Cloud: commit `db.py` to GitHub, then Manage app → Reboot app.")
    st.stop()

if not hasattr(gantt, "make_combined_chart"):
    importlib.reload(gantt)

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


def combined_rows(rows):
    out = []
    for r in rows:
        out.append({"label": f'{r["seq"]}. {r["name"]}',
                    "p_start": db.to_date(r["planned_start"]), "p_end": db.to_date(r["planned_end"]),
                    "a_start": db.to_date(r["actual_start"]), "a_end": db.to_date(r["actual_end"]),
                    "concrete": bool(r["is_concrete"])})
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


st.subheader("🧰 Site engineer's observations")
if hasattr(finance, "schedule_insights"):
    for _line in finance.schedule_insights():
        st.markdown(f"- {_line}")
else:
    st.info("Your `finance.py` is the old version. Replace it with the new `finance.py`, then stop the app (Ctrl+C) "
            "and run `streamlit run app.py` again.")

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

        with st.expander("📊 Planned vs actual chart", expanded=True):
            st.caption("Light blocks on the top lane = **planned**, solid blocks below = **actual**. Each block is one day. "
                       "Choose how many days to show and move forward or back.")
            crows = combined_rows(rows)
            first_day = min(r["p_start"] for r in crows)
            last_day = max(max(r["p_end"], r["a_end"] or r["a_start"] or r["p_end"]) for r in crows)
            span_opt = st.radio("Days to show", ["14 days", "21 days", "28 days", "42 days", "Whole floor"],
                                index=1, horizontal=True, key=f"span_{floor}")
            n_days = None if span_opt == "Whole floor" else int(span_opt.split()[0])
            if n_days is None:
                w_start, w_end = first_day, last_day
            else:
                skey = f"from_{floor}"
                if skey not in st.session_state:
                    st.session_state[skey] = min(max(TODAY - timedelta(days=3), first_day),
                                                 max(last_day - timedelta(days=n_days - 1), first_day))

                def _shift(k, d):
                    st.session_state[k] = st.session_state[k] + timedelta(days=d)

                b1, b2, b3 = st.columns([1, 1, 2])
                b1.button("◀ Earlier", key=f"earlier_{floor}", on_click=_shift, args=(skey, -n_days))
                b2.button("Later ▶", key=f"later_{floor}", on_click=_shift, args=(skey, n_days))
                b3.date_input("Show from", key=skey, format="DD/MM/YYYY")
                w_start = st.session_state[skey]
                w_end = w_start + timedelta(days=n_days - 1)
            fig = gantt.make_combined_chart(f"CMS School – Barchant : {floor}", crows,
                                            f"{w_start:%d %b %Y} → {w_end:%d %b %Y}  ·  each block = one day  ·  green = concrete work",
                                            today=TODAY, start=w_start, end=w_end)
            if fig is None:
                st.info("No activities fall in these dates. Use ◀ Earlier / Later ▶ or choose **Whole floor**.")
            else:
                st.pyplot(fig)

        with st.expander("➕ Add / remove an activity"):
            st.caption("Add an activity with its planned start and end date. It is placed in date order "
                       "and you can then enter its actual dates and remarks like the others.")
            with st.form(f"add_act_{floor}", clear_on_submit=True):
                a1, a2, a3 = st.columns([3, 1, 1])
                new_name = a1.text_input("Activity name *", key=f"an_{floor}", placeholder="e.g. Flooring")
                new_ps = a2.date_input("Planned start", value=end, format="DD/MM/YYYY", key=f"ap_{floor}")
                new_pe = a3.date_input("Planned end", value=end, format="DD/MM/YYYY", key=f"ae_{floor}")
                new_conc = st.checkbox("This is concrete work (shown in green)", key=f"ac_{floor}")
                if st.form_submit_button("Add activity", type="primary"):
                    if not new_name.strip():
                        st.error("Enter the activity name.")
                    elif new_pe < new_ps:
                        st.error("Planned end cannot be before planned start.")
                    else:
                        db.add_activity(floor, new_name, new_ps, new_pe, new_conc or None)
                        st.success(f"Added: {new_name.strip()}")
                        st.rerun()
            opts = {f'{r["seq"]}. {r["name"]}': r["id"] for r in rows}
            pick = st.selectbox("Remove an activity", ["—"] + list(opts), key=f"rm_{floor}")
            sure = st.checkbox("Yes, remove it (its actual dates and remarks are deleted too)", key=f"rms_{floor}")
            if st.button("Remove activity", key=f"rmb_{floor}", disabled=not (sure and pick != "—")):
                db.delete_activity(opts[pick])
                st.rerun()

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
