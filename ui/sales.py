from datetime import timedelta

import pandas as pd
import streamlit as st

import config
from database import mongo_db
from services import ai_service, people_service, product_service, sales_service
from ui.common import current_user, money, show_error, show_table, csv_button, today


def _add_to_cart(product, qty):
    """Add qty of a product to the cart. Returns an error message or None."""
    cart = st.session_state.cart
    line = next((l for l in cart if l["product_id"] == product["product_id"]), None)
    in_cart = line["quantity"] if line else 0
    if in_cart + qty > product["quantity"]:
        return f"Only {product['quantity']} {product['name']} in stock ({in_cart} already in cart)."
    if line:
        line["quantity"] += qty
    else:
        cart.append({"product_id": product["product_id"], "sku": product["sku"],
                     "name": product["name"], "unit_price": float(product["unit_price"]),
                     "quantity": qty})
    return None


def _show_receipt(sale_id):
    header = sales_service.sale_header(sale_id)
    if not header:
        return
    with st.container(border=True):
        st.markdown(f"#### 🧾 {config.STORE_NAME} - Receipt #{sale_id}")
        st.caption(f"{header['sale_date']:%Y-%m-%d %H:%M}  |  Customer: {header['customer']}"
                   f"  |  Cashier: {header['cashier'] or '-'}  |  Paid by {header['payment_method']}")
        show_table(sales_service.sale_items_df(sale_id))
        a, b, c, d = st.columns(4)
        a.metric("Subtotal", money(header["subtotal"]))
        b.metric("Discount", money(header["discount"]))
        c.metric(f"Tax ({config.TAX_RATE:.0%})", money(header["tax"]))
        d.metric("Total", money(header["total"]))


def _cart_and_checkout(cart, products):
    cart_df = pd.DataFrame(cart)
    cart_df["line_total"] = cart_df["unit_price"] * cart_df["quantity"]
    show_table(cart_df[["sku", "name", "unit_price", "quantity", "line_total"]])

    a, b = st.columns([3, 1])
    remove = a.selectbox("Remove an item", [l["name"] for l in cart], key="remove_pick")
    b.write("")
    if b.button("Remove", width="stretch"):
        st.session_state.cart = [l for l in cart if l["name"] != remove]
        st.rerun()

    # ---------- AI suggestions from MongoDB ----------
    if mongo_db.is_available():
        sellable = {p["product_id"]: p for p in products}
        in_cart = {l["product_id"] for l in cart}
        suggestions = {}
        for line in cart:
            for rec in ai_service.get_recommendations(line["product_id"]):
                pid = rec["product_id"]
                if pid not in in_cart and pid in sellable:
                    suggestions.setdefault(pid, rec)
        if suggestions:
            st.markdown("**🤖 Customers who bought these also bought:**")
            cols = st.columns(min(len(suggestions), 4))
            for col, (pid, rec) in zip(cols, list(suggestions.items())[:4]):
                if col.button(f"+ {rec['name']}", key=f"suggest_{pid}", width="stretch"):
                    error = _add_to_cart(sellable[pid], 1)
                    if error:
                        st.error(error)
                    else:
                        st.rerun()

    st.divider()

    # ---------- Checkout ----------
    customers = people_service.list_customers()
    cust_options = {"Walk-in customer": None}
    cust_options.update({f"{c['name']} ({c['phone'] or 'no phone'})": c["customer_id"]
                         for c in customers})

    a, b, c = st.columns(3)
    customer = a.selectbox("Customer", list(cust_options))
    payment = b.selectbox("Payment method", ["Cash", "Card", "Mobile Wallet"])
    discount_pct = c.number_input("Discount %", min_value=0.0, max_value=50.0, step=5.0)

    subtotal, discount, tax, total = sales_service.calculate_totals(cart, discount_pct)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Subtotal", money(subtotal))
    m2.metric("Discount", money(discount))
    m3.metric(f"Tax ({config.TAX_RATE:.0%})", money(tax))
    m4.metric("Total", money(total))

    x, y = st.columns([3, 1])
    if x.button("✅ Checkout", type="primary", width="stretch"):
        user = current_user()
        try:
            sale_id = sales_service.checkout(
                cart, cust_options[customer],
                user["employee_id"] if user else None,
                payment, discount_pct)
            st.session_state.cart = []
            st.session_state.last_sale_id = sale_id
            st.rerun()
        except Exception as e:
            show_error(e)
    if y.button("Clear Cart", width="stretch"):
        st.session_state.cart = []
        st.rerun()


def render_sales_page():
    st.title("🛒 Sales & Billing")
    st.caption("Create a bill. Checkout saves the sale all-or-nothing (stock is put back if anything fails).")

    if "cart" not in st.session_state:
        st.session_state.cart = []
    cart = st.session_state.cart

    # Receipt of the sale that was just completed
    if "last_sale_id" in st.session_state:
        st.success(f"Sale #{st.session_state.last_sale_id} saved.")
        _show_receipt(st.session_state.last_sale_id)
        if st.button("Start New Sale"):
            del st.session_state["last_sale_id"]
            st.rerun()
        st.divider()

    tab_bill, tab_history = st.tabs(["🧾 New Bill", "📜 Sales History"])

    with tab_bill:
        products = product_service.list_sellable_products()
        by_label = {f"{p['sku']} - {p['name']}  ({money(p['unit_price'])}, stock {p['quantity']})": p
                    for p in products}

        # ---------- Add items ----------
        if not products:
            st.info("No products available for sale (all out of stock or expired).")
        else:
            with st.form("add_to_cart", clear_on_submit=True):
                a, b = st.columns([4, 1])
                label = a.selectbox("Product", list(by_label))
                qty = b.number_input("Qty", min_value=1, step=1, value=1)
                if st.form_submit_button("Add to Cart", width="stretch"):
                    error = _add_to_cart(by_label[label], qty)
                    if error:
                        st.error(error)
                    else:
                        st.rerun()

        # ---------- Cart ----------
        st.subheader("Cart")
        if not cart:
            st.info("Cart is empty.")
        else:
            _cart_and_checkout(cart, products)

    with tab_history:
        a, b = st.columns(2)
        start = a.date_input("From", value=today() - timedelta(days=7), key="hist_from")
        end = b.date_input("To", value=today(), key="hist_to")

        history = sales_service.sales_history_df(start, end)
        if not history.empty:
            st.caption(f"{len(history)} sales, total {money(history['total'].sum())}")
        show_table(history, "No sales in this period.")
        csv_button(history, "sales_history.csv")

        if not history.empty:
            sale_id = st.selectbox("View a receipt", history["sale_id"].tolist())
            _show_receipt(int(sale_id))
