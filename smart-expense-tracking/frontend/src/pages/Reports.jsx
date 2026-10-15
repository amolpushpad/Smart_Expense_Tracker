import { useState } from 'react';
import AnalyticsPeriodFilter from '../components/AnalyticsPeriodFilter';
import PageHeader from '../components/PageHeader';
import { useAnalyticsReport } from '../hooks/useAnalyticsReport';
import { analyticsApi, getApiErrorMessage } from '../services/api';
import '../styles/analytics.css';
import '../styles/expenses.css';

const currency = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 });
const money = value => currency.format(Number(value || 0));

function downloadCsv(blob, fileName) {
	const url = URL.createObjectURL(blob);
	const link = document.createElement('a');
	link.href = url;
	link.download = fileName;
	document.body.appendChild(link);
	link.click();
	link.remove();
	URL.revokeObjectURL(url);
}

export default function Reports() {
	const filter = useAnalyticsReport();
	const [exporting, setExporting] = useState(false);
	const [exportError, setExportError] = useState('');
	const report = filter.report;

	const exportReport = async () => {
		setExporting(true);
		setExportError('');
		try {
			const response = await analyticsApi.exportCsv(filter.params);
			const safePeriod = report.period.type === 'custom'
				? `${report.period.start_date}-to-${report.period.end_date}`
				: report.period.type === 'weekly'
					? `week-${report.period.start_date}`
					: `${report.period.start_date.slice(0, 7)}`;
			downloadCsv(response.data, `financial-report-${safePeriod}.csv`);
		} catch (requestError) {
			setExportError(getApiErrorMessage(requestError, 'Unable to export the report. Please try again.'));
		} finally {
			setExporting(false);
		}
	};

	return <section className="analytics-page">
		<PageHeader title="Reports" description="Review a date-filtered financial summary and export it as CSV." />
		<div className="analytics-toolbar">
			<AnalyticsPeriodFilter {...filter} />
			<div className="analytics-report-actions">
				<button className="secondary-button" type="button" onClick={filter.refresh} disabled={filter.loading}>{filter.loading ? 'Loading...' : 'Refresh'}</button>
				<button className="primary-btn" type="button" onClick={exportReport} disabled={!report || filter.loading || exporting}>{exporting ? 'Preparing CSV...' : 'Export CSV'}</button>
			</div>
		</div>
		{filter.error && <div className="analytics-alert" role="alert">{filter.error}</div>}
		{exportError && <div className="analytics-alert" role="alert">{exportError}</div>}
		{filter.loading && !report && <div className="analytics-loading" role="status"><span className="analytics-spinner" /> Generating report for the selected period...</div>}
		{report && <>
			<div className="analytics-period-heading">
				<div><h3>{report.period.label}</h3><p>Both boundary dates are included. The CSV contains these records and the same calculated summary totals.</p></div>
				{filter.loading && <span role="status">Updating...</span>}
			</div>
			<section className="analytics-summary-grid report-summary-grid">
				<article className="analytics-summary-card"><span>Total income</span><strong>{money(report.summary.total_income)}</strong></article>
				<article className="analytics-summary-card"><span>Total expenses</span><strong>{money(report.summary.total_expenses)}</strong></article>
				<article className="analytics-summary-card"><span>Savings</span><strong className={Number(report.summary.savings) < 0 ? 'analytics-negative' : 'analytics-positive'}>{money(report.summary.savings)}</strong></article>
				<article className="analytics-summary-card"><span>Balance</span><strong>{money(report.summary.balance)}</strong></article>
			</section>
			<div className="analytics-report-meta">
				<span>{report.transactions.length} transactions</span>
				<span>Largest transaction: {report.largest_transaction ? `${money(report.largest_transaction.amount)} (${report.largest_transaction.transaction_type})` : 'None'}</span>
				<span>Highest spending category: {report.highest_spending_category?.category_name || 'None'}</span>
			</div>
			<div className="expense-table-wrap">
				<table className="expense-table analytics-report-table">
					<thead><tr><th>Date</th><th>Type</th><th>Category</th><th>Description</th><th className="amount-cell">Income</th><th className="amount-cell">Expense</th></tr></thead>
					<tbody>
						{report.transactions.map((transaction, index) => <tr key={`${transaction.transaction_type}-${transaction.date}-${index}`}>
							<td>{new Date(`${transaction.date}T00:00:00`).toLocaleDateString()}</td>
							<td><span className={`analytics-type ${transaction.transaction_type}`}>{transaction.transaction_type}</span></td>
							<td>{transaction.category || '—'}</td>
							<td>{transaction.description}</td>
							<td className="amount-cell report-income">{transaction.income === '0.00' ? '—' : money(transaction.income)}</td>
							<td className="amount-cell report-expense">{transaction.expense === '0.00' ? '—' : money(transaction.expense)}</td>
						</tr>)}
						{report.transactions.length === 0 && <tr><td colSpan="6" className="table-message">No transactions recorded in this date range.</td></tr>}
					</tbody>
					{report.transactions.length > 0 && <tfoot><tr><th colSpan="4">Period totals</th><th className="amount-cell report-income">{money(report.summary.total_income)}</th><th className="amount-cell report-expense">{money(report.summary.total_expenses)}</th></tr></tfoot>}
				</table>
			</div>
		</>}
	</section>;
}
