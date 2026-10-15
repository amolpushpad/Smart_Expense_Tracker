from calendar import monthrange
from datetime import date
from decimal import Decimal

from sqlalchemy import func

from extensions import db
from models import Expense

MIN_HISTORY_MONTHS = 3
MODEL_HISTORY_MONTHS = 6


def _month_shift(year, month, offset):
    index = year * 12 + month - 1 + offset
    return divmod(index, 12)[0], divmod(index, 12)[1] + 1


def predict_monthly_spending(user_id, month=None, year=None, today=None):
    today = today or date.today()
    month = month or today.month
    year = year or today.year
    target_start = date(year, month, 1)
    target_end = date(year, month, monthrange(year, month)[1])
    if (year, month) < (today.year, today.month):
        return {
            "prediction_value": None,
            "prediction_period": {"month": month, "year": year, "start_date": target_start.isoformat(), "end_date": target_end.isoformat()},
            "currency": "INR",
            "model": None,
            "sufficient_history": False,
            "history_months": 0,
            "explanation": "Predictions are provided for the current or a future month, not completed periods.",
            "is_estimate": True,
        }

    previous_year, previous_month = _month_shift(year, month, -1)
    history_start_year, history_start_month = _month_shift(previous_year, previous_month, -11)
    history_start = date(history_start_year, history_start_month, 1)
    history_end = date(previous_year, previous_month, monthrange(previous_year, previous_month)[1])
    rows = db.session.query(
        func.extract("year", Expense.date).label("year"),
        func.extract("month", Expense.date).label("month"),
        func.sum(Expense.amount).label("total"),
    ).filter(
        Expense.user_id == user_id,
        Expense.date >= history_start,
        Expense.date <= history_end,
    ).group_by(
        func.extract("year", Expense.date),
        func.extract("month", Expense.date),
    ).all()
    totals = {(int(row.year), int(row.month)): Decimal(row.total) for row in rows}

    months = []
    for offset in range(-11, 1):
        historical_year, historical_month = _month_shift(previous_year, previous_month, offset)
        month_total = totals.get((historical_year, historical_month), Decimal("0.00"))
        months.append({
            "year": historical_year,
            "month": historical_month,
            "total": month_total,
            "days": monthrange(historical_year, historical_month)[1],
        })

    observed = [item for item in months if item["total"] > 0]
    if len(observed) < MIN_HISTORY_MONTHS:
        return {
            "prediction_value": None,
            "prediction_period": {"month": month, "year": year, "start_date": target_start.isoformat(), "end_date": target_end.isoformat()},
            "currency": "INR",
            "model": None,
            "sufficient_history": False,
            "history_months": len(observed),
            "explanation": f"At least {MIN_HISTORY_MONTHS} completed months with recorded expenses are required. This estimate is not financial advice.",
            "is_estimate": True,
        }

    daily_rates = [float(item["total"] / item["days"]) for item in observed]
    method = "historical_daily_average"
    predicted_daily_rate = sum(daily_rates) / len(daily_rates)
    if len(observed) >= MODEL_HISTORY_MONTHS:
        try:
            import numpy as np
            import pandas as pd
            from sklearn.linear_model import LinearRegression

            frame = pd.DataFrame(observed)
            frame["month_index"] = frame["year"] * 12 + frame["month"]
            frame["daily_rate"] = frame.apply(lambda row: float(row["total"] / row["days"]), axis=1)
            model = LinearRegression()
            x_values = frame[["month_index"]].to_numpy(dtype=float)
            y_values = frame["daily_rate"].to_numpy(dtype=float)
            model.fit(x_values, y_values)
            target_index = np.array([[year * 12 + month]], dtype=float)
            predicted_daily_rate = max(0.0, float(model.predict(target_index)[0]))
            method = "scikit_learn_linear_regression"
        except ImportError:
            method = "historical_daily_average"

    if (year, month) == (today.year, today.month):
        actual_start = target_start
        actual_end = min(today, target_end)
        actual_spent = Decimal(db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
            Expense.user_id == user_id,
            Expense.date >= actual_start,
            Expense.date <= actual_end,
        ).scalar() or 0)
        elapsed_days = max(0, (actual_end - actual_start).days + 1)
        remaining_days = max(0, (target_end - actual_end).days)
        projection = float(actual_spent) + predicted_daily_rate * remaining_days
        explanation = (
            f"Actual spending through {actual_end.isoformat()} plus projected spending for {remaining_days} remaining days, "
            f"based on {len(observed)} completed months. This estimate is not financial advice."
        )
    else:
        actual_spent = Decimal("0.00")
        elapsed_days = 0
        remaining_days = target_end.day
        projection = predicted_daily_rate * target_end.day
        explanation = (
            f"Projected using {len(observed)} completed months of per-day spending history. "
            "This estimate is not financial advice."
        )

    from decimal import ROUND_HALF_UP
    prediction_value = Decimal(str(max(0.0, projection))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {
        "prediction_value": format(prediction_value, ".2f"),
        "actual_spending_to_date": format(actual_spent, ".2f") if elapsed_days else None,
        "prediction_period": {
            "month": month,
            "year": year,
            "start_date": target_start.isoformat(),
            "end_date": target_end.isoformat(),
        },
        "currency": "INR",
        "model": method,
        "sufficient_history": True,
        "history_months": len(observed),
        "explanation": explanation,
        "is_estimate": True,
    }
