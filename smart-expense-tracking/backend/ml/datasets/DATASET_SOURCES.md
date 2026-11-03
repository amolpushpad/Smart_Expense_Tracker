# SpendWise Dataset Sources and Suitability

## User-provided synthetic personal-finance CSV

| Property | Finding |
|---|---|
| File name | `synthetic_personal_finance_dataset.csv` |
| Source | Supplied as a local file by the project owner; original publisher and source URL were not provided |
| License | Not provided; redistribution rights cannot be verified |
| Format | CSV |
| Records / columns | 32,424 rows / 20 columns |
| Content | One synthetic profile snapshot per unique `user_id`; age, employment, monthly income, monthly expense total, savings, loan fields, credit score, region, and a single record date |
| Date range | 2021-07-23 through 2025-07-22 |
| Source currency | USD |
| Demo conversion | Fixed ₹95 per USD; imported amounts are stored as INR |
| Missing values | 19,429 missing `loan_type` values; these correspond to the 19,429 `has_loan = No` records |
| Exact duplicate rows / duplicate IDs | 0 / 0 |
| Suitability | Aggregate, explicitly synthetic demonstration only. It is not a transaction dataset and its provenance/license is unknown. |

The source CSV is intentionally not copied into the repository. Provide its local path to the isolated importer; the demo reads only records from the dedicated synthetic snapshot table.

## Use limitations

- The file is synthetic, and no trustworthy public source, version, or license was supplied. It is not represented as a genuine or externally validated financial dataset.
- Each user appears once. The date describes the snapshot, not an ordered series of that user's activity. Monthly values are profile attributes, not transaction rows.
- There are no transaction descriptions, merchants, expense categories, or transaction timestamps. Do not convert monthly totals into invented ledger entries.
- The dataset cannot train or validate expense categorization, duplicate detection, personal anomaly detection, or next-month spending forecasts.
- The UI displays INR cohort aggregates and a limited cross-sectional model. Imported records are isolated from the application's real user income and expense tables.
- USD fields are converted to INR at the selected fixed ₹95/USD rate. The import CLI refuses to merge or overwrite a different dataset or rate.
- The model estimates reported monthly expense totals from profile fields, evaluated on a deterministic held-out split against a mean baseline. This is not a forecast, does not demonstrate real-world predictive value, and must not be used as financial advice.
- Raw source records, including synthetic IDs, are not served publicly. Only aggregate outputs and a user-submitted estimate are exposed; estimates are not persisted.

## Model-training data status

No externally sourced public training dataset is approved by this project. The owner-provided synthetic snapshots are used only for the explicitly limited demo described above. Before adding another model-training dataset, record a verified original URL, version, license/terms, schema, and task-specific suitability here. Fraud labels must not be presented as labels for unusual personal spending. Evaluation metrics must be generated from an appropriate held-out split; do not claim metrics beyond this dataset-specific profile task.
