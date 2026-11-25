"""
Demo data: 30 products, 15 customers, 5 employees and about 8 weeks of
realistic sales (more on weekends, items bought together in "baskets"),
so reports and AI have something to learn from.
"""

import random
from datetime import date, datetime, timedelta

import config

CATEGORIES = ["Dairy", "Bakery", "Grains", "Grocery", "Beverages", "Snacks",
              "Fruits & Vegetables", "Household", "Personal Care", "Meat"]

SUPPLIERS = [
    ("Fresh Foods", "0300-1112233", "orders@freshfoods.pk", "Rawalpindi"),
    ("Daily Bakers", "0301-2223344", "sales@dailybakers.pk", "Wah Cantt"),
    ("ABC Traders", "0302-3334455", "abc@traders.pk", "Islamabad"),
    ("Oil Suppliers", "0303-4445566", "info@oilsuppliers.pk", "Lahore"),
    ("Sweet Foods", "0304-5556677", "hello@sweetfoods.pk", "Rawalpindi"),
    ("Green Farms", "0305-6667788", "farm@greenfarms.pk", "Attock"),
    ("Clean Home Distributors", "0306-7778899", "cleanhome@dist.pk", "Islamabad"),
    ("Al-Noor Meats", "0307-8889900", "alnoor@meats.pk", "Taxila"),
]

# sku, name, category, supplier, price, final stock, min stock, expiry (days from today, None = no expiry), popularity
PRODUCTS = [
    ("P001", "Milk 1L", "Dairy", "Fresh Foods", 280, 8, 20, 5, 10),
    ("P002", "Yogurt 500g", "Dairy", "Fresh Foods", 160, 30, 15, 10, 6),
    ("P003", "Butter 200g", "Dairy", "Fresh Foods", 450, 25, 10, 40, 4),
    ("P004", "Cheese Slices", "Dairy", "Fresh Foods", 650, 12, 8, 25, 2),
    ("P005", "Eggs (dozen)", "Dairy", "Fresh Foods", 420, 40, 20, 14, 7),
    ("P006", "Bread", "Bakery", "Daily Bakers", 180, 6, 15, 3, 9),
    ("P007", "Rusk", "Bakery", "Daily Bakers", 250, 50, 15, 60, 3),
    ("P008", "Basmati Rice 5kg", "Grains", "ABC Traders", 1850, 60, 20, 365, 3),
    ("P009", "Wheat Flour 10kg", "Grains", "ABC Traders", 1500, 35, 15, 120, 4),
    ("P010", "Daal Masoor 1kg", "Grains", "ABC Traders", 380, 45, 15, 240, 4),
    ("P011", "Cooking Oil 1L", "Grocery", "Oil Suppliers", 550, 15, 25, 180, 6),
    ("P012", "Sugar 1kg", "Grocery", "ABC Traders", 160, 80, 30, 365, 6),
    ("P013", "Salt 800g", "Grocery", "ABC Traders", 60, 100, 20, 720, 3),
    ("P014", "Black Tea 450g", "Beverages", "ABC Traders", 1100, 22, 10, 300, 5),
    ("P015", "Mineral Water 1.5L", "Beverages", "Sweet Foods", 100, 120, 40, 365, 7),
    ("P016", "Cola 1.5L", "Beverages", "Sweet Foods", 220, 70, 30, 150, 6),
    ("P017", "Mango Juice 1L", "Beverages", "Sweet Foods", 350, 0, 15, 90, 3),
    ("P018", "Biscuits", "Snacks", "Sweet Foods", 100, 0, 15, 120, 5),
    ("P019", "Potato Chips", "Snacks", "Sweet Foods", 120, 55, 20, 100, 5),
    ("P020", "Chocolate Bar", "Snacks", "Sweet Foods", 200, 40, 15, -2, 4),
    ("P021", "Bananas (dozen)", "Fruits & Vegetables", "Green Farms", 180, 18, 15, 4, 5),
    ("P022", "Apples 1kg", "Fruits & Vegetables", "Green Farms", 350, 25, 10, 12, 4),
    ("P023", "Tomatoes 1kg", "Fruits & Vegetables", "Green Farms", 200, 30, 15, 6, 6),
    ("P024", "Onions 1kg", "Fruits & Vegetables", "Green Farms", 150, 45, 20, 30, 6),
    ("P025", "Dishwash Liquid", "Household", "Clean Home Distributors", 320, 28, 10, None, 2),
    ("P026", "Laundry Detergent 1kg", "Household", "Clean Home Distributors", 650, 20, 10, None, 2),
    ("P027", "Shampoo", "Personal Care", "Clean Home Distributors", 550, 18, 8, None, 2),
    ("P028", "Toothpaste", "Personal Care", "Clean Home Distributors", 280, 9, 10, None, 2),
    ("P029", "Chicken 1kg", "Meat", "Al-Noor Meats", 750, 14, 10, 2, 5),
    ("P030", "Beef 1kg", "Meat", "Al-Noor Meats", 1300, 10, 6, 2, 2),
]

# Groups of products people tend to buy together (this is what the recommender learns)
BUNDLES = [
    ["P006", "P003", "P005", "P001"],                  # breakfast
    ["P014", "P012", "P001", "P007", "P018"],          # tea time
    ["P009", "P011", "P010", "P024", "P023", "P013"],  # home cooking
    ["P008", "P029", "P024", "P023", "P011"],          # rice and chicken
    ["P019", "P016", "P020", "P017"],                  # snacks
    ["P021", "P022", "P002"],                          # fruit
    ["P025", "P026"],                                  # cleaning
    ["P027", "P028"],                                  # personal care
    ["P030", "P024", "P023"],                          # beef curry
]

EMPLOYEES = [
    ("Ayesha Khan", "Manager", "0311-1000001", 120000, 900),
    ("Bilal Ahmed", "Cashier", "0311-1000002", 55000, 600),
    ("Hina Raza", "Cashier", "0311-1000003", 52000, 400),
    ("Sana Malik", "Cashier", "0311-1000004", 50000, 150),
    ("Usman Tariq", "Inventory Staff", "0311-1000005", 60000, 500),
]

# name, phone, email, shopping style
CUSTOMERS = [
    ("Ali Hassan", "0321-5550001", "ali.hassan@mail.com", "frequent"),
    ("Fatima Noor", "0321-5550002", "fatima.noor@mail.com", "frequent"),
    ("Ahmed Raza", "0321-5550003", None, "frequent"),
    ("Zainab Iqbal", "0321-5550004", "zainab@mail.com", "regular"),
    ("Hamza Sheikh", "0321-5550005", None, "regular"),
    ("Maryam Aslam", "0321-5550006", "maryam.a@mail.com", "regular"),
    ("Omar Farooq", "0321-5550007", None, "regular"),
    ("Ayesha Siddiqui", "0321-5550008", "ayesha.s@mail.com", "lapsed"),
    ("Imran Qureshi", "0321-5550009", None, "lapsed"),
    ("Nida Akhtar", "0321-5550010", "nida@mail.com", "lapsed"),
    ("Saad Mehmood", "0321-5550011", None, "new"),
    ("Hira Javed", "0321-5550012", "hira.j@mail.com", "new"),
    ("Kamran Butt", "0321-5550013", None, "occasional"),
    ("Rabia Anwar", "0321-5550014", "rabia@mail.com", "occasional"),
    ("Tariq Mahmood", "0321-5550015", None, "occasional"),
]

STYLE_WEIGHT = {"frequent": 10, "regular": 5, "lapsed": 6, "new": 6, "occasional": 1}
HISTORY_DAYS = 60


def _customer_allowed(style, days_ago):
    if style == "lapsed":
        return days_ago > 30     # stopped coming a month ago
    if style == "new":
        return days_ago <= 7     # only started this week
    return True


def _make_basket(rng, popularity, trend_boost):
    items = {}
    for bundle in rng.sample(BUNDLES, k=rng.choice([1, 1, 2])):
        for sku in bundle:
            if rng.random() < 0.55:
                items[sku] = rng.choice([1, 1, 1, 2, 2, 3])
    # a couple of random extra items, weighted by popularity
    skus = list(popularity)
    weights = [popularity[s] * trend_boost.get(s, 1) for s in skus]
    for sku in rng.choices(skus, weights=weights, k=rng.choice([0, 1, 1, 2])):
        items[sku] = items.get(sku, 0) + 1
    if not items:
        items[rng.choices(skus, weights=weights)[0]] = 1
    return items


def seed():
    """Fill the store collections (they must be empty: setup_database.py drops them first)."""
    from database import mongo_db as m

    rng = random.Random(42)
    today = date.today()
    now = datetime.now()
    midnight = datetime(today.year, today.month, today.day)
    db = m.get_db()

    def ids(collection, count):
        """Reserve `count` ids at once from the counters collection."""
        doc = db[m.COUNTERS].find_one_and_update({"_id": collection}, {"$inc": {"seq": count}},
                                                 upsert=True, return_document=True)
        return list(range(doc["seq"] - count + 1, doc["seq"] + 1))

    # ---------- Lookup collections ----------
    cat_id = dict(zip(CATEGORIES, ids(m.CATEGORIES, len(CATEGORIES))))
    db[m.CATEGORIES].insert_many([{"category_id": i, "name": n} for n, i in cat_id.items()])

    sup_id = dict(zip([s[0] for s in SUPPLIERS], ids(m.SUPPLIERS, len(SUPPLIERS))))
    db[m.SUPPLIERS].insert_many([{"supplier_id": sup_id[n], "name": n, "phone": ph, "email": em,
                                  "address": ad} for n, ph, em, ad in SUPPLIERS])

    # ---------- Products (final stock levels; sales below don't touch stock) ----------
    prod_id = dict(zip([p[0] for p in PRODUCTS], ids(m.PRODUCTS, len(PRODUCTS))))
    db[m.PRODUCTS].insert_many([{
        "product_id": prod_id[sku], "sku": sku, "name": name,
        "category_id": cat_id[cat], "supplier_id": sup_id[sup],
        "unit_price": float(price), "quantity": final, "min_stock": min_stock,
        "expiry_date": midnight + timedelta(days=exp) if exp is not None else None,
        "is_active": True, "created_at": midnight - timedelta(days=HISTORY_DAYS + 30),
    } for sku, name, cat, sup, price, final, min_stock, exp, pop in PRODUCTS])
    price_of = {p[0]: p[4] for p in PRODUCTS}
    name_of = {p[0]: p[1] for p in PRODUCTS}
    popularity = {p[0]: p[8] for p in PRODUCTS}

    # ---------- People ----------
    emp_ids = ids(m.EMPLOYEES, len(EMPLOYEES))
    db[m.EMPLOYEES].insert_many([{
        "employee_id": i, "name": n, "job_role": r, "phone": ph, "salary": float(sal),
        "hire_date": midnight - timedelta(days=d)} for i, (n, r, ph, sal, d) in zip(emp_ids, EMPLOYEES)])
    cashiers = [i for i, e in zip(emp_ids, EMPLOYEES) if e[1] == "Cashier"]

    cust_ids = ids(m.CUSTOMERS, len(CUSTOMERS))
    db[m.CUSTOMERS].insert_many([{
        "customer_id": i, "name": n, "phone": ph, "email": em, "loyalty_points": 0,
        "created_at": midnight - timedelta(days=7 if style == "new" else 90)}
        for i, (n, ph, em, style) in zip(cust_ids, CUSTOMERS)])
    customers = [(i, c[3]) for i, c in zip(cust_ids, CUSTOMERS)]

    # ---------- Deliveries from suppliers ----------
    purchases = []
    for sku, name, cat, sup, price, *_ in PRODUCTS:
        for weeks_ago in (8, 5, 2):
            purchases.append({"purchase_date": now - timedelta(weeks=weeks_ago, hours=rng.randint(0, 48)),
                              "supplier_id": sup_id[sup], "product_id": prod_id[sku],
                              "quantity": rng.randint(40, 150), "unit_cost": round(price * 0.8, 2)})
    for doc, i in zip(purchases, ids(m.PURCHASES, len(purchases))):
        doc["purchase_id"] = i
    db[m.PURCHASES].insert_many(purchases)

    # ---------- Sales history (items embedded in each sale) ----------
    sales = []
    for days_ago in range(HISTORY_DAYS, -1, -1):
        day = today - timedelta(days=days_ago)
        weekend = day.weekday() >= 4          # Fri, Sat, Sun are busier
        n_sales = rng.randint(14, 22) + (8 if weekend else 0)
        # Cola and water slowly become more popular (gives the forecast a trend)
        growth = 1 + (HISTORY_DAYS - days_ago) / HISTORY_DAYS
        trend_boost = {"P016": growth, "P015": growth}

        times = sorted(datetime(day.year, day.month, day.day, rng.randint(9, 21), rng.randint(0, 59))
                       for _ in range(n_sales))
        if days_ago == 0:
            times = [t for t in times if t <= now]

        for when in times:
            items = _make_basket(rng, popularity, trend_boost)

            customer = None
            if rng.random() < 0.45:
                choices = [(cid, STYLE_WEIGHT[s]) for cid, s in customers if _customer_allowed(s, days_ago)]
                customer = rng.choices([c for c, _ in choices], weights=[w for _, w in choices])[0]

            subtotal = sum(price_of[s] * q for s, q in items.items())
            discount = round(subtotal * 0.05, 2) if customer and rng.random() < 0.2 else 0
            tax = round((subtotal - discount) * config.TAX_RATE, 2)
            total = round(subtotal - discount + tax, 2)
            payment = rng.choices(["Cash", "Card", "Mobile Wallet"], weights=[55, 25, 20])[0]

            sales.append({
                "sale_date": when, "customer_id": customer, "employee_id": rng.choice(cashiers),
                "subtotal": float(subtotal), "discount": float(discount), "tax": float(tax),
                "total": float(total), "payment_method": payment,
                "items": [{"product_id": prod_id[s], "sku": s, "name": name_of[s], "quantity": q,
                           "unit_price": float(price_of[s])} for s, q in items.items()],
            })

    for doc, i in zip(sales, ids(m.SALES, len(sales))):
        doc["sale_id"] = i
    db[m.SALES].insert_many(sales)

    # ---------- Loyalty points from each customer's total spending ----------
    for row in db[m.SALES].aggregate([
            {"$match": {"customer_id": {"$ne": None}}},
            {"$group": {"_id": "$customer_id", "spent": {"$sum": "$total"}}}]):
        db[m.CUSTOMERS].update_one({"customer_id": row["_id"]},
                                   {"$set": {"loyalty_points": int(row["spent"] // config.POINTS_PER_RUPEES)}})
    return len(sales)
