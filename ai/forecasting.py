"""
Demand forecasting (pure Python, no ML libraries).

Idea, in three steps:
1. Level   = average units sold per day over the last 7 days.
2. Trend   = slope of a straight line fitted to the last 28 days
             (least squares), so a rising product forecasts higher.
3. Weekday = how busy each weekday is compared with the average day
             (supermarkets sell more on weekends).

forecast(day) = (level + trend * days_ahead) * weekday_factor
"""

from datetime import date, timedelta


def linear_slope(values):
    """Slope of the best straight line through the points (0, v0), (1, v1), ..."""
    n = len(values)
    if n < 2:
        return 0.0
    mean_x = (n - 1) / 2
    mean_y = sum(values) / n
    top = sum((x - mean_x) * (y - mean_y) for x, y in enumerate(values))
    bottom = sum((x - mean_x) ** 2 for x in range(n))
    return top / bottom


def weekday_factors(daily, start_day):
    """daily[i] is units sold on start_day + i. Returns {weekday: factor}."""
    totals = {d: 0.0 for d in range(7)}
    counts = {d: 0 for d in range(7)}
    for i, qty in enumerate(daily):
        wd = (start_day + timedelta(days=i)).weekday()
        totals[wd] += qty
        counts[wd] += 1

    overall = sum(daily) / len(daily) if daily else 0
    factors = {}
    for wd in range(7):
        if overall == 0 or counts[wd] == 0:
            factors[wd] = 1.0
        else:
            factors[wd] = (totals[wd] / counts[wd]) / overall
    return factors


def forecast_demand(daily, start_day, days_ahead=7):
    """
    daily      : list of units sold per day, oldest first (no gaps; 0 for no sales)
    start_day  : the date of daily[0]
    Returns a list of {"date", "qty"} for the next days_ahead days.
    """
    if not daily:
        return []

    recent = daily[-7:]
    level = sum(recent) / len(recent)
    slope = linear_slope(daily[-28:])
    # Use weekday factors only when there are at least 2 weeks of data
    factors = weekday_factors(daily, start_day) if len(daily) >= 14 else {d: 1.0 for d in range(7)}

    last_day = start_day + timedelta(days=len(daily) - 1)
    result = []
    for step in range(1, days_ahead + 1):
        day = last_day + timedelta(days=step)
        qty = (level + slope * step) * factors[day.weekday()]
        result.append({"date": day.isoformat(), "qty": round(max(qty, 0), 1)})
    return result


def restock_advice(forecast, current_stock, min_stock, lead_days=3):
    """
    Decide whether to reorder.
    Need = what we expect to sell before the next delivery arrives + a week after it
           + the minimum stock we always want to keep.
    """
    daily_rate = sum(f["qty"] for f in forecast) / len(forecast) if forecast else 0

    if daily_rate > 0:
        days_left = round(current_stock / daily_rate, 1)
    else:
        days_left = None  # not selling, never runs out

    needed = daily_rate * (lead_days + 7) + min_stock
    reorder_qty = max(0, round(needed - current_stock))

    if current_stock == 0:
        urgency = "Critical"
    elif days_left is not None and days_left <= lead_days:
        urgency = "High"
    elif reorder_qty > 0:
        urgency = "Medium"
    else:
        urgency = "OK"

    return {
        "avg_daily_demand": round(daily_rate, 2),
        "days_until_stockout": days_left,
        "reorder_qty": reorder_qty,
        "urgency": urgency,
    }


def fill_daily_series(sales_by_day, start_day, end_day):
    """Turn {date: qty} into a full list with 0 for days without sales."""
    days = (end_day - start_day).days + 1
    return [float(sales_by_day.get(start_day + timedelta(days=i), 0)) for i in range(days)]


if __name__ == "__main__":
    # Quick demo: a product selling about 10 a day, more on weekends
    start = date.today() - timedelta(days=27)
    history = [10 + (5 if (start + timedelta(days=i)).weekday() >= 5 else 0) for i in range(28)]
    fc = forecast_demand(history, start)
    print(fc)
    print(restock_advice(fc, current_stock=25, min_stock=20))
