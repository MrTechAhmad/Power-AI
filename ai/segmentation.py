"""
Customer segmentation with RFM scoring (pure Python).

R = Recency   : days since the last visit (fewer is better)
F = Frequency : number of visits
M = Monetary  : total money spent

Each is scored 1 to 3 by comparing a customer with the others
(bottom third = 1, middle = 2, top third = 3), then simple rules
name the segment.
"""


def _score(value, sorted_values, higher_is_better=True):
    """Score 1-3 based on where value sits among all customers."""
    n = len(sorted_values)
    if n == 0:
        return 2
    position = sum(1 for v in sorted_values if v < value) / n  # 0.0 to <1.0
    score = 1 + int(position * 3)
    score = min(score, 3)
    return score if higher_is_better else 4 - score


def segment_name(r, f, m):
    if r == 3 and f == 3 and m >= 2:
        return "Champion"
    if f >= 2 and m >= 2 and r >= 2:
        return "Loyal"
    if r == 1 and (f >= 2 or m >= 2):
        return "At Risk"
    if r == 3 and f == 1:
        return "New"
    if r == 1:
        return "Inactive"
    return "Regular"


def segment_customers(customers):
    """
    customers : list of dicts with keys
                customer_id, name, recency_days, visits, total_spent
    Returns the same dicts with r_score, f_score, m_score and segment added.
    """
    recency = sorted(c["recency_days"] for c in customers)
    visits = sorted(c["visits"] for c in customers)
    spent = sorted(c["total_spent"] for c in customers)

    result = []
    for c in customers:
        r = _score(c["recency_days"], recency, higher_is_better=False)
        f = _score(c["visits"], visits)
        m = _score(c["total_spent"], spent)
        row = dict(c)
        row.update({"r_score": r, "f_score": f, "m_score": m,
                    "segment": segment_name(r, f, m)})
        result.append(row)
    return result


if __name__ == "__main__":
    demo = [
        {"customer_id": 1, "name": "Ali", "recency_days": 1, "visits": 20, "total_spent": 30000},
        {"customer_id": 2, "name": "Sara", "recency_days": 40, "visits": 12, "total_spent": 18000},
        {"customer_id": 3, "name": "Usman", "recency_days": 2, "visits": 1, "total_spent": 900},
    ]
    for row in segment_customers(demo):
        print(row["name"], row["segment"])
