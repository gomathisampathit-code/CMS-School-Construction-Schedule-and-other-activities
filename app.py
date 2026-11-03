"""CMS School : Construction Schedule and other activities
Run with:  streamlit run app.py
"""
import streamlit as st

import auth
import db
import storage

st.set_page_config(page_title="CMS School : Construction Schedule and other activities",
                   page_icon="🏗️", layout="wide")

# Streamlit Cloud erases the app's disk on restart -> bring the saved database back BEFORE opening it
_problem = storage.restore_if_needed()
if _problem:
    st.error("Could not load your saved data from cloud storage, so the app has stopped to protect it "
             "(nothing has been overwritten). Wait a minute and reload the page.\n\n"
             f"Details: {_problem}")
    st.stop()
storage.setup()                 # from now on every change is saved to cloud storage

db.init_db()
auth.require_login()          # first page: asks for the password; nothing below runs until it is correct

st.sidebar.markdown("### 🏗️ CMS School")
st.sidebar.markdown("**Construction Schedule and other activities**")
auth.sidebar_logout()
_msg = storage.status_text()
if _msg:
    st.sidebar.caption(_msg)
else:
    st.sidebar.warning("Cloud backup is OFF – data is lost when this app restarts. "
                       "Open **Account → Backup & Restore** for the setup steps.")

pages = st.navigation([
    st.Page("views/schedule.py", title="Schedule", icon="📅", default=True),
    st.Page("views/attendance.py", title="Attendance", icon="👷"),
    st.Page("views/procurement.py", title="Procurement", icon="🛒"),
    st.Page("views/account.py", title="Account", icon="💰"),
])
pages.run()
