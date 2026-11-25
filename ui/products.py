from datetime import timedelta

import streamlit as st

from services import people_service, product_service
from ui.common import csv_button, flash, show_error, show_flash, show_table, to_date, today


def render_products_page():
    st.title("🏷️ Products")
    st.caption("The product catalogue: names, categories, suppliers and prices.")
    show_flash()

    categories = product_service.list_categories()
    suppliers = people_service.list_suppliers()
    cat_ids = {c["name"]: c["category_id"] for c in categories}
    sup_ids = {s["name"]: s["supplier_id"] for s in suppliers}

    if not categories:
        st.warning("Add a category first (bottom of this page).")

    # ---------- Product list ----------
    df = product_service.list_products_df()

    col1, col2 = st.columns([2, 1])
    search = col1.text_input("🔍 Search", placeholder="Name or SKU")
    category = col2.selectbox("Category", ["All"] + list(cat_ids))

    view = df
    if not df.empty:
        if search:
            mask = (df["name"].str.contains(search, case=False, regex=False)
                    | df["sku"].str.contains(search, case=False, regex=False))
            view = view[mask]
        if category != "All":
            view = view[view["category"] == category]
        view = view[["sku", "name", "category", "supplier", "unit_price", "quantity", "expiry_date"]]

    show_table(view, "No products found.")
    csv_button(view, "products.csv")

    tab_add, tab_edit, tab_remove, tab_cat = st.tabs(
        ["➕ Add Product", "✏️ Edit Product", "🗑️ Remove Product", "📂 Categories"])

    # ---------- Add ----------
    with tab_add:
        with st.form("add_product", clear_on_submit=True):
            a, b = st.columns(2)
            sku = a.text_input("SKU *", placeholder="e.g. P025")
            name = a.text_input("Product name *")
            cat = a.selectbox("Category *", list(cat_ids))
            sup = a.selectbox("Supplier", ["(none)"] + list(sup_ids))
            price = b.number_input("Unit price *", min_value=0.0, step=10.0)
            qty = b.number_input("Opening stock", min_value=0, step=1)
            min_stock = b.number_input("Minimum stock", min_value=0, step=1, value=10)
            has_expiry = b.checkbox("Has an expiry date", value=True)
            expiry = b.date_input("Expiry date", value=today() + timedelta(days=90))

            if st.form_submit_button("Add Product", width="stretch"):
                if not sku.strip() or not name.strip() or not cat:
                    st.error("SKU, name and category are required.")
                else:
                    try:
                        product_service.add_product({
                            "sku": sku.strip().upper(), "name": name.strip(),
                            "category_id": cat_ids[cat], "supplier_id": sup_ids.get(sup),
                            "unit_price": price, "quantity": qty, "min_stock": min_stock,
                            "expiry_date": expiry if has_expiry else None,
                        })
                        flash(f"Product {sku.strip().upper()} added.")
                        st.rerun()
                    except Exception as e:
                        show_error(e)

    products = product_service.list_active_products()
    labels = {f"{p['sku']} - {p['name']}": p for p in products}

    # ---------- Edit ----------
    with tab_edit:
        if not products:
            st.info("No products yet.")
        else:
            choice = st.selectbox("Product", list(labels), key="edit_product_pick")
            p = labels[choice]
            cat_names = list(cat_ids)
            sup_names = ["(none)"] + list(sup_ids)
            cur_cat = next((n for n, i in cat_ids.items() if i == p["category_id"]), cat_names[0])
            cur_sup = next((n for n, i in sup_ids.items() if i == p["supplier_id"]), "(none)")

            with st.form(f"edit_product_{p['product_id']}"):
                a, b = st.columns(2)
                name = a.text_input("Product name", value=p["name"])
                cat = a.selectbox("Category", cat_names, index=cat_names.index(cur_cat))
                sup = a.selectbox("Supplier", sup_names, index=sup_names.index(cur_sup))
                price = b.number_input("Unit price", min_value=0.0, value=float(p["unit_price"]))
                min_stock = b.number_input("Minimum stock", min_value=0, value=int(p["min_stock"]))
                has_expiry = b.checkbox("Has an expiry date", value=p["expiry_date"] is not None)
                expiry = b.date_input("Expiry date",
                                      value=to_date(p["expiry_date"]) or today() + timedelta(days=90))
                st.caption("Stock quantity is changed on the Inventory page (restock or adjust).")

                if st.form_submit_button("Save Changes", width="stretch"):
                    try:
                        product_service.update_product(p["product_id"], {
                            "name": name.strip(), "category_id": cat_ids[cat],
                            "supplier_id": sup_ids.get(sup), "unit_price": price,
                            "min_stock": min_stock, "expiry_date": expiry if has_expiry else None,
                        })
                        flash(f"{name} updated.")
                        st.rerun()
                    except Exception as e:
                        show_error(e)

    # ---------- Remove ----------
    with tab_remove:
        if products:
            choice = st.selectbox("Product", list(labels), key="remove_product_pick")
            st.caption("Products that were sold before are hidden instead of deleted, "
                       "so old sales keep their records (foreign key).")
            confirm = st.checkbox("I confirm I want to remove this product.")
            if st.button("Remove Product", type="primary"):
                if not confirm:
                    st.warning("Please tick the confirmation box first.")
                else:
                    try:
                        result = product_service.remove_product(labels[choice]["product_id"])
                        flash(f"{choice} was {result}.")
                        st.rerun()
                    except Exception as e:
                        show_error(e)

    # ---------- Categories ----------
    with tab_cat:
        st.write(", ".join(cat_ids) or "No categories yet.")
        with st.form("add_category", clear_on_submit=True):
            new_cat = st.text_input("New category name")
            if st.form_submit_button("Add Category"):
                if new_cat.strip():
                    try:
                        product_service.add_category(new_cat.strip())
                        flash(f"Category {new_cat.strip()} added.")
                        st.rerun()
                    except Exception as e:
                        show_error(e)
