import streamlit as st

from services import people_service
from ui.common import flash, show_error, show_flash, show_table, today


def render_employees_page():
    st.title("🧑‍💼 Employees")
    st.caption("Staff records and how many sales each person made.")
    show_flash()

    show_table(people_service.list_employees_df(), "No employees yet.")

    employees = people_service.list_employees()
    labels = {f"{e['name']} ({e['job_role']})": e for e in employees}
    roles = people_service.ROLES

    tab_add, tab_edit, tab_delete = st.tabs(["➕ Add", "✏️ Edit", "🗑️ Delete"])

    with tab_add:
        with st.form("add_employee", clear_on_submit=True):
            a, b = st.columns(2)
            name = a.text_input("Name *")
            role = a.selectbox("Role", roles)
            phone = b.text_input("Phone")
            salary = b.number_input("Monthly salary", min_value=0.0, step=1000.0)
            hire_date = b.date_input("Hire date", value=today())
            if st.form_submit_button("Add Employee", width="stretch"):
                if not name.strip():
                    st.error("Name is required.")
                else:
                    try:
                        people_service.add_employee(name.strip(), role, phone.strip(),
                                                    salary, hire_date)
                        flash(f"{name.strip()} added.")
                        st.rerun()
                    except Exception as e:
                        show_error(e)

    if not employees:
        return

    with tab_edit:
        e = labels[st.selectbox("Employee", list(labels), key="edit_employee_pick")]
        with st.form(f"edit_employee_{e['employee_id']}"):
            name = st.text_input("Name", value=e["name"])
            role = st.selectbox("Role", roles, index=roles.index(e["job_role"]))
            phone = st.text_input("Phone", value=e["phone"] or "")
            salary = st.number_input("Monthly salary", min_value=0.0, value=float(e["salary"] or 0))
            if st.form_submit_button("Save Changes", width="stretch"):
                try:
                    people_service.update_employee(e["employee_id"], name.strip(), role,
                                                   phone.strip(), salary)
                    flash(f"{name} updated.")
                    st.rerun()
                except Exception as err:
                    show_error(err)

    with tab_delete:
        e = labels[st.selectbox("Employee", list(labels), key="delete_employee_pick")]
        st.caption("Employees who made sales cannot be deleted (foreign key protects sales).")
        confirm = st.checkbox("I confirm I want to delete this employee.")
        if st.button("Delete Employee", type="primary"):
            if not confirm:
                st.warning("Please tick the confirmation box first.")
            else:
                try:
                    people_service.delete_employee(e["employee_id"])
                    flash(f"{e['name']} deleted.")
                    st.rerun()
                except Exception as err:
                    show_error(err)
