"""
Reports (MongoDB aggregation pipelines).

Each report keeps the function that builds its pipeline, so the Reports
page can show the exact pipeline next to the result. The same JSON works
in mongosh or MongoDB Compass (Aggregations tab).
"""

from datetime import date, timedelta

import pandas as pd

from database import mongo_db as m
from database.mongo_db import day_start, to_dt
from services.product_service import inventory_status_pipeline


def _period(start, end):
    return {"$gte": to_dt(start), "$lt": to_dt(end) + timedelta(days=1)}


def _lookup(frm, local, foreign, as_):
    return {"$lookup": {"from": frm, "localField": local, "foreignField": foreign, "as": as_}}


REPORTS = {
    "Daily sales": {
        "concept": "$match on a date range + $group by day ($dateTrunc) + $sum/$avg",
        "collection": m.SALES,
        "chart": ("sale_day", "revenue"),
        "pipeline": lambda s, e: [
            {"$match": {"sale_date": _period(s, e)}},
            {"$group": {"_id": {"$dateTrunc": {"date": "$sale_date", "unit": "day"}},
                        "orders": {"$sum": 1}, "revenue": {"$sum": "$total"},
                        "avg_order": {"$avg": "$total"}}},
            {"$project": {"_id": 0, "sale_day": "$_id", "orders": 1, "revenue": {"$round": ["$revenue", 2]},
                          "avg_order": {"$round": ["$avg_order", 2]}}},
            {"$sort": {"sale_day": 1}},
        ],
    },
    "Top selling products": {
        "concept": "$unwind the embedded items array + $group + $sort + $limit",
        "collection": m.SALES,
        "chart": ("product", "units_sold"),
        "pipeline": lambda s, e: [
            {"$match": {"sale_date": _period(s, e)}},
            {"$unwind": "$items"},
            {"$group": {"_id": "$items.product_id",
                        "units_sold": {"$sum": "$items.quantity"},
                        "revenue": {"$sum": {"$multiply": ["$items.quantity", "$items.unit_price"]}}}},
            {"$sort": {"units_sold": -1}},
            {"$limit": 10},
            _lookup(m.PRODUCTS, "_id", "product_id", "p"),
            {"$project": {"_id": 0, "product": {"$first": "$p.name"}, "units_sold": 1,
                          "revenue": {"$round": ["$revenue", 2]}}},
        ],
    },
    "Revenue by category": {
        "concept": "$unwind + two $lookup joins + $group + $match after grouping (like HAVING)",
        "collection": m.SALES,
        "chart": ("category", "revenue"),
        "pipeline": lambda s, e: [
            {"$match": {"sale_date": _period(s, e)}},
            {"$unwind": "$items"},
            _lookup(m.PRODUCTS, "items.product_id", "product_id", "p"),
            _lookup(m.CATEGORIES, "p.category_id", "category_id", "c"),
            {"$group": {"_id": {"$first": "$c.name"},
                        "units_sold": {"$sum": "$items.quantity"},
                        "revenue": {"$sum": {"$multiply": ["$items.quantity", "$items.unit_price"]}}}},
            {"$match": {"units_sold": {"$gt": 0}}},
            {"$project": {"_id": 0, "category": "$_id", "units_sold": 1,
                          "revenue": {"$round": ["$revenue", 2]}}},
            {"$sort": {"revenue": -1}},
        ],
    },
    "Payment methods": {
        "concept": "$group + percentage with a window function ($setWindowFields)",
        "collection": m.SALES,
        "chart": ("payment_method", "revenue"),
        "pipeline": lambda s, e: [
            {"$match": {"sale_date": _period(s, e)}},
            {"$group": {"_id": "$payment_method", "orders": {"$sum": 1}, "revenue": {"$sum": "$total"}}},
            {"$setWindowFields": {"output": {"all_revenue": {"$sum": "$revenue"}}}},
            {"$project": {"_id": 0, "payment_method": "$_id", "orders": 1,
                          "revenue": {"$round": ["$revenue", 2]},
                          "percent_of_revenue": {"$round": [
                              {"$multiply": [100, {"$divide": ["$revenue", "$all_revenue"]}]}, 1]}}},
            {"$sort": {"revenue": -1}},
        ],
    },
    "Cashier performance": {
        "concept": "$lookup + $group + $rank window function",
        "collection": m.SALES,
        "chart": ("cashier", "revenue"),
        "pipeline": lambda s, e: [
            {"$match": {"sale_date": _period(s, e), "employee_id": {"$ne": None}}},
            {"$group": {"_id": "$employee_id", "orders": {"$sum": 1}, "revenue": {"$sum": "$total"}}},
            {"$setWindowFields": {"sortBy": {"revenue": -1}, "output": {"rank_no": {"$rank": {}}}}},
            _lookup(m.EMPLOYEES, "_id", "employee_id", "e"),
            {"$project": {"_id": 0, "cashier": {"$first": "$e.name"}, "orders": 1,
                          "revenue": {"$round": ["$revenue", 2]}, "rank_no": 1}},
            {"$sort": {"rank_no": 1}},
        ],
    },
    "Top customers": {
        "concept": "$match (walk-in sales excluded) + $group + $lookup + $limit",
        "collection": m.SALES,
        "chart": ("customer", "total_spent"),
        "pipeline": lambda s, e: [
            {"$match": {"sale_date": _period(s, e), "customer_id": {"$ne": None}}},
            {"$group": {"_id": "$customer_id", "visits": {"$sum": 1}, "total_spent": {"$sum": "$total"}}},
            {"$sort": {"total_spent": -1}},
            {"$limit": 10},
            _lookup(m.CUSTOMERS, "_id", "customer_id", "c"),
            {"$project": {"_id": 0, "customer": {"$first": "$c.name"}, "visits": 1,
                          "total_spent": {"$round": ["$total_spent", 2]},
                          "loyalty_points": {"$first": "$c.loyalty_points"}}},
        ],
    },
    "Supplier purchases": {
        "concept": "$group on the purchases collection + $lookup",
        "collection": m.PURCHASES,
        "chart": ("supplier", "total_cost"),
        "pipeline": lambda s, e: [
            {"$match": {"purchase_date": _period(s, e)}},
            {"$group": {"_id": "$supplier_id", "deliveries": {"$sum": 1}, "units": {"$sum": "$quantity"},
                        "total_cost": {"$sum": {"$multiply": ["$quantity", "$unit_cost"]}}}},
            _lookup(m.SUPPLIERS, "_id", "supplier_id", "s"),
            {"$project": {"_id": 0, "supplier": {"$first": "$s.name"}, "deliveries": 1, "units": 1,
                          "total_cost": {"$round": ["$total_cost", 2]}}},
            {"$sort": {"total_cost": -1}},
        ],
    },
    "Products never sold in this period": {
        "concept": "$lookup with a sub-pipeline + $match on an empty array (like NOT EXISTS)",
        "collection": m.PRODUCTS,
        "chart": None,
        "pipeline": lambda s, e: [
            {"$match": {"is_active": True}},
            {"$lookup": {"from": m.SALES, "localField": "product_id", "foreignField": "items.product_id",
                         "pipeline": [{"$match": {"sale_date": _period(s, e)}}, {"$limit": 1}],
                         "as": "sold"}},
            {"$match": {"sold": {"$size": 0}}},
            {"$project": {"_id": 0, "sku": 1, "name": 1, "quantity": 1}},
            {"$sort": {"name": 1}},
        ],
    },
    "Stock alerts (inventory status pipeline)": {
        "concept": "Reusing the inventory-status pipeline (replaces the SQL view) + $match",
        "collection": m.PRODUCTS,
        "chart": None,
        "pipeline": lambda s, e: inventory_status_pipeline() + [
            {"$match": {"$or": [{"stock_status": {"$ne": "In Stock"}},
                                {"expiry_status": {"$in": ["Expired", "Expiring Soon"]}}]}},
            {"$project": {"sku": 1, "name": 1, "quantity": 1, "min_stock": 1, "stock_status": 1,
                          "expiry_date": 1, "expiry_status": 1}},
            {"$sort": {"quantity": 1}},
        ],
    },
}


def build_pipeline(name, start_date, end_date):
    return REPORTS[name]["pipeline"](start_date, end_date)


def run_report(name, start_date, end_date):
    report = REPORTS[name]
    return pd.DataFrame(m.aggregate(report["collection"], build_pipeline(name, start_date, end_date)))


# ---------- Small numbers for the dashboard ----------

def kpis():
    today = day_start()
    revenue = m.aggregate(m.SALES, [{"$match": {"sale_date": {"$gte": today}}},
                                    {"$group": {"_id": None, "revenue": {"$sum": "$total"},
                                                "orders": {"$sum": 1}}}])
    status = m.aggregate(m.PRODUCTS, inventory_status_pipeline())
    return {
        "products": m.col(m.PRODUCTS).count_documents({"is_active": True}),
        "revenue_today": revenue[0]["revenue"] if revenue else 0,
        "orders_today": revenue[0]["orders"] if revenue else 0,
        "low_stock": sum(1 for p in status if p["stock_status"] != "In Stock"),
        "expiring": sum(1 for p in status if p["expiry_status"] in ("Expired", "Expiring Soon")),
        "customers": m.col(m.CUSTOMERS).count_documents({}),
    }


def revenue_last_days(days=14):
    """Revenue per day for the last N days, including days with no sales."""
    first = date.today() - timedelta(days=days - 1)
    rows = m.aggregate(m.SALES, [
        {"$match": {"sale_date": {"$gte": to_dt(first)}}},
        {"$group": {"_id": {"$dateTrunc": {"date": "$sale_date", "unit": "day"}},
                    "revenue": {"$sum": "$total"}}},
    ])
    by_day = {r["_id"].date(): r["revenue"] for r in rows}
    all_days = [first + timedelta(days=i) for i in range(days)]
    return pd.DataFrame({"sale_day": pd.to_datetime(all_days),
                         "revenue": [round(by_day.get(d, 0), 2) for d in all_days]})


ALERT_COLUMNS = ["sku", "name", "quantity", "min_stock", "stock_status", "expiry_date",
                 "days_to_expiry", "expiry_status"]


def stock_alerts_df():
    rows = [p for p in m.aggregate(m.PRODUCTS, inventory_status_pipeline())
            if p["stock_status"] != "In Stock" or p["expiry_status"] in ("Expired", "Expiring Soon")]
    rows.sort(key=lambda p: p["quantity"])
    return pd.DataFrame(rows, columns=ALERT_COLUMNS)
