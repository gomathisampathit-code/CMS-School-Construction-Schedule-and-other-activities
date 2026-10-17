"""Simple password protection. The password is set here in the code - change PASSWORD to change it."""
import hmac

import streamlit as st

PASSWORD = "star123"

# Account page (money details) has its own login
ADMIN_ID = "admin"
ADMIN_PASSWORD = "star123"


def require_login():
    """Call at the top of app.py. Shows the password page and stops until the right password is entered."""
    if st.session_state.get("authed"):
        return
    st.markdown("## 🏗️ CMS School : Construction Schedule and other activities")
    with st.form("login"):
        pw = st.text_input("Password", type="password")
        go = st.form_submit_button("Log in", type="primary")
    if go:
        if hmac.compare_digest(pw.encode(), PASSWORD.encode()):
            st.session_state["authed"] = True
            st.rerun()
        else:
            st.error("Wrong password.")
    st.stop()


def sidebar_logout():
    with st.sidebar:
        st.divider()
        if st.button("🚪 Log out"):
            st.session_state.clear()
            st.rerun()


def require_admin():
    """Call at the top of the Account page. Asks for the admin Login ID and password."""
    if st.session_state.get("admin"):
        return
    st.title("💰 Account – admin login")
    st.caption("Money details are visible only to the admin.")
    with st.form("admin_login"):
        uid = st.text_input("Login ID")
        pw = st.text_input("Password", type="password")
        go = st.form_submit_button("Open Account", type="primary")
    if go:
        ok_id = hmac.compare_digest(uid.strip().encode(), ADMIN_ID.encode())
        ok_pw = hmac.compare_digest(pw.encode(), ADMIN_PASSWORD.encode())
        if ok_id and ok_pw:
            st.session_state["admin"] = True
            st.rerun()
        else:
            st.error("Wrong Login ID or password.")
    st.stop()
