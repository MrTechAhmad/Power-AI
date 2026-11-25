import pandas as pd
import streamlit as st

from ai import store_navigation as nav
from services.product_service import list_active_products, list_categories

STARTS = {"Entrance": "E", "Checkout": "K"}

COLORS = {
    "wall": "background-color:#374151;color:#374151",
    "shelf": "background-color:#e7d7b8;color:#6b4f1d",
    "target": "background-color:#f59e0b;color:#000;font-weight:bold",
    "crowded": "background-color:#fecaca;color:#991b1b",
    "explored": "background-color:#bfdbfe;color:#1e3a8a",
    "path": "background-color:#22c55e;color:#fff;font-weight:bold",
    "end": "background-color:#7c3aed;color:#fff;font-weight:bold",
    "aisle": "",
}

ABOUT = {
    "BFS": "FIFO queue. Fewest **steps**, but ignores that crowded aisles cost more.",
    "DFS": "LIFO stack. Dives deep first: finds *a* path, usually a long one. Not optimal.",
    "UCS": "Priority queue on g(n), the cost so far. Always finds the **cheapest** path.",
    "Greedy Best-First": "Priority queue on h(n) only. Very few nodes expanded, but not optimal.",
    "A*": "Priority queue on g(n) + h(n). Cheapest path like UCS, with far fewer nodes expanded.",
}


def _grid_table(result, start, goal, target_letter, show_explored):
    """Colour every map cell according to the search result."""
    path = set(result["path"])
    explored = set(result["expanded_order"]) if show_explored else set()
    labels, styles = [], []
    for r, row in enumerate(nav.STORE_MAP):
        lab, sty = [], []
        for c, ch in enumerate(row):
            cell = (r, c)
            if cell in (start, goal):
                lab.append("START" if cell == start else "GOAL")
                sty.append(COLORS["end"])
            elif cell in path:
                lab.append("●")
                sty.append(COLORS["path"])
            elif ch == "#":
                lab.append("#")
                sty.append(COLORS["wall"])
            elif ch in nav.SHELF_CATEGORY:
                lab.append(ch)
                sty.append(COLORS["target"] if ch == target_letter else COLORS["shelf"])
            elif cell in explored:
                lab.append("·")
                sty.append(COLORS["explored"])
            elif ch == "~":
                lab.append("~")
                sty.append(COLORS["crowded"])
            else:
                lab.append(ch if ch in "EK" else "")
                sty.append(COLORS["aisle"])
        labels.append(lab)
        styles.append(sty)

    cols = [str(c) for c in range(len(nav.STORE_MAP[0]))]
    df = pd.DataFrame(labels, columns=cols)
    style_df = pd.DataFrame(styles, columns=cols)
    return df.style.apply(lambda _: style_df, axis=None).set_properties(
        **{"text-align": "center", "min-width": "2.2em"})


def render_store_navigator_page():
    st.title("🧭 Store Navigator")
    st.caption("Finds the way to a product's shelf with AI search algorithms: "
               "BFS, DFS, UCS, Greedy Best-First and A*.")

    # ---------- Choose the problem ----------
    cat_names = {c["category_id"]: c["name"] for c in list_categories()}
    products = list_active_products()
    options = {f"{p['name']} ({cat_names.get(p.get('category_id'), 'Unknown')})":
               cat_names.get(p.get("category_id"), "Unknown") for p in products}
    if not options:
        options = {name: name for name in nav.SHELF_CATEGORY.values()}

    a, b = st.columns([3, 2], vertical_alignment="bottom")
    choice = a.selectbox("Product to find", list(options))
    start_name = b.segmented_control("Start from", list(STARTS), default="Entrance",
                                     required=True)

    category = options[choice]
    letter = nav.letter_for_category(category)
    start = nav.find_cell(STARTS[start_name])
    goal = nav.pick_point(letter)

    results = nav.compare_all(start, goal)
    best_cost = min(r["cost"] for r in results.values() if r["found"])

    # ---------- Comparison table ----------
    st.subheader("Algorithm comparison")
    rows = [{
        "algorithm": name,
        "path_cost": r["cost"],
        "steps": r["steps"],
        "nodes_expanded": r["expanded"],
        "optimal": "Yes" if r["cost"] == best_cost else "No",
        "how_it_works": ABOUT[name],
    } for name, r in results.items()]
    st.dataframe(
        pd.DataFrame(rows), hide_index=True, width="stretch",
        alt="Path cost, steps and nodes expanded for each search algorithm",
        column_config={
            "algorithm": "Algorithm",
            "path_cost": st.column_config.NumberColumn("Path cost", help="Aisle = 1, crowded = 5"),
            "steps": "Steps",
            "nodes_expanded": st.column_config.ProgressColumn(
                "Nodes expanded", format="%d", min_value=0,
                max_value=max(r["expanded"] for r in results.values())),
            "optimal": "Optimal?",
            "how_it_works": st.column_config.TextColumn("How it works", width="large"),
        })

    # ---------- Map ----------
    st.subheader("Store map")
    c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
    algo = c1.segmented_control("Show path of", nav.ALGORITHMS, default="A*", required=True)
    show_explored = c2.toggle("Show explored nodes", value=True)

    res = results[algo]
    st.markdown(f"**{algo}** → {category} shelf (**{letter}**): "
                f"cost **{res['cost']}**, {res['steps']} steps, {res['expanded']} nodes expanded.")
    st.table(_grid_table(res, start, goal, letter, show_explored))
    st.caption("Legend: :violet[START / GOAL] · :green[● path] · :blue[· explored] · "
               ":orange[target shelf] · :red[~ crowded aisle (cost 5)] · # wall · "
               "E entrance · K checkout")

    with st.expander("Shelf letters and the heuristic"):
        st.table({f"{k}": v for k, v in nav.SHELF_CATEGORY.items()})
        st.markdown(
            "**Heuristic** h(n) = Manhattan distance = |row₁ − row₂| + |col₁ − col₂|.  \n"
            "Each move costs at least 1, so h(n) never overestimates the true cost "
            "(admissible and consistent). That is why **A\\*** returns the same cost as **UCS**.")
