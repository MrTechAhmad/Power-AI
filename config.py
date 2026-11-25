"""
App settings.

Change the values here to match your computer, or set them as
environment variables (for example MONGO_URI) instead.
"""

import os

# ---------- MongoDB (the only database: store data + AI data) ----------
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "supermart")

# ---------- Store rules ----------
STORE_NAME = "Smart Supermarket"
CURRENCY = "Rs"
TAX_RATE = 0.05            # 5% sales tax added at checkout
POINTS_PER_RUPEES = 100    # customer earns 1 loyalty point per Rs 100
EXPIRY_WARNING_DAYS = 30   # "expiring soon" window
SUPPLIER_LEAD_DAYS = 3     # days a supplier needs to deliver (used by AI restock)
