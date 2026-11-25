"""
One-time setup (MongoDB only):
  1. Creates the store collections with validators and indexes
  2. Fills them with demo data
  3. Runs the AI analysis and stores the results in MongoDB

Run with:  python setup_database.py
WARNING: this deletes any existing data in the supermart database.
"""

import sys

import config
from database import mongo_db
from database.demo_data import seed


def main():
    print(f"This will DELETE all data in the MongoDB database '{config.MONGO_DB}' and create fresh demo data.")
    if "--yes" not in sys.argv and input("Type yes to continue: ").strip().lower() != "yes":
        print("Cancelled.")
        return

    print(f"\n[1/3] Connecting to MongoDB at {config.MONGO_URI} ...")
    ok, message = mongo_db.check_connection()
    print(message)
    if not ok:
        return

    print("Creating collections, validators and indexes ...")
    mongo_db.ensure_schema(drop=True)
    for name in mongo_db.ALL_COLLECTIONS:
        mongo_db.get_db()[name].delete_many({})
    print("Done.")

    print("\n[2/3] Adding demo data (this takes a few seconds) ...")
    sales = seed()
    print(f"Done: {sales} sales created.")

    print("\n[3/3] Running AI analysis ...")
    from services.ai_service import run_full_analysis
    summary = run_full_analysis()
    print(f"Done: {summary}")

    print("\nAll set. Start the app with:  python -m streamlit run app.py")


if __name__ == "__main__":
    main()
