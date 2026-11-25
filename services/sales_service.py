"""Sales and checkout (MongoDB)."""

from datetime import datetime, timedelta

import pandas as pd

import config
from database import mongo_db as m
from database.mongo_db import RuleError, col, next_id, to_dt


def calculate_totals(cart, discount_percent):
    """cart lines have unit_price and quantity. Returns subtotal, discount, tax, total."""
    subtotal = round(sum(line["unit_price"] * line["quantity"] for line in cart), 2)
    discount = round(subtotal * discount_percent / 100, 2)
    tax = round((subtotal - discount) * config.TAX_RATE, 2)
    total = round(subtotal - discount + tax, 2)
    return subtotal, discount, tax, total


def _save_sale(cart, customer_id, employee_id, payment_method, discount_percent, taken, session=None):
    """
    The three steps of a sale:
      1. Take each item out of stock. The filter {quantity: {$gte: qty}} makes the
         check and the update ONE atomic operation, so stock can never go below 0
         (this replaces the Oracle trigger + CHECK constraint).
      2. Insert the sale document with its items embedded in an array.
      3. Add loyalty points to the customer.
    Every stock change is added to `taken` so it can be undone if a later step fails.
    Returns the new sale_id.
    """
    for line in cart:
        result = col(m.PRODUCTS).update_one(
            {"product_id": line["product_id"], "quantity": {"$gte": line["quantity"]}},
            {"$inc": {"quantity": -line["quantity"]}}, session=session)
        if result.modified_count == 0:
            raise RuleError(f"Not enough stock for {line.get('name', 'a product')}.")
        taken.append(line)

    subtotal, discount, tax, total = calculate_totals(cart, discount_percent)
    sale_id = next_id(m.SALES)
    col(m.SALES).insert_one({
        "sale_id": sale_id,
        "sale_date": datetime.now(),
        "customer_id": customer_id,
        "employee_id": employee_id,
        "subtotal": subtotal, "discount": discount, "tax": tax, "total": total,
        "payment_method": payment_method,
        "items": [{"product_id": l["product_id"], "sku": l.get("sku"), "name": l.get("name"),
                   "quantity": int(l["quantity"]), "unit_price": float(l["unit_price"])}
                  for l in cart],
    }, session=session)

    if customer_id:
        col(m.CUSTOMERS).update_one(
            {"customer_id": customer_id},
            {"$inc": {"loyalty_points": int(total // config.POINTS_PER_RUPEES)}}, session=session)
    return sale_id


def checkout(cart, customer_id, employee_id, payment_method, discount_percent=0):
    """
    Save a sale all-or-nothing.
    - If MongoDB runs as a replica set, a real multi-document transaction is used
      (commit at the end, abort on any error).
    - On a normal standalone install, if any step fails the stock already taken
      is put back (a "compensating" rollback).
    Returns the new sale_id.
    """
    if m.supports_transactions():
        with m.get_db().client.start_session() as session:
            with session.start_transaction():
                return _save_sale(cart, customer_id, employee_id, payment_method,
                                  discount_percent, [], session)

    taken = []
    try:
        return _save_sale(cart, customer_id, employee_id, payment_method, discount_percent, taken)
    except Exception:
        for line in taken:   # ROLLBACK: put the stock back
            col(m.PRODUCTS).update_one({"product_id": line["product_id"]},
                                       {"$inc": {"quantity": line["quantity"]}})
        raise


# ---------- History and receipts ----------

def _sales_pipeline(match):
    """$lookup the customer and cashier names (like the LEFT JOINs in SQL)."""
    return [
        {"$match": match},
        {"$sort": {"sale_date": -1}},
        {"$lookup": {"from": m.CUSTOMERS, "localField": "customer_id",
                     "foreignField": "customer_id", "as": "c"}},
        {"$lookup": {"from": m.EMPLOYEES, "localField": "employee_id",
                     "foreignField": "employee_id", "as": "e"}},
        {"$project": {"_id": 0, "sale_id": 1, "sale_date": 1,
                      "customer": {"$ifNull": [{"$first": "$c.name"}, "Walk-in"]},
                      "cashier": {"$first": "$e.name"},
                      "subtotal": 1, "discount": 1, "tax": 1, "total": 1, "payment_method": 1}},
    ]


HISTORY_COLUMNS = ["sale_id", "sale_date", "customer", "cashier", "subtotal", "discount",
                   "tax", "total", "payment_method"]


def sales_history_df(start_date, end_date):
    """Sales between two dates (inclusive) with customer and cashier names."""
    rows = m.aggregate(m.SALES, _sales_pipeline(
        {"sale_date": {"$gte": to_dt(start_date), "$lt": to_dt(end_date) + timedelta(days=1)}}))
    return pd.DataFrame(rows, columns=HISTORY_COLUMNS)


def sale_header(sale_id):
    rows = m.aggregate(m.SALES, _sales_pipeline({"sale_id": sale_id}))
    return rows[0] if rows else None


def sale_items_df(sale_id):
    rows = m.aggregate(m.SALES, [
        {"$match": {"sale_id": sale_id}},
        {"$unwind": "$items"},
        {"$lookup": {"from": m.PRODUCTS, "localField": "items.product_id",
                     "foreignField": "product_id", "as": "p"}},
        {"$project": {"_id": 0,
                      "sku": {"$first": "$p.sku"}, "product": {"$first": "$p.name"},
                      "quantity": "$items.quantity", "unit_price": "$items.unit_price",
                      "line_total": {"$multiply": ["$items.quantity", "$items.unit_price"]}}},
        {"$sort": {"product": 1}},
    ])
    return pd.DataFrame(rows, columns=["sku", "product", "quantity", "unit_price", "line_total"])
