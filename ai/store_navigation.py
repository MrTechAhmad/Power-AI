"""
Store navigation with classic AI search algorithms (pure Python).

The supermarket floor is a grid. A shopper (or staff member) starts at the
entrance or the checkout and must walk to the shelf of a product's category.

Search algorithms implemented (one generic graph search, different frontier):
- BFS                 : FIFO queue           -> fewest steps, ignores cost
- DFS                 : LIFO stack           -> finds *a* path, not the best
- UCS                 : priority = g(n)      -> cheapest path (optimal)
- Greedy Best-First   : priority = h(n)      -> fast, not always optimal
- A*                  : priority = g(n)+h(n) -> cheapest path, fewer nodes than UCS

g(n) = cost walked so far, h(n) = Manhattan distance to the goal.
Every step costs at least 1, so Manhattan distance never overestimates
(admissible and consistent), which makes A* optimal.

Map legend
  .  aisle (cost 1)          ~  crowded aisle (cost 5)
  #  wall                    E  entrance        K  checkout
  letter = shelf of a category (see SHELF_CATEGORY)
"""

import heapq
from collections import deque

STORE_MAP = [
    "E..............",
    ".DD.BB.GG.RR.V.",
    ".DD.BB.GG.RR.V.",
    "...~~~.........",
    ".SS.FF.HH.PP.M.",
    ".SS.FF.HH.PP.M.",
    "...........~~~.",
    "####.######.###",
    "...............",
    "K......~~~.....",
]

SHELF_CATEGORY = {
    "D": "Dairy", "B": "Bakery", "G": "Grains", "R": "Grocery", "V": "Beverages",
    "S": "Snacks", "F": "Fruits & Vegetables", "H": "Household",
    "P": "Personal Care", "M": "Meat",
}

STEP_COST = {".": 1, "~": 5, "E": 1, "K": 1}
WALKABLE = set(STEP_COST)

# Neighbour order: up, right, down, left (matters for BFS / DFS tie-breaking)
MOVES = [(-1, 0), (0, 1), (1, 0), (0, -1)]

ALGORITHMS = ["BFS", "DFS", "UCS", "Greedy Best-First", "A*"]


# ---------- The problem: states, actions, costs, heuristic ----------

def find_cell(symbol, grid=STORE_MAP):
    for r, row in enumerate(grid):
        c = row.find(symbol)
        if c != -1:
            return (r, c)
    raise ValueError(f"{symbol!r} is not on the map")


def neighbours(cell, grid=STORE_MAP):
    """Walkable cells next to `cell` with the cost of stepping onto them."""
    r, c = cell
    for dr, dc in MOVES:
        nr, nc = r + dr, c + dc
        if 0 <= nr < len(grid) and 0 <= nc < len(grid[0]) and grid[nr][nc] in WALKABLE:
            yield (nr, nc), STEP_COST[grid[nr][nc]]


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def shelf_cells(letter, grid=STORE_MAP):
    return [(r, c) for r, row in enumerate(grid) for c, ch in enumerate(row) if ch == letter]


def pick_point(letter, grid=STORE_MAP):
    """The aisle cell in front of a shelf (its lowest, then left-most, walkable neighbour)."""
    spots = {nb for cell in shelf_cells(letter, grid) for nb, _ in neighbours(cell, grid)}
    if not spots:
        raise ValueError(f"Shelf {letter!r} cannot be reached")
    return min(spots, key=lambda rc: (-rc[0], rc[1]))


def letter_for_category(category_name):
    """Shelf letter for a category; unknown categories share a shelf by name."""
    for letter, name in SHELF_CATEGORY.items():
        if name.lower() == str(category_name).lower():
            return letter
    letters = list(SHELF_CATEGORY)
    return letters[sum(map(ord, str(category_name))) % len(letters)]


# ---------- Generic graph search ----------

def search(start, goal, algorithm, grid=STORE_MAP):
    """
    Graph search where only the frontier changes between algorithms.
    Returns {"path", "cost", "steps", "expanded", "expanded_order", "found"}.
    """
    if algorithm not in ALGORITHMS:
        raise ValueError(f"Unknown algorithm {algorithm!r}")

    def priority(g, cell):
        h = manhattan(cell, goal)
        return {"UCS": g, "Greedy Best-First": h, "A*": g + h}[algorithm]

    # Frontier entries: (cell, g). Heap entries add (priority, tie-breaker) in front.
    if algorithm == "BFS":
        frontier = deque([(start, 0)])
        pop, push = frontier.popleft, frontier.append
    elif algorithm == "DFS":
        frontier = [(start, 0)]
        pop, push = frontier.pop, frontier.append
    else:
        counter = 0
        frontier = [(priority(0, start), counter, start, 0)]

        def pop():
            _, _, cell, g = heapq.heappop(frontier)
            return cell, g

        def push(item):
            nonlocal counter
            counter += 1
            cell, g = item
            heapq.heappush(frontier, (priority(g, cell), counter, cell, g))

    parent = {start: None}
    best_g = {start: 0}
    explored = set()
    expanded_order = []

    while frontier:
        cell, g = pop()
        if cell in explored:
            continue                      # an older, worse copy of this state
        explored.add(cell)
        expanded_order.append(cell)

        if cell == goal:                  # goal test on expansion
            path = [cell]
            while parent[path[-1]] is not None:
                path.append(parent[path[-1]])
            path.reverse()
            return {"path": path, "cost": g, "steps": len(path) - 1,
                    "expanded": len(expanded_order), "expanded_order": expanded_order,
                    "found": True}

        children = list(neighbours(cell, grid))
        if algorithm == "DFS":
            children.reverse()            # so the first move is explored first
        for nb, step in children:
            if nb in explored:
                continue
            new_g = g + step
            # BFS/DFS keep the first parent found; cost-based searches keep the cheapest
            if algorithm in ("BFS", "DFS"):
                if nb in parent and algorithm == "BFS":
                    continue
                parent[nb] = cell
            else:
                if nb in best_g and best_g[nb] <= new_g:
                    continue
                best_g[nb] = new_g
                parent[nb] = cell
            push((nb, new_g))

    return {"path": [], "cost": None, "steps": None, "expanded": len(expanded_order),
            "expanded_order": expanded_order, "found": False}


def compare_all(start, goal, grid=STORE_MAP):
    """Run every algorithm on the same problem. Returns {algorithm: result}."""
    return {name: search(start, goal, name, grid) for name in ALGORITHMS}


if __name__ == "__main__":
    start = find_cell("K")
    goal = pick_point("D")  # Dairy
    print(f"From checkout {start} to Dairy {goal}")
    for name, res in compare_all(start, goal).items():
        print(f"{name:18} cost={res['cost']:>3} steps={res['steps']:>3} expanded={res['expanded']:>3}")
