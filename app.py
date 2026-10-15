"""CMS School : Construction Schedule and other activities
Run with:  streamlit run app.py
"""
import streamlit as st

st.set_page_config(page_title="CMS School : Construction Schedule and other activities",
                   page_icon="🏗️", layout="wide")

st.sidebar.markdown("### 🏗️ CMS School")
st.sidebar.markdown("**Construction Schedule and other activities**")

pages = st.navigation([
    st.Page("views/schedule.py", title="Schedule", icon="📅", default=True),
    st.Page("views/attendance.py", title="Attendance", icon="👷"),
    st.Page("views/purchasing.py", title="Purchasing", icon="🛒"),
])
pages.run()
