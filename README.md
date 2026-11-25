# Smart Supermarket Management System — MongoDB-only version

**MongoDB** (the only database) + **Python** + **Streamlit**.

This is the MongoDB-only version of the Oracle + MongoDB project in `../SMS`.
All store data (products, stock, sales, customers, suppliers, employees) and all AI
results (forecasts, recommendations, customer segments, logs) live in one MongoDB
database called `supermart`. No Oracle install is needed.

---

## Setup (Windows)

### 1. Install the Python packages
Open a terminal in this folder (the one with `app.py`):
```
python -m pip install -r requirements.txt
```

### 2. Start MongoDB
Install **MongoDB Community Server** (it installs **MongoDB Compass** too) and make sure the
**MongoDB Server** service is running (Windows: Services).

### 3. Create the collections and demo data
```
python setup_database.py
```
Type `yes`. It creates the collections with validators and indexes, adds 30 products,
15 customers, 5 employees and about 8 weeks of sales, then runs the AI analysis.
**Running it again deletes all data and starts fresh.**

### 4. Run the app
```
python -m streamlit run app.py
```
Pick who is logged in from the sidebar. The Manager sees every page; a Cashier or Inventory
Staff member sees only their pages.

---

## How the Oracle features were replaced

| Oracle (old version) | MongoDB (this version) | Where |
|---|---|---|
| Tables | Collections: `categories`, `suppliers`, `products`, `customers`, `employees`, `sales`, `purchases` | `database/mongo_db.py` |
| Identity columns (`..._id`) | `counters` collection + atomic `$inc` (`next_id()`) | `database/mongo_db.py` |
| CHECK / NOT NULL constraints | `$jsonSchema` validators (e.g. `quantity` minimum 0, `job_role` enum) | `VALIDATORS` in `database/mongo_db.py` |
| UNIQUE constraints | Unique indexes (`sku`, category/supplier name, customer phone) | `INDEXES` in `database/mongo_db.py` |
| Indexes | `create_index` on `sale_date`, `items.product_id`, ... | `INDEXES` |
| `sale_items` table + composite key | `items` array **embedded** in each sale document | `services/sales_service.py` |
| View `v_inventory_status` | Aggregation pipeline with `$lookup` + `$switch` + `$dateDiff` | `inventory_status_pipeline()` in `services/product_service.py` |
| Trigger `trg_sale_item_stock` | Atomic conditional update `{quantity: {$gte: qty}}` + `$inc` | `_save_sale()` in `services/sales_service.py` |
| Procedure `sp_restock` | `restock()` function: insert purchase + `$inc` stock | `services/product_service.py` |
| Transaction (COMMIT / ROLLBACK) | Real transaction on a replica set; on a standalone server a compensating rollback puts the stock back | `checkout()` in `services/sales_service.py` |
| Foreign keys | Checked before deleting (`RuleError`); products with history are hidden instead | `services/people_service.py`, `remove_product()` |
| JOIN / GROUP BY / HAVING / window functions | `$lookup`, `$group`, `$match` after `$group`, `$setWindowFields` (`$rank`, `$sum`) | `services/report_service.py` (Reports page → Show pipeline) |
| NOT EXISTS subquery | `$lookup` with a sub-pipeline + `$match: {field: {$size: 0}}` | "Products never sold" report |

AI collections (`demand_forecasts`, `recommendations`, `customer_behavior`, `ai_logs`) work
exactly as before; see `services/mongo_queries.py` (AI Insights → MongoDB Query Lab).

---

## AI search algorithms (Store Navigator page)

The store floor is a grid (`STORE_MAP` in `ai/store_navigation.py`): aisles cost 1,
crowded aisles cost 5, and walls block the way. The page finds the path from the entrance
or the checkout to the shelf of the chosen product's category. It runs all five algorithms
and compares the results.

| Algorithm | Frontier | Optimal? | Where |
|---|---|---|---|
| BFS | FIFO queue (`deque`) | Fewest steps only | `search()` in `ai/store_navigation.py` |
| DFS | LIFO stack | No | `search()` |
| UCS | Priority queue on g(n) | Yes | `search()` |
| Greedy Best-First | Priority queue on h(n) | No | `search()` |
| A* | Priority queue on g(n) + h(n) | Yes (admissible heuristic) | `search()` |

h(n) is the Manhattan distance, which never overestimates because every step costs at least 1.
Run `python -m ai.store_navigation` for a console demo.

---

## Common problems

| Problem | Fix |
|---|---|
| "Cannot connect to MongoDB" | Start the MongoDB Server service, then click **Try again** |
| Pages are empty | Run `python setup_database.py` |
| "A value breaks a database rule" | A `$jsonSchema` validator rejected the value (e.g. negative stock) |
| `missing ScriptRunContext` warnings | You ran `python app.py`. Use `python -m streamlit run app.py` |
