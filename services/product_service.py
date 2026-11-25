"""Products, categories and stock (MongoDB)."""

from datetime import datetime, timedelta

import pandas as pd

import config
from database import mongo_db as m
from database.mongo_db import col, day_start, find_all, next_id, to_dt


# ---------- Categories ----------

def list_categories():
    return find_all(m.CATEGORIES, sort=[("name", 1)])


def add_category(name):
    col(m.CATEGORIES).insert_one({"category_id": next_id(m.CATEGORIES), "name": name})


# ---------- Inventory status (replaces the Oracle view v_inventory_status) ----------

def inventory_status_pipeline():
    """
    Aggregation pipeline that works like the old SQL view:
    $lookup joins category and supplier names, $switch computes the statuses.
    """
    today = day_start()
    soon = today + timedelta(days=config.EXPIRY_WARNING_DAYS)
    return [
        {"$match": {"is_active": True}},
        {"$lookup": {"from": m.CATEGORIES, "localField": "category_id",
                     "foreignField": "category_id", "as": "cat"}},
        {"$lookup": {"from": m.SUPPLIERS, "localField": "supplier_id",
                     "foreignField": "supplier_id", "as": "sup"}},
        {"$project": {
            "_id": 0, "product_id": 1, "sku": 1, "name": 1,
            "category": {"$first": "$cat.name"},
            "supplier": {"$first": "$sup.name"},
            "unit_price": 1, "quantity": 1, "min_stock": 1,
            "expiry_date": {"$ifNull": ["$expiry_date", None]},
            "days_to_expiry": {"$cond": [
                {"$ifNull": ["$expiry_date", False]},
                {"$dateDiff": {"startDate": today, "endDate": "$expiry_date", "unit": "day"}},
                None]},
            "stock_status": {"$switch": {"branches": [
                {"case": {"$eq": ["$quantity", 0]}, "then": "Out of Stock"},
                {"case": {"$lte": ["$quantity", "$min_stock"]}, "then": "Low Stock"},
            ], "default": "In Stock"}},
            "expiry_status": {"$switch": {"branches": [
                {"case": {"$eq": [{"$ifNull": ["$expiry_date", None]}, None]}, "then": "No Expiry"},
                {"case": {"$lt": ["$expiry_date", today]}, "then": "Expired"},
                {"case": {"$lte": ["$expiry_date", soon]}, "then": "Expiring Soon"},
            ], "default": "Valid"}},
        }},
        {"$sort": {"sku": 1}},
    ]


def inventory_status():
    return m.aggregate(m.PRODUCTS, inventory_status_pipeline())


COLUMNS = ["product_id", "sku", "name", "category", "supplier", "unit_price", "quantity",
           "min_stock", "expiry_date", "days_to_expiry", "stock_status", "expiry_status"]


# ---------- Products ----------

def list_products_df():
    """All active products with stock/expiry status."""
    return pd.DataFrame(inventory_status(), columns=COLUMNS)


def list_active_products():
    return find_all(m.PRODUCTS, {"is_active": True}, sort=[("name", 1)])


def list_sellable_products():
    """In stock and not expired."""
    return find_all(m.PRODUCTS, {
        "is_active": True,
        "quantity": {"$gt": 0},
        "$or": [{"expiry_date": None}, {"expiry_date": {"$gte": day_start()}}],
    }, sort=[("name", 1)], projection={"product_id": 1, "sku": 1, "name": 1,
                                       "unit_price": 1, "quantity": 1})


def add_product(data):
    doc = {
        "product_id": next_id(m.PRODUCTS),
        "sku": data["sku"], "name": data["name"],
        "category_id": data["category_id"], "supplier_id": data.get("supplier_id"),
        "unit_price": float(data["unit_price"]), "quantity": int(data["quantity"]),
        "min_stock": int(data["min_stock"]), "expiry_date": to_dt(data.get("expiry_date")),
        "is_active": True, "created_at": datetime.now(),
    }
    col(m.PRODUCTS).insert_one(doc)


def update_product(product_id, data):
    col(m.PRODUCTS).update_one({"product_id": product_id}, {"$set": {
        "name": data["name"], "category_id": data["category_id"],
        "supplier_id": data.get("supplier_id"), "unit_price": float(data["unit_price"]),
        "min_stock": int(data["min_stock"]), "expiry_date": to_dt(data.get("expiry_date")),
    }})


def remove_product(product_id):
    """
    Delete the product if it was never sold or bought.
    If it has history, we keep it (like a foreign key would) and hide it instead.
    Returns "deleted" or "deactivated".
    """
    used = (col(m.SALES).count_documents({"items.product_id": product_id}, limit=1)
            + col(m.PURCHASES).count_documents({"product_id": product_id}, limit=1))
    if used:
        col(m.PRODUCTS).update_one({"product_id": product_id}, {"$set": {"is_active": False}})
        return "deactivated"
    col(m.PRODUCTS).delete_one({"product_id": product_id})
    return "deleted"


# ---------- Stock ----------

def restock(product_id, supplier_id, quantity, unit_cost, expiry_date):
    """Record the purchase and add the stock (replaces the stored procedure sp_restock)."""
    col(m.PURCHASES).insert_one({
        "purchase_id": next_id(m.PURCHASES), "purchase_date": datetime.now(),
        "supplier_id": supplier_id, "product_id": product_id,
        "quantity": int(quantity), "unit_cost": float(unit_cost),
    })
    update = {"$inc": {"quantity": int(quantity)}}
    if expiry_date:
        update["$set"] = {"expiry_date": to_dt(expiry_date)}
    col(m.PRODUCTS).update_one({"product_id": product_id}, update)


def adjust_stock(product_id, new_quantity):
    """Stock count correction (damaged items, counting mistakes)."""
    col(m.PRODUCTS).update_one({"product_id": product_id}, {"$set": {"quantity": int(new_quantity)}})


def purchase_history_df(limit=50):
    rows = m.aggregate(m.PURCHASES, [
        {"$sort": {"purchase_date": -1, "purchase_id": -1}},
        {"$limit": limit},
        {"$lookup": {"from": m.SUPPLIERS, "localField": "supplier_id",
                     "foreignField": "supplier_id", "as": "s"}},
        {"$lookup": {"from": m.PRODUCTS, "localField": "product_id",
                     "foreignField": "product_id", "as": "p"}},
        {"$project": {"_id": 0, "purchase_id": 1, "purchase_date": 1,
                      "supplier": {"$first": "$s.name"}, "product": {"$first": "$p.name"},
                      "quantity": 1, "unit_cost": 1,
                      "total_cost": {"$multiply": ["$quantity", "$unit_cost"]}}},
    ])
    return pd.DataFrame(rows, columns=["purchase_id", "purchase_date", "supplier", "product",
                                       "quantity", "unit_cost", "total_cost"])
