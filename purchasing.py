"""Page 3 – Purchasing details with order / expected / received dates."""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

import compat
import db

db.init_db()
TODAY = date.today()
CATEGORIES = ["Cement", "Steel / Reinforcement", "Sand", "Aggregate / Metal", "Bricks / Blocks", "Shuttering / Centering",
              "Ready-mix concrete", "Electrical", "Plumbing", "Paint", "Tools & Equipment", "Labour / Contract", "Other"]
UNITS = ["Bags", "Kg", "Tonne", "Cu.m", "Cu.ft", "Nos", "Load", "Sq.ft", "Metre", "Litre", "Lot"]
STATUSES = ["Ordered", "Partially delivered", "Delivered", "Cancelled"]

st.title("🛒 Purchasing Details")
st.caption("Record what was ordered, when it was ordered, when it is expected and when it actually arrived.")

COLS = ["id", "item", "category", "quantity", "unit", "supplier", "rate", "amount",
        "order_date", "expected_date", "received_date", "status", "bill_no", "remarks"]


def load():
    with db.conn() as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM purchases ORDER BY COALESCE(order_date,'') DESC, id DESC")]
    df = pd.DataFrame(rows, columns=COLS)
    for col in ["order_date", "expected_date", "received_date"]:
        df[col] = pd.to_datetime(df[col])
    return df


def money(x):
    return f"₹{x:,.0f}"


def overdue_mask(df):
    exp = df["expected_date"]
    return (df["received_date"].isna() & exp.notna() & (exp < pd.Timestamp(TODAY))
            & df["status"].isin(["Ordered", "Partially delivered"]))


df = load()

# ---- summary
m = st.columns(4)
m[0].metric("Purchases recorded", len(df))
m[1].metric("Total amount", money(df.loc[df["status"] != "Cancelled", "amount"].fillna(0).sum()))
m[2].metric("Waiting for delivery", int(df["status"].isin(["Ordered", "Partially delivered"]).sum()))
od = df[overdue_mask(df)] if len(df) else df
m[3].metric("Overdue deliveries", len(od))
if len(od):
    st.warning("Delivery date passed but not received: "
               + ", ".join(f'{r.item} ({r.expected_date:%d %b})' for r in od.itertuples()))

tab_add, tab_reg, tab_sum = st.tabs(["➕ Add purchase", "📒 Purchase register", "📊 Summary"])

# ---------------------------------------------------------------- Add
with tab_add:
    with st.form("add_purchase", clear_on_submit=True):
        a, b, c_ = st.columns(3)
        item = a.text_input("Item *", placeholder="e.g. OPC 53 cement")
        category = b.selectbox("Category", CATEGORIES)
        supplier = c_.text_input("Supplier")
        a, b, c_, d = st.columns(4)
        qty = a.number_input("Quantity", min_value=0.0, step=1.0, format="%.2f")
        unit = b.selectbox("Unit", UNITS)
        rate = c_.number_input("Rate (₹ per unit)", min_value=0.0, step=1.0, format="%.2f")
        d.metric("Amount (auto)", money(qty * rate))
        a, b, c_, d = st.columns(4)
        order_date = a.date_input("Order date", value=TODAY, format="DD/MM/YYYY")
        expected = b.date_input("Expected delivery", value=None, format="DD/MM/YYYY")
        received = c_.date_input("Received date (if arrived)", value=None, format="DD/MM/YYYY")
        status = d.selectbox("Status", STATUSES)
        a, b = st.columns([1, 2])
        bill = a.text_input("Bill / invoice no.")
        remarks = b.text_input("Remarks")
        if st.form_submit_button("Add purchase", type="primary"):
            if not item.strip():
                st.error("Item is required.")
            else:
                if received and status == "Ordered":
                    status = "Delivered"
                with db.conn() as c:
                    c.execute(
                        "INSERT INTO purchases (item,category,quantity,unit,supplier,rate,amount,order_date,"
                        "expected_date,received_date,status,bill_no,remarks) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (item.strip(), category, qty, unit, supplier.strip(), rate, round(qty * rate, 2),
                         db.iso(order_date), db.iso(expected), db.iso(received), status, bill.strip(), remarks.strip()))
                st.success(f"Added: {item}")
                st.rerun()

# ---------------------------------------------------------------- Register
with tab_reg:
    f1, f2, f3 = st.columns(3)
    f_status = f1.multiselect("Status", STATUSES)
    f_cat = f2.multiselect("Category", CATEGORIES)
    f_text = f3.text_input("Search item / supplier")
    view = df
    if f_status:
        view = view[view["status"].isin(f_status)]
    if f_cat:
        view = view[view["category"].isin(f_cat)]
    if f_text:
        t = f_text.lower()
        view = view[view["item"].str.lower().str.contains(t, na=False) | view["supplier"].str.lower().str.contains(t, na=False)]

    edited = compat.data_editor(
        view, key="purchase_editor", hide_index=True, num_rows="dynamic",
        column_order=["item", "category", "quantity", "unit", "supplier", "rate", "amount",
                      "order_date", "expected_date", "received_date", "status", "bill_no", "remarks"],
        column_config={
            "item": st.column_config.TextColumn("Item", required=True),
            "category": st.column_config.SelectboxColumn("Category", options=CATEGORIES),
            "quantity": st.column_config.NumberColumn("Qty", format="%.2f"),
            "unit": st.column_config.SelectboxColumn("Unit", options=UNITS, width="small"),
            "supplier": st.column_config.TextColumn("Supplier"),
            "rate": st.column_config.NumberColumn("Rate ₹", format="%.2f"),
            "amount": st.column_config.NumberColumn("Amount ₹", format="%.2f", help="Leave blank to auto-calculate Qty × Rate"),
            "order_date": st.column_config.DateColumn("Order date", format="DD/MM/YYYY"),
            "expected_date": st.column_config.DateColumn("Expected", format="DD/MM/YYYY"),
            "received_date": st.column_config.DateColumn("Received", format="DD/MM/YYYY"),
            "status": st.column_config.SelectboxColumn("Status", options=STATUSES, default="Ordered"),
            "bill_no": st.column_config.TextColumn("Bill no."),
            "remarks": st.column_config.TextColumn("Remarks"),
        },
    )
    st.caption("Edit any cell, add a row at the bottom, or select a row and press Delete. Then click Save.")
    if st.button("💾 Save changes", type="primary"):
        shown_ids = set(view["id"].dropna().astype(int))
        keep_ids = set()
        with db.conn() as c:
            for _, r in edited.iterrows():
                item = db.clean_text(r["item"])
                if not item:
                    continue
                q = None if pd.isna(r["quantity"]) else float(r["quantity"])
                rt = None if pd.isna(r["rate"]) else float(r["rate"])
                amt = None if pd.isna(r["amount"]) else float(r["amount"])
                if amt is None and q is not None and rt is not None:
                    amt = round(q * rt, 2)
                rec = db.to_date(r["received_date"])
                status = db.clean_text(r["status"]) or "Ordered"
                if rec and status == "Ordered":
                    status = "Delivered"
                vals = (item, db.clean_text(r["category"]), q, db.clean_text(r["unit"]), db.clean_text(r["supplier"]),
                        rt, amt, db.iso(r["order_date"]), db.iso(r["expected_date"]), db.iso(rec), status,
                        db.clean_text(r["bill_no"]), db.clean_text(r["remarks"]))
                pid = None if pd.isna(r["id"]) else int(r["id"])
                if pid is None:
                    c.execute("INSERT INTO purchases (item,category,quantity,unit,supplier,rate,amount,order_date,"
                              "expected_date,received_date,status,bill_no,remarks) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", vals)
                else:
                    c.execute("UPDATE purchases SET item=?,category=?,quantity=?,unit=?,supplier=?,rate=?,amount=?,"
                              "order_date=?,expected_date=?,received_date=?,status=?,bill_no=?,remarks=? WHERE id=?",
                              vals + (pid,))
                    keep_ids.add(pid)
            for pid in shown_ids - keep_ids:          # rows deleted in the table
                c.execute("DELETE FROM purchases WHERE id=?", (pid,))
        st.success("Saved.")
        st.rerun()
    st.download_button("⬇️ Download as CSV", df.drop(columns=["id"]).to_csv(index=False).encode(),
                       file_name="purchases.csv", mime="text/csv")

# ---------------------------------------------------------------- Summary
with tab_sum:
    live = df[df["status"] != "Cancelled"]
    if live.empty:
        st.info("No purchases yet.")
    else:
        st.markdown("**Amount by category (₹)**")
        st.bar_chart(live.groupby("category")["amount"].sum().sort_values(ascending=False))
        st.markdown("**Amount by supplier (₹)**")
        sup = live.assign(supplier=live["supplier"].replace("", "(none)")).groupby("supplier")["amount"].sum()
        compat.dataframe(sup.sort_values(ascending=False).rename("Amount ₹").reset_index(), hide_index=True, fit=True)
        st.markdown("**Spend by month of order (₹)**")
        mon = live.dropna(subset=["order_date"]).assign(Month=lambda d: d["order_date"].dt.strftime("%Y-%m")) \
                  .groupby("Month")["amount"].sum()
        st.bar_chart(mon)
