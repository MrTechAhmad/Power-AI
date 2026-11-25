import streamlit as st

from services import people_service
from ui.common import csv_button, flash, show_error, show_flash, show_table


def render_suppliers_page():
    st.title("🚚 Suppliers")
    st.caption("Supplier contacts, the products they supply and how much we bought.")
    show_flash()

    df = people_service.list_suppliers_df()
    show_table(df, "No suppliers yet.")
    csv_button(df, "suppliers.csv")

    suppliers = people_service.list_suppliers()
    labels = {s["name"]: s for s in suppliers}

    tab_add, tab_edit, tab_delete = st.tabs(["➕ Add", "✏️ Edit", "🗑️ Delete"])

    with tab_add:
        with st.form("add_supplier", clear_on_submit=True):
            name = st.text_input("Supplier name *")
            phone = st.text_input("Phone")
            email = st.text_input("Email")
            address = st.text_input("Address")
            if st.form_submit_button("Add Supplier", width="stretch"):
                if not name.strip():
                    st.error("Name is required.")
                else:
                    try:
                        people_service.add_supplier(name.strip(), phone.strip(),
                                                    email.strip(), address.strip())
                        flash(f"Supplier {name.strip()} added.")
                        st.rerun()
                    except Exception as e:
                        show_error(e)

    if not suppliers:
        return

    with tab_edit:
        s = labels[st.selectbox("Supplier", list(labels), key="edit_supplier_pick")]
        with st.form(f"edit_supplier_{s['supplier_id']}"):
            name = st.text_input("Name", value=s["name"])
            phone = st.text_input("Phone", value=s["phone"] or "")
            email = st.text_input("Email", value=s["email"] or "")
            address = st.text_input("Address", value=s["address"] or "")
            if st.form_submit_button("Save Changes", width="stretch"):
                try:
                    people_service.update_supplier(s["supplier_id"], name.strip(), phone.strip(),
                                                   email.strip(), address.strip())
                    flash(f"{name} updated.")
                    st.rerun()
                except Exception as e:
                    show_error(e)

    with tab_delete:
        s = labels[st.selectbox("Supplier", list(labels), key="delete_supplier_pick")]
        st.caption("A supplier linked to products or purchases cannot be deleted (foreign key).")
        confirm = st.checkbox("I confirm I want to delete this supplier.")
        if st.button("Delete Supplier", type="primary"):
            if not confirm:
                st.warning("Please tick the confirmation box first.")
            else:
                try:
                    people_service.delete_supplier(s["supplier_id"])
                    flash(f"{s['name']} deleted.")
                    st.rerun()
                except Exception as e:
                    show_error(e)
