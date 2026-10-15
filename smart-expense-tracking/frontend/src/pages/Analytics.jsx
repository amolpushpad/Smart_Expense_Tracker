import {
	Bar,
	BarChart,
	CartesianGrid,
	Legend,
	Line,
	LineChart,
	ResponsiveContainer,
	Tooltip,
	XAxis,
	YAxis,
} from 'recharts';
import AnalyticsPeriodFilter from '../components/AnalyticsPeriodFilter';
import PageHeader from '../components/PageHeader';
import { useAnalyticsReport } from '../hooks/useAnalyticsReport';
import { Link } from 'react-router-dom';
import '../styles/analytics.css';

const currency = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 });
const percent = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 });
const money = value => currency.format(Number(value || 0));

function Summary({ report }) {
	const summary = report.summary;
	const change = report.previous_period;
	const direction = Number(change.change_amount);
	return <>
		<section className="analytics-summary-grid">
			<article className="analytics-summary-card"><span>Income</span><strong>{money(summary.total_income)}</strong></article>
			<article className="analytics-summary-card"><span>Expenses</span><strong>{money(summary.total_expenses)}</strong></article>
			<article className="analytics-summary-card"><span>Savings</span><strong className={Number(summary.savings) < 0 ? 'analytics-negative' : 'analytics-positive'}>{money(summary.savings)}</strong><small>Income minus expenses</small></article>
			<article className="analytics-summary-card"><span>Balance for period</span><strong>{money(summary.balance)}</strong><small>Selected-period net total</small></article>
		</section>
		<div className={`analytics-comparison${direction > 0 ? ' increased' : direction < 0 ? ' decreased' : ''}`}>
			<strong>Spending vs previous period</strong>
			<span>{money(change.expenses)} previously ({change.start_date} to {change.end_date})</span>
			<b>{direction > 0 ? '↑' : direction < 0 ? '↓' : '→'} {money(Math.abs(direction))}{change.change_percentage === null ? '' : ` (${percent.format(Math.abs(Number(change.change_percentage)))}%)`}{direction > 0 ? ' more' : direction < 0 ? ' less' : ' change'}</b>
		</div>
	</>;
}

export default function Analytics() {
	const filter = useAnalyticsReport();
	const report = filter.report;

	return <section className="analytics-page">
		<PageHeader title="Analytics" description="Explore weekly and monthly financial trends from your transactions." />
		<div className="analytics-toolbar">
			<AnalyticsPeriodFilter {...filter} />
			<button className="secondary-button" type="button" onClick={filter.refresh} disabled={filter.loading}>{filter.loading ? 'Loading...' : 'Refresh'}</button>
		</div>
		{filter.error && <div className="analytics-alert" role="alert">{filter.error}</div>}
		{filter.loading && !report && <div className="analytics-loading" role="status"><span className="analytics-spinner" /> Loading analytics for the selected period...</div>}
		{report && <>
			<div className="analytics-period-heading">
				<div><h3>{report.period.label}</h3><p>{report.period.type === 'weekly' ? 'Calendar week runs Monday through Sunday.' : 'Date ranges include both their start and end dates.'}</p></div>
				{filter.loading && <span role="status">Updating...</span>}
			</div>
			<Summary report={report} />
			<section className="analytics-chart-grid">
				<article className="panel analytics-panel analytics-wide">
					<div className="analytics-panel-title"><div><h2>{report.period.type === 'weekly' ? 'Weekly income vs expenses' : 'Income and spending trend'}</h2><p>{report.series.granularity === 'day' ? 'Daily totals in the selected range.' : 'Monthly totals in the selected range.'}</p></div></div>
					{report.series.items.some(item => Number(item.income) || Number(item.expenses)) ? <div className="analytics-chart">
						<ResponsiveContainer width="100%" height="100%"><LineChart data={report.series.items} margin={{ top: 10, right: 15, left: 4, bottom: 6 }}>
							<CartesianGrid strokeDasharray="3 3" vertical={false} />
							<XAxis dataKey="label" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
							<YAxis tick={{ fontSize: 10 }} tickFormatter={value => `₹${Number(value).toLocaleString('en-IN')}`} width={72} />
							<Tooltip formatter={value => money(value)} />
							<Legend />
							<Line type="monotone" dataKey="income" name="Income" stroke="#188354" strokeWidth={2.5} dot={report.series.items.length <= 14} />
							<Line type="monotone" dataKey="expenses" name="Expenses" stroke="#d35248" strokeWidth={2.5} dot={report.series.items.length <= 14} />
						</LineChart></ResponsiveContainer>
					</div> : <div className="analytics-empty">No transactions in this date range.</div>}
				</article>
				<article className="panel analytics-panel">
					<div className="analytics-panel-title"><div><h2>Category spending</h2><p>Total expense by category.</p></div></div>
					{report.categories.length ? <div className="analytics-category-chart">
						<ResponsiveContainer width="100%" height="100%"><BarChart data={report.categories} layout="vertical" margin={{ top: 4, right: 20, left: 8, bottom: 4 }}>
							<CartesianGrid strokeDasharray="3 3" horizontal={false} />
							<XAxis type="number" tick={{ fontSize: 10 }} tickFormatter={value => `₹${Number(value).toLocaleString('en-IN')}`} />
							<YAxis type="category" dataKey="category_name" width={95} tick={{ fontSize: 10 }} />
							<Tooltip formatter={value => money(value)} />
							<Bar dataKey="amount" name="Expenses" fill="#635bff" radius={[0, 5, 5, 0]} />
						</BarChart></ResponsiveContainer>
					</div> : <div className="analytics-empty">No expense transactions to break down.</div>}
					{report.highest_spending_category && <p className="analytics-highlight">Highest spending: <strong>{report.highest_spending_category.category_name}</strong> · {money(report.highest_spending_category.amount)}</p>}
				</article>
				<article className="panel analytics-panel">
					<div className="analytics-panel-title"><div><h2>Largest transaction</h2><p>Highest single income or expense.</p></div></div>
					{report.largest_transaction ? <div className="analytics-largest">
						<span className={`analytics-type ${report.largest_transaction.transaction_type}`}>{report.largest_transaction.transaction_type}</span>
						<strong>{money(report.largest_transaction.amount)}</strong>
						<span>{report.largest_transaction.description}</span>
						<small>{report.largest_transaction.date}{report.largest_transaction.category ? ` · ${report.largest_transaction.category}` : ''}</small>
					</div> : <div className="analytics-empty">No transactions in this period.</div>}
				</article>
				{report.budget && <article className="panel analytics-panel">
					<div className="analytics-panel-title"><div><h2>Monthly budget</h2><p>Actual spending against the selected month’s budget.</p></div></div>
					<div className="analytics-budget-summary"><span>Budget <strong>{money(report.budget.monthly_budget)}</strong></span><span>Spent <strong>{money(report.budget.budgeted_spending)}</strong></span><span>Remaining <strong className={report.budget.over_budget ? 'analytics-negative' : ''}>{money(report.budget.remaining_budget)}</strong></span></div>
					{report.budget.monthly_budget !== '0.00' ? <div className="analytics-budget-progress" role="progressbar" aria-label="Monthly budget utilization" aria-valuemin="0" aria-valuemax="100" aria-valuenow={Math.min(100, Number(report.budget.budget_utilization || 0))}><span className={report.budget.over_budget ? 'over' : ''} style={{ width: `${Math.min(100, Math.max(0, Number(report.budget.budget_utilization || 0)))}%` }} /></div> : <p className="analytics-muted">No budget set for this month.</p>}
					{report.budget.budget_utilization !== null && <p className="analytics-highlight">{percent.format(Number(report.budget.budget_utilization))}% utilized{report.budget.over_budget ? ' — budget exceeded.' : '.'}</p>}
				</article>}
			</section>
			<p className="analytics-daily-average">Average daily spending in this period: <strong>{money(report.summary.average_daily_spending)}</strong></p>
			<div className="analytics-footer-link">Need a downloadable report? <Link to="/reports">Go to Reports and CSV export</Link></div>
		</>}
	</section>;
}
