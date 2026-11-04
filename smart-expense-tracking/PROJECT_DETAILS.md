# SpendWise — Project Details

SpendWise is a web application for tracking personal finances and managing organization expenses. Users can record income and expenses, set monthly budgets, review dashboards and reports, and manage their profiles. A separate Corporate Mode supports organization expense submissions and approvals. Optional machine-learning-style features provide suggestions and estimates; they do not make financial decisions or modify transactions.

## Project at a glance

| Area | Details |
|---|---|
| Frontend | React, React Router, Vite, Axios, Recharts |
| Backend | Python, Flask, Flask-SQLAlchemy, SQLAlchemy |
| Main database | MySQL, accessed through PyMySQL |
| Test database | Isolated in-memory SQLite |
| Personal authentication | Hashed passwords and signed HTTP-only cookie sessions |
| API security | CSRF token required for state-changing requests; credentialed CORS with configured origins |
| Currency and precision | Monetary values use decimal database columns and decimal-formatted API values |
| Main product areas | Personal finance, corporate expenses, analytics/reports, profile management, synthetic dataset demo |
| Appearance | Purple-branded Light, Dark, and System themes with persistent user preference |

## Features

### Personal finance

- Register, sign in, sign out, and check the active session.
- Create, view, edit, filter, sort, search, paginate, and delete personal expenses.
- Manage income records with inclusive date-range filtering.
- Create overall or category-specific monthly budgets that repeat from their start month until deleted; later budget versions take effect from their own start month.
- Review a dashboard with lifetime totals, selected-month figures, recent transactions, six-month trends, category breakdowns, budget progress, and insights.
- Analyze weekly (Monday–Sunday), monthly, or custom inclusive date ranges, with prior-period comparisons, category totals, and largest transactions.
- Export filtered analytics as CSV, including corresponding summary totals.
- Update profile details, upload/remove a profile photo, change a password, and change an email after confirming the current password.
- Choose Light, Dark, or System appearance from the application navbar, Profile settings, and public authentication/demo screens; the choice is stored locally and system preference changes are followed.
- Use predefined expense categories. Category changes are restricted to administrator emails configured by the operator.

### Corporate workspace

Corporate Mode keeps organization finances separate from Personal Mode records. An organization can be created with an initial Admin account, and members can join with its active joining code. Admins can update organization details, manage departments and member access, assign department managers, regenerate the joining code, and review an organization audit log. Admin-managed member creation is available for users who need a directly provisioned account.

Roles are Admin, Employee, Manager, Finance Officer, and Executive. Expenses support the Employee → Manager → Finance Officer review flow, searchable queues, approval history, reviewer notes, and required rejection reasons. Employees see their own expenses, managers are scoped to the departments they manage, and finance/admin/executive roles have organization-wide visibility. Approved expenses can be tracked as paid without changing the existing expense status values. PDF, PNG, and JPG receipts are stored outside the static web root and require an authenticated, authorized download.

Role-scoped reports include filtered transaction lists, status totals, department/category/employee/month summaries, and formula-safe CSV export. Corporate API mutations use the existing cookie-session, CSRF, and organization membership checks.

The repeatable `flask --app app migrate-corporate-workflows` command adds the workflow columns and approval/audit tables to an existing corporate schema. It does not replace existing corporate expenses or modify personal tables. Back up the database before applying it. Configure `CORPORATE_RECEIPT_DIR` to persistent storage in deployments whose application filesystem is ephemeral; otherwise receipts use `backend/instance/corporate_receipts`.

The optional `seed-corporate-demo` command creates a fictional organization and sample expenses spanning three calendar months. It refuses to overwrite an existing demo organization or colliding demo accounts.

### Optional insights and dataset demo

- **Category suggestions:** TF-IDF/logistic-regression baseline over static example phrases, with keyword fallback rules. A user can accept or override a suggestion.
- **Spending estimates:** Historical daily-average estimate after at least three completed months; linear regression is used when at least six completed months are available. An estimate is withheld if history is insufficient.
- **Unusual spending:** Same-user, same-category median/MAD comparisons.
- **Possible duplicates:** Conservative candidates based on matching transaction details and normalized description/vendor text.
- **Spending patterns:** Rule-based insights.

These are advisory baselines, not financial advice, fraud findings, or automatic actions. They do not merge, delete, or change transactions, and the application does not send records to a third-party model service.

The public `/demo` page is a separate synthetic-data demonstration. It displays INR aggregate statistics and an experimental estimate based on profile attributes. Its imported snapshots live in a dedicated table and do not become personal transactions or train the personal transaction models. The source CSV is not included in the repository; its original source URL and redistribution license were not provided. See [backend/ml/datasets/DATASET_SOURCES.md](backend/ml/datasets/DATASET_SOURCES.md) for suitability and limitations.

## Architecture and code map

```text
backend/
  app.py                 Flask app factory, API registration, CLI commands, error handlers
  config.py              Environment-driven database, CORS, and session settings
  extensions.py          Shared SQLAlchemy extension
  models/                Personal and corporate database models
  routes/                REST API endpoints and request handling
  services/              Validation, corporate workflow, analytics, dashboard, and ML logic
  ml/                    Synthetic snapshot import and preprocessing
  tests/                 Backend API/service tests

frontend/
  src/App.jsx            Routing and workspace protection
  src/context/           Authentication/session state
  src/components/        Shared forms, navigation, dialogs, and UI
  src/pages/             Personal finance, analytics, corporate, and demo screens
  src/services/api.js    Axios configuration and frontend API clients
  src/styles/            Application styles
  src/test/               Frontend test setup

database/
  README.md              MySQL setup, permissions, and schema initialization
```

The backend registers blueprints for authentication, analytics, budgets, categories, corporate functions, dashboard, synthetic demo, expenses, income, ML, and users. Routes delegate business rules and calculations to services. The frontend uses protected routes and chooses a workspace home based on the authenticated user's workspace mode.

## Data model and calculations

Personal data is associated with its owner. Core tables are `user`, `category`, `expenses`, `income`, and `budgets`. Corporate data is stored separately in `corporate_organizations`, `corporate_departments`, `corporate_memberships`, and `corporate_expenses`, with approval history in `corporate_expense_approvals` and administrative activity in `corporate_audit_logs`. Receipt files are stored separately from MySQL. Synthetic demo snapshots are isolated in `synthetic_finance_snapshots`.

Expense, income, and budget monetary values use `DECIMAL(10,2)`/SQLAlchemy `Numeric(10,2)`; corporate expenses use `Numeric(12,2)`. Authoritative financial totals use database `SUM` and Python `Decimal`, rather than floating-point or Pandas/NumPy aggregation. A personal budget version is unique for a user, month, year, and category scope; the scope also distinguishes the overall budget from category budgets. The latest version whose start month is not after the viewed month is active. Deleting a budget removes all versions in that scope so an older recurring version cannot unexpectedly resume.

Dashboard lifetime income, expenses, and balance are separate from selected-month totals. Monthly savings rate is `(monthly income - monthly expenses) / monthly income`. Average daily spending divides by elapsed days for the current month or all days in a completed month.

## API overview

Base API URL: `http://localhost:5000/api` in local development. Health, CSRF bootstrap, personal registration/login, corporate organization creation/joining, and synthetic demo endpoints are public; other account and financial routes require authentication. State-changing requests, including public registration and corporate organization actions, use `X-CSRF-Token`. Personal financial reads and writes are user-scoped. Dates use ISO `YYYY-MM-DD`; analytics date ranges are inclusive.

| Group | Endpoints |
|---|---|
| Health and authentication | `GET /health`; `GET /auth/csrf`; `POST /auth/register`; `POST /auth/login`; `POST /auth/logout`; `GET /auth/me` |
| Expenses | `GET/POST /expenses`; `GET/PUT/DELETE /expenses/<id>` |
| Income | `GET/POST /income`; `GET/PUT/DELETE /income/<id>` |
| Budgets | `GET/POST /budgets`; `GET/PUT/DELETE /budgets/<id>` |
| Categories | `GET/POST /categories`; `PUT/DELETE /categories/<id>` |
| Dashboard | `GET /dashboard/summary`; `/dashboard/recent-transactions`; `/dashboard/monthly-trends`; `/dashboard/category-breakdown`; `/dashboard/budget-progress` |
| Analytics | `GET /analytics`; `GET /analytics/export.csv` |
| ML insights | `POST /ml/categorize`; `GET /ml/prediction`; `/ml/anomalies`; `/ml/duplicates`; `/ml/insights` |
| Profile and account security | `GET/PUT /users/profile`; `GET/POST/DELETE /users/profile/photo`; `POST /users/password` |
| Corporate | `/corporate/organizations`, `/corporate/join`, `/corporate/overview`, `/corporate/organization`, `/corporate/departments`, `/corporate/members`, `/corporate/expenses`, `/corporate/approvals`, `/corporate/reimbursements`, `/corporate/reports`, and `/corporate/audit-log` |
| Public synthetic demo | `GET /demo/analytics`; `GET /demo/ml/evaluation`; `POST /demo/ml/estimate-monthly-expenses` |

## Local setup

### Requirements

- Python with `venv` support
- Node.js and npm
- MySQL

### 1. Configure MySQL and the backend

Follow [database/README.md](database/README.md) to create a database and least-privilege application account. In PowerShell, from the project root:

```powershell
Copy-Item backend/.env.example backend/.env
Set-Location backend
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Set local values in `backend/.env`, including `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`, and a long random `SECRET_KEY`. Do not commit the real `.env` file. Then initialize the database and start the API:

```powershell
python -m flask --app app init-db
python -m flask --app app migrate-profile
python -m flask --app app run
```

The API listens at `http://localhost:5000`. `GET /api/health` checks database connectivity. `init-db` creates missing tables and seeds built-in categories without resetting existing tables. The repeatable `migrate-profile` command adds optional profile fields to an existing user table.

### 2. Start the frontend

In another PowerShell terminal from the project root:

```powershell
Set-Location frontend
npm install
npm run dev
```

Vite normally serves the application at `http://localhost:5173`. The frontend API base URL can be set using `VITE_API_BASE_URL`; use a consistent hostname for frontend and API (`localhost` or `127.0.0.1`) and allow the frontend origin in `FRONTEND_ORIGINS`.

### Configuration reference

Backend configuration is read from environment variables:

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Stable, random Flask session-signing key |
| `MYSQL_HOST`, `MYSQL_PORT` | MySQL server location |
| `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE` | Database connection |
| `FRONTEND_ORIGINS` | Comma-separated allowed browser origins |
| `SESSION_COOKIE_SECURE` | Set `true` when serving over HTTPS |
| `FLASK_DEBUG` | Local development debug setting |
| `ADMIN_EMAILS` | Comma-separated existing accounts allowed to manage categories |
| `PROFILE_UPLOAD_DIR` | Optional persistent directory for private profile photos |

The frontend reads `VITE_API_BASE_URL`. Templates contain placeholders; never commit actual credentials or secrets.

## Database and privacy notes

- `init-db` creates missing tables and seeds eight built-in categories: Food, Transportation, Shopping, Bills, Entertainment, Healthcare, Education, and Other.
- There is no default personal user or personal transaction seed. Register through the UI or API.
- Corporate demo data is optional and separate from personal records.
- Backend tests use in-memory SQLite and do not access the configured MySQL database.
- Profile photos are decoded and re-encoded as JPEG, PNG, or WebP, limited to 5 MB and 20 megapixels, stored outside the static web root, and served only to the authenticated owner.
- Password reset email and email verification are not implemented. Password changes require signing in; email changes require the current password.
- Local-development settings are not, on their own, a production deployment configuration. Production use requires HTTPS, stable secrets, durable shared photo storage for multi-instance deployments, and environment-specific configuration.

## Tests and checks

From the project root:

```powershell
Set-Location backend
python -m pip install -r requirements.txt
python -m pytest
Set-Location ..\frontend
npm ci
npm test
npm run build
```

Backend tests exercise APIs and services against isolated SQLite databases. Frontend tests run with Vitest and mocked API/context behavior; they do not require a live backend or database.

## Further documentation

- [README.md](README.md) — project runbook, configuration details, API notes, troubleshooting, and feature limitations.
- [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) — implementation phases, important files, and verification notes.
- [database/README.md](database/README.md) — MySQL database and optional corporate demo setup.
- [backend/ml/datasets/DATASET_SOURCES.md](backend/ml/datasets/DATASET_SOURCES.md) — synthetic dataset provenance and suitability.
