import { useEffect, useState } from 'react';
import BudgetForm from '../components/BudgetForm';
import ConfirmDialog from '../components/ConfirmDialog';
import PageHeader from '../components/PageHeader';
import { budgetsApi, categoriesApi, getApiErrorMessage, notifyDashboardDataChanged } from '../services/api';
import '../styles/expenses.css';
import '../styles/phase4.css';

const currency = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' });

function toCents(amount) {
	const [whole, fraction = ''] = String(amount).split('.');
	const sign = whole.startsWith('-') ? -1n : 1n;
	return BigInt(whole) * 100n + sign * BigInt(fraction.padEnd(2, '0'));
}

function formatCents(cents) {
	return currency.format(Number(cents) / 100);
}

function currentPeriod() {
	const now = new Date();
	return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
}

function BudgetProgress({ budget }) {
	const utilization = Number(budget.utilization_percentage || 0);
	return <div className="budget-progress-wrap">
		<div className="budget-progress-track" role="progressbar" aria-label={`${budget.category_name || 'Overall'} budget utilized`} aria-valuemin="0" aria-valuemax="100" aria-valuenow={Math.min(100, utilization)}>
			<span className={budget.over_budget ? 'over' : ''} style={{ width: `${Math.min(100, Math.max(0, utilization))}%` }} />
		</div>
		<div className="budget-progress-caption"><span>{utilization.toFixed(2)}% used</span><span>{budget.over_budget ? 'Over budget' : `${currency.format(Number(budget.remaining_amount))} remaining`}</span></div>
	</div>;
}

export default function Budgets() {
	const [period, setPeriod] = useState(currentPeriod);
	const [budgets, setBudgets] = useState([]);
	const [categories, setCategories] = useState([]);
	const [reloadKey, setReloadKey] = useState(0);
	const [loading, setLoading] = useState(true);
	const [saving, setSaving] = useState(false);
	const [deleting, setDeleting] = useState(false);
	const [error, setError] = useState('');
	const [formError, setFormError] = useState('');
	const [notice, setNotice] = useState('');
	const [formOpen, setFormOpen] = useState(false);
	const [editingBudget, setEditingBudget] = useState(null);
	const [pendingDelete, setPendingDelete] = useState(null);
	const [year, month] = period.split('-');

	useEffect(() => {
		let active = true;
		setLoading(true);
		Promise.all([
			categoriesApi.list(),
			budgetsApi.list({ month: Number(month), year: Number(year) }),
		]).then(([categoryResponse, budgetResponse]) => {
			if (!active) return;
			setCategories(categoryResponse.data.data.categories);
			setBudgets(budgetResponse.data.data.budgets);
			setError('');
		}).catch(requestError => {
			if (active) setError(getApiErrorMessage(requestError));
		}).finally(() => { if (active) setLoading(false); });
		return () => { active = false; };
	}, [month, year, reloadKey]);

	const overallBudget = budgets.find(budget => budget.category_id === null);
	const categoryBudgets = budgets.filter(budget => budget.category_id !== null);
	const selectedBudgets = overallBudget ? [overallBudget] : categoryBudgets;
	const totals = selectedBudgets.reduce((result, budget) => ({
			amount: result.amount + toCents(budget.amount),
			spent: result.spent + toCents(budget.spent_amount),
			remaining: result.remaining + toCents(budget.remaining_amount),
		}), { amount: 0n, spent: 0n, remaining: 0n });
	const utilization = totals.amount > 0n ? Number(totals.spent) / Number(totals.amount) * 100 : null;

	const saveBudget = async values => {
		setSaving(true);
		setFormError('');
		try {
			if (editingBudget) await budgetsApi.update(editingBudget.budget_id, values);
			else await budgetsApi.create(values);
			notifyDashboardDataChanged();
			setNotice(editingBudget ? 'Budget updated.' : 'Budget created.');
			setFormOpen(false);
			setEditingBudget(null);
			setReloadKey(value => value + 1);
		} catch (requestError) {
			const errors = requestError.response?.data?.errors;
			setFormError(errors ? Object.values(errors).join(' ') : getApiErrorMessage(requestError));
		} finally {
			setSaving(false);
		}
	};

	const deleteBudget = async () => {
		if (!pendingDelete) return;
		setDeleting(true);
		setError('');
		try {
			await budgetsApi.remove(pendingDelete.budget_id);
			notifyDashboardDataChanged();
			setNotice('Budget deleted.');
			setPendingDelete(null);
			setReloadKey(value => value + 1);
		} catch (requestError) {
			setError(getApiErrorMessage(requestError));
			setPendingDelete(null);
		} finally {
			setDeleting(false);
		}
	};

	const openCreate = () => {
		setEditingBudget(null);
		setFormError('');
		setFormOpen(true);
	};
	const openEdit = budget => {
		setEditingBudget(budget);
		setFormError('');
		setFormOpen(true);
	};
	const budgetCard = budget => <article className={`phase4-budget-card${budget.over_budget ? ' is-over' : ''}`} key={budget.budget_id}>
		<div className="phase4-budget-heading"><div><span className="phase4-eyebrow">{budget.category_id === null ? 'Overall budget' : 'Category budget'}</span><h3>{budget.category_name || 'All categories'}</h3></div><div className="phase4-card-actions"><button className="text-button" type="button" onClick={() => openEdit(budget)}>Edit</button><button className="text-button destructive" type="button" onClick={() => setPendingDelete(budget)}>Delete</button></div></div>
		<div className="phase4-budget-numbers"><div><span>Budget</span><strong>{currency.format(Number(budget.amount))}</strong></div><div><span>Spent</span><strong>{currency.format(Number(budget.spent_amount))}</strong></div><div><span>{budget.over_budget ? 'Over by' : 'Remaining'}</span><strong className={budget.over_budget ? 'budget-negative' : ''}>{currency.format(Math.abs(Number(budget.remaining_amount)))}</strong></div></div>
		<BudgetProgress budget={budget} />
		{budget.over_budget && <p className="budget-warning" role="status">This budget has been exceeded. Your transactions have not been changed.</p>}
	</article>;

	return <section className="phase4-page">
		<PageHeader title="Budgets" description="Set monthly spending limits and track actual expenses." />
		<div className="phase4-toolbar">
			<label className="phase4-period">Selected month<input type="month" value={period} onChange={event => { if (event.target.value) setPeriod(event.target.value); }} /></label>
			<button className="primary-btn" type="button" onClick={openCreate}>＋ Add budget</button>
		</div>
		{notice && <div className="expense-alert success" role="status"><span>{notice}</span><button type="button" onClick={() => setNotice('')} aria-label="Dismiss notification">×</button></div>}
		{error && <div className="expense-alert error" role="alert">{error}</div>}
		<section className="phase4-summary-grid" aria-label="Monthly budget totals">
			<div className="phase4-summary"><span>Total monthly budget</span><strong>{formatCents(totals.amount)}</strong><small>{overallBudget ? 'Overall limit (category limits shown separately)' : 'Sum of category limits'}</small></div>
			<div className="phase4-summary"><span>Amount spent</span><strong>{formatCents(totals.spent)}</strong><small>For the selected month</small></div>
			<div className="phase4-summary"><span>Remaining budget</span><strong className={totals.remaining < 0n ? 'budget-negative' : ''}>{formatCents(totals.remaining)}</strong><small>{totals.remaining < 0n ? 'Over budget' : 'Available to spend'}</small></div>
			<div className="phase4-summary"><span>Utilization</span><strong>{utilization === null ? '—' : `${utilization.toFixed(2)}%`}</strong><small>{utilization === null ? 'Create a budget to track utilization' : 'Actual spending ÷ budget'}</small></div>
		</section>
		{loading ? <div className="phase4-empty" role="status">Loading budgets...</div> : !error && budgets.length === 0 ? <div className="phase4-empty"><h3>No budgets for this month</h3><p>Create an overall monthly budget or set limits for individual categories.</p></div> : !error && <>
			{overallBudget && <section className="phase4-budget-section"><h2>Overall monthly budget</h2>{budgetCard(overallBudget)}</section>}
			<section className="phase4-budget-section"><h2>Category-specific budgets</h2>{categoryBudgets.length ? <div className="phase4-budget-list">{categoryBudgets.map(budgetCard)}</div> : <p className="phase4-muted">No category-specific budgets for this month.</p>}</section>
		</>}
		{formOpen && <BudgetForm budget={editingBudget} categories={categories} month={month} year={year} error={formError} saving={saving} onClose={() => setFormOpen(false)} onSave={saveBudget} />}
		{pendingDelete && <ConfirmDialog title="Delete budget?" message={`Delete the budget for ${pendingDelete.category_name || 'all categories'}? Existing transactions will remain unchanged.`} confirming={deleting} onCancel={() => setPendingDelete(null)} onConfirm={deleteBudget} />}
	</section>;
}
