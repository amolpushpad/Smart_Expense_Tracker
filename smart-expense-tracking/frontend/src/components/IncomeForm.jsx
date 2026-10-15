import { useEffect, useState } from 'react';

function localDate() {
	const today = new Date();
	today.setMinutes(today.getMinutes() - today.getTimezoneOffset());
	return today.toISOString().slice(0, 10);
}

export default function IncomeForm({ income, error, saving, onClose, onSave }) {
	const [form, setForm] = useState({ source: '', amount: '', date: localDate(), description: '' });
	const [validationError, setValidationError] = useState('');

	useEffect(() => {
		if (income) setForm({
			source: income.source,
			amount: income.amount,
			date: income.date,
			description: income.description || '',
		});
	}, [income]);

	const update = ({ target }) => setForm(current => ({ ...current, [target.name]: target.value }));
	const submit = event => {
		event.preventDefault();
		setValidationError('');
		if (!form.source.trim() || form.source.trim().length > 120) {
			setValidationError('Enter a source name between 1 and 120 characters.');
			return;
		}
		if (!/^\d{1,8}(\.\d{1,2})?$/.test(form.amount) || Number(form.amount) <= 0) {
			setValidationError('Enter an amount greater than zero with up to two decimal places.');
			return;
		}
		if (!form.date) {
			setValidationError('Choose a date.');
			return;
		}
		onSave({
			source: form.source.trim(),
			amount: form.amount,
			date: form.date,
			description: form.description.trim() || null,
		});
	};

	return <div className="expense-dialog-backdrop" role="presentation">
		<section className="expense-dialog" role="dialog" aria-modal="true" aria-labelledby="income-form-title">
			<div className="expense-dialog-header">
				<div><h3 id="income-form-title">{income ? 'Edit income' : 'Add income'}</h3><p>Enter the income details.</p></div>
				<button className="icon-button" type="button" onClick={onClose} aria-label="Close income form">×</button>
			</div>
			{(validationError || error) && <div className="expense-alert error" role="alert">{validationError || error}</div>}
			<form className="expense-form" onSubmit={submit}>
				<label>Source<input name="source" maxLength={120} value={form.source} onChange={update} placeholder="e.g. Salary" required /></label>
				<label>Amount<input name="amount" type="text" inputMode="decimal" autoComplete="off" value={form.amount} onChange={update} placeholder="0.00" required /></label>
				<label>Date<input name="date" type="date" value={form.date} onChange={update} required /></label>
				<label>Description <span className="field-optional">Optional</span><input name="description" maxLength={500} value={form.description} onChange={update} placeholder="Optional details" /></label>
				<div className="expense-form-actions"><button type="button" className="secondary-button" onClick={onClose}>Cancel</button><button type="submit" className="primary-btn" disabled={saving}>{saving ? 'Saving...' : income ? 'Save changes' : 'Add income'}</button></div>
			</form>
		</section>
	</div>;
}
