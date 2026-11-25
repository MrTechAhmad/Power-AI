"""
Product recommendations with market basket analysis (pure Python).

For every pair of products A and B that appear in the same sale:
- support    = share of all sales that contain both A and B
- confidence = of the sales containing A, the share that also contain B
- lift       = confidence / (share of sales containing B)
               lift > 1 means A and B are bought together more than by chance.

"Customers who bought A also bought B" = the rules with the highest lift.
"""

from itertools import combinations


def build_rules(baskets, min_support=0.01, min_confidence=0.1):
    """
    baskets : list of sets of product ids, one set per sale
    Returns a list of rules: {"from", "to", "support", "confidence", "lift"}
    """
    total = len(baskets)
    if total == 0:
        return []

    item_count = {}
    pair_count = {}

    for basket in baskets:
        items = sorted(set(basket))
        for item in items:
            item_count[item] = item_count.get(item, 0) + 1
        for a, b in combinations(items, 2):
            pair_count[(a, b)] = pair_count.get((a, b), 0) + 1

    rules = []
    for (a, b), together in pair_count.items():
        support = together / total
        if support < min_support:
            continue
        # A pair gives two rules: A -> B and B -> A
        for x, y in ((a, b), (b, a)):
            confidence = together / item_count[x]
            if confidence < min_confidence:
                continue
            lift = confidence / (item_count[y] / total)
            rules.append({
                "from": x,
                "to": y,
                "support": round(support, 4),
                "confidence": round(confidence, 4),
                "lift": round(lift, 3),
            })

    rules.sort(key=lambda r: (r["lift"], r["confidence"]), reverse=True)
    return rules


def recommend_for(product_id, rules, top_n=3):
    """Best products to suggest next to product_id (only rules with lift > 1)."""
    picks = [r for r in rules if r["from"] == product_id and r["lift"] > 1]
    return picks[:top_n]


if __name__ == "__main__":
    demo = [{"bread", "butter"}, {"bread", "butter", "milk"}, {"milk", "tea"},
            {"bread", "butter"}, {"tea", "sugar"}, {"milk", "tea", "sugar"}]
    rules = build_rules(demo)
    for r in recommend_for("bread", rules):
        print(r)
