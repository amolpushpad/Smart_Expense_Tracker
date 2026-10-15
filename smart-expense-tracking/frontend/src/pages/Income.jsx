import { useEffect, useState } from 'react';
import ConfirmDialog from '../components/ConfirmDialog';
import IncomeForm from '../components/IncomeForm';
import PageHeader from '../components/PageHeader';
import { getApiErrorMessage, incomeApi, notifyDashboardDataChanged } from '../services/api';
import '../styles/expenses.css';
import '../styles/phase4.css';

const currency = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' });

function monthStart() {
	const now = new Date();
	return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`;
}

function localDate() {
	const today = new Date();
	today.setMinutes(today.getMinutes() - today.getTimezoneOffset());
	return today.toISOString().slice(0, 10);
}

export default function Income() {
	const [incomes, setIncomes] = useState([]);
	const [totalAmount, setTotalAmount] = useState('0.00');
	const [filters, setFilters] = useState({ start_date: monthStart(), end_date: localDate(), sort: 'newest' });
	const [draft, setDraft] = useState(filters);
	const [reloadKey, setReloadKey] = useState(0);
	const [loading, setLoading] = useState(true);
	const [saving, setSaving] = useState(false);
	const [error, setError] = useState('');
	const [formError, setFormError] = useState('');
	const [notice, setNotice] = useState('');
	const [editingIncome, setEditingIncome] = useState(null);
	const [incomeFormOpen, setIncomeFormOpen] = useState(false);
	const [pendingDelete, setPendingDelete] = useState(null);
	const [deleting, setDeleting] = useState(false);

	useEffect(() => {
		const controller = new AbortController();
		setLoading(true);
		setError('');
		incomeApi.list(filters, { signal: controller.signal })
			.then(response => {
				setIncomes(response.data.data.incomes);
				setTotalAmount(response.data.data.total_amount);
			})
			.catch(requestError => {
				if (requestError.name !== 'CanceledError') setError(getApiErrorMessage(requestError));
			})
			.finally(() => { if (!controller.signal.aborted) setLoading(false); });
		return () => controller.abort();
	}, [filters, reloadKey]);

	const changeFilter = ({ target }) => setDraft(current => ({ ...current, [target.name]: target.value }));
	const applyFilters = event => {
		event.preventDefault();
		if (draft.start_date && draft.end_date && draft.start_date > draft.end_date) {
			setError('Start date must be on or before end date.');
			return;
		}
		setError('');
		setFilters({ ...draft });
	};

	const saveIncome = async values => {
		setSaving(true);
		setFormError('');
		try {
			if (editingIncome) await incomeApi.update(editingIncome.income_id, values);
			else await incomeApi.create(values);
			notifyDashboardDataChanged();
			setNotice(editingIncome ? 'Income updated.' : 'Income added.');
			setEditingIncome(null);
			setIncomeFormOpen(false);
			setReloadKey(value => value + 1);
		} catch (requestError) {
			const errors = requestError.response?.data?.errors;
			setFormError(errors ? Object.values(errors).join(' ') : getApiErrorMessage(requestError));
		} finally {
			setSaving(false);
		}
	};

	const deleteIncome = async () => {
		if (!pendingDelete) return;
		setDeleting(true);
		setError('');
		try {
			await incomeApi.remove(pendingDelete.income_id);
			notifyDashboardDataChanged();
			setNotice('Income deleted.');
			setPendingDelete(null);
			setReloadKey(value => value + 1);
		} catch (requestError) {
			setError(getApiErrorMessage(requestError));
			setPendingDelete(null);
		} finally {
			setDeleting(false);
		}
	};

	return <section className="phase4-page">
		<PageHeader title="Income" description="Track and manage your income sources." />
		<div className="phase4-toolbar">
			<div className="expense-total"><span>{incomes.length} {incomes.length === 1 ? 'income record' : 'income records'}</span><strong>{currency.format(Number(totalAmount))}</strong><small>Total income for the selected period</small></div>
			<button className="primary-btn" type="button" onClick={() => { setEditingIncome(null); setFormError(''); setNotice(''); setIncomeFormOpen(true); }}>＋ Add income</button>
		</div>
		{notice && <div className="expense-alert success" role="status"><span>{notice}</span><button type="button" onClick={() => setNotice('')} aria-label="Dismiss notification">×</button></div>}
		{error && <div className="expense-alert error" role="alert">{error}</div>}
		<form className="phase4-filters" onSubmit={applyFilters}>
			<label>From<input name="start_date" type="date" value={draft.start_date} onChange={changeFilter} /></label>
			<label>To<input name="end_date" type="date" value={draft.end_date} onChange={changeFilter} /></label>
			<label>Sort<select name="sort" value={draft.sort} onChange={changeFilter}><option value="newest">Newest first</option><option value="oldest">Oldest first</option><option value="amount_high">Highest amount</option><option value="amount_low">Lowest amount</option></select></label>
			<div className="expense-filter-actions"><button className="secondary-button" type="button" onClick={() => { const reset = { start_date: '', end_date: '', sort: 'newest' }; setDraft(reset); setFilters(reset); }}>Clear dates</button><button className="primary-btn" type="submit">Apply</button></div>
		</form>
		<div className="expense-table-wrap">
			<table className="expense-table income-table">
				<thead><tr><th>Source</th><th>Amount</th><th>Date</th><th>Description</th><th><span className="visually-hidden">Actions</span></th></tr></thead>
				<tbody>
					{loading && <tr><td colSpan="5" className="table-message" role="status">Loading income...</td></tr>}
					{!loading && !error && incomes.map(income => <tr key={income.income_id}>
						<td><strong>{income.source}</strong></td><td className="amount-cell">{currency.format(Number(income.amount))}</td>
						<td>{new Date(`${income.date}T00:00:00`).toLocaleDateString()}</td><td>{income.description || '—'}</td>
						<td><div className="expense-row-actions"><button className="text-button" type="button" onClick={() => { setEditingIncome(income); setFormError(''); setIncomeFormOpen(true); }}>Edit</button><button className="text-button destructive" type="button" onClick={() => setPendingDelete(income)}>Delete</button></div></td>
					</tr>)}
					{!loading && !error && incomes.length === 0 && <tr><td colSpan="5" className="table-message">No income records for this period.</td></tr>}
				</tbody>
			</table>
		</div>
		{incomeFormOpen && <IncomeForm income={editingIncome} error={formError} saving={saving} onClose={() => setIncomeFormOpen(false)} onSave={saveIncome} />}
		{pendingDelete && <ConfirmDialog title="Delete income?" message={`Delete income from ${pendingDelete.source}? This cannot be undone.`} confirming={deleting} onCancel={() => setPendingDelete(null)} onConfirm={deleteIncome} />}
	</section>;
}
