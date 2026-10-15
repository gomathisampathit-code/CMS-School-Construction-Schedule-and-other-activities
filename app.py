"""CMS School : Construction Schedule and other activities
Run with:  streamlit run app.py
"""
import streamlit as st

import auth
import db

st.set_page_config(page_title="CMS School : Construction Schedule and other activities",
                   page_icon="🏗️", layout="wide")

db.init_db()
auth.require_login()          # nothing below runs until the correct password is entered

st.sidebar.markdown("### 🏗️ CMS School")
st.sidebar.markdown("**Construction Schedule and other activities**")
auth.sidebar_account()

pages = st.navigation([
    st.Page("views/schedule.py", title="Schedule", icon="📅", default=True),
    st.Page("views/attendance.py", title="Attendance", icon="👷"),
    st.Page("views/purchasing.py", title="Purchasing", icon="🛒"),
])
pages.run()
