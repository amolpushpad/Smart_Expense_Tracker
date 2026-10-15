from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from models import Expense

MIN_CATEGORY_HISTORY = 5
MAX_SCANNED_EXPENSES = 5000


def _median(values):
    try:
        import numpy as np

        return Decimal(str(float(np.median(np.asarray([float(value) for value in values], dtype=float)))))
    except ImportError:
        ordered = sorted(values)
        middle = len(ordered) // 2
        if len(ordered) % 2:
            return ordered[middle]
        return (ordered[middle - 1] + ordered[middle]) / 2


def detect_unusual_expenses(user_id, today=None):
    today = today or date.today()
    cutoff = today - timedelta(days=365)
    expenses = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.date >= cutoff,
        Expense.date <= today,
    ).order_by(Expense.date.asc(), Expense.expense_id.asc()).limit(MAX_SCANNED_EXPENSES).all()
    history = defaultdict(list)
    anomalies = []

    for expense in expenses:
        prior = history[expense.category_id]
        if len(prior) >= MIN_CATEGORY_HISTORY:
            baseline = _median(prior)
            deviations = [abs(value - baseline) for value in prior]
            mad = _median(deviations)
            threshold = max(baseline * 3, baseline + mad * Decimal("4.5"))
            if expense.amount > threshold:
                anomalies.append({
                    "expense_id": expense.expense_id,
                    "date": expense.date.isoformat(),
                    "amount": format(expense.amount, ".2f"),
                    "category": expense.category.category_name,
                    "description": expense.description or expense.vendor or "Expense",
                    "reason": (
                        f"Amount is above the robust historical threshold of {threshold.quantize(Decimal('0.01'))} "
                        f"for this category (median {baseline.quantize(Decimal('0.01'))}). This is only an unusual-spending flag."
                    ),
                    "detection_method": "category_median_mad",
                })
        prior.append(expense.amount)

    return list(reversed(anomalies[-25:]))
