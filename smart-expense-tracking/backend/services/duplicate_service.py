import re
from datetime import date, timedelta

from models import Expense

MAX_SCANNED_EXPENSES = 5000
TOKEN_PATTERN = re.compile(r"[^a-z0-9]+")


def _normalize(value):
    return TOKEN_PATTERN.sub(" ", (value or "").casefold()).strip()


def find_possible_duplicates(user_id, today=None):
    today = today or date.today()
    expenses = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.date >= today - timedelta(days=365),
        Expense.date <= today,
    ).order_by(Expense.date.asc(), Expense.expense_id.asc()).limit(MAX_SCANNED_EXPENSES).all()
    groups = {}
    for expense in expenses:
        description = _normalize(expense.description)
        vendor = _normalize(expense.vendor)
        if not description and not vendor:
            continue
        key = (expense.date, expense.category_id, expense.amount)
        groups.setdefault(key, []).append((expense, description, vendor))

    pairs = []
    for candidates in groups.values():
        for left_index, (left, left_description, left_vendor) in enumerate(candidates):
            for right, right_description, right_vendor in candidates[left_index + 1:]:
                reasons = []
                if left_description and left_description == right_description:
                    reasons.append("normalized description matches")
                if left_vendor and left_vendor == right_vendor and (
                    not left_description or not right_description or left_description == right_description
                ):
                    reasons.append("normalized vendor matches")
                if not reasons:
                    continue
                pairs.append({
                    "first": {
                        "expense_id": left.expense_id,
                        "date": left.date.isoformat(),
                        "amount": format(left.amount, ".2f"),
                        "category": left.category.category_name,
                        "description": left.description or "",
                        "vendor": left.vendor or "",
                    },
                    "second": {
                        "expense_id": right.expense_id,
                        "date": right.date.isoformat(),
                        "amount": format(right.amount, ".2f"),
                        "category": right.category.category_name,
                        "description": right.description or "",
                        "vendor": right.vendor or "",
                    },
                    "matching_reasons": reasons,
                    "detection_method": "exact_date_amount_category_normalized_text",
                    "explanation": "Possible duplicate only; review both records. Neither transaction was changed.",
                })
    pairs.sort(key=lambda pair: (pair["first"]["date"], pair["first"]["expense_id"]), reverse=True)
    return pairs[:50]
