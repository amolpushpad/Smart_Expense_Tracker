# Project Context

## Project
Smart Expense Tracking and Analytics System. Current stack: React + Vite frontend, Flask API, Flask-SQLAlchemy, MySQL via PyMySQL, and cookie-based authentication with CSRF protection.

## Implemented Scope
- **Phase 1:** Existing responsive UI, navigation, dashboard presentation data, and placeholder pages.
- **Phase 2:** User registration/login/logout/session lookup, profile update API, hashed passwords, MySQL configuration, and safe user serialization.
- **Phase 3:** Expense CRUD, server-side search/filter/sort/pagination, authenticated user ownership checks, predefined categories, and admin-only category mutations.
- **Phase 4:** User-scoped income CRUD and date-range filtering; user-scoped overall and category budgets with month/year uniqueness and decimal spending/utilization calculations.
- **Phase 5:** User-scoped dashboard summary, recent transactions, six-month income/expense trends, category spending breakdown, and budget progress; Recharts visualizations and transparent rule-based insights.
- Dashboard lifetime income/expenses/balance are distinct from the selected-month totals. Monthly savings rate is `(monthly income - monthly expenses) / monthly income`; average daily spending uses elapsed days for the current month and all days for completed months.
- **Phase 6:** Authenticated weekly (Monday–Sunday), monthly, and custom-range analytics; previous-period comparisons, category and largest-transaction analysis; filtered transaction/summary CSV exports.
- Analytics financial aggregates use database `SUM` and Python `Decimal` so MySQL `DECIMAL(10,2)` calculations remain exact; Pandas/NumPy are not needed for these aggregations.
- **Phase 7 / 7A:** Dashboard weekly/monthly report selector reuses the existing analytics API, displays period comparisons, trends, categories, and month-to-date budgets. Optional ML routes provide static-sample TF-IDF categorization, historical spending prediction, category median/MAD flags, deterministic duplicate candidates, and rule-based spending patterns.
- Predictions and flags are advisory only; no ML feature writes, merges, or deletes transactions. Models never train on private cross-user records.

## Important Files
- `frontend/src/pages/Expenses.jsx`: expense table, summary, filters, pagination, and create/edit/delete UI.
- `frontend/src/components/ExpenseForm.jsx`: reusable add/edit dialog and client validation.
- `frontend/src/pages/Income.jsx` and `frontend/src/pages/Budgets.jsx`: API-backed income and monthly-budget interfaces.
- `frontend/src/pages/Dashboard.jsx`: selected-month financial cards, charts, budget progress, recent transactions, and financial insights.
- `frontend/src/pages/Analytics.jsx` and `frontend/src/pages/Reports.jsx`: date-filtered analytics and CSV reporting.
- `frontend/src/hooks/useAnalyticsReport.js` and `frontend/src/components/AnalyticsPeriodFilter.jsx`: shared period selection and analytics data loading.
- `frontend/src/components/ExpenseForm.jsx`: opt-in category suggestion which users can accept or override before saving.
- `frontend/src/services/api.js`: Axios client, credentials, CSRF token, and expense/category/income/budget/dashboard/analytics APIs.
- `backend/app.py`: app factory, CORS, CSRF enforcement, health route, schema seed command, and database error responses.
- `backend/config.py`: environment-driven MySQL URI, CORS origins, and admin email allowlist.
- `backend/models/expense.py`: decimal amount, date, references, timestamps, constraints, and indexes.
- `backend/models/income.py` and `backend/models/budget.py`: income and monthly budget persistence, constraints, and serialization.
- `backend/routes/expense_routes.py`: authenticated expense endpoints with user-scoped access.
- `backend/routes/income_routes.py` and `backend/routes/budget_routes.py`: authenticated income and budget APIs.
- `backend/routes/dashboard_routes.py` and `backend/services/dashboard_service.py`: authenticated summary and visualization datasets, all scoped by user and selected month.
- `backend/routes/analytics_routes.py` and `backend/services/analytics_service.py`: authenticated weekly/monthly/custom analytics and CSV exports with consistent date boundaries.
- `backend/routes/ml_routes.py`: authenticated ML endpoints. Corresponding categorization, prediction, anomaly, and duplicate logic lives in separate backend services.
- `backend/services/income_service.py` and `backend/services/budget_service.py`: backend validation, filtering, and budget calculations.
- `backend/routes/category_routes.py`: authenticated category reads and administrator-only mutations.
- `backend/services/expense_service.py`: expense validation and filtering.
- `backend/tests/test_auth.py`: isolated SQLite tests for authentication, expense APIs, categories, filtering, and authorization.

## Database Compatibility
Phase 2 uses physical tables named `user` and `category`; later phases retain those names so existing data is not stranded. Expenses are stored in `expenses`, with foreign keys to those tables. Income and budgets reference `user`; budgets optionally reference a category and use an indexed generated scope key to enforce uniqueness for both nullable overall-budget and category budgets. Monetary values use `DECIMAL(10,2)`/SQLAlchemy `Numeric(10,2)`.

## Verification Performed
- Backend tests use an in-memory SQLite database and do not connect to or modify the configured MySQL database.
- Analytics tests cover week/month/year boundaries, custom filtering, category totals, CSV-total agreement, spreadsheet-formula escaping, and cross-user isolation.
- ML tests cover classification and fallback behavior, history thresholds, statistical anomalies, cautious duplicate matching, endpoint failures, and cross-user isolation.
- Frontend: `npm run build` succeeded.
- Flask expense/category routes were registered; credentialed localhost CORS preflight succeeded.
- Tests do not connect to or modify the MySQL development database.

## Run Checks
From the repository root in PowerShell:

```powershell
Set-Location backend
.venv\Scripts\python.exe -m pytest -q
Set-Location ..\frontend
npm run build
```

See `README.md` for setup instructions. Do not put real credentials in this note; configure them locally in the ignored `backend/.env` file.
