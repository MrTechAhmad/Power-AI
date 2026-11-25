import json

import pandas as pd
import streamlit as st

from database import mongo_db
from services import ai_service
from services.mongo_queries import PIPELINES, run_pipeline
from ui.common import flash, money, mongo_ready, show_error, show_flash, show_table


def _json(value):
    """Pretty JSON for showing a pipeline (dates become text)."""
    return json.dumps(value, indent=2, default=str)


def render_ai_insights_page():
    st.title("🤖 AI Insights")
    st.caption("AI modules read the sales collection and store their results in the AI collections.")

    if not mongo_ready():
        return
    show_flash()

    # ---------- Run the analysis ----------
    last = ai_service.last_run_time()
    a, b = st.columns([3, 1])
    a.info(f"Last analysis: {last:%Y-%m-%d %H:%M}" if last else "The AI analysis has not been run yet.")
    if b.button("▶ Run AI Analysis", type="primary", width="stretch"):
        try:
            with st.spinner("Reading sales and saving AI results to MongoDB..."):
                summary = ai_service.run_full_analysis()
            flash(f"Saved {summary['forecasts']} forecasts, "
                  f"{summary['recommendations']} recommendation sets and "
                  f"{summary['segments']} customer segments to MongoDB.")
            st.rerun()
        except Exception as e:
            show_error(e)

    tab_fc, tab_rec, tab_seg, tab_lab = st.tabs(
        ["📦 Demand & Restock", "🛍️ Recommendations", "👥 Customer Segments", "🧪 MongoDB Query Lab"])

    # ---------- Forecasts ----------
    with tab_fc:
        forecasts = ai_service.get_forecasts()
        if not forecasts:
            st.info("No forecasts yet. Click 'Run AI Analysis'.")
        else:
            rows = [{
                "sku": f["sku"], "name": f["name"], "stock": f["current_stock"],
                "sold_last_7_days": f["last_7_days_sold"],
                "expected_next_7_days": f["forecast_total"],
                "days_until_stockout": f["restock"]["days_until_stockout"],
                "reorder_qty": f["restock"]["reorder_qty"],
                "urgency": f["restock"]["urgency"],
            } for f in forecasts]
            df = pd.DataFrame(rows)

            only_reorder = st.toggle("Show only products that need reordering", value=True)
            if only_reorder:
                df = df[df["reorder_qty"] > 0]
            order = {"Critical": 0, "High": 1, "Medium": 2, "OK": 3}
            df = df.sort_values("urgency", key=lambda s: s.map(order))
            show_table(df, "Nothing needs reordering right now.")

            st.subheader("History vs forecast")
            names = {f"{f['sku']} - {f['name']}": f for f in forecasts}
            f = names[st.selectbox("Product", list(names))]
            hist = pd.DataFrame(f["recent_history"]).rename(columns={"qty": "Sold"})
            pred = pd.DataFrame(f["forecast"]).rename(columns={"qty": "Forecast"})
            chart = pd.concat([hist, pred]).set_index("date")
            st.line_chart(chart, x_label="Date", y_label="Units")
            st.caption(f"Method: {f['method']}. Average demand "
                       f"{f['restock']['avg_daily_demand']} units/day.")

    # ---------- Recommendations ----------
    with tab_rec:
        products = ai_service.get_forecasts()  # same product list, already loaded from MongoDB
        if not products:
            st.info("No recommendations yet. Click 'Run AI Analysis'.")
        else:
            names = {f"{p['sku']} - {p['name']}": p["product_id"] for p in products}
            pick = st.selectbox("A customer buys...", sorted(names))
            recs = ai_service.get_recommendations(names[pick])
            if not recs:
                st.info("No strong pattern found for this product yet.")
            else:
                st.write("**...they often also buy:**")
                show_table(pd.DataFrame(recs)[["sku", "name", "confidence", "lift"]])
                st.caption("Confidence = how often they are bought together when the first product is bought. "
                           "Lift above 1 means more often than by chance.")

    # ---------- Segments ----------
    with tab_seg:
        segments = ai_service.get_segments()
        if not segments:
            st.info("No segments yet. Click 'Run AI Analysis'.")
        else:
            df = pd.DataFrame(segments)
            counts = df["segment"].value_counts()
            cols = st.columns(len(counts))
            for col, (seg, n) in zip(cols, counts.items()):
                col.metric(seg, n)
            df["total_spent"] = df["total_spent"].map(money)
            show_table(df[["name", "segment", "visits", "total_spent", "recency_days",
                           "favorite_category", "r_score", "f_score", "m_score"]])
            st.caption("RFM: Recency (days since last visit), Frequency (visits), "
                       "Monetary (money spent), each scored 1-3.")

    # ---------- Query lab ----------
    with tab_lab:
        st.write("Real aggregation pipelines running on MongoDB. "
                 "Copy any pipeline into mongosh or MongoDB Compass to try it yourself.")
        name = st.selectbox("Pipeline", list(PIPELINES))
        item = PIPELINES[name]
        st.caption(f"Collection: `{item['collection']}`  |  Stages: {item['stages']}")
        st.code(f"db.{item['collection']}.aggregate({_json(item['pipeline'])})", language="javascript")
        try:
            result = run_pipeline(name)
            if result:
                st.dataframe(pd.DataFrame(result).astype(str), width="stretch", hide_index=True)
                with st.expander("Raw documents"):
                    st.code(_json(result), language="json")
            else:
                st.info("No documents yet. Run the AI analysis first.")
        except Exception as e:
            show_error(e)

        with st.expander("Collection sizes"):
            st.json(mongo_db.collection_counts())
