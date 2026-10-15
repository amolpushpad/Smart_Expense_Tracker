# SMART EXPENSE TRACKING AND ANALYTICS SYSTEM
## Phases 1–8

An authenticated personal-finance application for recording expenses and income, setting monthly budgets, reviewing real dashboard/analytics data, exporting reports, and managing an account profile. Financial features use the signed-in account’s MySQL records; the ML features are optional estimates and review suggestions, not financial advice.

## Technology and architecture

- **Frontend:** React, React Router, Vite, Axios, Recharts
- **Backend:** Python, Flask, Flask-SQLAlchemy, SQLAlchemy ORM, PyMySQL
- **Database:** MySQL in local development; isolated in-memory SQLite databases in backend tests
- **Analysis:** Decimal/SQL aggregates for authoritative financial calculations; Pandas, NumPy, and Scikit-learn for documented optional baselines/classification
- **Authentication:** Werkzeug password hashes, signed HTTP-only cookie sessions, CSRF token checks on state-changing API requests

```text
backend/
  app.py                 Flask app factory, error handlers, schema commands
  config.py              Environment-backed database and session configuration
  models/                User, category, expense, income, and budget models
  routes/                Authenticated REST API blueprints
  services/              Validation, CRUD, analytics, dashboard, and ML services
  tests/                 SQLite-isolated API and service tests
frontend/
  src/components/        Shared navigation, forms, charts, and dialogs
  src/context/           Authentication/session context
  src/pages/             Dashboard, finance, analytics, reports, and profile screens
  src/services/          Axios API clients
  src/styles/            Responsive page styles
  src/test/              Frontend test setup
database/
  README.md              MySQL database and least-privilege account setup
```

Phase 1 provides the React/Vite interface. Phase 2 adds Flask, MySQL-backed accounts, and cookie-based authentication. Phase 3 adds authenticated expense management and category administration. Phase 4 adds user-scoped income and monthly budget management. Phase 5 connects the dashboard, charts, and insights to authenticated financial data. Phase 6 adds weekly/monthly/custom analytics and CSV reports. Phase 7 adds optional, user-scoped categorization, predictions, unusual-spending checks, and duplicate candidates.

### Included
- Login and registration connected to Flask APIs with frontend and server-side validation
- Protected dashboard routes with responsive navigation across finance, analytics, reports, and account screens
- Expense CRUD, server-side search/filter/sort, and paginated transaction history
- Income CRUD with inclusive date-range filtering and deterministic sorting
- Monthly overall and category-specific budgets with server-calculated spending, balances, utilization, and over-budget status
- Database-enforced uniqueness for a user's overall or category budget per month and year
- Authenticated dashboard summary, recent transactions, six-month trends, category breakdown, and budget-progress APIs
- Recharts visualizations, selected-month filtering, real transaction history, and transparent financial insights
- Weekly (Monday–Sunday), monthly, and custom inclusive date-range analytics with previous-period comparisons, category totals, largest transactions, and monthly budget utilization
- Authenticated CSV exports containing filtered transaction rows and matching income, expense, savings, and balance totals
- Aggregations use MySQL/SQLAlchemy `SUM` and Python `Decimal` for monetary precision; Pandas/NumPy are intentionally not used for these database-backed financial totals
- Weekly and monthly dashboard views reuse the authenticated analytics report; week boundaries are Monday–Sunday. Month-to-date budget progress remains distinct from weekly cash flow.
- Optional ML APIs provide a TF-IDF/logistic-regression category suggestion trained on small static example phrases, keyword fallback rules, a historical daily-average or Scikit-learn monthly prediction, category median/MAD unusual-spending flags, and exact normalized-text duplicate candidates. ML insights cannot mutate transactions.
- Profile and account management includes optional personal details, unique usernames, authenticated avatar uploads, current-password-confirmed email changes, password changes, and account logout.
- Profile photos are decoded and re-encoded as JPEG, PNG, or WebP, stored under the Flask instance directory (not the static web root), limited to 5 MB and 20 megapixels, and served only to the signed-in account owner.
- Lifetime totals and balance are separate from selected-month metrics; savings rate is monthly net income divided by monthly income, and average daily spending uses elapsed days in the current month or all days in a completed month
- Categories seeded from the predefined list; only emails in `ADMIN_EMAILS` can mutate categories
- HTTP-only signed session cookies and CSRF protection for state-changing requests
- Password hashing with Werkzeug; no passwords or session secrets are stored in browser local storage
- Idempotent category seed command and SQLite-isolated authentication tests

## ML implementation and limitations

- **Categorization:** Cached TF-IDF/logistic-regression classifier trained on a small static set of example phrases; transparent keyword rules are used for common examples or when the optional classifier is unavailable. The examples are not private user transactions. Suggestions require user confirmation.
- **Prediction:** A historical daily-average estimate with at least three completed months of history; linear regression is used when at least six completed months are available. Insufficient history returns no numeric estimate.
- **Unusual-spending flags:** Same-user, same-category historical median/MAD thresholds; a flag is neither a fraud determination nor an automatic transaction change.
- **Possible duplicates:** Conservative exact date/amount/category and normalized description/vendor comparisons. Results are review candidates only.
- These are deliberately simple baselines, not financial advice. The application does not send data to a third-party model service.

## Database setup and schema

Install MySQL and create a database and application user using [database/README.md](database/README.md). The MySQL application user needs the documented permissions to initialize tables and run the profile schema migration. Configure the backend environment file before starting Flask.

`flask --app app init-db` creates missing tables and seeds built-in categories without dropping or resetting existing tables. For an existing database, back it up and run `flask --app app migrate-profile` to add missing nullable profile fields and username uniqueness. The profile migration is repeatable. Neither command deletes financial records.

Tests use in-memory SQLite fixtures and do not read or write configured MySQL records. Local runtime verification uses only the health endpoint; it does not create, modify, or delete user transactions.

## Environment variables

Copy the templates and use local values:

```powershell
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env
```

Backend settings:

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Long, random, stable Flask session-signing key; never use the template value in a real deployment. |
| `MYSQL_HOST`, `MYSQL_PORT` | MySQL server address and port. |
| `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE` | Application database credentials and database name. |
| `FRONTEND_ORIGINS` | Comma-separated allowed frontend origins; defaults to localhost and 127.0.0.1 on port 5173. |
| `SESSION_COOKIE_SECURE` | Set `true` behind HTTPS; keep `false` only for local HTTP development. Cookies are HTTP-only and SameSite=Lax. |
| `FLASK_DEBUG` | Set `true` only for local development. |
| `ADMIN_EMAILS` | Optional comma-separated existing account emails allowed to administer shared categories. |
| `PROFILE_UPLOAD_DIR` | Optional absolute persistent directory for profile photos; defaults to `backend/instance/profile_photos`. |

The frontend uses `VITE_API_BASE_URL`, defaulting to `http://localhost:5000/api`. Use matching hostnames for the frontend/backend in local development because cookies are host-scoped. The Vite default origin must be listed in `FRONTEND_ORIGINS`.

Never commit `backend/.env` or `frontend/.env`. `.env.example` files contain placeholders only. `SECRET_KEY` falls back to a generated process-local value if it is not set; configure a stable secret before relying on persistent sessions across restarts.

## Installation and run

Run these commands from the project root in PowerShell.

```powershell
Set-Location backend
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m flask --app app init-db
python -m flask --app app migrate-profile
python -m flask --app app run
```

The API listens at `http://localhost:5000`; `GET /api/health` checks the MySQL connection. In another terminal:

```powershell
Set-Location frontend
npm install
npm run dev
```

Vite defaults to `http://localhost:5173`.

## API overview

All account and financial routes below require the authenticated session except registration, login, CSRF bootstrap, and health. State-changing requests must send `X-CSRF-Token`. Record reads and updates are scoped to the current user; category administration additionally requires an email listed in `ADMIN_EMAILS`.

| Group | Routes |
|---|---|
| Health/auth | `GET /api/health`; `GET /api/auth/csrf`; `POST /api/auth/register`; `POST /api/auth/login`; `POST /api/auth/logout`; `GET /api/auth/me` |
| Expenses | `GET/POST /api/expenses`; `GET/PUT/DELETE /api/expenses/<id>` |
| Income | `GET/POST /api/income`; `GET/PUT/DELETE /api/income/<id>` |
| Budgets | `GET/POST /api/budgets`; `GET/PUT/DELETE /api/budgets/<id>` |
| Categories | `GET/POST /api/categories`; `PUT/DELETE /api/categories/<id>` |
| Dashboard | `GET /api/dashboard/summary`; `GET /api/dashboard/recent-transactions`; `GET /api/dashboard/monthly-trends`; `GET /api/dashboard/category-breakdown`; `GET /api/dashboard/budget-progress` |
| Analytics/reports | `GET /api/analytics` with weekly/monthly/custom filters; `GET /api/analytics/export.csv` |
| ML insights | `POST /api/ml/categorize`; `GET /api/ml/prediction`; `/anomalies`; `/duplicates`; `/insights` |
| Profile/security | `GET/PUT /api/users/profile`; `POST/DELETE/GET /api/users/profile/photo`; `POST /api/users/password` |

Dates are ISO `YYYY-MM-DD`; report date filters are inclusive. Weekly analytics use Monday through Sunday. Monetary API values are decimal-formatted strings.

## Seed data

`flask --app app init-db` seeds the eight built-in expense categories idempotently. There is no development user, sample financial transaction seed, or default account/password. Register an account through the UI or `POST /api/auth/register`. Category writes require setting the registered email in `ADMIN_EMAILS`.

## Tests and build checks

Backend and frontend checks:

```powershell
Set-Location backend
python -m pip install -r requirements.txt
python -m pytest
Set-Location ..\frontend
npm ci
npm test
npm run build
```

Backend tests use isolated in-memory SQLite databases. Frontend tests exercise registration/login interactions using mocked API context; they do not call a live API or database.

## Troubleshooting and known limitations

- If `/api/health` fails, verify MySQL is running, the database/user exists, `backend/.env` matches the local MySQL configuration, and the account can connect.
- If the browser reports a CORS or login/session issue, use a hostname consistently (`localhost` or `127.0.0.1`), include the frontend origin in `FRONTEND_ORIGINS`, and keep credentials enabled.
- For a missing database table/column, back up the database and run `flask --app app init-db` and `flask --app app migrate-profile`; these are non-resetting commands.
- If ML dependencies are unavailable, categorization rules and the prediction/statistical fallbacks remain available; predictions may be unavailable when history is insufficient.
- Password reset by email and email verification are not implemented. Users can change their password after signing in from Profile → Account & Security; email changes require the current password.
- Profile images are private authenticated API responses. Multi-instance deployments need shared durable photo storage and HTTPS; the supplied defaults target local development and are not, by themselves, a production deployment configuration.
