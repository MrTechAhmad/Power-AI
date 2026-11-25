"""
MongoDB connection helpers - the ONLY database of this version.

All store data (products, sales, customers ...) and all AI results
(forecasts, recommendations, segments, logs) live in one MongoDB database.

What replaces the Oracle features:
  - identity columns      -> a "counters" collection (next_id)
  - CHECK / NOT NULL      -> $jsonSchema validators on each collection
  - UNIQUE                -> unique indexes
  - indexes               -> create_index
  - sale_items table      -> an "items" array embedded in each sale document
  - foreign keys          -> checked in Python before deleting (see services)
"""

from datetime import date, datetime

from pymongo import ASCENDING, DESCENDING, MongoClient, ReturnDocument
from pymongo.errors import CollectionInvalid

import config

_client = None

# ---------- Store collections (were Oracle tables) ----------
CATEGORIES = "categories"
SUPPLIERS = "suppliers"
PRODUCTS = "products"
CUSTOMERS = "customers"
EMPLOYEES = "employees"
SALES = "sales"
PURCHASES = "purchases"
COUNTERS = "counters"
STORE_COLLECTIONS = [CATEGORIES, SUPPLIERS, PRODUCTS, CUSTOMERS, EMPLOYEES, SALES, PURCHASES]

# ---------- AI collections ----------
FORECASTS = "demand_forecasts"
RECOMMENDATIONS = "recommendations"
CUSTOMER_SEGMENTS = "customer_behavior"
AI_LOGS = "ai_logs"
ALL_COLLECTIONS = [FORECASTS, RECOMMENDATIONS, CUSTOMER_SEGMENTS, AI_LOGS]

ROLES = ["Manager", "Cashier", "Inventory Staff"]
PAYMENT_METHODS = ["Cash", "Card", "Mobile Wallet"]


class RuleError(Exception):
    """A business rule was broken (the message is shown to the user as-is)."""


# ---------- Connection ----------

def get_db():
    """Return the MongoDB database object (the client is created once)."""
    global _client
    if _client is None:
        _client = MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=3000)
    return _client[config.MONGO_DB]


def col(name):
    return get_db()[name]


def is_available():
    """True if MongoDB answers a ping."""
    try:
        get_db().command("ping")
        return True
    except Exception:
        return False


def check_connection():
    """Return (ok, message)."""
    try:
        info = get_db().client.server_info()
        return True, f"Connected to MongoDB {info['version']} at {config.MONGO_URI}, database '{config.MONGO_DB}'"
    except Exception as error:
        return False, friendly_error(error)


def supports_transactions():
    """Multi-document transactions need a replica set; a plain local install is standalone."""
    try:
        return bool(get_db().client.admin.command("hello").get("setName"))
    except Exception:
        return False


# ---------- Small helpers ----------

def next_id(name):
    """Auto-increment number, like an Oracle identity column (atomic $inc)."""
    doc = col(COUNTERS).find_one_and_update(
        {"_id": name}, {"$inc": {"seq": 1}}, upsert=True, return_document=ReturnDocument.AFTER)
    return doc["seq"]


def to_dt(value):
    """MongoDB stores datetimes, not dates: turn a date into midnight of that day."""
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    return value


def day_start(value=None):
    value = value or date.today()
    return datetime(value.year, value.month, value.day)


def find_all(name, query=None, sort=None, projection=None):
    """find() returning plain dicts without Mongo's _id."""
    proj = {"_id": 0}
    if projection:
        proj.update(projection)
    cursor = col(name).find(query or {}, proj)
    if sort:
        cursor = cursor.sort(sort)
    return list(cursor)


def find_one(name, query):
    return col(name).find_one(query, {"_id": 0})


def aggregate(name, pipeline):
    return list(col(name).aggregate(pipeline))


def log_ai_action(action, details=None, duration_ms=0):
    """Save one entry in the ai_logs collection. Never crashes the app."""
    try:
        col(AI_LOGS).insert_one({
            "timestamp": datetime.now(),
            "action": action,
            "details": details or {},
            "duration_ms": round(duration_ms, 1),
        })
    except Exception:
        pass


def collection_counts(names=None):
    db = get_db()
    return {name: db[name].count_documents({}) for name in (names or ALL_COLLECTIONS)}


def friendly_error(error):
    """Turn a MongoDB error into a short message a user can understand."""
    if isinstance(error, RuleError):
        return str(error)
    text = str(error)
    if "E11000" in text or "duplicate key" in text:
        return "This value already exists (it must be unique)."
    if getattr(error, "code", None) == 121 or "Document failed validation" in text:
        return "A value breaks a database rule (schema validation)."
    if type(error).__name__ in ("ServerSelectionTimeoutError", "ConnectionFailure", "AutoReconnect"):
        return (f"Cannot reach MongoDB at {config.MONGO_URI}. "
                "Start the MongoDB Server service (Windows: Services).")
    return text


# ---------- Schema: validators (CHECK constraints) and indexes ----------

NUM = ["int", "long", "double", "decimal"]
OPT_STR = ["string", "null"]
OPT_DATE = ["date", "null"]

VALIDATORS = {
    CATEGORIES: {
        "required": ["category_id", "name"],
        "properties": {"category_id": {"bsonType": NUM}, "name": {"bsonType": "string", "minLength": 1}},
    },
    SUPPLIERS: {
        "required": ["supplier_id", "name"],
        "properties": {
            "supplier_id": {"bsonType": NUM},
            "name": {"bsonType": "string", "minLength": 1},
            "phone": {"bsonType": OPT_STR}, "email": {"bsonType": OPT_STR},
            "address": {"bsonType": OPT_STR},
        },
    },
    PRODUCTS: {
        "required": ["product_id", "sku", "name", "category_id", "unit_price", "quantity",
                     "min_stock", "is_active", "created_at"],
        "properties": {
            "product_id": {"bsonType": NUM},
            "sku": {"bsonType": "string", "minLength": 1},
            "name": {"bsonType": "string", "minLength": 1},
            "category_id": {"bsonType": NUM},
            "supplier_id": {"bsonType": NUM + ["null"]},
            "unit_price": {"bsonType": NUM, "minimum": 0},
            "quantity": {"bsonType": NUM, "minimum": 0},     # stock can never go negative
            "min_stock": {"bsonType": NUM, "minimum": 0},
            "expiry_date": {"bsonType": OPT_DATE},
            "is_active": {"bsonType": "bool"},
            "created_at": {"bsonType": "date"},
        },
    },
    CUSTOMERS: {
        "required": ["customer_id", "name", "loyalty_points", "created_at"],
        "properties": {
            "customer_id": {"bsonType": NUM},
            "name": {"bsonType": "string", "minLength": 1},
            "phone": {"bsonType": OPT_STR}, "email": {"bsonType": OPT_STR},
            "loyalty_points": {"bsonType": NUM, "minimum": 0},
            "created_at": {"bsonType": "date"},
        },
    },
    EMPLOYEES: {
        "required": ["employee_id", "name", "job_role", "hire_date"],
        "properties": {
            "employee_id": {"bsonType": NUM},
            "name": {"bsonType": "string", "minLength": 1},
            "job_role": {"enum": ROLES},
            "phone": {"bsonType": OPT_STR},
            "salary": {"bsonType": NUM + ["null"], "minimum": 0},
            "hire_date": {"bsonType": "date"},
        },
    },
    SALES: {
        "required": ["sale_id", "sale_date", "subtotal", "discount", "tax", "total",
                     "payment_method", "items"],
        "properties": {
            "sale_id": {"bsonType": NUM},
            "sale_date": {"bsonType": "date"},
            "customer_id": {"bsonType": NUM + ["null"]},
            "employee_id": {"bsonType": NUM + ["null"]},
            "subtotal": {"bsonType": NUM, "minimum": 0},
            "discount": {"bsonType": NUM, "minimum": 0},
            "tax": {"bsonType": NUM, "minimum": 0},
            "total": {"bsonType": NUM, "minimum": 0},
            "payment_method": {"enum": PAYMENT_METHODS},
            # Embedded line items (replaces the sale_items table)
            "items": {
                "bsonType": "array", "minItems": 1,
                "items": {
                    "bsonType": "object",
                    "required": ["product_id", "quantity", "unit_price"],
                    "properties": {
                        "product_id": {"bsonType": NUM},
                        "quantity": {"bsonType": NUM, "minimum": 1},
                        "unit_price": {"bsonType": NUM, "minimum": 0},
                    },
                },
            },
        },
    },
    PURCHASES: {
        "required": ["purchase_id", "purchase_date", "supplier_id", "product_id", "quantity", "unit_cost"],
        "properties": {
            "purchase_id": {"bsonType": NUM},
            "purchase_date": {"bsonType": "date"},
            "supplier_id": {"bsonType": NUM},
            "product_id": {"bsonType": NUM},
            "quantity": {"bsonType": NUM, "minimum": 1},
            "unit_cost": {"bsonType": NUM, "minimum": 0},
        },
    },
}

INDEXES = {
    CATEGORIES: [([("category_id", ASCENDING)], True), ([("name", ASCENDING)], True)],
    SUPPLIERS: [([("supplier_id", ASCENDING)], True), ([("name", ASCENDING)], True)],
    PRODUCTS: [([("product_id", ASCENDING)], True), ([("sku", ASCENDING)], True),
               ([("category_id", ASCENDING)], False), ([("supplier_id", ASCENDING)], False)],
    CUSTOMERS: [([("customer_id", ASCENDING)], True)],
    EMPLOYEES: [([("employee_id", ASCENDING)], True)],
    SALES: [([("sale_id", ASCENDING)], True), ([("sale_date", DESCENDING)], False),
            ([("customer_id", ASCENDING)], False), ([("items.product_id", ASCENDING)], False)],
    PURCHASES: [([("purchase_id", ASCENDING)], True), ([("purchase_date", DESCENDING)], False)],
}


def ensure_schema(drop=False):
    """Create the store collections with validators and indexes. drop=True starts fresh."""
    db = get_db()
    if drop:
        for name in STORE_COLLECTIONS + [COUNTERS]:
            db.drop_collection(name)
    for name, schema in VALIDATORS.items():
        validator = {"$jsonSchema": {"bsonType": "object", **schema}}
        try:
            db.create_collection(name, validator=validator)
        except CollectionInvalid:
            db.command("collMod", name, validator=validator)
        for keys, unique in INDEXES.get(name, []):
            db[name].create_index(keys, unique=unique)
    # Customers' phone must be unique, but many customers may have no phone
    db[CUSTOMERS].create_index("phone", unique=True,
                               partialFilterExpression={"phone": {"$type": "string"}})
