from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func

from extensions import db
from models import Budget, Category, Expense, Income
from services.budget_service import budget_list_response

ZERO = Decimal("0.00")
CENT = Decimal("0.01")


def date_period_for_request(params):
    period = params.get("period", "monthly")
    if period == "weekly":
        raw_date = params.get("date", date.today().isoformat())
        anchor, error = _parse_date(raw_date)
        if error:
            return None, {"date": error}
        start = anchor - timedelta(days=anchor.weekday())
        return {"kind": "weekly", "start": start, "end": start + timedelta(days=6)}, None

    if period == "monthly":
        month_raw = params.get("month", str(date.today().month))
        year_raw = params.get("year", str(date.today().year))
        errors = {}
        if not month_raw.isdigit() or not 1 <= int(month_raw) <= 12:
            errors["month"] = "Month must be an integer from 1 to 12."
        if not year_raw.isdigit() or not 1900 <= int(year_raw) <= 9999:
            errors["year"] = "Year must be between 1900 and 9999."
        if errors:
            return None, errors
        month, year = int(month_raw), int(year_raw)
        return {
            "kind": "monthly",
            "start": date(year, month, 1),
            "end": date(year, month, monthrange(year, month)[1]),
            "month": month,
            "year": year,
        }, None

    if period == "custom":
        start, start_error = _parse_date(params.get("start_date"))
        end, end_error = _parse_date(params.get("end_date"))
        errors = {}
        if start_error:
            errors["start_date"] = start_error
        if end_error:
            errors["end_date"] = end_error
        if start and end and start > end:
            errors["date_range"] = "Start date must be on or before end date."
        if errors:
            return None, errors
        return {"kind": "custom", "start": start, "end": end}, None

    return None, {"period": "Period must be weekly, monthly, or custom."}


def _parse_date(value):
    if not isinstance(value, str) or len(value) != 10:
        return None, "Enter a valid date in YYYY-MM-DD format."
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None, "Enter a valid date in YYYY-MM-DD format."
    if parsed.isoformat() != value:
        return None, "Enter a valid date in YYYY-MM-DD format."
    return parsed, None


def _money(value):
    return format(Decimal(value or 0).quantize(CENT), ".2f")


def _period_totals(user_id, start, end):
    income = Decimal(db.session.query(func.coalesce(func.sum(Income.amount), 0)).filter(
        Income.user_id == user_id, Income.date >= start, Income.date <= end
    ).scalar() or 0)
    expenses = Decimal(db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
        Expense.user_id == user_id, Expense.date >= start, Expense.date <= end
    ).scalar() or 0)
    return income, expenses


def _category_totals(user_id, start, end):
    rows = db.session.query(
        Category.category_id,
        Category.category_name,
        func.sum(Expense.amount).label("amount"),
    ).join(Expense, Expense.category_id == Category.category_id).filter(
        Expense.user_id == user_id,
        Expense.date >= start,
        Expense.date <= end,
    ).group_by(Category.category_id, Category.category_name).order_by(
        func.sum(Expense.amount).desc(), Category.category_name.asc()
    ).all()
    return [
        {"category_id": row.category_id, "category_name": row.category_name, "amount": _money(row.amount)}
        for row in rows
    ]


def _transactions(user_id, start, end):
    expenses = Expense.query.filter(
        Expense.user_id == user_id, Expense.date >= start, Expense.date <= end
    ).order_by(Expense.date.asc(), Expense.created_at.asc(), Expense.expense_id.asc()).all()
    incomes = Income.query.filter(
        Income.user_id == user_id, Income.date >= start, Income.date <= end
    ).order_by(Income.date.asc(), Income.created_at.asc(), Income.income_id.asc()).all()
    records = []
    for expense in expenses:
        records.append({
            "_date": expense.date,
            "_created_at": expense.created_at,
            "_id": expense.expense_id,
            "transaction_type": "expense",
            "date": expense.date.isoformat(),
            "category": expense.category.category_name,
            "description": expense.description or expense.vendor or "Expense",
            "income": "0.00",
            "expense": _money(expense.amount),
        })
    for income in incomes:
        records.append({
            "_date": income.date,
            "_created_at": income.created_at,
            "_id": income.income_id,
            "transaction_type": "income",
            "date": income.date.isoformat(),
            "category": "",
            "description": income.description or income.source,
            "income": _money(income.amount),
            "expense": "0.00",
        })
    records.sort(key=lambda row: (row["_date"], row["_created_at"], row["transaction_type"], row["_id"]))
    return [{key: value for key, value in row.items() if not key.startswith("_")} for row in records]


def _previous_period(period):
    start, end = period["start"], period["end"]
    if period["kind"] == "weekly":
        previous_end = start - timedelta(days=1)
        return previous_end - timedelta(days=6), previous_end
    if period["kind"] == "monthly":
        previous_end = start - timedelta(days=1)
        return date(previous_end.year, previous_end.month, 1), previous_end
    days = (end - start).days + 1
    previous_end = start - timedelta(days=1)
    return previous_end - timedelta(days=days - 1), previous_end


def _period_label(period):
    start, end = period["start"], period["end"]
    if period["kind"] == "weekly":
        return f"Week of {start.isoformat()} to {end.isoformat()} (Monday to Sunday)"
    if period["kind"] == "monthly":
        return start.strftime("%B %Y")
    return f"{start.isoformat()} to {end.isoformat()}"


def _time_series(user_id, start, end, kind):
    day_count = (end - start).days + 1
    use_day = kind == "weekly" or day_count <= 62
    if use_day:
        income_rows = db.session.query(Income.date, func.sum(Income.amount)).filter(
            Income.user_id == user_id, Income.date >= start, Income.date <= end
        ).group_by(Income.date).all()
        expense_rows = db.session.query(Expense.date, func.sum(Expense.amount)).filter(
            Expense.user_id == user_id, Expense.date >= start, Expense.date <= end
        ).group_by(Expense.date).all()
        income_by_day = {row[0]: Decimal(row[1]) for row in income_rows}
        expense_by_day = {row[0]: Decimal(row[1]) for row in expense_rows}
        return {
            "granularity": "day",
            "items": [
                {
                    "date": (start + timedelta(days=offset)).isoformat(),
                    "label": (start + timedelta(days=offset)).strftime("%a %d %b"),
                    "income": _money(income_by_day.get(start + timedelta(days=offset), ZERO)),
                    "expenses": _money(expense_by_day.get(start + timedelta(days=offset), ZERO)),
                }
                for offset in range(day_count)
            ],
        }

    income_rows = db.session.query(
        func.extract("year", Income.date),
        func.extract("month", Income.date),
        func.sum(Income.amount),
    ).filter(Income.user_id == user_id, Income.date >= start, Income.date <= end).group_by(
        func.extract("year", Income.date), func.extract("month", Income.date)
    ).all()
    expense_rows = db.session.query(
        func.extract("year", Expense.date),
        func.extract("month", Expense.date),
        func.sum(Expense.amount),
    ).filter(Expense.user_id == user_id, Expense.date >= start, Expense.date <= end).group_by(
        func.extract("year", Expense.date), func.extract("month", Expense.date)
    ).all()
    income_by_month = {(int(row[0]), int(row[1])): Decimal(row[2]) for row in income_rows}
    expense_by_month = {(int(row[0]), int(row[1])): Decimal(row[2]) for row in expense_rows}
    items = []
    cursor = date(start.year, start.month, 1)
    while cursor <= end:
        key = (cursor.year, cursor.month)
        items.append({
            "date": cursor.isoformat(),
            "label": cursor.strftime("%b %Y"),
            "income": _money(income_by_month.get(key, ZERO)),
            "expenses": _money(expense_by_month.get(key, ZERO)),
        })
        cursor = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)
    return {"granularity": "month", "items": items}


def _monthly_budgets(user_id, period, expenses):
    if period["kind"] != "monthly":
        return None
    query = Budget.query.filter_by(user_id=user_id, month=period["month"], year=period["year"]).order_by(
        Budget.category_id.asc(), Budget.budget_id.asc()
    )
    budgets = budget_list_response(query)["budgets"]
    overall = next((budget for budget in budgets if budget["category_id"] is None), None)
    if overall:
        amount = Decimal(overall["amount"])
        spent = expenses
    else:
        amount = sum((Decimal(budget["amount"]) for budget in budgets), ZERO)
        spent = sum((Decimal(budget["spent_amount"]) for budget in budgets), ZERO)
    remaining = amount - spent
    utilization = spent / amount * 100 if amount else None
    return {
        "budgets": budgets,
        "monthly_budget": _money(amount),
        "budgeted_spending": _money(spent),
        "remaining_budget": _money(remaining),
        "budget_utilization": _money(utilization) if utilization is not None else None,
        "over_budget": remaining < 0,
    }


def analytics_report(user_id, period):
    start, end = period["start"], period["end"]
    income, expenses = _period_totals(user_id, start, end)
    previous_start, previous_end = _previous_period(period)
    _previous_income, previous_expenses = _period_totals(user_id, previous_start, previous_end)
    change = expenses - previous_expenses
    change_percentage = change / previous_expenses * 100 if previous_expenses else None

    categories = _category_totals(user_id, start, end)
    largest_expense = Expense.query.filter(
        Expense.user_id == user_id, Expense.date >= start, Expense.date <= end
    ).order_by(Expense.amount.desc(), Expense.date.desc(), Expense.expense_id.desc()).first()
    largest_income = Income.query.filter(
        Income.user_id == user_id, Income.date >= start, Income.date <= end
    ).order_by(Income.amount.desc(), Income.date.desc(), Income.income_id.desc()).first()
    largest = None
    if largest_expense and (not largest_income or largest_expense.amount >= largest_income.amount):
        largest = {
            "transaction_type": "expense",
            "amount": _money(largest_expense.amount),
            "date": largest_expense.date.isoformat(),
            "description": largest_expense.description or largest_expense.vendor or "Expense",
            "category": largest_expense.category.category_name,
        }
    elif largest_income:
        largest = {
            "transaction_type": "income",
            "amount": _money(largest_income.amount),
            "date": largest_income.date.isoformat(),
            "description": largest_income.description or largest_income.source,
            "category": None,
        }

    day_count = (end - start).days + 1
    budget = _monthly_budgets(user_id, period, expenses)
    result = {
        "period": {
            "type": period["kind"],
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "label": _period_label(period),
            "week_starts_on": "Monday" if period["kind"] == "weekly" else None,
        },
        "summary": {
            "total_income": _money(income),
            "total_expenses": _money(expenses),
            "savings": _money(income - expenses),
            "balance": _money(income - expenses),
            "average_daily_spending": _money(expenses / day_count),
        },
        "previous_period": {
            "start_date": previous_start.isoformat(),
            "end_date": previous_end.isoformat(),
            "expenses": _money(previous_expenses),
            "change_amount": _money(change),
            "change_percentage": _money(change_percentage) if change_percentage is not None else None,
        },
        "categories": categories,
        "highest_spending_category": categories[0] if categories else None,
        "largest_transaction": largest,
        "series": _time_series(user_id, start, end, period["kind"]),
        "transactions": _transactions(user_id, start, end),
        "budget": budget,
    }
    return result
