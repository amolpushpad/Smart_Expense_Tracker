from calendar import monthrange
from datetime import date
from decimal import Decimal

from sqlalchemy import func

from extensions import db
from models import Budget, Category, Expense, Income
from services.budget_service import budget_list_response

ZERO = Decimal("0.00")


def _period(month, year):
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    return start, end


def _amount(value):
    return format(Decimal(value or 0).quantize(Decimal("0.01")), ".2f")


def _expense_sum(user_id, start=None, end=None):
    query = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter(Expense.user_id == user_id)
    if start is not None:
        query = query.filter(Expense.date >= start)
    if end is not None:
        query = query.filter(Expense.date <= end)
    return Decimal(query.scalar() or 0)


def _income_sum(user_id, start=None, end=None):
    query = db.session.query(func.coalesce(func.sum(Income.amount), 0)).filter(Income.user_id == user_id)
    if start is not None:
        query = query.filter(Income.date >= start)
    if end is not None:
        query = query.filter(Income.date <= end)
    return Decimal(query.scalar() or 0)


def _monthly_budget(user_id, month, year, start, end, month_expenses):
    budgets = Budget.query.filter_by(user_id=user_id, month=month, year=year).all()
    overall = next((budget for budget in budgets if budget.category_id is None), None)
    if overall:
        return overall.amount, month_expenses
    if not budgets:
        return ZERO, ZERO
    category_ids = [budget.category_id for budget in budgets]
    covered_spending = Decimal(db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
        Expense.user_id == user_id,
        Expense.category_id.in_(category_ids),
        Expense.date >= start,
        Expense.date <= end,
    ).scalar() or 0)
    return sum((budget.amount for budget in budgets), ZERO), covered_spending


def dashboard_summary(user_id, month, year):
    start, end = _period(month, year)
    today = date.today()
    month_income = _income_sum(user_id, start, end)
    month_expenses = _expense_sum(user_id, start, end)
    total_income = _income_sum(user_id)
    total_expenses = _expense_sum(user_id)
    monthly_budget, budgeted_spending = _monthly_budget(user_id, month, year, start, end, month_expenses)

    highest = db.session.query(
        Category.category_name,
        func.sum(Expense.amount).label("total"),
    ).join(Expense, Expense.category_id == Category.category_id).filter(
        Expense.user_id == user_id,
        Expense.date >= start,
        Expense.date <= end,
    ).group_by(Category.category_id, Category.category_name).order_by(
        func.sum(Expense.amount).desc(), Category.category_name.asc()
    ).first()

    days_in_period = min(today.day, end.day) if (today.year, today.month) == (year, month) else end.day
    average_daily = month_expenses / days_in_period if days_in_period else ZERO
    savings_rate = ((month_income - month_expenses) / month_income * 100) if month_income else ZERO
    remaining = monthly_budget - budgeted_spending
    utilization = (budgeted_spending / monthly_budget * 100) if monthly_budget else None

    return {
        "period": {"month": month, "year": year, "start_date": start.isoformat(), "end_date": end.isoformat()},
        "total_income": _amount(total_income),
        "total_expenses": _amount(total_expenses),
        "current_balance": _amount(total_income - total_expenses),
        "monthly_income": _amount(month_income),
        "monthly_expenses": _amount(month_expenses),
        "monthly_budget": _amount(monthly_budget),
        "budgeted_spending": _amount(budgeted_spending),
        "budget_utilization": _amount(utilization) if utilization is not None else None,
        "remaining_budget": _amount(remaining),
        "savings_rate": _amount(savings_rate),
        "highest_spending_category": (
            {"category_name": highest.category_name, "amount": _amount(highest.total)} if highest else None
        ),
        "average_daily_spending": _amount(average_daily),
        "budget_exceeded": remaining < 0,
    }


def recent_transactions(user_id, limit=10):
    expenses = Expense.query.filter_by(user_id=user_id).order_by(
        Expense.date.desc(), Expense.created_at.desc(), Expense.expense_id.desc()
    ).limit(limit).all()
    incomes = Income.query.filter_by(user_id=user_id).order_by(
        Income.date.desc(), Income.created_at.desc(), Income.income_id.desc()
    ).limit(limit).all()

    records = []
    for expense in expenses:
        records.append({
            "_date": expense.date,
            "_created_at": expense.created_at,
            "_id": expense.expense_id,
            "transaction_type": "expense",
            "transaction_id": expense.expense_id,
            "description": expense.description or expense.vendor or "Expense",
            "source": None,
            "category": expense.category.category_name,
            "amount": _amount(expense.amount),
            "date": expense.date.isoformat(),
        })
    for income in incomes:
        records.append({
            "_date": income.date,
            "_created_at": income.created_at,
            "_id": income.income_id,
            "transaction_type": "income",
            "transaction_id": income.income_id,
            "description": income.description or income.source,
            "source": income.source,
            "category": None,
            "amount": _amount(income.amount),
            "date": income.date.isoformat(),
        })
    records.sort(
        key=lambda item: (item["_date"], item["_created_at"], item["transaction_type"], item["_id"]),
        reverse=True,
    )
    return [
        {key: value for key, value in item.items() if not key.startswith("_")}
        for item in records[:limit]
    ]


def monthly_trends(user_id, month, year, count=6):
    month_index = year * 12 + month - 1
    periods = []
    for offset in reversed(range(count)):
        current = month_index - offset
        current_year, zero_month = divmod(current, 12)
        periods.append((zero_month + 1, current_year))

    start = date(periods[0][1], periods[0][0], 1)
    end_month, end_year = periods[-1]
    end = date(end_year, end_month, monthrange(end_year, end_month)[1])

    expenses = db.session.query(
        func.extract("year", Expense.date).label("year"),
        func.extract("month", Expense.date).label("month"),
        func.coalesce(func.sum(Expense.amount), 0),
    ).filter(Expense.user_id == user_id, Expense.date >= start, Expense.date <= end).group_by(
        func.extract("year", Expense.date), func.extract("month", Expense.date)
    ).all()
    incomes = db.session.query(
        func.extract("year", Income.date).label("year"),
        func.extract("month", Income.date).label("month"),
        func.coalesce(func.sum(Income.amount), 0),
    ).filter(Income.user_id == user_id, Income.date >= start, Income.date <= end).group_by(
        func.extract("year", Income.date), func.extract("month", Income.date)
    ).all()

    expense_totals = {(int(row.year), int(row.month)): Decimal(row[2] or 0) for row in expenses}
    income_totals = {(int(row.year), int(row.month)): Decimal(row[2] or 0) for row in incomes}
    return [
        {
            "month": period_month,
            "year": period_year,
            "label": date(period_year, period_month, 1).strftime("%b %Y"),
            "income": _amount(income_totals.get((period_year, period_month), ZERO)),
            "expenses": _amount(expense_totals.get((period_year, period_month), ZERO)),
        }
        for period_month, period_year in periods
    ]


def category_breakdown(user_id, month, year):
    start, end = _period(month, year)
    rows = db.session.query(
        Category.category_id,
        Category.category_name,
        func.sum(Expense.amount).label("total"),
    ).join(Expense, Expense.category_id == Category.category_id).filter(
        Expense.user_id == user_id,
        Expense.date >= start,
        Expense.date <= end,
    ).group_by(Category.category_id, Category.category_name).order_by(
        func.sum(Expense.amount).desc(), Category.category_name.asc()
    ).all()
    return [
        {"category_id": row.category_id, "category_name": row.category_name, "amount": _amount(row.total)}
        for row in rows
    ]


def budget_progress(user_id, month, year):
    query = Budget.query.filter_by(user_id=user_id, month=month, year=year).order_by(
        Budget.category_id.asc(), Budget.budget_id.asc()
    )
    return budget_list_response(query)["budgets"]
