import streamlit as st

from services import report_service, sales_service
from ui.common import money, show_table, today

from datetime import timedelta


def render_dashboard_page():
    st.title("📊 Dashboard")
    st.caption("Live numbers from the MongoDB database.")

    k = report_service.kpis()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Active Products", k["products"])
    c2.metric("Today's Revenue", money(k["revenue_today"]))
    c3.metric("Orders Today", k["orders_today"])
    c4.metric("Stock Alerts", k["low_stock"])
    c5.metric("Expiry Alerts", k["expiring"])

    st.divider()

    left, right = st.columns([3, 2])

    with left:
        st.subheader("Revenue: last 14 days")
        rev = report_service.revenue_last_days(14)
        if not rev.empty:
            rev["sale_day"] = rev["sale_day"].dt.strftime("%m-%d")
            st.bar_chart(rev, x="sale_day", y="revenue", x_label="Day", y_label="Revenue", sort=False)

    with right:
        st.subheader("⚠️ Alerts")
        alerts = report_service.stock_alerts_df()
        if alerts.empty:
            st.success("No stock or expiry alerts.")
        for _, a in alerts.head(8).iterrows():
            if a["stock_status"] == "Out of Stock":
                st.error(f"{a['name']} is out of stock.")
            elif a["stock_status"] == "Low Stock":
                st.warning(f"{a['name']} is low: {a['quantity']} left (minimum {a['min_stock']}).")
            if a["expiry_status"] == "Expired":
                st.error(f"{a['name']} has expired.")
            elif a["expiry_status"] == "Expiring Soon":
                st.info(f"{a['name']} expires in {int(a['days_to_expiry'])} days.")
        if len(alerts) > 8:
            st.caption(f"{len(alerts) - 8} more alerts on the Inventory page.")

    st.divider()

    left, right = st.columns(2)

    with left:
        st.subheader("Top products this week")
        top = report_service.run_report("Top selling products", today() - timedelta(days=6), today())
        show_table(top.head(5), "No sales this week.")

    with right:
        st.subheader("Recent sales")
        recent = sales_service.sales_history_df(today() - timedelta(days=30), today())
        show_table(recent[["sale_id", "sale_date", "customer", "total"]].head(5)
                   if not recent.empty else recent, "No sales yet.")
