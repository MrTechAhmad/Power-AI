"""
Smart Supermarket Management System
Run with:  python -m streamlit run app.py
"""

import streamlit as st

import config
from database.mongo_db import check_connection, friendly_error
from services.people_service import list_employees
from ui.ai_assistant import render_ai_assistant_page
from ui.ai_insights import render_ai_insights_page
from ui.customers import render_customers_page
from ui.dashboard import render_dashboard_page
from ui.employees import render_employees_page
from ui.inventory import render_inventory_page
from ui.products import render_products_page
from ui.reports import render_reports_page
from ui.sales import render_sales_page
from ui.settings import render_settings_page
from ui.store_navigator import render_store_navigator_page
from ui.suppliers import render_suppliers_page

st.set_page_config(page_title=config.STORE_NAME, page_icon="🛒", layout="wide")

# page name -> (function, roles allowed to open it)
PAGES = {
    "Dashboard":       (render_dashboard_page,    ["Manager", "Cashier", "Inventory Staff"]),
    "Products":        (render_products_page,     ["Manager", "Inventory Staff"]),
    "Inventory":       (render_inventory_page,    ["Manager", "Inventory Staff"]),
    "Sales & Billing": (render_sales_page,        ["Manager", "Cashier"]),
    "Customers":       (render_customers_page,    ["Manager", "Cashier"]),
    "Suppliers":       (render_suppliers_page,    ["Manager", "Inventory Staff"]),
    "Employees":       (render_employees_page,    ["Manager"]),
    "Reports":         (render_reports_page,      ["Manager"]),
    "AI Insights":     (render_ai_insights_page,  ["Manager", "Inventory Staff"]),
    "AI Assistant":    (render_ai_assistant_page, ["Manager", "Cashier", "Inventory Staff"]),
    "Store Navigator": (render_store_navigator_page, ["Manager", "Cashier", "Inventory Staff"]),
    "Settings":        (render_settings_page,     ["Manager"]),
}

st.sidebar.title(f"🛒 {config.STORE_NAME}")
st.sidebar.caption("Management System")

# ---------- Stop early with clear help if MongoDB is not reachable ----------
if "db_ok" not in st.session_state:
    st.session_state.db_ok = check_connection()
ok, message = st.session_state.db_ok
if not ok:
    st.title("Cannot connect to MongoDB")
    st.error(message)
    st.markdown("""
1. Start the MongoDB Server service (Windows **Services**: `MongoDB`).
2. Check `MONGO_URI` in **config.py**.
3. Make sure you ran `python setup_database.py`.
""")
    if st.button("Try again"):
        del st.session_state["db_ok"]
        st.rerun()
    st.stop()

# ---------- "Log in" as an employee (demo: no password) ----------
try:
    employees = list_employees()
except Exception as error:
    st.error(friendly_error(error))
    st.stop()
if employees:
    labels = {f"{e['name']} ({e['job_role']})": e for e in employees}
    who = st.sidebar.selectbox("Logged in as", list(labels))
    st.session_state.current_user = labels[who]
    role = labels[who]["job_role"]
else:
    st.sidebar.warning("No employees found. Showing all pages.")
    st.session_state.current_user = None
    role = "Manager"

allowed = [name for name, (_, roles) in PAGES.items() if role in roles]
page = st.sidebar.radio("Menu", allowed)

st.sidebar.divider()
st.sidebar.caption("MongoDB: store data + AI data")

render_page, _ = PAGES[page]
try:
    render_page()
except Exception as error:
    # Show a short message; the full error is inside the expander
    st.error(friendly_error(error))
    with st.expander("Technical details"):
        st.exception(error)
