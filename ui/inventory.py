from datetime import timedelta

import streamlit as st

from services import people_service, product_service
from ui.common import csv_button, flash, show_error, show_flash, show_table, to_date, today


def render_inventory_page():
    st.title("📦 Inventory Management")
    st.caption("Stock levels, expiry dates and restocking.")
    show_flash()

    df = product_service.list_products_df()

    # ---------- Overview ----------
    if not df.empty:
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Products", len(df))
        c2.metric("Total Units", int(df["quantity"].sum()))
        c3.metric("Low Stock", int((df["stock_status"] == "Low Stock").sum()))
        c4.metric("Out of Stock", int((df["stock_status"] == "Out of Stock").sum()))
        c5.metric("Expiring / Expired",
                  int(df["expiry_status"].isin(["Expiring Soon", "Expired"]).sum()))
    st.divider()

    # ---------- Stock table with filters ----------
    st.subheader("Stock Levels")
    col1, col2, col3 = st.columns(3)
    search = col1.text_input("🔍 Search", placeholder="Name or SKU")
    stock_filter = col2.selectbox("Stock status", ["All", "In Stock", "Low Stock", "Out of Stock"])
    expiry_filter = col3.selectbox("Expiry status",
                                   ["All", "Valid", "Expiring Soon", "Expired", "No Expiry"])

    view = df
    if not df.empty:
        if search:
            view = view[view["name"].str.contains(search, case=False, regex=False)
                        | view["sku"].str.contains(search, case=False, regex=False)]
        if stock_filter != "All":
            view = view[view["stock_status"] == stock_filter]
        if expiry_filter != "All":
            view = view[view["expiry_status"] == expiry_filter]
        view = view[["sku", "name", "category", "quantity", "min_stock",
                     "stock_status", "expiry_date", "days_to_expiry", "expiry_status"]]

    show_table(view, "No products match the filters.")
    csv_button(view, "inventory.csv", "Download Inventory CSV")

    products = product_service.list_active_products()
    labels = {f"{p['sku']} - {p['name']} (stock {p['quantity']})": p for p in products}

    tab_restock, tab_adjust, tab_history = st.tabs(
        ["🚚 Restock", "🔧 Adjust Stock", "📜 Purchase History"])

    # ---------- Restock (calls the stored procedure sp_restock) ----------
    with tab_restock:
        suppliers = people_service.list_suppliers()
        sup_ids = {s["name"]: s["supplier_id"] for s in suppliers}

        if not products or not suppliers:
            st.info("You need at least one product and one supplier to restock.")
        else:
            choice = st.selectbox("Product", list(labels), key="restock_pick")
            p = labels[choice]
            sup_names = list(sup_ids)
            default_sup = next((i for i, n in enumerate(sup_names)
                                if sup_ids[n] == p["supplier_id"]), 0)

            with st.form(f"restock_{p['product_id']}", clear_on_submit=True):
                a, b = st.columns(2)
                supplier = a.selectbox("Supplier", sup_names, index=default_sup)
                qty = a.number_input("Quantity received", min_value=1, step=1, value=10)
                cost = b.number_input("Unit cost (what we paid)", min_value=0.0,
                                      value=round(float(p["unit_price"]) * 0.8, 2))
                new_expiry = b.date_input(
                    "Expiry date of this batch",
                    value=to_date(p["expiry_date"]) or today() + timedelta(days=90))
                st.caption("Runs the stored procedure sp_restock: inserts a purchase row and adds the stock.")

                if st.form_submit_button("Record Delivery", width="stretch"):
                    try:
                        product_service.restock(p["product_id"], sup_ids[supplier],
                                                qty, cost, new_expiry)
                        flash(f"Added {qty} units of {p['name']}.")
                        st.rerun()
                    except Exception as e:
                        show_error(e)

    # ---------- Adjust ----------
    with tab_adjust:
        if products:
            choice = st.selectbox("Product", list(labels), key="adjust_pick")
            p = labels[choice]
            with st.form(f"adjust_{p['product_id']}"):
                new_qty = st.number_input("Counted quantity", min_value=0, value=int(p["quantity"]))
                st.caption("Use this after a stock count, or to remove damaged or expired items.")
                if st.form_submit_button("Save Count"):
                    try:
                        product_service.adjust_stock(p["product_id"], new_qty)
                        flash(f"{p['name']} stock set to {new_qty}.")
                        st.rerun()
                    except Exception as e:
                        show_error(e)

    # ---------- Purchase history ----------
    with tab_history:
        show_table(product_service.purchase_history_df(50), "No deliveries recorded yet.")
