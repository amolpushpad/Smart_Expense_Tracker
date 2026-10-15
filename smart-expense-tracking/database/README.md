# MySQL Database

The schema contains the existing Phase 2 `user` and `category` tables, `expenses`, `income`, and `budgets`. Income and budget records reference their owning user; budgets can optionally reference a category. Category deletion is blocked while expenses or budgets reference that category. The singular existing table names are retained to preserve Phase 2 database data. Budget records are unique by user, category (including an overall-budget scope), month, and year.

Create a local database and least-privilege application account in MySQL:

```sql
CREATE DATABASE smart_expense_tracking CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'smart_expense_user'@'localhost' IDENTIFIED BY 'choose-a-local-password';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES
	ON smart_expense_tracking.* TO 'smart_expense_user'@'localhost';
FLUSH PRIVILEGES;
```

Copy `backend/.env.example` to `backend/.env`, set the connection values and a long random `SECRET_KEY`, then run `python -m flask --app app init-db` from the `backend` directory. This command creates missing tables and seeds the predefined categories idempotently without resetting existing tables. Set `ADMIN_EMAILS` to a comma-separated list of existing account email addresses authorized to manage categories. Never commit the real `.env` file.
