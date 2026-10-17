"""Page 4 – Account (admin only): wages, purchases, expenses, funds, suppliers, budget, reports."""
import sys
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

import auth
import compat
import db
import finance as fin

db.init_db()
auth.require_admin()                       # needs Login ID + password

TODAY = date.today()
MODES = ["Cash", "Bank transfer", "UPI", "Cheque", "Other"]
RS = "₹%.0f"

head_l, head_r = st.columns([5, 1])
head_l.title("💰 Account")
head_l.caption("Money in and money out for the whole construction – wages, purchases, expenses, funds, budget and reports.")
if head_r.button("🔒 Lock Account"):
    st.session_state["admin"] = False
    st.rerun()


# ---------------------------------------------------------------- helpers
def to_excel_bytes(df, sheet="Report"):
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.date
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        df.to_excel(xw, sheet_name=sheet[:31], index=False)
        ws = xw.sheets[sheet[:31]]
        for i, col in enumerate(df.columns, 1):
            ws.column_dimensions[ws.cell(1, i).column_letter].width = min(
                max([len(str(col))] + [len(str(v)) for v in df[col].head(200)]) + 2, 45)
    return buf.getvalue()


def downloads(df, name, key):
    """CSV + Excel download buttons for a table."""
    if df is None or df.empty:
        return
    d = df.copy()
    c1, c2, _ = st.columns([1, 1, 4])
    c1.download_button("⬇️ CSV", d.to_csv(index=False).encode("utf-8-sig"), file_name=f"{name}.csv",
                       mime="text/csv", key=f"{key}_csv")
    c2.download_button("⬇️ Excel", to_excel_bytes(d, name), file_name=f"{name}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"{key}_xlsx")


def period_picker(key, kinds=None):
    """Returns (ok, kind, start, end, label). start/end are None for Overall."""
    kinds = kinds or fin.PERIODS
    kind = st.radio("Show", kinds, horizontal=True, key=f"{key}_kind")
    anchor, custom = TODAY, None
    if kind == "Day":
        anchor = st.date_input("Date", value=TODAY, format="DD/MM/YYYY", key=f"{key}_day")
    elif kind == "Week (Sun–Sat)":
        anchor = st.date_input("Any date in the week", value=TODAY, format="DD/MM/YYYY", key=f"{key}_week")
    elif kind == "Month":
        anchor = st.date_input("Any date in the month", value=TODAY, format="DD/MM/YYYY", key=f"{key}_month")
    elif kind == "Custom":
        r = st.date_input("From – To", value=(TODAY.replace(day=1), TODAY), format="DD/MM/YYYY", key=f"{key}_custom")
        if not (isinstance(r, (tuple, list)) and len(r) == 2):
            st.info("Pick both the start and the end date.")
            return False, kind, None, None, ""
        custom = (r[0], r[1])
    start, end = fin.period_range(kind, anchor, custom)
    if start is None:
        label = "Overall (whole project)"
    elif start == end:
        label = f"{start:%A, %d %b %Y}"
    else:
        label = f"{start:%d %b %Y} → {end:%d %b %Y}"
    st.markdown(f"**Period:** {label}")
    return True, kind, start, end, label


def trend(df, date_col, value_col, start, end, title):
    """Daily bars for short periods, monthly bars for long ones."""
    d = df.dropna(subset=[date_col])
    if d.empty:
        return
    span = (end - start).days if start else 9999
    if span <= 62:
        g = d.groupby(d[date_col].dt.strftime("%d %b"), sort=False)[value_col].sum()
        order = d.sort_values(date_col)[date_col].dt.strftime("%d %b").drop_duplicates()
        g = g.reindex(order)
    else:
        g = d.groupby(d[date_col].dt.strftime("%Y-%m"))[value_col].sum().sort_index()
    st.markdown(f"**{title}**")
    st.bar_chart(g.rename("Amount ₹"))


def stacked(df):
    try:
        st.bar_chart(df, stack=False)
    except TypeError:
        st.bar_chart(df)


def to_dt(df, cols):
    return fin.as_dates(df, cols)


# ================================================================ 1. Overview
def tab_overview():
    cs, ss, bt = fin.cash_summary(), fin.schedule_summary(), fin.budget_table()
    total_budget = float(bt["Budget"].sum())
    a = st.columns(5)
    a[0].metric("Total budget", fin.inr(total_budget))
    a[1].metric("Cost incurred", fin.inr(cs["cost_incurred"]), help="Wages (attendance × rate) + purchases + other expenses")
    a[2].metric("Funds received", fin.inr(cs["funds"]))
    a[3].metric("Money paid out", fin.inr(cs["cash_out"]), help="Advances + wages paid + supplier payments + other expenses")
    a[4].metric("Cash in hand", fin.inr(cs["cash_in_hand"]), delta="shortfall" if cs["cash_in_hand"] < 0 else None,
                delta_color="inverse")
    b = st.columns(5)
    b[0].metric("Owed to suppliers", fin.inr(cs["supplier_payable"]))
    b[1].metric("Wages pending", fin.inr(cs["wages_pending"]))
    b[2].metric("Advances to recover", fin.inr(cs["advance_balance"]))
    b[3].metric("Work completed", f"{ss['progress']:.0%}", help="Completed activities ÷ all activities (Schedule page)")
    b[4].metric("Delayed activities", ss["delayed"])

    st.subheader("🧰 Site engineer's observations")
    for line in fin.insights(cs, ss, bt):
        st.markdown(f"- {line}")

    left, right = st.columns(2)
    with left:
        st.markdown("**Cost incurred per month (₹)**")
        mc = fin.monthly_cost()
        if mc.empty:
            st.caption("No costs recorded yet.")
        else:
            st.bar_chart(mc)
    with right:
        st.markdown("**Money in vs money out per month (₹)**")
        mf = fin.monthly_cashflow()
        if mf.empty:
            st.caption("No funds / payments recorded yet.")
        else:
            stacked(mf)

    st.markdown("**Cost by head vs budget**")
    show = bt.copy()
    compat.dataframe(show, hide_index=True, column_config={
        "Budget": st.column_config.NumberColumn(format=RS), "Actual": st.column_config.NumberColumn(format=RS),
        "Balance": st.column_config.NumberColumn(format=RS), "% used": st.column_config.NumberColumn(format="%.1f%%")})
    st.markdown("**Progress by floor**")
    compat.dataframe(fin.floor_progress(), hide_index=True,
                     column_config={"% complete": st.column_config.ProgressColumn(format="%d%%", min_value=0, max_value=100)})


# ================================================================ 2. Weekly wages
def tab_wages():
    st.caption("Wages = days worked (Present = 1, Half day = 0.5) × daily wage. The pay week runs **Sunday to Saturday**; "
               "pick the Saturday you are paying on.")
    picked = st.date_input("Pay Saturday (any date in the week works)", value=fin.week_end_of(TODAY),
                           format="DD/MM/YYYY", key="wk_pick")
    we = fin.week_end_of(picked)
    ws_ = we - timedelta(days=6)
    st.markdown(f"**Week:** {ws_:%a %d %b} → **{we:%a %d %b %Y}**")
    df = fin.wages_week(we)
    if df.empty:
        st.info("No attendance saved for this week. Mark attendance on the Attendance page first.")
    else:
        pend = df[df["Status"] == "Pending"]
        paid = df[df["Status"] == "Paid"]
        m = st.columns(5)
        m[0].metric("Workers", len(df))
        m[1].metric("Man-days", f"{df['Days payable'].sum():g}")
        m[2].metric("Gross wages", fin.inr(df["Gross wages"].sum()))
        m[3].metric("To pay now (net)", fin.inr(pend["Net payable"].sum()))
        m[4].metric("Already paid", fin.inr(paid["Net payable"].sum()))
        no_rate = df[(df["Daily wage"] <= 0) & (df["Status"] == "Pending")]["Worker"].tolist()
        if no_rate:
            st.warning("Daily wage not set for: " + ", ".join(no_rate) + " – set it in the **Rates & Advances** tab.")

        edited = compat.data_editor(
            df, key=f"wages_{we.isoformat()}", hide_index=True,
            disabled=["ID", "Worker", "Role", "Agency", "Present", "Half day", "Days payable", "Daily wage", "Gross wages",
                      "Advance balance", "Net payable", "Status", "Paid on"],
            column_order=["Worker", "Role", "Agency", "Present", "Half day", "Days payable", "Daily wage", "Gross wages",
                          "Advance balance", "Deduct advance", "Net payable", "Status", "Paid on", "Pay"],
            column_config={
                "Daily wage": st.column_config.NumberColumn(format=RS),
                "Gross wages": st.column_config.NumberColumn(format=RS),
                "Advance balance": st.column_config.NumberColumn(format=RS, help="Advance given and not yet recovered"),
                "Deduct advance": st.column_config.NumberColumn("Deduct advance ✏️", format=RS, min_value=0.0,
                                                                help="Amount of advance to cut from this week's pay"),
                "Net payable": st.column_config.NumberColumn(format=RS),
                "Paid on": st.column_config.DateColumn(format="DD/MM/YYYY"),
                "Pay": st.column_config.CheckboxColumn("Pay ✏️", help="Tick the workers you are paying now"),
            })
        # live net after the deduction currently typed
        live = edited[edited["Status"] == "Pending"]
        if not live.empty and live["Pay"].any():
            tick = live[live["Pay"]]
            st.info(f"Ticked: **{len(tick)}** worker(s) · cash to hand over: "
                    f"**{fin.inr((tick['Gross wages'] - tick['Deduct advance'].fillna(0)).sum())}**")

        c1, c2 = st.columns([1, 2])
        paid_on = c1.date_input("Paid on", value=min(TODAY, we) if TODAY >= ws_ else we, format="DD/MM/YYYY", key="wk_paid_on")
        if c2.button("✅ Record payment for ticked workers", type="primary"):
            n, errs = fin.record_wage_payments(we, edited, paid_on)
            if errs:
                st.error("Not saved:\n\n" + "\n".join(f"- {e}" for e in errs))
            elif n == 0:
                st.warning("Nothing to record – tick at least one pending worker.")
            else:
                st.success(f"Recorded payment for {n} worker(s).")
                st.rerun()
        if len(paid):
            with st.expander("↩ Cancel this week's recorded payments"):
                sure = st.checkbox("Yes, delete the payment records for this week (use only to correct a mistake)")
                if st.button("Cancel payments", disabled=not sure):
                    fin.cancel_wage_payments(we)
                    st.rerun()
        with st.expander("🗓 Day-by-day attendance this week (P = present, ½ = half day, A = absent, L = leave)"):
            grid = fin.week_attendance_grid(we)
            if grid.empty:
                st.caption("No attendance.")
            else:
                compat.dataframe(grid, hide_index=True)
        downloads(df.drop(columns=["ID", "Pay"]), f"wages_week_ending_{we:%Y-%m-%d}", "wk_dl")

    st.divider()
    st.subheader("All weeks")
    allw = fin.wages_by_week()
    if allw.empty:
        st.caption("No attendance recorded yet.")
    else:
        compat.dataframe(allw, hide_index=True, column_config={
            "Week ending (Sat)": st.column_config.DateColumn(format="ddd DD MMM YYYY"),
            "Gross wages": st.column_config.NumberColumn(format=RS), "Paid (net)": st.column_config.NumberColumn(format=RS),
            "Advance recovered": st.column_config.NumberColumn(format=RS)})
        st.bar_chart(allw.sort_values("Week ending (Sat)").set_index("Week ending (Sat)")["Gross wages"])
        downloads(allw, "wages_by_week", "allw_dl")


# ================================================================ 3. Purchase expenses
def tab_purchases():
    ok, kind, start, end, label = period_picker("pur")
    if not ok:
        return
    basis = st.radio("Count orders by", ["Order date", "Received date"], horizontal=True, key="pur_basis")
    col = "order_date" if basis == "Order date" else "received_date"
    df = fin.purchases_active()
    view = df[fin.in_period(df[col], start, end)] if start else df
    if basis == "Received date":
        view = view[view[col].notna()]
    view = view.sort_values(col, ascending=False)
    sp = fin.supplier_payments_df()
    sp_in = sp[fin.in_period(sp["pay_date"], start, end)] if start else sp
    m = st.columns(4)
    m[0].metric("Procurement expense", fin.inr(view["amount"].sum()))
    m[1].metric("Items", len(view))
    m[2].metric("Paid to suppliers (in period)", fin.inr(sp_in["amount"].sum()))
    m[3].metric("Owed to suppliers (all time)", fin.inr(fin.cash_summary()["supplier_payable"]))
    if view.empty:
        st.info("No orders in this period.")
        return
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**By category (₹)**")
        st.bar_chart(view.groupby("category")["amount"].sum().sort_values(ascending=False).rename("Amount ₹"))
    with c2:
        st.markdown("**By supplier (₹)**")
        sup = view.assign(supplier=view["supplier"].replace("", "(none)")).groupby("supplier")["amount"].sum()
        compat.dataframe(sup.sort_values(ascending=False).rename("Amount ₹").reset_index(), hide_index=True, fit=True)
    trend(view, col, "amount", start, end, f"Procurement expense over time ({basis.lower()})")
    show = view[["order_date", "item", "category", "quantity", "unit", "supplier", "rate", "amount", "status",
                 "expected_date", "received_date", "bill_no"]]
    compat.dataframe(show, hide_index=True, column_config={
        "order_date": st.column_config.DateColumn("Order date", format="DD/MM/YYYY"),
        "expected_date": st.column_config.DateColumn("Expected", format="DD/MM/YYYY"),
        "received_date": st.column_config.DateColumn("Received", format="DD/MM/YYYY"),
        "rate": st.column_config.NumberColumn("Rate ₹", format="%.2f"),
        "amount": st.column_config.NumberColumn("Amount ₹", format=RS)})
    downloads(show, "procurement_expenses", "pur_dl")


# ================================================================ 4. Other expenses
def tab_expenses():
    st.caption("Everything that is not a material purchase or wages – transport, machinery rent, site overheads, "
               "contractor payments, approvals, etc.")
    with st.form("add_expense", clear_on_submit=True):
        a, b, c = st.columns(3)
        d = a.date_input("Date", value=TODAY, format="DD/MM/YYYY")
        head = b.selectbox("Head", db.EXPENSE_HEADS)
        amount = c.number_input("Amount (₹) *", min_value=0.0, step=100.0, format="%.2f")
        a, b, c = st.columns(3)
        desc = a.text_input("Description *", placeholder="e.g. Lorry for sand")
        paid_to = b.text_input("Paid to")
        mode = c.selectbox("Mode", MODES)
        a, b = st.columns(2)
        ref = a.text_input("Bill / voucher / reference")
        remarks = b.text_input("Remarks")
        if st.form_submit_button("Add expense", type="primary"):
            if not desc.strip() or amount <= 0:
                st.error("Description and a positive amount are required.")
            else:
                with db.conn() as cn:
                    cn.execute("INSERT INTO expenses (exp_date, head, description, paid_to, amount, mode, ref, remarks) "
                               "VALUES (?,?,?,?,?,?,?,?)",
                               (db.iso(d), head, desc.strip(), paid_to.strip(), amount, mode, ref.strip(), remarks.strip()))
                st.success("Expense added.")
                st.rerun()
    st.divider()
    ok, kind, start, end, label = period_picker("exp")
    if not ok:
        return
    df = fin.expenses_df()
    view = df[fin.in_period(df["exp_date"], start, end)] if start else df
    m = st.columns(3)
    m[0].metric("Other expenses", fin.inr(view["amount"].sum()))
    m[1].metric("Entries", len(view))
    m[2].metric("Largest head", view.groupby("head")["amount"].sum().idxmax() if len(view) else "–")
    if len(view):
        st.markdown("**By head (₹)**")
        st.bar_chart(view.groupby("head")["amount"].sum().sort_values(ascending=False).rename("Amount ₹"))
    st.markdown("**Expense register** – edit a cell, add a row at the bottom, or select a row and press Delete, then Save.")
    edited = compat.data_editor(
        view, key=f"exp_editor_{kind}_{label}", hide_index=True, num_rows="dynamic",
        column_order=["exp_date", "head", "description", "paid_to", "amount", "mode", "ref", "remarks"],
        column_config={
            "exp_date": st.column_config.DateColumn("Date", format="DD/MM/YYYY", required=True),
            "head": st.column_config.SelectboxColumn("Head", options=db.EXPENSE_HEADS),
            "description": st.column_config.TextColumn("Description", required=True),
            "paid_to": st.column_config.TextColumn("Paid to"),
            "amount": st.column_config.NumberColumn("Amount ₹", format="%.2f", required=True),
            "mode": st.column_config.SelectboxColumn("Mode", options=MODES),
            "ref": st.column_config.TextColumn("Reference"), "remarks": st.column_config.TextColumn("Remarks")})
    if st.button("💾 Save expense changes", type="primary"):
        fin.sync_table("expenses", [("exp_date", "date", True), ("head", "text", False), ("description", "text", True),
                                    ("paid_to", "text", False), ("amount", "num", True), ("mode", "text", False),
                                    ("ref", "text", False), ("remarks", "text", False)],
                       edited, set(view["id"].astype(int)))
        st.success("Saved.")
        st.rerun()
    downloads(view.drop(columns=["id"]), "other_expenses", "exp_dl")


# ================================================================ 5. Funds & cash flow
def tab_funds():
    st.caption("Money received for the project (school / trust / client releases, loans, donations) and the resulting cash position.")
    with st.form("add_fund", clear_on_submit=True):
        a, b, c = st.columns(3)
        d = a.date_input("Date received", value=TODAY, format="DD/MM/YYYY")
        source = b.text_input("Received from *", placeholder="e.g. School management")
        amount = c.number_input("Amount (₹) *", min_value=0.0, step=1000.0, format="%.2f")
        a, b, c = st.columns(3)
        mode = a.selectbox("Mode", MODES)
        ref = b.text_input("Reference (cheque / UTR no.)")
        remarks = c.text_input("Remarks")
        if st.form_submit_button("Add funds received", type="primary"):
            if not source.strip() or amount <= 0:
                st.error("Source and a positive amount are required.")
            else:
                with db.conn() as cn:
                    cn.execute("INSERT INTO fund_receipts (rec_date, source, amount, mode, ref, remarks) VALUES (?,?,?,?,?,?)",
                               (db.iso(d), source.strip(), amount, mode, ref.strip(), remarks.strip()))
                st.success("Added.")
                st.rerun()
    cs = fin.cash_summary()
    st.subheader("Cash position")
    m = st.columns(5)
    m[0].metric("Funds received", fin.inr(cs["funds"]))
    m[1].metric("Paid to labour", fin.inr(cs["labour_cash"]), help="Advances + wages paid (net)")
    m[2].metric("Paid to suppliers", fin.inr(cs["supplier_cash"]))
    m[3].metric("Other expenses paid", fin.inr(cs["other_cash"]))
    m[4].metric("Cash in hand", fin.inr(cs["cash_in_hand"]))
    st.markdown("**Still to be paid (commitments)**")
    m = st.columns(3)
    m[0].metric("Suppliers", fin.inr(cs["supplier_payable"]))
    m[1].metric("Wages pending", fin.inr(cs["wages_pending"]))
    m[2].metric("Funds needed", fin.inr(max(cs["supplier_payable"] + cs["wages_pending"] - cs["cash_in_hand"], 0)),
                help="Pending payments minus cash in hand")
    mf = fin.monthly_cashflow()
    if not mf.empty:
        st.markdown("**Money in vs money out per month (₹)**")
        stacked(mf)
    st.markdown("**Funds register** – edit, add a row at the bottom, or select a row and press Delete, then Save.")
    df = fin.funds_df()
    edited = compat.data_editor(
        df, key="funds_editor", hide_index=True, num_rows="dynamic",
        column_order=["rec_date", "source", "amount", "mode", "ref", "remarks"],
        column_config={
            "rec_date": st.column_config.DateColumn("Date", format="DD/MM/YYYY", required=True),
            "source": st.column_config.TextColumn("Received from", required=True),
            "amount": st.column_config.NumberColumn("Amount ₹", format="%.2f", required=True),
            "mode": st.column_config.SelectboxColumn("Mode", options=MODES),
            "ref": st.column_config.TextColumn("Reference"), "remarks": st.column_config.TextColumn("Remarks")})
    if st.button("💾 Save funds changes", type="primary"):
        fin.sync_table("fund_receipts", [("rec_date", "date", True), ("source", "text", True), ("amount", "num", True),
                                         ("mode", "text", False), ("ref", "text", False), ("remarks", "text", False)],
                       edited, set(df["id"].astype(int)))
        st.success("Saved.")
        st.rerun()
    downloads(df.drop(columns=["id"]), "funds_received", "funds_dl")


# ================================================================ 6. Supplier payments
def tab_suppliers():
    st.caption("Record payments made to suppliers. The ledger shows what is still owed on the orders you entered.")
    names = sorted({s for s in fin.purchases_active()["supplier"].dropna() if s})
    with st.form("add_sp", clear_on_submit=True):
        a, b, c = st.columns(3)
        d = a.date_input("Payment date", value=TODAY, format="DD/MM/YYYY")
        sel = b.selectbox("Supplier", [""] + names)
        new = c.text_input("…or type a new supplier name")
        a, b, c, e = st.columns(4)
        amount = a.number_input("Amount (₹) *", min_value=0.0, step=1000.0, format="%.2f")
        mode = b.selectbox("Mode", MODES)
        ref = c.text_input("Reference / cheque no.")
        remarks = e.text_input("Remarks")
        if st.form_submit_button("Add payment", type="primary"):
            supplier = new.strip() or sel
            if not supplier or amount <= 0:
                st.error("Supplier and a positive amount are required.")
            else:
                with db.conn() as cn:
                    cn.execute("INSERT INTO supplier_payments (pay_date, supplier, amount, mode, ref, remarks) VALUES (?,?,?,?,?,?)",
                               (db.iso(d), supplier, amount, mode, ref.strip(), remarks.strip()))
                st.success("Payment added.")
                st.rerun()
    led = fin.supplier_ledger()
    st.subheader("Supplier ledger")
    if led.empty:
        st.info("No purchases or payments yet.")
    else:
        m = st.columns(3)
        m[0].metric("Purchased", fin.inr(led["Purchased"].sum()))
        m[1].metric("Paid", fin.inr(led["Paid"].sum()))
        m[2].metric("Outstanding", fin.inr(led["Outstanding"].sum()))
        compat.dataframe(led, hide_index=True, column_config={
            "Purchased": st.column_config.NumberColumn(format=RS), "Paid": st.column_config.NumberColumn(format=RS),
            "Outstanding": st.column_config.NumberColumn(format=RS)})
        downloads(led, "supplier_ledger", "led_dl")
    st.markdown("**Payments register** – edit, add a row, or select a row and press Delete, then Save.")
    df = fin.supplier_payments_df()
    edited = compat.data_editor(
        df, key="sp_editor", hide_index=True, num_rows="dynamic",
        column_order=["pay_date", "supplier", "amount", "mode", "ref", "remarks"],
        column_config={
            "pay_date": st.column_config.DateColumn("Date", format="DD/MM/YYYY", required=True),
            "supplier": st.column_config.TextColumn("Supplier", required=True),
            "amount": st.column_config.NumberColumn("Amount ₹", format="%.2f", required=True),
            "mode": st.column_config.SelectboxColumn("Mode", options=MODES),
            "ref": st.column_config.TextColumn("Reference"), "remarks": st.column_config.TextColumn("Remarks")})
    if st.button("💾 Save payment changes", type="primary"):
        fin.sync_table("supplier_payments", [("pay_date", "date", True), ("supplier", "text", True), ("amount", "num", True),
                                             ("mode", "text", False), ("ref", "text", False), ("remarks", "text", False)],
                       edited, set(df["id"].astype(int)))
        st.success("Saved.")
        st.rerun()
    downloads(df.drop(columns=["id"]), "supplier_payments", "sp_dl")


# ================================================================ 7. Budget
def tab_budget():
    st.caption("Enter the estimated cost for each head. **Actual** is calculated automatically from attendance × wages, "
               "purchases and other expenses.")
    bt = fin.budget_table()
    edited = compat.data_editor(
        bt, key="budget_editor", hide_index=True, disabled=["Head", "Actual", "Balance", "% used"],
        column_config={
            "Budget": st.column_config.NumberColumn("Budget ₹ ✏️", format=RS, min_value=0.0),
            "Actual": st.column_config.NumberColumn(format=RS), "Balance": st.column_config.NumberColumn(format=RS),
            "% used": st.column_config.NumberColumn(format="%.1f%%")})
    if st.button("💾 Save budget", type="primary"):
        fin.save_budget(edited)
        st.success("Budget saved.")
        st.rerun()
    tb, ta = float(bt["Budget"].sum()), float(bt["Actual"].sum())
    m = st.columns(4)
    m[0].metric("Total budget", fin.inr(tb))
    m[1].metric("Actual cost", fin.inr(ta))
    m[2].metric("Balance", fin.inr(tb - ta))
    m[3].metric("Budget used", f"{ta / tb:.0%}" if tb else "–")
    stacked(bt.set_index("Head")[["Budget", "Actual"]])
    downloads(bt, "budget_vs_actual", "bud_dl")


# ================================================================ 8. Rates & advances
def tab_rates():
    st.caption("Set each worker's **daily wage** here (only the admin sees wages). Weeks already marked as paid keep the rate "
               "used when they were paid; pending weeks use the current rate.")
    w = fin.workers_all()
    if w.empty:
        st.info("No workers yet. Add them on the **Attendance** page → Workers list.")
        return
    w["active"] = w["active"].astype(bool)
    edited = compat.data_editor(
        w, key="rates_editor", hide_index=True, disabled=["id", "name", "role", "agency", "active"],
        column_order=["name", "role", "agency", "active", "daily_wage"],
        column_config={"name": "Worker", "role": "Role", "agency": "Agency", "active": "Active",
                       "daily_wage": st.column_config.NumberColumn("Daily wage ₹ ✏️", format=RS, min_value=0.0)})
    if st.button("💾 Save wage rates", type="primary"):
        with db.conn() as cn:
            for _, r in edited.iterrows():
                cn.execute("UPDATE workers SET daily_wage=? WHERE id=?",
                           (0.0 if pd.isna(r["daily_wage"]) else float(r["daily_wage"]), int(r["id"])))
        st.success("Rates saved.")
        st.rerun()

    st.divider()
    st.subheader("Advances to workers")
    name_to_id = dict(zip(w["name"], w["id"]))
    with st.form("add_adv", clear_on_submit=True):
        a, b, c, e = st.columns(4)
        who = a.selectbox("Worker", list(name_to_id))
        d = b.date_input("Date", value=TODAY, format="DD/MM/YYYY")
        amt = c.number_input("Amount (₹) *", min_value=0.0, step=100.0, format="%.2f")
        rem = e.text_input("Remarks")
        if st.form_submit_button("Give advance", type="primary"):
            if amt <= 0:
                st.error("Enter a positive amount.")
            else:
                with db.conn() as cn:
                    cn.execute("INSERT INTO advances (worker_id, adv_date, amount, remarks) VALUES (?,?,?,?)",
                               (int(name_to_id[who]), db.iso(d), amt, rem.strip()))
                st.success("Advance recorded. Recover it from the Weekly Wages tab (Deduct advance).")
                st.rerun()
    summ = fin.advance_summary()
    if len(summ):
        compat.dataframe(summ, hide_index=True, column_config={
            c: st.column_config.NumberColumn(format=RS) for c in ["Advance given", "Recovered", "Balance"]})
    adv = fin.as_dates(fin.q("SELECT a.id, a.adv_date, w.name AS worker, a.amount, a.remarks FROM advances a "
                             "JOIN workers w ON w.id = a.worker_id ORDER BY a.adv_date DESC, a.id DESC"), ["adv_date"])
    st.markdown("**Advance register** – edit, add a row, or select a row and press Delete, then Save.")
    ed = compat.data_editor(
        adv, key="adv_editor", hide_index=True, num_rows="dynamic",
        column_order=["adv_date", "worker", "amount", "remarks"],
        column_config={"adv_date": st.column_config.DateColumn("Date", format="DD/MM/YYYY", required=True),
                       "worker": st.column_config.SelectboxColumn("Worker", options=list(name_to_id), required=True),
                       "amount": st.column_config.NumberColumn("Amount ₹", format="%.2f", required=True),
                       "remarks": st.column_config.TextColumn("Remarks")})
    if st.button("💾 Save advance changes", type="primary"):
        ed2 = ed.copy()
        ed2["worker_id"] = ed2["worker"].map(name_to_id)
        fin.sync_table("advances", [("adv_date", "date", True), ("worker_id", "int", True), ("amount", "num", True),
                                    ("remarks", "text", False)], ed2, set(adv["id"].astype(int)))
        st.success("Saved.")
        st.rerun()
    downloads(adv.drop(columns=["id"]), "advances", "adv_dl")


# ================================================================ 9. Reports
def tab_reports():
    st.caption("Download a complete Excel report (Summary, weekly wages, purchases, expenses, funds, supplier ledger, "
               "budget vs actual, advances, attendance).")
    ok, kind, start, end, label = period_picker("rep", ["Overall", "Month", "Custom"])
    if not ok:
        return
    pick = st.date_input("Wage sheet for the week ending Saturday", value=fin.week_end_of(TODAY),
                         format="DD/MM/YYYY", key="rep_week")
    we = fin.week_end_of(pick)
    st.markdown(f"Wage sheet week: **{we - timedelta(days=6):%d %b} → {we:%d %b %Y}**")
    data = fin.build_report(start, end, we)
    tag = "overall" if start is None else f"{start:%Y%m%d}_{end:%Y%m%d}"
    st.download_button("⬇️ Download full report (Excel)", data, file_name=f"CMS_School_Account_Report_{tag}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
    st.info("Every tab above also has its own CSV / Excel download buttons under the table.")


tabs = st.tabs(["📊 Overview", "💵 Weekly Wages", "🛒 Procurement Expenses", "🧾 Other Expenses",
                "🏦 Funds & Cash Flow", "🤝 Suppliers", "🎯 Budget", "👷 Rates & Advances", "⬇️ Reports"])
for tab, fn in zip(tabs, [tab_overview, tab_wages, tab_purchases, tab_expenses, tab_funds,
                          tab_suppliers, tab_budget, tab_rates, tab_reports]):
    with tab:
        fn()