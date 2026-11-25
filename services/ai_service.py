"""
AI service: reads sales data from the MongoDB store collections, runs the
AI modules, and saves the results as documents in the AI collections.

sales / products / customers  -> facts (what was sold, when, to whom)
demand_forecasts / recommendations / customer_behavior / ai_logs -> AI output
"""

import time
from datetime import date, datetime, timedelta

import config
from ai.forecasting import fill_daily_series, forecast_demand, restock_advice
from ai.recommender import build_rules, recommend_for
from ai.segmentation import segment_customers
from database import mongo_db
from database.mongo_db import day_start, find_all, to_dt

HISTORY_DAYS = 56  # 8 weeks of history for forecasting


# ---------- 1. Demand forecasting ----------

def run_forecasts(days_ahead=7):
    end_day = date.today() - timedelta(days=1)          # yesterday = last full day
    start_day = end_day - timedelta(days=HISTORY_DAYS - 1)

    products = find_all(mongo_db.PRODUCTS, {"is_active": True})
    # units sold per product per day ($unwind the items, $group by product + day)
    rows = mongo_db.aggregate(mongo_db.SALES, [
        {"$match": {"sale_date": {"$gte": to_dt(start_day), "$lt": to_dt(end_day) + timedelta(days=1)}}},
        {"$unwind": "$items"},
        {"$group": {"_id": {"product_id": "$items.product_id",
                            "sale_day": {"$dateTrunc": {"date": "$sale_date", "unit": "day"}}},
                    "qty": {"$sum": "$items.quantity"}}},
        {"$project": {"_id": 0, "product_id": "$_id.product_id", "sale_day": "$_id.sale_day", "qty": 1}},
    ])

    # {product_id: {date: qty}}
    history = {}
    for r in rows:
        history.setdefault(r["product_id"], {})[r["sale_day"].date()] = r["qty"]

    docs = []
    for p in products:
        daily = fill_daily_series(history.get(p["product_id"], {}), start_day, end_day)
        forecast = forecast_demand(daily, start_day, days_ahead)
        advice = restock_advice(forecast, p["quantity"], p["min_stock"], config.SUPPLIER_LEAD_DAYS)
        docs.append({
            "product_id": p["product_id"],
            "sku": p["sku"],
            "name": p["name"],
            "current_stock": p["quantity"],
            "min_stock": p["min_stock"],
            "history_days": len(daily),
            "last_7_days_sold": sum(daily[-7:]),
            "recent_history": [
                {"date": (end_day - timedelta(days=27 - i)).isoformat(), "qty": q}
                for i, q in enumerate(daily[-28:])
            ],
            "forecast": forecast,
            "forecast_total": round(sum(f["qty"] for f in forecast), 1),
            "restock": advice,
            "method": "7-day level + 28-day trend + weekday factor",
            "generated_at": datetime.now(),
        })

    col = mongo_db.get_db()[mongo_db.FORECASTS]
    col.delete_many({})
    if docs:
        col.insert_many(docs)
    return len(docs)


# ---------- 2. Recommendations ----------

def run_recommendations():
    # Each sale document already holds its basket in the embedded items array
    sales = find_all(mongo_db.SALES, {"sale_date": {"$gte": day_start() - timedelta(days=90)}},
                     projection={"sale_id": 1, "items.product_id": 1})
    names = {p["product_id"]: (p["sku"], p["name"]) for p in find_all(mongo_db.PRODUCTS)}

    baskets = {s["sale_id"]: {i["product_id"] for i in s["items"]} for s in sales}

    rules = build_rules(list(baskets.values()), min_support=0.01, min_confidence=0.1)

    docs = []
    for pid, (sku, name) in names.items():
        picks = recommend_for(pid, rules, top_n=3)
        if not picks:
            continue
        docs.append({
            "product_id": pid,
            "sku": sku,
            "name": name,
            "recommended": [
                {"product_id": r["to"], "sku": names[r["to"]][0], "name": names[r["to"]][1],
                 "support": r["support"], "confidence": r["confidence"], "lift": r["lift"]}
                for r in picks
            ],
            "baskets_analyzed": len(baskets),
            "generated_at": datetime.now(),
        })

    col = mongo_db.get_db()[mongo_db.RECOMMENDATIONS]
    col.delete_many({})
    if docs:
        col.insert_many(docs)
    return len(docs)


# ---------- 3. Customer segmentation ----------

def run_segmentation():
    # Recency, frequency and monetary value per customer
    rows = mongo_db.aggregate(mongo_db.SALES, [
        {"$match": {"customer_id": {"$ne": None}}},
        {"$group": {"_id": "$customer_id", "last_visit": {"$max": "$sale_date"},
                    "visits": {"$sum": 1}, "total_spent": {"$sum": "$total"}}},
        {"$lookup": {"from": mongo_db.CUSTOMERS, "localField": "_id",
                     "foreignField": "customer_id", "as": "c"}},
        {"$project": {"_id": 0, "customer_id": "$_id", "name": {"$first": "$c.name"},
                      "last_visit": 1, "visits": 1, "total_spent": 1}},
    ])
    # Favourite category: units per (customer, category), then keep the top one
    fav_rows = mongo_db.aggregate(mongo_db.SALES, [
        {"$match": {"customer_id": {"$ne": None}}},
        {"$unwind": "$items"},
        {"$lookup": {"from": mongo_db.PRODUCTS, "localField": "items.product_id",
                     "foreignField": "product_id", "as": "p"}},
        {"$lookup": {"from": mongo_db.CATEGORIES, "localField": "p.category_id",
                     "foreignField": "category_id", "as": "c"}},
        {"$group": {"_id": {"customer_id": "$customer_id", "category": {"$first": "$c.name"}},
                    "units": {"$sum": "$items.quantity"}}},
        {"$sort": {"units": -1}},
        {"$group": {"_id": "$_id.customer_id", "category": {"$first": "$_id.category"}}},
    ])
    favourite = {r["_id"]: r["category"] for r in fav_rows}

    today = date.today()
    for r in rows:
        r["recency_days"] = (today - r.pop("last_visit").date()).days
        r["total_spent"] = float(r["total_spent"] or 0)

    docs = []
    for c in segment_customers(rows):
        c["favorite_category"] = favourite.get(c["customer_id"])
        c["avg_basket"] = round(c["total_spent"] / c["visits"], 2) if c["visits"] else 0
        c["generated_at"] = datetime.now()
        docs.append(c)

    col = mongo_db.get_db()[mongo_db.CUSTOMER_SEGMENTS]
    col.delete_many({})
    if docs:
        col.insert_many(docs)
    return len(docs)


# ---------- Run everything ----------

def run_full_analysis():
    """Run all three AI jobs. Returns a summary dict and logs it to ai_logs."""
    summary = {}
    for label, job in [("forecasts", run_forecasts),
                       ("recommendations", run_recommendations),
                       ("segments", run_segmentation)]:
        started = time.perf_counter()
        count = job()
        ms = (time.perf_counter() - started) * 1000
        mongo_db.log_ai_action(f"run_{label}", {"documents": count}, ms)
        summary[label] = count
    return summary


# ---------- Read results back from MongoDB ----------

def get_forecasts():
    return list(mongo_db.get_db()[mongo_db.FORECASTS].find({}, {"_id": 0}).sort("forecast_total", -1))


def get_forecast(product_id):
    return mongo_db.get_db()[mongo_db.FORECASTS].find_one({"product_id": product_id}, {"_id": 0})


def get_recommendations(product_id):
    doc = mongo_db.get_db()[mongo_db.RECOMMENDATIONS].find_one({"product_id": product_id}, {"_id": 0})
    return doc["recommended"] if doc else []


def get_segments():
    return list(mongo_db.get_db()[mongo_db.CUSTOMER_SEGMENTS].find({}, {"_id": 0}).sort("total_spent", -1))


def last_run_time():
    log = mongo_db.get_db()[mongo_db.AI_LOGS].find_one(
        {"action": "run_forecasts"}, sort=[("timestamp", -1)])
    return log["timestamp"] if log else None
