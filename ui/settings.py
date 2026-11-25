import streamlit as st

import config
from database import mongo_db
from ui.common import money


def render_settings_page():
    st.title("⚙️ Settings & System Status")

    # ---------- MongoDB ----------
    st.subheader("MongoDB (the only database)")
    ok, message = mongo_db.check_connection()
    (st.success if ok else st.error)(message)
    if mongo_db.supports_transactions():
        st.caption("Replica set detected: checkout uses real multi-document transactions.")
    else:
        st.caption("Standalone server: checkout uses a compensating rollback (stock is put back on failure).")

    if ok:
        st.write("**Store collections (documents)**")
        st.dataframe([mongo_db.collection_counts(mongo_db.STORE_COLLECTIONS)], width="stretch", hide_index=True)
        st.write("**AI collections (documents)**")
        st.dataframe([mongo_db.collection_counts()], width="stretch", hide_index=True)

        db = mongo_db.get_db()
        rows = []
        for name in mongo_db.STORE_COLLECTIONS:
            info = db.command("listCollections", filter={"name": name})["cursor"]["firstBatch"]
            schema = info[0]["options"].get("validator", {}).get("$jsonSchema", {}) if info else {}
            for idx in db[name].list_indexes():
                if idx["name"] != "_id_":
                    rows.append({"collection": name, "type": "UNIQUE INDEX" if idx.get("unique") else "INDEX",
                                 "name": idx["name"]})
            if schema:
                rows.append({"collection": name, "type": "VALIDATOR ($jsonSchema)",
                             "name": "required: " + ", ".join(schema.get("required", []))})
        with st.expander("Validators and indexes (replace CHECK constraints, UNIQUE keys and indexes)"):
            st.dataframe(rows, width="stretch", hide_index=True)

    st.divider()

    # ---------- Store rules ----------
    st.subheader("Store rules")
    st.caption("Change these in config.py, then restart the app.")
    st.table({
        "Setting": ["Store name", "Sales tax", "Loyalty points", "Expiry warning",
                    "Supplier lead time (AI restock)"],
        "Value": [config.STORE_NAME, f"{config.TAX_RATE:.0%}",
                  f"1 point per {money(config.POINTS_PER_RUPEES)}",
                  f"{config.EXPIRY_WARNING_DAYS} days", f"{config.SUPPLIER_LEAD_DAYS} days"],
    })
