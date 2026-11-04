import { useCallback, useEffect, useState } from 'react';
import { corporateApi } from '../services/api';
import CorporateWorkflowPanel from './CorporateWorkflowPanel';
import '../styles/corporate.css';

const ROLES = ['Admin', 'Employee', 'Manager', 'Finance Officer', 'Executive'];
const CATEGORIES = ['Travel', 'Meals', 'Software', 'Equipment', 'Training', 'Office Supplies', 'Other'];
const today = new Date().toISOString().slice(0, 10);
const money = amount => new Intl.NumberFormat(undefined, { style: 'currency', currency: 'INR' }).format(Number(amount || 0));

export default function CorporateDashboard({ user }) {
	const [data, setData] = useState(null);
	const [form, setForm] = useState({ amount: '', date: today, category: 'Travel', merchant: '', description: '' });
	const [departmentName, setDepartmentName] = useState('');
	const [memberEdits, setMemberEdits] = useState({});
	const [notes, setNotes] = useState({});
	const [view, setView] = useState('overview');
	const [receipt, setReceipt] = useState(null);
	const [uploadProgress, setUploadProgress] = useState(0);
	const [loading, setLoading] = useState(true);
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState('');
	const [message, setMessage] = useState('');

	const refresh = useCallback(async () => {
		setError('');
		try {
			const rolePath = { Admin: 'admin', Employee: 'employee', Manager: 'manager', 'Finance Officer': 'finance', Executive: 'executive' }[user.role];
			const [response, dashboard] = await Promise.all([
				corporateApi.overview(),
				corporateApi.dashboard(rolePath),
			]);
			const overview = response.data.data;
			const roleData = dashboard.data.data;
			setData({
				...overview,
				summary: { ...overview.summary, ...roleData.summary },
			});
			setMemberEdits(Object.fromEntries((overview.members || []).map(member => [
				member.membership_id,
				{ role: member.role, department_id: member.department_id ?? '' },
			])));
		} catch (requestError) {
			setError(requestError.response?.data?.message || 'Corporate dashboard could not be loaded.');
		} finally {
			setLoading(false);
		}
	}, [user.role]);

	useEffect(() => { refresh(); }, [refresh]);

	const runAction = async action => {
		setBusy(true);
		setError('');
		setMessage('');
		try {
			await action();
			setMessage('Changes saved successfully.');
			await refresh();
		} catch (requestError) {
			setError(requestError.response?.data?.message || 'The corporate request could not be completed.');
		} finally {
			setBusy(false);
		}
	};

	const submitExpense = event => {
		event.preventDefault();
		runAction(async () => {
			setUploadProgress(0);
			await corporateApi.submitExpenseWithReceipt(
				{ ...form, receipt },
				{ onUploadProgress: progress => {
					if (progress.total) setUploadProgress(Math.round((progress.loaded / progress.total) * 100));
				} },
			);
			setForm({ amount: '', date: today, category: 'Travel', merchant: '', description: '' });
			setReceipt(null);
			setUploadProgress(0);
		});
	};

	const createDepartment = event => {
		event.preventDefault();
		runAction(async () => {
			await corporateApi.createDepartment({ name: departmentName });
			setDepartmentName('');
		});
	};

	const canSubmit = ['Employee', 'Manager', 'Admin'].includes(user.role);
	const tabs = [
		{ id: 'overview', label: 'Overview', roles: ROLES },
		{ id: 'approvals', label: 'Approvals', roles: ['Manager', 'Finance Officer', 'Admin'] },
		{ id: 'reimbursements', label: 'Reimbursements', roles: ['Employee', 'Finance Officer', 'Admin', 'Executive'] },
		{ id: 'reports', label: 'Reports', roles: ['Admin', 'Manager', 'Finance Officer', 'Executive'] },
		{ id: 'settings', label: 'Organization settings', roles: ['Admin'] },
	].filter(tab => tab.roles.includes(user.role));
	const summary = data?.summary;
	if (loading) return <div className="corporate-loading" role="status">Loading corporate workspace…</div>;

	return <div className="corporate-page">
		<header className="corporate-heading">
			<div><p className="corporate-eyebrow">CORPORATE WORKSPACE · {user.role}</p><h2>{data?.organization.name}</h2><p>{user.department || 'Organization-wide access'} · {user.name}</p></div>
			{user.role === 'Admin' && <div className="joining-code"><span>Organization joining code</span><strong>{data?.organization.joining_code}</strong></div>}
		</header>
		{error && <div className="corporate-alert error" role="alert">{error}</div>}
		{message && <div className="corporate-alert success" role="status">{message}</div>}
		<nav className="corporate-tabs" aria-label="Corporate workspace sections">
			{tabs.map(tab => <button key={tab.id} type="button" className={view === tab.id ? 'selected' : ''} aria-current={view === tab.id ? 'page' : undefined} onClick={() => setView(tab.id)}>{tab.label}</button>)}
		</nav>
		{view === 'overview' ? <>
		<section className="corporate-stats" aria-label="Corporate expense summary">
			<article><span>Expenses in view</span><strong>{summary?.expense_count ?? 0}</strong></article>
			<article><span>Total submitted</span><strong>{money(summary?.total_amount)}</strong></article>
			<article><span>Awaiting manager</span><strong>{summary?.pending_manager ?? 0}</strong></article>
			<article><span>Awaiting finance</span><strong>{summary?.pending_finance ?? 0}</strong></article>
		</section>

		{data?.approvals?.length > 0 && <section className="corporate-panel">
			<div className="corporate-section-title"><div><h3>Approval queue</h3><p>Expenses assigned to your role in the approval workflow.</p></div><span className="queue-count">{data.approvals.length} pending</span></div>
			<div className="corporate-table-wrap"><table className="corporate-table">
				<thead><tr><th>Expense</th><th>Submitted by</th><th>Date</th><th>Amount</th><th>Stage</th><th>Decision</th></tr></thead>
				<tbody>{data.approvals.map(expense => <tr key={expense.expense_id}>
					<td><strong>{expense.merchant}</strong><small>{expense.category} · {expense.description || 'No description'}</small></td>
					<td>{expense.submitter}<small>{expense.department || 'No department'}</small></td>
					<td>{expense.date}</td><td>{money(expense.amount)}</td><td><span className="status-pill pending">{expense.status}</span></td>
					<td><div className="decision-controls"><input aria-label={`Approval note for ${expense.merchant}`} placeholder="Optional note" value={notes[expense.expense_id] || ''} onChange={event => setNotes({ ...notes, [expense.expense_id]: event.target.value })} /><button disabled={busy} onClick={() => runAction(() => corporateApi.decideExpense(expense.expense_id, { approve: true, note: notes[expense.expense_id] || '' }))}>Approve</button><button className="reject" disabled={busy} onClick={() => runAction(() => corporateApi.decideExpense(expense.expense_id, { approve: false, note: notes[expense.expense_id] || '' }))}>Reject</button></div></td>
				</tr>)}</tbody>
			</table></div>
		</section>}

		<div className="corporate-columns">
			{canSubmit && <section className="corporate-panel">
				<div className="corporate-section-title"><div><h3>Submit an expense</h3><p>New submissions go to a manager, then finance.</p></div></div>
				<form className="corporate-form" onSubmit={submitExpense}>
					<label>Amount (₹)<input type="number" min="0.01" step="0.01" value={form.amount} onChange={event => setForm({ ...form, amount: event.target.value })} required /></label>
					<label>Expense date<input type="date" value={form.date} onChange={event => setForm({ ...form, date: event.target.value })} required /></label>
					<label>Category<select value={form.category} onChange={event => setForm({ ...form, category: event.target.value })}>{CATEGORIES.map(category => <option key={category}>{category}</option>)}</select></label>
					<label>Merchant<input value={form.merchant} onChange={event => setForm({ ...form, merchant: event.target.value })} maxLength={160} required /></label>
					<label className="wide">Description<textarea value={form.description} onChange={event => setForm({ ...form, description: event.target.value })} maxLength={500} rows="3" /></label>
					<label className="wide">Receipt (PDF, PNG or JPG, up to 5 MB)<input type="file" accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg" onChange={event => {
						const selected = event.target.files?.[0] || null;
						setError('');
						if (selected && selected.size > 5 * 1024 * 1024) {
							setReceipt(null);
							setError('Receipt must be 5 MB or smaller.');
							event.target.value = '';
							return;
						}
						setReceipt(selected);
					}} /></label>
					{receipt && <p className="corporate-upload-file">{receipt.name} · {(receipt.size / 1024 / 1024).toFixed(2)} MB</p>}
					{busy && receipt && <div className="corporate-upload-progress" role="status"><span>Uploading receipt… {uploadProgress}%</span><progress max="100" value={uploadProgress} /></div>}
					<button className="corporate-primary" disabled={busy}>{busy ? 'Saving…' : 'Submit for approval'}</button>
				</form>
			</section>}
			{user.role === 'Admin' && <section className="corporate-panel">
				<div className="corporate-section-title"><div><h3>Departments</h3><p>Organize your team and assign members.</p></div></div>
				<form className="department-form" onSubmit={createDepartment}><input aria-label="New department name" placeholder="Department name" value={departmentName} onChange={event => setDepartmentName(event.target.value)} maxLength={100} required /><button className="corporate-primary" disabled={busy}>Add</button></form>
				<div className="department-tags">{data?.departments.map(department => <span key={department.department_id}>{department.name}</span>)}</div>
			</section>}
		</div>

		{user.role === 'Admin' && <section className="corporate-panel">
			<div className="corporate-section-title"><div><h3>Team and roles</h3><p>Assign access levels and departments for this organization.</p></div></div>
			<div className="corporate-table-wrap"><table className="corporate-table">
				<thead><tr><th>Team member</th><th>Role</th><th>Department</th><th></th></tr></thead>
				<tbody>{data?.members?.map(member => {
					const edit = memberEdits[member.membership_id] || { role: member.role, department_id: member.department_id ?? '' };
					return <tr key={member.membership_id}><td><strong>{member.name}</strong><small>{member.email}</small></td>
						<td><select aria-label={`Role for ${member.name}`} value={edit.role} onChange={event => setMemberEdits({ ...memberEdits, [member.membership_id]: { ...edit, role: event.target.value } })}>{ROLES.map(role => <option key={role}>{role}</option>)}</select></td>
						<td><select aria-label={`Department for ${member.name}`} value={edit.department_id} onChange={event => setMemberEdits({ ...memberEdits, [member.membership_id]: { ...edit, department_id: event.target.value } })}><option value="">Unassigned</option>{data.departments.map(department => <option key={department.department_id} value={department.department_id}>{department.name}</option>)}</select></td>
						<td><button className="table-action" disabled={busy} onClick={() => runAction(() => corporateApi.updateMember(member.membership_id, { role: edit.role, department_id: edit.department_id === '' ? null : Number(edit.department_id) }))}>Save</button></td>
					</tr>;
				})}</tbody>
			</table></div>
		</section>}

		<section className="corporate-panel">
			<div className="corporate-section-title"><div><h3>Expense history</h3><p>{user.role === 'Employee' ? 'Your corporate submissions.' : 'Corporate submissions visible to your role.'}</p></div></div>
			<div className="corporate-table-wrap"><table className="corporate-table">
				<thead><tr><th>Expense</th><th>Submitted by</th><th>Department</th><th>Date</th><th>Amount</th><th>Status</th></tr></thead>
				<tbody>{data?.expenses?.length ? data.expenses.map(expense => <tr key={expense.expense_id}>
					<td><strong>{expense.merchant}</strong><small>{expense.category} · {expense.description || 'No description'}</small></td>
					<td>{expense.submitter}</td><td>{expense.department || '—'}</td><td>{expense.date}</td><td>{money(expense.amount)}</td>
					<td><span className={`status-pill ${expense.status === 'Approved' ? 'approved' : expense.status === 'Rejected' ? 'rejected' : 'pending'}`}>{expense.status}</span></td>
				</tr>) : <tr><td className="empty-row" colSpan="6">No corporate expense submissions yet.</td></tr>}</tbody>
			</table></div>
		</section>
		</> : <CorporateWorkflowPanel view={view} user={user} onRefresh={refresh} />}
	</div>;
}
