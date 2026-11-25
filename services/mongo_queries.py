"""
MongoDB queries and aggregation pipelines.

Each entry keeps the collection name and the pipeline as plain Python
lists/dicts, so the AI Insights page can show the exact pipeline
next to its result (the same text works in mongosh or Compass).
"""

from database import mongo_db

PIPELINES = {
    "Highest expected demand (next 7 days)": {
        "collection": mongo_db.FORECASTS,
        "stages": "$project, $sort, $limit",
        "pipeline": [
            {"$project": {"_id": 0, "sku": 1, "name": 1, "current_stock": 1,
                          "forecast_total": 1}},
            {"$sort": {"forecast_total": -1}},
            {"$limit": 5},
        ],
    },
    "Products to reorder, by urgency": {
        "collection": mongo_db.FORECASTS,
        "stages": "$match, $group, $sort",
        "pipeline": [
            {"$match": {"restock.urgency": {"$in": ["Critical", "High", "Medium"]}}},
            {"$group": {"_id": "$restock.urgency",
                        "products": {"$sum": 1},
                        "units_to_order": {"$sum": "$restock.reorder_qty"},
                        "items": {"$push": "$name"}}},
            {"$sort": {"units_to_order": -1}},
        ],
    },
    "Forecast per day (unwind the daily array)": {
        "collection": mongo_db.FORECASTS,
        "stages": "$unwind, $group, $sort",
        "pipeline": [
            {"$unwind": "$forecast"},
            {"$group": {"_id": "$forecast.date",
                        "expected_units": {"$sum": "$forecast.qty"}}},
            {"$sort": {"_id": 1}},
        ],
    },
    "Customer segments summary": {
        "collection": mongo_db.CUSTOMER_SEGMENTS,
        "stages": "$group, $project, $sort",
        "pipeline": [
            {"$group": {"_id": "$segment",
                        "customers": {"$sum": 1},
                        "avg_spent": {"$avg": "$total_spent"},
                        "avg_visits": {"$avg": "$visits"}}},
            {"$project": {"segment": "$_id", "_id": 0, "customers": 1,
                          "avg_spent": {"$round": ["$avg_spent", 0]},
                          "avg_visits": {"$round": ["$avg_visits", 1]}}},
            {"$sort": {"avg_spent": -1}},
        ],
    },
    "Strongest product pairs (lift)": {
        "collection": mongo_db.RECOMMENDATIONS,
        "stages": "$unwind, $match, $project, $sort, $limit",
        "pipeline": [
            {"$unwind": "$recommended"},
            {"$match": {"recommended.lift": {"$gt": 1.2}}},
            {"$project": {"_id": 0, "bought": "$name",
                          "also_bought": "$recommended.name",
                          "confidence": "$recommended.confidence",
                          "lift": "$recommended.lift"}},
            {"$sort": {"lift": -1}},
            {"$limit": 10},
        ],
    },
    "Reorder items with their recommendations ($lookup join)": {
        "collection": mongo_db.FORECASTS,
        "stages": "$match, $lookup, $unwind, $project, $sort",
        "pipeline": [
            {"$match": {"restock.reorder_qty": {"$gt": 0}}},
            {"$lookup": {"from": mongo_db.RECOMMENDATIONS,
                         "localField": "product_id",
                         "foreignField": "product_id",
                         "as": "rec"}},
            {"$unwind": {"path": "$rec", "preserveNullAndEmptyArrays": True}},
            {"$project": {"_id": 0, "name": 1, "reorder_qty": "$restock.reorder_qty",
                          "also_restock": "$rec.recommended.name"}},
            {"$sort": {"reorder_qty": -1}},
        ],
    },
    "AI activity log": {
        "collection": mongo_db.AI_LOGS,
        "stages": "$group, $sort",
        "pipeline": [
            {"$group": {"_id": "$action",
                        "times_run": {"$sum": 1},
                        "avg_ms": {"$avg": "$duration_ms"},
                        "last_run": {"$max": "$timestamp"}}},
            {"$sort": {"last_run": -1}},
        ],
    },
}


def run_pipeline(name):
    item = PIPELINES[name]
    collection = mongo_db.get_db()[item["collection"]]
    return list(collection.aggregate(item["pipeline"]))
