"""Customers, suppliers and employees (MongoDB)."""

from datetime import datetime

import pandas as pd

from database import mongo_db as m
from database.mongo_db import RuleError, col, find_all, next_id, to_dt

ROLES = m.ROLES


def _blank_to_none(value):
    value = (value or "").strip() if isinstance(value, str) else value
    return value or None


def _check_unused(collection, field, value, what):
    """Referential integrity: refuse to delete a record that other documents point to."""
    if col(collection).count_documents({field: value}, limit=1):
        raise RuleError(f"This record is used by other records ({what}), so it cannot be deleted.")


# ---------- Customers ----------

def list_customers_df():
    """Customers with visit count and total spent ($lookup + $size/$sum keeps customers with no sales)."""
    rows = m.aggregate(m.CUSTOMERS, [
        {"$lookup": {"from": m.SALES, "localField": "customer_id",
                     "foreignField": "customer_id", "as": "s"}},
        {"$project": {"_id": 0, "customer_id": 1, "name": 1, "phone": 1, "email": 1,
                      "loyalty_points": 1,
                      "visits": {"$size": "$s"},
                      "total_spent": {"$sum": "$s.total"},
                      "last_visit": {"$max": "$s.sale_date"}}},
        {"$sort": {"name": 1}},
    ])
    return pd.DataFrame(rows, columns=["customer_id", "name", "phone", "email", "loyalty_points",
                                       "visits", "total_spent", "last_visit"])


def list_customers():
    return find_all(m.CUSTOMERS, sort=[("name", 1)])


def add_customer(name, phone, email):
    col(m.CUSTOMERS).insert_one({
        "customer_id": next_id(m.CUSTOMERS), "name": name,
        "phone": _blank_to_none(phone), "email": _blank_to_none(email),
        "loyalty_points": 0, "created_at": datetime.now(),
    })


def update_customer(customer_id, name, phone, email):
    col(m.CUSTOMERS).update_one({"customer_id": customer_id}, {"$set": {
        "name": name, "phone": _blank_to_none(phone), "email": _blank_to_none(email)}})


def delete_customer(customer_id):
    _check_unused(m.SALES, "customer_id", customer_id, "past sales")
    col(m.CUSTOMERS).delete_one({"customer_id": customer_id})


def customer_history_df(customer_id):
    rows = m.aggregate(m.SALES, [
        {"$match": {"customer_id": customer_id}},
        {"$sort": {"sale_date": -1}},
        {"$lookup": {"from": m.PRODUCTS, "localField": "items.product_id",
                     "foreignField": "product_id", "as": "p"}},
        {"$project": {"_id": 0, "sale_id": 1, "sale_date": 1, "total": 1, "payment_method": 1,
                      "items": 1, "p.product_id": 1, "p.name": 1}},
    ])
    for r in rows:
        names = {p["product_id"]: p["name"] for p in r.pop("p")}
        r["items"] = ", ".join(sorted(f"{names.get(i['product_id'], '?')} x{i['quantity']}"
                                      for i in r["items"]))
    return pd.DataFrame(rows, columns=["sale_id", "sale_date", "total", "payment_method", "items"])


# ---------- Suppliers ----------

def list_suppliers_df():
    """Suppliers with how many products they supply and how much we bought from them."""
    rows = m.aggregate(m.SUPPLIERS, [
        {"$lookup": {"from": m.PRODUCTS, "localField": "supplier_id", "foreignField": "supplier_id",
                     "pipeline": [{"$match": {"is_active": True}}], "as": "p"}},
        {"$lookup": {"from": m.PURCHASES, "localField": "supplier_id",
                     "foreignField": "supplier_id", "as": "pu"}},
        {"$project": {"_id": 0, "supplier_id": 1, "name": 1, "phone": 1, "email": 1, "address": 1,
                      "products": {"$size": "$p"},
                      "total_purchased": {"$sum": {"$map": {
                          "input": "$pu", "as": "x",
                          "in": {"$multiply": ["$$x.quantity", "$$x.unit_cost"]}}}}}},
        {"$sort": {"name": 1}},
    ])
    return pd.DataFrame(rows, columns=["supplier_id", "name", "phone", "email", "address",
                                       "products", "total_purchased"])


def list_suppliers():
    return find_all(m.SUPPLIERS, sort=[("name", 1)])


def add_supplier(name, phone, email, address):
    col(m.SUPPLIERS).insert_one({
        "supplier_id": next_id(m.SUPPLIERS), "name": name, "phone": _blank_to_none(phone),
        "email": _blank_to_none(email), "address": _blank_to_none(address)})


def update_supplier(supplier_id, name, phone, email, address):
    col(m.SUPPLIERS).update_one({"supplier_id": supplier_id}, {"$set": {
        "name": name, "phone": _blank_to_none(phone), "email": _blank_to_none(email),
        "address": _blank_to_none(address)}})


def delete_supplier(supplier_id):
    _check_unused(m.PRODUCTS, "supplier_id", supplier_id, "products")
    _check_unused(m.PURCHASES, "supplier_id", supplier_id, "purchases")
    col(m.SUPPLIERS).delete_one({"supplier_id": supplier_id})


# ---------- Employees ----------

def list_employees():
    return find_all(m.EMPLOYEES, sort=[("job_role", 1), ("name", 1)])


def list_employees_df():
    """Employees with the number of sales they made and the revenue."""
    rows = m.aggregate(m.EMPLOYEES, [
        {"$lookup": {"from": m.SALES, "localField": "employee_id",
                     "foreignField": "employee_id", "as": "s"}},
        {"$project": {"_id": 0, "employee_id": 1, "name": 1, "job_role": 1, "phone": 1,
                      "salary": 1, "hire_date": 1,
                      "sales_made": {"$size": "$s"}, "revenue": {"$sum": "$s.total"}}},
        {"$sort": {"job_role": 1, "name": 1}},
    ])
    return pd.DataFrame(rows, columns=["employee_id", "name", "job_role", "phone", "salary",
                                       "hire_date", "sales_made", "revenue"])


def add_employee(name, job_role, phone, salary, hire_date):
    col(m.EMPLOYEES).insert_one({
        "employee_id": next_id(m.EMPLOYEES), "name": name, "job_role": job_role,
        "phone": _blank_to_none(phone), "salary": float(salary) if salary is not None else None,
        "hire_date": to_dt(hire_date)})


def update_employee(employee_id, name, job_role, phone, salary):
    col(m.EMPLOYEES).update_one({"employee_id": employee_id}, {"$set": {
        "name": name, "job_role": job_role, "phone": _blank_to_none(phone),
        "salary": float(salary) if salary is not None else None}})


def delete_employee(employee_id):
    _check_unused(m.SALES, "employee_id", employee_id, "past sales")
    col(m.EMPLOYEES).delete_one({"employee_id": employee_id})
