import { useEffect, useState } from 'react';

export default function BudgetForm({ budget, categories, month, year, error, saving, onClose, onSave }) {
	const [form, setForm] = useState({ category_id: '', amount: '' });
	const [validationError, setValidationError] = useState('');

	useEffect(() => {
		setForm(budget
			? { category_id: budget.category_id ? String(budget.category_id) : '', amount: budget.amount }
			: { category_id: '', amount: '' });
	}, [budget]);

	const submit = event => {
		event.preventDefault();
		setValidationError('');
		if (!/^\d{1,8}(\.\d{1,2})?$/.test(form.amount) || Number(form.amount) <= 0) {
			setValidationError('Enter an amount greater than zero with up to two decimal places.');
			return;
		}
		onSave({
			amount: form.amount,
			category_id: form.category_id ? Number(form.category_id) : null,
			month: Number(month),
			year: Number(year),
		});
	};

	return <div className="expense-dialog-backdrop" role="presentation">
		<section className="expense-dialog" role="dialog" aria-modal="true" aria-labelledby="budget-form-title">
			<div className="expense-dialog-header">
				<div><h3 id="budget-form-title">{budget ? 'Edit budget' : 'Add budget'}</h3><p>For {new Date(Number(year), Number(month) - 1, 1).toLocaleDateString(undefined, { month: 'long', year: 'numeric' })}.</p></div>
				<button className="icon-button" type="button" onClick={onClose} aria-label="Close budget form">×</button>
			</div>
			{(validationError || error) && <div className="expense-alert error" role="alert">{validationError || error}</div>}
			<form className="expense-form" onSubmit={submit}>
				<label>Budget type<select value={form.category_id} onChange={event => setForm(current => ({ ...current, category_id: event.target.value }))}><option value="">Overall monthly budget</option>{categories.map(category => <option key={category.category_id} value={category.category_id}>{category.category_name}</option>)}</select></label>
				<label>Amount<input type="text" inputMode="decimal" autoComplete="off" value={form.amount} onChange={event => setForm(current => ({ ...current, amount: event.target.value }))} placeholder="0.00" required /></label>
				<div className="expense-form-actions"><button type="button" className="secondary-button" onClick={onClose}>Cancel</button><button type="submit" className="primary-btn" disabled={saving}>{saving ? 'Saving...' : budget ? 'Save changes' : 'Create budget'}</button></div>
			</form>
		</section>
	</div>;
}
