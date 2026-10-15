import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
	Bar,
	BarChart,
	CartesianGrid,
	Cell,
	Legend,
	Line,
	LineChart,
	Pie,
	PieChart,
	ResponsiveContainer,
	Tooltip,
	XAxis,
	YAxis,
} from 'recharts';
import PageHeader from '../components/PageHeader';
import SummaryCard from '../components/SummaryCard';
import { dashboardApi, getApiErrorMessage } from '../services/api';
import '../styles/dashboard.css';

const currency = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 });
const percent = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 1 });
const chartColors = ['#635bff', '#20a77a', '#f59e0b', '#2681d8', '#e05245', '#8e62cc', '#16a6b5', '#768398'];

function localIsoDate(value = new Date()) {
	const date = new Date(value);
	date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
	return date.toISOString().slice(0, 10);
}

function currentMonth() {
	return localIsoDate().slice(0, 7);
}

function money(value) {
	return currency.format(Number(value || 0));
}

function periodMonth(period) {
	return new Date(Number(period.year), Number(period.month) - 1, 1).toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
}

function ProgressBudget({ budget }) {
	const value = Number(budget.utilization_percentage || 0);
	return <div className="dashboard-budget" key={budget.budget_id}>
		<div className="dashboard-budget-heading">
			<div><strong>{budget.category_name || 'Overall budget'}</strong><span>{budget.category_id === null ? 'Overall monthly limit' : 'Category limit'}</span></div>
			<b>{money(budget.spent_amount)} / {money(budget.amount)}</b>
		</div>
		<div className="dashboard-progress" role="progressbar" aria-label={`${budget.category_name || 'Overall'} budget used`} aria-valuemin="0" aria-valuemax="100" aria-valuenow={Math.min(100, value)}>
			<span className={budget.over_budget ? 'is-over' : ''} style={{ width: `${Math.min(100, Math.max(0, value))}%` }} />
		</div>
		<div className="dashboard-budget-caption"><span>{percent.format(value)}% used</span><span>{budget.over_budget ? `Over by ${money(Math.abs(Number(budget.remaining_amount)))}` : `${money(budget.remaining_amount)} remaining`}</span></div>
	</div>;
}

function DashboardSkeleton() {
	return <div className="dashboard-skeleton" role="status" aria-label="Loading dashboard">
		<span className="visually-hidden">Loading dashboard data...</span>
		<div className="summary-grid">{Array.from({ length: 6 }, (_, index) => <SummaryCard key={index} loading title="Loading" />)}</div>
		<div className="dashboard-panels">{Array.from({ length: 4 }, (_, index) => <div className="dashboard-panel-skeleton" key={index} />)}</div>
	</div>;
}

function changeSummary(comparison) {
	const previous = Number(comparison.expenses);
	const delta = Number(comparison.change_amount);
	if (previous <= 0) return { label: 'No previous spending to compare', tone: 'neutral' };
	const change = Math.abs(delta / previous * 100);
	return {
		label: `${delta > 0 ? '↑' : delta < 0 ? '↓' : '→'} ${percent.format(change)}% vs previous period`,
		tone: delta > 0 ? 'negative' : delta < 0 ? 'positive' : 'neutral',
	};
}

function InsightPanel({ dashboard, view }) {
	const insights = dashboard.mlInsights || {};
	const errors = insights.errors || {};
	const prediction = insights.prediction;
	const anomalies = insights.anomalies || [];
	const duplicates = insights.duplicates || [];
	const patterns = insights.spending_patterns || [];
	const hasError = Object.keys(errors).length > 0;

	return <article className="panel dashboard-panel dashboard-ai-insights">
		<div className="dashboard-panel-title"><div><h2>AI and smart insights</h2><p>Model predictions and transparent statistical checks; these are advisory, not financial advice.</p></div></div>
		{view === 'monthly' && <section className="dashboard-ai-section prediction-section">
			<h3>Predicted month-end spending</h3>
			{errors.prediction ? <p className="dashboard-ai-error" role="alert">{errors.prediction}</p>
				: prediction?.sufficient_history ? <div className="dashboard-prediction-values">
					<div><span>Actual spending so far</span><strong>{prediction.actual_spending_to_date === null ? 'Not available' : money(prediction.actual_spending_to_date)}</strong></div>
					<div><span>Estimated month-end total</span><strong>{money(prediction.prediction_value)}</strong></div>
					<p>Estimate · {prediction.model === 'scikit_learn_linear_regression' ? 'Scikit-learn linear regression' : 'Historical daily-average baseline'} · based on {prediction.history_months} completed months. {prediction.explanation}</p>
				</div> : <div className="dashboard-ai-empty">{prediction?.explanation || 'Not enough historical data for a prediction.'}</div>}
		</section>}
		<section className="dashboard-ai-section">
			<h3>Spending patterns</h3>
			{errors.spending_patterns ? <p className="dashboard-ai-error" role="alert">{errors.spending_patterns}</p>
				: patterns.length ? <ul className="dashboard-insights">{patterns.map((pattern, index) => <li className="info" key={`${pattern.type}-${index}`}>{pattern.message} <small>{pattern.method.replaceAll('_', ' ')}</small></li>)}</ul>
					: <div className="dashboard-ai-empty">No notable patterns in this period.</div>}
		</section>
		<section className="dashboard-ai-section">
			<h3>Unusual-spending flags</h3>
			{errors.anomalies ? <p className="dashboard-ai-error" role="alert">{errors.anomalies}</p>
				: anomalies.length ? <ul className="dashboard-ai-list">{anomalies.slice(0, 4).map(item => <li key={item.expense_id}><strong>{item.category} · {money(item.amount)}</strong><span>{item.date} · {item.description}</span><small>{item.reason}</small></li>)}</ul>
					: <div className="dashboard-ai-empty">No unusual spending flags. Flags compare amounts with your own category history and do not indicate fraud.</div>}
		</section>
		<section className="dashboard-ai-section">
			<h3>Possible duplicate expenses</h3>
			{errors.duplicates ? <p className="dashboard-ai-error" role="alert">{errors.duplicates}</p>
				: duplicates.length ? <ul className="dashboard-ai-list">{duplicates.slice(0, 4).map(pair => <li key={`${pair.first.expense_id}-${pair.second.expense_id}`}><strong>{money(pair.first.amount)} · {pair.first.date}</strong><span>{pair.first.description || pair.first.vendor} / {pair.second.description || pair.second.vendor}</span><small>{pair.matching_reasons.join(', ')}. Please review; records were not changed.</small></li>)}</ul>
					: <div className="dashboard-ai-empty">No possible duplicate expenses found.</div>}
		</section>
		{hasError && <p className="dashboard-ai-footnote">Some insight checks were unavailable. Dashboard totals and charts are still based on the financial records.</p>}
		<Link className="dashboard-ai-link" to="/analytics">Explore analytics and insights</Link>
	</article>;
}

export default function Dashboard() {
	const [view, setView] = useState('monthly');
	const [monthPeriod, setMonthPeriod] = useState(currentMonth);
	const [weekDate, setWeekDate] = useState(localIsoDate);
	const [dashboard, setDashboard] = useState(null);
	const [loading, setLoading] = useState(true);
	const [refreshing, setRefreshing] = useState(false);
	const [error, setError] = useState('');
	const [reloadKey, setReloadKey] = useState(0);
	const [refreshLabel, setRefreshLabel] = useState('Refresh');
	const anchorDate = view === 'weekly' ? weekDate : `${monthPeriod}-01`;
	const [year, month] = anchorDate.slice(0, 7).split('-');

	const load = useCallback(async ({ background = false } = {}) => {
		if (background) setRefreshing(true);
		else setLoading(true);
		setError('');
		try {
			const data = await dashboardApi.load({
				period: view,
				month: Number(month),
				year: Number(year),
				weekDate,
			});
			setDashboard(data);
			setRefreshLabel('Refresh');
		} catch (requestError) {
			setDashboard(null);
			setError(getApiErrorMessage(requestError));
			setRefreshLabel('Retry');
		} finally {
			setLoading(false);
			setRefreshing(false);
		}
	}, [view, month, year, weekDate]);

	useEffect(() => {
		load();
	}, [load, reloadKey]);

	useEffect(() => {
		const onDataChanged = () => setReloadKey(value => value + 1);
		window.addEventListener('dashboard:data-changed', onDataChanged);
		return () => window.removeEventListener('dashboard:data-changed', onDataChanged);
	}, []);

	const report = dashboard?.report;
	const summary = report?.summary;
	const trends = report?.series?.items || [];
	const categories = report?.categories || [];
	const budgets = dashboard?.budgets || [];
	const transactions = dashboard?.transactions || [];
	const budgetSummary = view === 'monthly'
		? report?.budget
		: {
			monthly_budget: dashboard?.summary.monthly_budget,
			budget_utilization: dashboard?.summary.budget_utilization,
			remaining_budget: dashboard?.summary.remaining_budget,
			over_budget: dashboard?.summary.budget_exceeded,
		};
	const comparison = report ? changeSummary(report.previous_period) : null;
	const net = summary?.balance;
	const cards = report ? [
		{ title: `Income ${view === 'weekly' ? 'this week' : 'this month'}`, value: money(summary.total_income), icon: '↗', tone: 'green', detail: report.period.label },
		{ title: `Expenses ${view === 'weekly' ? 'this week' : 'this month'}`, value: money(summary.total_expenses), icon: '↘', tone: 'red', detail: report.period.label },
		{ title: 'Net cash flow', value: money(net), icon: '₹', tone: Number(net) < 0 ? 'red' : 'blue', detail: 'Income minus expenses' },
		{ title: 'Budget utilization', value: budgetSummary?.budget_utilization === null || budgetSummary?.budget_utilization === undefined ? '—' : `${percent.format(Number(budgetSummary.budget_utilization))}%`, icon: '◫', tone: 'purple', detail: view === 'weekly' ? 'Selected week’s month-to-date budget status' : 'Actual monthly spending / budget' },
		{ title: 'Average daily spending', value: money(summary.average_daily_spending), icon: '⌁', tone: 'red', detail: 'Across selected period days' },
		{ title: 'Previous-period spending', value: comparison?.label || '—', icon: '↔', tone: comparison?.tone === 'positive' ? 'green' : comparison?.tone === 'negative' ? 'red' : 'blue', detail: report.previous_period.expenses ? `${money(report.previous_period.expenses)} previously` : 'Comparison unavailable without previous spending' },
	] : [];
	const weekNavigation = offset => {
		const date = new Date(`${weekDate}T12:00:00`);
		date.setDate(date.getDate() + offset * 7);
		setDashboard(null);
		setWeekDate(localIsoDate(date));
	};

	return <section className="dashboard-page">
		<PageHeader title="Dashboard" description="Weekly and monthly views of your financial activity." />
		<div className="dashboard-toolbar dashboard-analytics-toolbar">
			<div className="dashboard-period-tabs" role="tablist" aria-label="Dashboard analytics period">
				<button type="button" role="tab" aria-selected={view === 'weekly'} className={view === 'weekly' ? 'active' : ''} onClick={() => { setDashboard(null); setView('weekly'); }}>Weekly</button>
				<button type="button" role="tab" aria-selected={view === 'monthly'} className={view === 'monthly' ? 'active' : ''} onClick={() => { setDashboard(null); setView('monthly'); }}>Monthly</button>
			</div>
			{view === 'weekly' ? <div className="dashboard-period-picker">
				<button type="button" className="secondary-button" aria-label="Previous week" onClick={() => weekNavigation(-1)}>←</button>
				<label>Week containing<input type="date" value={weekDate} onChange={event => { if (event.target.value) { setDashboard(null); setWeekDate(event.target.value); } }} /></label>
				<button type="button" className="secondary-button" aria-label="Next week" onClick={() => weekNavigation(1)}>→</button>
			</div> : <label className="dashboard-month-picker">Month<input type="month" value={monthPeriod} onChange={event => { if (event.target.value) { setDashboard(null); setMonthPeriod(event.target.value); } }} /></label>}
			<button type="button" className="secondary-btn dashboard-refresh" onClick={() => load({ background: Boolean(dashboard) })} disabled={refreshing}>{refreshing ? 'Refreshing...' : refreshLabel}</button>
		</div>
		{error && <div className="dashboard-error" role="alert"><span>{error}</span><button type="button" onClick={() => load({ background: Boolean(dashboard) })}>Retry</button></div>}
		{loading && !dashboard ? <DashboardSkeleton /> : dashboard && report && <>
			<div className="dashboard-period-heading">
				<div><h2>{report.period.label}</h2><p>{view === 'weekly' ? 'Weeks start Monday and end Sunday. Transactions are grouped by their local calendar date.' : 'Calendar-month totals; transaction dates determine period membership.'}</p></div>
				{loading && <span role="status">Updating...</span>}
			</div>
			<section className="summary-grid dashboard-summary-grid" aria-label={`${view} financial summary`}>
				{cards.map(card => <SummaryCard key={card.title} {...card} />)}
			</section>
			{loading && <p className="dashboard-refresh-note" role="status">Refreshing dashboard data...</p>}
			<section className="dashboard-panels">
				<article className="panel dashboard-panel dashboard-wide">
					<div className="dashboard-panel-title"><div><h2>{view === 'weekly' ? 'Daily expense trend' : 'Spending trend across the month'}</h2><p>{view === 'weekly' ? 'Daily spending, Monday through Sunday.' : 'Actual daily totals for the selected calendar month.'}</p></div></div>
					{trends.some(item => Number(item.expenses)) ? <div className="dashboard-chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={trends} margin={{ top: 8, right: 14, left: 4, bottom: 4 }}>
						<CartesianGrid strokeDasharray="3 3" vertical={false} />
						<XAxis dataKey="label" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
						<YAxis tick={{ fontSize: 11 }} tickFormatter={value => `₹${Number(value).toLocaleString('en-IN')}`} width={72} />
						<Tooltip formatter={value => money(value)} />
						<Legend />
						<Line type="monotone" dataKey="expenses" name="Expenses" stroke="#e05245" strokeWidth={2.5} dot={trends.length <= 14 ? { r: 3 } : false} />
						{view === 'monthly' && <Line type="monotone" dataKey="income" name="Income" stroke="#20a77a" strokeWidth={2} dot={trends.length <= 14 ? { r: 3 } : false} />}
					</LineChart></ResponsiveContainer></div> : <div className="dashboard-empty">No expenses recorded in this period.</div>}
				</article>
				<article className="panel dashboard-panel">
					<div className="dashboard-panel-title"><div><h2>Income vs expenses</h2><p>{view === 'weekly' ? 'Totals for this Monday–Sunday week.' : 'Daily cash flows in this calendar month.'}</p></div></div>
					{trends.some(item => Number(item.income) || Number(item.expenses)) ? <div className="dashboard-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={trends} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
						<CartesianGrid strokeDasharray="3 3" vertical={false} />
						<XAxis dataKey="label" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
						<YAxis tick={{ fontSize: 10 }} tickFormatter={value => `₹${Number(value).toLocaleString('en-IN')}`} width={67} />
						<Tooltip formatter={value => money(value)} />
						<Legend />
						<Bar dataKey="income" name="Income" fill="#20a77a" radius={[4, 4, 0, 0]} />
						<Bar dataKey="expenses" name="Expenses" fill="#e05245" radius={[4, 4, 0, 0]} />
					</BarChart></ResponsiveContainer></div> : <div className="dashboard-empty">No income or expenses recorded in this period.</div>}
				</article>
				<article className="panel dashboard-panel">
					<div className="dashboard-panel-title"><div><h2>Spending by category</h2><p>{view === 'weekly' ? 'Expenses in the selected week.' : 'Expenses in the selected month.'}</p></div></div>
					{categories.length ? <div className="dashboard-chart dashboard-pie-chart"><ResponsiveContainer width="100%" height="100%"><PieChart>
						<Pie data={categories} dataKey="amount" nameKey="category_name" cx="50%" cy="50%" innerRadius={58} outerRadius={94} paddingAngle={2}>
							{categories.map((category, index) => <Cell key={category.category_id} fill={chartColors[index % chartColors.length]} />)}
						</Pie>
						<Tooltip formatter={value => money(value)} />
						<Legend />
					</PieChart></ResponsiveContainer></div> : <div className="dashboard-empty">No expenses to break down for this period.</div>}
				</article>
				<article className="panel dashboard-panel">
					<div className="dashboard-panel-title"><div><h2>{view === 'weekly' ? 'Monthly budget status' : 'Budget progress'}</h2><p>{view === 'weekly' ? `Month-to-date limits for ${periodMonth(dashboard.summary.period)}.` : `Monthly limits for ${report.period.label}.`}</p></div></div>
					{budgets.length ? <div className="dashboard-budget-list">{budgets.map(budget => <ProgressBudget key={budget.budget_id} budget={budget} />)}</div> : <div className="dashboard-empty">No applicable budgets. <Link to="/budgets">Set a budget</Link></div>}
					{view === 'weekly' && <p className="dashboard-ai-footnote">Budget utilization reflects the full month to date, not only this week.</p>}
				</article>
				<article className="panel dashboard-panel">
					<div className="dashboard-panel-title"><div><h2>Recent transactions</h2><p>Latest income and expenses.</p></div><div className="dashboard-links"><Link to="/expenses">Expenses</Link><Link to="/income">Income</Link></div></div>
					{transactions.length ? <div className="dashboard-transactions">{transactions.map(transaction => <div className="dashboard-transaction" key={`${transaction.transaction_type}-${transaction.transaction_id}`}>
						<span className={`transaction-type-icon ${transaction.transaction_type}`}>{transaction.transaction_type === 'income' ? '↗' : '↘'}</span>
						<div className="dashboard-transaction-main"><strong>{transaction.description}</strong><span>{transaction.transaction_type === 'income' ? transaction.source : transaction.category || 'Expense'} · {new Date(`${transaction.date}T00:00:00`).toLocaleDateString()}</span></div>
						<strong className={`transaction-amount ${transaction.transaction_type}`}>{transaction.transaction_type === 'income' ? '+' : '−'}{money(transaction.amount)}</strong>
					</div>)}</div> : <div className="dashboard-empty">No transactions have been recorded yet. <span><Link to="/expenses">Add an expense</Link> or <Link to="/income">add income</Link>.</span></div>}
				</article>
				<InsightPanel dashboard={dashboard} view={view} />
			</section>
		</>}
	</section>;
}
