import json
from datetime import timedelta

import streamlit as st

from services.report_service import REPORTS, build_pipeline, run_report
from ui.common import csv_button, show_error, show_table, today


def render_reports_page():
    st.title("📈 Reports")
    st.caption("Every report is one MongoDB aggregation pipeline. Open 'Show pipeline' to see it.")

    a, b, c = st.columns([2, 1, 1])
    name = a.selectbox("Report", list(REPORTS))
    period = b.selectbox("Period", ["Today", "Last 7 days", "Last 30 days", "Last 90 days", "Custom"])

    days = {"Today": 0, "Last 7 days": 6, "Last 30 days": 29, "Last 90 days": 89}
    if period == "Custom":
        start = c.date_input("From", value=today() - timedelta(days=30))
        end = c.date_input("To", value=today())
    else:
        start, end = today() - timedelta(days=days[period]), today()
        c.write("")
        c.caption(f"{start} to {end}")

    report = REPORTS[name]

    with st.expander("Show pipeline"):
        st.caption(f"Concept: {report['concept']}")
        st.caption(f"db.{report['collection']}.aggregate(...)")
        st.code(json.dumps(build_pipeline(name, start, end), indent=2, default=str), language="json")

    try:
        df = run_report(name, start, end)
    except Exception as e:
        show_error(e)
        return

    if report["chart"] and not df.empty:
        x, y = report["chart"]
        chart_df = df.copy()
        if x == "sale_day":
            chart_df[x] = chart_df[x].dt.strftime("%m-%d")
        st.bar_chart(chart_df, x=x, y=y, x_label=x.replace("_", " ").title(),
                     y_label=y.replace("_", " ").title(), sort=False)  # keep the pipeline's $sort

    show_table(df, "No data for this period.")
    csv_button(df, f"{name.lower().replace(' ', '_')}.csv")
