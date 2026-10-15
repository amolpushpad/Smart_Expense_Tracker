import { useEffect, useState } from 'react';
import ExpenseForm from '../components/ExpenseForm';
import PageHeader from '../components/PageHeader';
import { categoriesApi, expensesApi, getApiErrorMessage, notifyDashboardDataChanged } from '../services/api';
import '../styles/expenses.css';

const emptyFilters = { search: '', category_id: '', start_date: '', end_date: '', min_amount: '', max_amount: '', sort: 'newest' };
const currency = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' });

export default function Expenses() {
	const [categories, setCategories] = useState([]);
	const [expenses, setExpenses] = useState([]);
	const [pagination, setPagination] = useState({ page: 1, per_page: 20, total: 0, pages: 0 });
	const [totalAmount, setTotalAmount] = useState('0.00');
	const [draft, setDraft] = useState(emptyFilters);
	const [filters, setFilters] = useState(emptyFilters);
	const [page, setPage] = useState(1);
	const [reloadKey, setReloadKey] = useState(0);
	const [loading, setLoading] = useState(true);
	const [saving, setSaving] = useState(false);
	const [error, setError] = useState('');
	const [formError, setFormError] = useState('');
	const [notice, setNotice] = useState('');
	const [editingExpense, setEditingExpense] = useState(null);
	const [formOpen, setFormOpen] = useState(false);

	useEffect(() => {
		let active = true;
		categoriesApi.list()
			.then(response => { if (active) setCategories(response.data.data.categories); })
			.catch(requestError => { if (active) setError(getApiErrorMessage(requestError)); });
		return () => { active = false; };
	}, []);

	useEffect(() => {
		const controller = new AbortController();
		setLoading(true);
		setError('');
		expensesApi.list({ ...filters, page, per_page: 20 }, { signal: controller.signal })
			.then(response => {
				const data = response.data.data;
				setExpenses(data.expenses);
				setPagination(data.pagination);
				setTotalAmount(data.total_amount);
			})
			.catch(requestError => {
				if (requestError.name !== 'CanceledError') setError(getApiErrorMessage(requestError));
			})
			.finally(() => { if (!controller.signal.aborted) setLoading(false); });
		return () => controller.abort();
	}, [filters, page, reloadKey]);

	const changeDraft = event => setDraft(current => ({ ...current, [event.target.name]: event.target.value }));
	const applyFilters = event => {
		event.preventDefault();
		if (draft.start_date && draft.end_date && draft.start_date > draft.end_date) {
			setError('Start date must be on or before end date.');
			return;
		}
		setError('');
		setPage(1);
		setFilters({ ...draft });
	};

	const openCreate = () => {
		setEditingExpense(null);
		setFormError('');
		setFormOpen(true);
	};

	const openEdit = expense => {
		setEditingExpense(expense);
		setFormError('');
		setFormOpen(true);
	};

	const saveExpense = async values => {
		setSaving(true);
		setFormError('');
		try {
			if (editingExpense) await expensesApi.update(editingExpense.expense_id, values);
			else await expensesApi.create(values);
			notifyDashboardDataChanged();
			setNotice(editingExpense ? 'Expense updated.' : 'Expense added.');
			setFormOpen(false);
			setReloadKey(value => value + 1);
		} catch (requestError) {
			const data = requestError.response?.data;
			setFormError(data?.errors ? Object.values(data.errors).join(' ') : getApiErrorMessage(requestError));
		} finally {
			setSaving(false);
		}
	};

	const deleteExpense = async expense => {
		const label = expense.description || expense.vendor || 'this expense';
		if (!window.confirm(`Delete ${label}? This cannot be undone.`)) return;
		setError('');
		try {
			await expensesApi.remove(expense.expense_id);
			notifyDashboardDataChanged();
			setNotice('Expense deleted.');
			if (expenses.length === 1 && page > 1) setPage(current => current - 1);
			else setReloadKey(value => value + 1);
		} catch (requestError) {
			setError(getApiErrorMessage(requestError));
		}
	};

	return <section className="expenses-page">
		<PageHeader title="Expenses" description="Search, filter, and manage your recorded expenses." />
		<div className="expenses-toolbar">
			<div className="expense-total"><span>{pagination.total} {pagination.total === 1 ? 'expense' : 'expenses'}</span><strong>{currency.format(Number(totalAmount))}</strong><small>Total for current filters</small></div>
			<button className="primary-btn add-expense-button" type="button" onClick={openCreate}>＋ Add expense</button>
		</div>

		{notice && <div className="expense-alert success" role="status"><span>{notice}</span><button type="button" onClick={() => setNotice('')} aria-label="Dismiss notification">×</button></div>}
		{error && <div className="expense-alert error" role="alert">{error}</div>}

		<form className="expense-filters" onSubmit={applyFilters}>
			<label className="expense-search">Search<input name="search" value={draft.search} onChange={changeDraft} placeholder="Description or vendor" /></label>
			<label>Category<select name="category_id" value={draft.category_id} onChange={changeDraft}><option value="">All categories</option>{categories.map(category => <option key={category.category_id} value={category.category_id}>{category.category_name}</option>)}</select></label>
			<label>From<input name="start_date" type="date" value={draft.start_date} onChange={changeDraft} /></label>
			<label>To<input name="end_date" type="date" value={draft.end_date} onChange={changeDraft} /></label>
			<label>Min amount<input name="min_amount" type="number" min="0" step="0.01" value={draft.min_amount} onChange={changeDraft} placeholder="0.00" /></label>
			<label>Max amount<input name="max_amount" type="number" min="0" step="0.01" value={draft.max_amount} onChange={changeDraft} placeholder="Any" /></label>
			<label>Sort<select name="sort" value={draft.sort} onChange={changeDraft}><option value="newest">Newest first</option><option value="oldest">Oldest first</option><option value="amount_high">Highest amount</option><option value="amount_low">Lowest amount</option></select></label>
			<div className="expense-filter-actions"><button className="secondary-button" type="button" onClick={() => { setDraft(emptyFilters); setFilters(emptyFilters); setPage(1); }}>Reset</button><button className="primary-btn" type="submit">Apply filters</button></div>
		</form>

		<div className="expense-table-wrap">
			<table className="expense-table">
				<thead><tr><th>Date</th><th>Description / vendor</th><th>Category</th><th>Payment</th><th className="amount-cell">Amount</th><th><span className="visually-hidden">Actions</span></th></tr></thead>
				<tbody>
					{loading && <tr><td colSpan="6" className="table-message" role="status">Loading expenses...</td></tr>}
					{!loading && !error && expenses.map(expense => <tr key={expense.expense_id}>
						<td>{new Date(`${expense.date}T00:00:00`).toLocaleDateString()}</td>
						<td><strong>{expense.description || 'Expense'}</strong><span className="expense-secondary">{expense.vendor || 'No vendor'}</span></td>
						<td>{expense.category_name}</td><td>{expense.payment_method || '—'}</td>
						<td className="amount-cell">{currency.format(Number(expense.amount))}</td>
						<td><div className="expense-row-actions"><button className="text-button" type="button" onClick={() => openEdit(expense)}>Edit</button><button className="text-button destructive" type="button" onClick={() => deleteExpense(expense)}>Delete</button></div></td>
					</tr>)}
					{!loading && !error && expenses.length === 0 && <tr><td colSpan="6" className="table-message">No expenses match these filters.</td></tr>}
				</tbody>
			</table>
		</div>
		<div className="expense-pagination"><span>{pagination.total ? `Page ${page} of ${pagination.pages}` : 'No results'}</span><div><button className="secondary-button" type="button" disabled={page <= 1 || loading} onClick={() => setPage(current => current - 1)}>Previous</button><button className="secondary-button" type="button" disabled={page >= pagination.pages || loading} onClick={() => setPage(current => current + 1)}>Next</button></div></div>

		{formOpen && <ExpenseForm expense={editingExpense} categories={categories} error={formError} saving={saving} onClose={() => setFormOpen(false)} onSave={saveExpense} />}
	</section>;
}
