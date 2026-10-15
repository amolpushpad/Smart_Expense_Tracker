import { useEffect, useState } from 'react';
import { getApiErrorMessage, mlApi } from '../services/api';
import '../styles/expense-suggestion.css';

function localDate() {
  const today = new Date();
  today.setMinutes(today.getMinutes() - today.getTimezoneOffset());
  return today.toISOString().slice(0, 10);
}

export default function ExpenseForm({ expense, categories, error, saving, onClose, onSave }) {
  const [form, setForm] = useState({
    amount: '',
    date: localDate(),
    category_id: '',
    description: '',
    vendor: '',
    payment_method: '',
  });
  const [validationError, setValidationError] = useState('');
  const [suggestion, setSuggestion] = useState(null);
  const [suggestionError, setSuggestionError] = useState('');
  const [suggesting, setSuggesting] = useState(false);

  useEffect(() => {
    if (expense) {
      setForm({
        amount: expense.amount,
        date: expense.date,
        category_id: String(expense.category_id),
        description: expense.description || '',
        vendor: expense.vendor || '',
        payment_method: expense.payment_method || '',
      });
    }
  }, [expense]);

  const update = (event) => setForm(current => ({ ...current, [event.target.name]: event.target.value }));

  const suggestCategory = async () => {
    setSuggesting(true);
    setSuggestion(null);
    setSuggestionError('');
    try {
      const response = await mlApi.categorize({
        description: form.description.trim(),
        vendor: form.vendor.trim(),
      });
      setSuggestion(response.data.data);
    } catch (requestError) {
      setSuggestionError(getApiErrorMessage(requestError, 'Category suggestion is temporarily unavailable.'));
    } finally {
      setSuggesting(false);
    }
  };

  const applySuggestion = () => {
    const category = categories.find(item => item.category_name === suggestion?.suggested_category);
    if (!category) {
      setSuggestionError('The suggested category is no longer available. Choose a category manually.');
      return;
    }
    setForm(current => ({ ...current, category_id: String(category.category_id) }));
    setSuggestionError('');
  };

  const submit = (event) => {
    event.preventDefault();
    setValidationError('');
    if (!/^\d{1,8}(\.\d{1,2})?$/.test(form.amount) || Number(form.amount) <= 0) {
      setValidationError('Enter an amount greater than zero with up to two decimal places.');
      return;
    }
    if (!form.date || !form.category_id) {
      setValidationError('Choose a date and category.');
      return;
    }
    onSave({
      amount: form.amount,
      date: form.date,
      category_id: Number(form.category_id),
      description: form.description.trim() || null,
      vendor: form.vendor.trim() || null,
      payment_method: form.payment_method || null,
    });
  };

  return <div className="expense-dialog-backdrop" role="presentation">
    <section className="expense-dialog" role="dialog" aria-modal="true" aria-labelledby="expense-form-title">
      <div className="expense-dialog-header">
        <div><h3 id="expense-form-title">{expense ? 'Edit expense' : 'Add expense'}</h3><p>Enter the transaction details.</p></div>
        <button className="icon-button" type="button" onClick={onClose} aria-label="Close expense form">×</button>
      </div>
      {(validationError || error) && <div className="expense-alert error" role="alert">{validationError || error}</div>}
      <form className="expense-form" onSubmit={submit}>
        <label>Amount<input name="amount" type="text" inputMode="decimal" autoComplete="off" placeholder="0.00" value={form.amount} onChange={update} required /></label>
        <label>Date<input name="date" type="date" value={form.date} onChange={update} required /></label>
        <label>Category<select name="category_id" value={form.category_id} onChange={update} required><option value="">Select a category</option>{categories.map(category => <option key={category.category_id} value={category.category_id}>{category.category_name}</option>)}</select></label>
        <label>Description <span className="field-optional">Optional</span><input name="description" maxLength={500} value={form.description} onChange={update} placeholder="What was this expense for?" /></label>
        <label>Vendor <span className="field-optional">Optional</span><input name="vendor" maxLength={160} value={form.vendor} onChange={update} placeholder="Merchant or payee" /></label>
        {!expense && <div className="category-suggestion">
          <button type="button" className="secondary-button" onClick={suggestCategory} disabled={suggesting || (!form.description.trim() && !form.vendor.trim())}>
            {suggesting ? 'Suggesting...' : 'Suggest category'}
          </button>
          {suggestionError && <span className="expense-suggestion-error" role="alert">{suggestionError}</span>}
          {suggestion?.suggested_category && <div className="expense-suggestion-result">
            <span>Suggested: <strong>{suggestion.suggested_category}</strong>{suggestion.confidence !== null ? ` · ${Math.round(suggestion.confidence * 100)}% confidence` : ''}</span>
            <small>{suggestion.explanation}</small>
            <button type="button" className="text-button" onClick={applySuggestion}>Apply suggestion</button>
          </div>}
          {suggestion && !suggestion.suggested_category && <div className="expense-suggestion-result"><small>{suggestion.explanation}</small></div>}
        </div>}
        <label>Payment method <span className="field-optional">Optional</span><select name="payment_method" value={form.payment_method} onChange={update}><option value="">Select a method</option><option>Cash</option><option>Card</option><option>Bank transfer</option><option>Digital wallet</option><option>Other</option></select></label>
        <div className="expense-form-actions"><button type="button" className="secondary-button" onClick={onClose}>Cancel</button><button type="submit" className="primary-btn" disabled={saving || categories.length === 0}>{saving ? 'Saving...' : expense ? 'Save changes' : 'Add expense'}</button></div>
      </form>
    </section>
  </div>;
}