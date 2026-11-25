import streamlit as st

from services import people_service
from ui.common import csv_button, flash, show_error, show_flash, show_table


def render_customers_page():
    st.title("👥 Customers")
    st.caption("Customer records, loyalty points and purchase history.")
    show_flash()

    df = people_service.list_customers_df()
    search = st.text_input("🔍 Search", placeholder="Name or phone")
    view = df
    if search and not df.empty:
        view = df[df["name"].str.contains(search, case=False, regex=False)
                  | df["phone"].fillna("").str.contains(search, regex=False)]
    show_table(view, "No customers yet.")
    csv_button(view, "customers.csv")

    customers = people_service.list_customers()
    labels = {f"{c['name']} ({c['phone'] or 'no phone'})": c for c in customers}

    tab_add, tab_edit, tab_history, tab_delete = st.tabs(
        ["➕ Add", "✏️ Edit", "🧾 Purchase History", "🗑️ Delete"])

    with tab_add:
        with st.form("add_customer", clear_on_submit=True):
            name = st.text_input("Name *")
            phone = st.text_input("Phone (must be unique)")
            email = st.text_input("Email")
            if st.form_submit_button("Add Customer", width="stretch"):
                if not name.strip():
                    st.error("Name is required.")
                else:
                    try:
                        people_service.add_customer(name.strip(), phone.strip(), email.strip())
                        flash(f"Customer {name.strip()} added.")
                        st.rerun()
                    except Exception as e:
                        show_error(e)

    if not customers:
        return

    with tab_edit:
        c = labels[st.selectbox("Customer", list(labels), key="edit_customer_pick")]
        with st.form(f"edit_customer_{c['customer_id']}"):
            name = st.text_input("Name", value=c["name"])
            phone = st.text_input("Phone", value=c["phone"] or "")
            email = st.text_input("Email", value=c["email"] or "")
            st.caption(f"Loyalty points: {c['loyalty_points']} (earned automatically at checkout)")
            if st.form_submit_button("Save Changes", width="stretch"):
                try:
                    people_service.update_customer(c["customer_id"], name.strip(),
                                                   phone.strip(), email.strip())
                    flash(f"{name} updated.")
                    st.rerun()
                except Exception as e:
                    show_error(e)

    with tab_history:
        c = labels[st.selectbox("Customer", list(labels), key="history_customer_pick")]
        show_table(people_service.customer_history_df(c["customer_id"]),
                   "This customer has no purchases yet.")

    with tab_delete:
        c = labels[st.selectbox("Customer", list(labels), key="delete_customer_pick")]
        st.caption("Customers with past purchases cannot be deleted (foreign key protects sales).")
        confirm = st.checkbox("I confirm I want to delete this customer.")
        if st.button("Delete Customer", type="primary"):
            if not confirm:
                st.warning("Please tick the confirmation box first.")
            else:
                try:
                    people_service.delete_customer(c["customer_id"])
                    flash(f"{c['name']} deleted.")
                    st.rerun()
                except Exception as e:
                    show_error(e)
