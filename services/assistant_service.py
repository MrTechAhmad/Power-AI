"""
Store assistant: answers simple questions in plain English.

It is rule-based (no internet, no API key): it looks for keywords to
find the intent, finds any product named in the question, then runs
the matching MongoDB query or reads the stored AI results.
"""

import re
import time
from datetime import timedelta, date

import pandas as pd

import config
from database import mongo_db
from database.mongo_db import find_all
from services import ai_service, report_service

HELP_TEXT = """I can answer questions like:
- **Which products are low on stock?**
- **What is expiring soon?**
- **How are sales today?**
- **What are the top selling products?**
- **Forecast for milk** (AI, from MongoDB)
- **What goes with bread?** (AI, from MongoDB)
- **Price of rice** / **Stock of cooking oil**
- **Show customer segments** (AI, from MongoDB)"""

# keyword -> intent (checked in this order)
INTENTS = [
    ("help", ["help", "what can you"]),
    ("recommend", ["goes with", "bought with", "recommend", "suggest", "together"]),
    ("forecast", ["forecast", "demand", "predict", "will we sell", "how many will"]),
    ("low_stock", ["low stock", "low on", "reorder", "out of stock", "running out", "restock"]),
    ("expiry", ["expir", "expire"]),
    ("segments", ["segment", "best customer", "loyal", "customers"]),
    ("top", ["top", "best sell", "most sold", "popular"]),
    ("sales_today", ["today", "revenue", "sales"]),
    ("price", ["price", "cost"]),
    ("stock_of", ["stock of", "how many", "quantity"]),
]


def detect_intent(question):
    q = question.lower()
    for intent, words in INTENTS:
        if any(w in q for w in words):
            return intent
    return "unknown"


def find_product(question):
    """Return the product whose name (or sku) appears in the question, or None."""
    q = question.lower()
    words = re.findall(r"[a-z0-9]+", q)
    products = find_all(mongo_db.PRODUCTS, {"is_active": True})
    # Longest names first so "cooking oil" wins over "oil"
    for p in sorted(products, key=lambda p: len(p["name"]), reverse=True):
        if p["name"].lower() in q or p["sku"].lower() in words:
            return p
    # Otherwise match any single word of the name, e.g. "oil"
    for p in products:
        if any(len(w) > 2 and w in words for w in p["name"].lower().split()):
            return p
    return None


def answer(question):
    """Returns (text, dataframe_or_None, intent)."""
    started = time.perf_counter()
    intent = detect_intent(question)
    text, table = _answer_intent(intent, question)
    mongo_db.log_ai_action("assistant_question",
                           {"question": question, "intent": intent},
                           (time.perf_counter() - started) * 1000)
    return text, table, intent


def _answer_intent(intent, question):
    cur = config.CURRENCY

    if intent == "help":
        return HELP_TEXT, None

    if intent == "low_stock":
        df = report_service.stock_alerts_df()
        df = df[df["stock_status"] != "In Stock"] if not df.empty else df
        if df.empty:
            return "Good news: no products are low or out of stock.", None
        return (f"**{len(df)} products** need attention:",
                df[["sku", "name", "quantity", "min_stock", "stock_status"]])

    if intent == "expiry":
        df = report_service.stock_alerts_df()
        df = df[df["expiry_status"].isin(["Expired", "Expiring Soon"])] if not df.empty else df
        if df.empty:
            return f"Nothing expires in the next {config.EXPIRY_WARNING_DAYS} days.", None
        return (f"**{len(df)} products** are expired or expiring soon:",
                df[["sku", "name", "quantity", "expiry_date", "days_to_expiry", "expiry_status"]])

    if intent == "top":
        df = report_service.run_report("Top selling products",
                                       date.today() - timedelta(days=6), date.today())
        if df.empty:
            return "No sales in the last 7 days.", None
        return "Top sellers in the **last 7 days**:", df.head(5)

    if intent == "sales_today":
        k = report_service.kpis()
        return (f"Today so far: **{k['orders_today']} orders** and "
                f"**{cur} {float(k['revenue_today']):,.2f}** revenue."), None

    product = find_product(question)

    if intent in ("price", "stock_of"):
        if not product:
            return "Which product? For example: *price of rice*.", None
        status = ("out of stock" if product["quantity"] == 0 else
                  "low on stock" if product["quantity"] <= product["min_stock"] else "in stock")
        return (f"**{product['name']}** ({product['sku']}) costs **{cur} {float(product['unit_price']):,.2f}**. "
                f"We have **{product['quantity']}** units ({status})."), None

    # The remaining intents use AI results stored in MongoDB
    if intent == "forecast":
        if not product:
            return "Which product? For example: *forecast for milk*.", None
        fc = ai_service.get_forecast(product["product_id"])
        if not fc:
            return "No forecast yet. Run the analysis on the AI Insights page first.", None
        r = fc["restock"]
        stockout = (f"Stock lasts about **{r['days_until_stockout']} days**."
                    if r["days_until_stockout"] is not None else "It is not selling at the moment.")
        advice = (f"Suggest ordering **{r['reorder_qty']} units** (urgency: {r['urgency']})."
                  if r["reorder_qty"] else "No reorder needed.")
        return (f"**{product['name']}**: expected to sell **{fc['forecast_total']} units** in the next 7 days "
                f"(~{r['avg_daily_demand']}/day). {stockout} {advice}",
                pd.DataFrame(fc["forecast"]))

    if intent == "recommend":
        if not product:
            return "Which product? For example: *what goes with bread?*", None
        recs = ai_service.get_recommendations(product["product_id"])
        if not recs:
            return f"No strong buying pattern found for {product['name']} yet.", None
        names = ", ".join(f"**{r['name']}**" for r in recs)
        return (f"Customers who buy {product['name']} often also buy {names}.",
                pd.DataFrame(recs)[["name", "confidence", "lift"]])

    if intent == "segments":
        segs = ai_service.get_segments()
        if not segs:
            return "No segments yet. Run the analysis on the AI Insights page first.", None
        df = pd.DataFrame(segs)
        summary = (df.groupby("segment")
                     .agg(customers=("name", "count"), avg_spent=("total_spent", "mean"))
                     .round(0).reset_index().sort_values("avg_spent", ascending=False))
        return "Customer segments (RFM analysis):", summary

    # Unknown intent: maybe they just typed a product name
    if product:
        return _answer_intent("price", question)
    return "Sorry, I did not understand that.\n\n" + HELP_TEXT, None
