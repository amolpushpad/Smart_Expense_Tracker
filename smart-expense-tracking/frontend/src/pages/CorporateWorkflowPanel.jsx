import { useCallback, useEffect, useMemo, useState } from 'react';
import { corporateApi, getApiErrorMessage } from '../services/api';

const ROLES = ['Admin', 'Employee', 'Manager', 'Finance Officer', 'Executive'];
const money = amount => new Intl.NumberFormat(undefined, { style: 'currency', currency: 'INR' }).format(Number(amount || 0));

function downloadBlob(blob, filename) {
	const url = URL.createObjectURL(blob);
	const link = document.createElement('a');
	link.href = url;
	link.download = filename;
	link.click();
	URL.revokeObjectURL(url);
}

function DataTable({ children, headers, empty = 'No records to display.' }) {
	const hasRows = Array.isArray(children) ? children.length > 0 : Boolean(children);
	return <div className="corporate-table-wrap"><table className="corporate-table">
		<thead><tr>{headers.map(header => <th key={header}>{header}</th>)}</tr></thead>
		<tbody>{hasRows ? children : <tr><td className="empty-row" colSpan={headers.length}>{empty}</td></tr>}</tbody>
	</table></div>;
}

function ApprovalPanel({ role, onRefresh }) {
	const [queue, setQueue] = useState(role === 'Manager' ? 'manager' : 'finance');
	const [rows, setRows] = useState([]);
	const [comments, setComments] = useState({});
	const [history, setHistory] = useState(null);
	const [loading, setLoading] = useState(true);
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState('');
	const [notice, setNotice] = useState('');

	const refresh = useCallback(async () => {
		setLoading(true);
		try {
			const response = await corporateApi.approvals({ queue });
			setRows(response.data.data.expenses);
			setError('');
		} catch (requestError) {
			setError(getApiErrorMessage(requestError, 'Approval queue could not be loaded.'));
		} finally {
			setLoading(false);
		}
	}, [queue]);

	useEffect(() => { refresh(); }, [refresh]);

	const act = async (expenseId, action) => {
		setBusy(true);
		setError('');
		setNotice('');
		try {
			await corporateApi.review(expenseId, action, { comments: comments[expenseId] || '' });
			setNotice(action === 'pay' ? 'Reimbursement marked as paid.' : `Expense ${action === 'approve' ? 'approved' : 'rejected'}.`);
			await Promise.all([refresh(), onRefresh()]);
		} catch (requestError) {
			setError(getApiErrorMessage(requestError));
		} finally {
			setBusy(false);
		}
	};

	const showHistory = async expenseId => {
		try {
			const response = await corporateApi.expense(expenseId);
			setHistory(response.data.data.expense);
			setError('');
		} catch (requestError) {
			setError(getApiErrorMessage(requestError, 'Expense details could not be loaded.'));
		}
	};

	const downloadReceipt = async expense => {
		try {
			const response = await corporateApi.receipt(expense.expense_id);
			downloadBlob(response.data, expense.receipt_filename || `receipt-${expense.expense_id}`);
		} catch (requestError) {
			setError(getApiErrorMessage(requestError, 'Receipt could not be downloaded.'));
		}
	};

	if (loading) return <p className="corporate-loading" role="status">Loading approvals…</p>;
	return <section className="corporate-panel">
		<div className="corporate-section-title">
			<div><h3>Approval queue</h3><p>Review expenses in the correct approval stage.</p></div>
			{role === 'Admin' && <label className="corporate-inline-field">Queue
				<select value={queue} onChange={event => setQueue(event.target.value)}><option value="manager">Manager review</option><option value="finance">Finance review</option></select>
			</label>}
		</div>
		{error && <div className="corporate-alert error" role="alert">{error}</div>}
		{notice && <div className="corporate-alert success" role="status">{notice}</div>}
		<DataTable headers={['Expense', 'Submitted by', 'Date', 'Amount', 'Receipt', 'Decision']}>
			{rows.map(expense => <tr key={expense.expense_id}>
				<td><strong>{expense.merchant}</strong><small>{expense.category} · {expense.description || 'No description'}</small><button className="table-action" onClick={() => showHistory(expense.expense_id)}>Details and history</button></td>
				<td>{expense.submitter}<small>{expense.department || 'No department'}</small></td>
				<td>{expense.date}</td>
				<td>{money(expense.amount)}</td>
				<td>{expense.has_receipt ? <button className="table-action" onClick={() => downloadReceipt(expense)}>Download receipt</button> : '—'}</td>
				<td><div className="decision-controls approval-actions">
					<input aria-label={`Review note for ${expense.merchant}`} placeholder="Note or rejection reason" value={comments[expense.expense_id] || ''} onChange={event => setComments({ ...comments, [expense.expense_id]: event.target.value })} />
					<button disabled={busy} onClick={() => act(expense.expense_id, 'approve')}>Approve</button>
					<button className="reject" disabled={busy} onClick={() => act(expense.expense_id, 'reject')}>Reject</button>
				</div></td>
			</tr>)}
		</DataTable>
		{history && <div className="corporate-history" role="region" aria-label="Expense approval history">
			<div className="corporate-section-title"><div><h4>{history.merchant} · {history.status}</h4><p>{history.date} · {money(history.amount)}</p></div><button className="table-action" onClick={() => setHistory(null)}>Close</button></div>
			{history.history?.length ? history.history.map(item => <p key={item.approval_id}>{item.reviewer_name} · {item.previous_status || 'Submitted'} → {item.new_status}{item.comments ? ` · ${item.comments}` : ''}</p>) : <p>No review actions recorded yet.</p>}
		</div>}
	</section>;
}

function ReimbursementPanel({ role, onRefresh }) {
	const [status, setStatus] = useState('unpaid');
	const [rows, setRows] = useState([]);
	const [loading, setLoading] = useState(true);
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState('');
	const [notice, setNotice] = useState('');
	const refresh = useCallback(async () => {
		setLoading(true);
		try {
			const response = await corporateApi.reimbursements({ status });
			setRows(response.data.data.reimbursements);
			setError('');
		} catch (requestError) {
			setError(getApiErrorMessage(requestError, 'Reimbursements could not be loaded.'));
		} finally {
			setLoading(false);
		}
	}, [status]);
	useEffect(() => { refresh(); }, [refresh]);
	const markPaid = async expenseId => {
		setBusy(true);
		setError('');
		try {
			await corporateApi.review(expenseId, 'pay');
			setNotice('Reimbursement marked as paid.');
			await Promise.all([refresh(), onRefresh()]);
		} catch (requestError) {
			setError(getApiErrorMessage(requestError));
		} finally {
			setBusy(false);
		}
	};
	if (loading) return <p className="corporate-loading" role="status">Loading reimbursements…</p>;
	return <section className="corporate-panel">
		<div className="corporate-section-title"><div><h3>Reimbursements</h3><p>Track approved expenses and payment status.</p></div>
			<label className="corporate-inline-field">Show <select value={status} onChange={event => setStatus(event.target.value)}><option value="unpaid">Awaiting payment</option><option value="paid">Paid</option></select></label>
		</div>
		{error && <div className="corporate-alert error" role="alert">{error}</div>}
		{notice && <div className="corporate-alert success" role="status">{notice}</div>}
		<DataTable headers={['Expense', 'Submitted by', 'Date', 'Amount', 'Payment status', ...(role === 'Admin' || role === 'Finance Officer' ? ['Action'] : [])]}>
			{rows.map(expense => <tr key={expense.expense_id}>
				<td><strong>{expense.merchant}</strong><small>{expense.category}</small></td>
				<td>{expense.submitter}</td><td>{expense.date}</td><td>{money(expense.amount)}</td><td>{expense.reimbursement_status}</td>
				{(role === 'Admin' || role === 'Finance Officer') && <td>{!expense.paid_at && <button className="table-action" disabled={busy} onClick={() => markPaid(expense.expense_id)}>Mark paid</button>}</td>}
			</tr>)}
		</DataTable>
	</section>;
}

function ReportsPanel() {
	const [filters, setFilters] = useState({ start_date: '', end_date: '', category: '' });
	const [appliedFilters, setAppliedFilters] = useState({});
	const [report, setReport] = useState(null);
	const [transactions, setTransactions] = useState([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState('');
	const params = useMemo(() => Object.fromEntries(Object.entries(appliedFilters).filter(([, value]) => value)), [appliedFilters]);
	const refresh = useCallback(async () => {
		setLoading(true);
		try {
			const [summaryResponse, transactionResponse] = await Promise.all([
				corporateApi.reportSummary(params),
				corporateApi.transactions(params),
			]);
			setReport(summaryResponse.data.data);
			setTransactions(transactionResponse.data.data.transactions);
			setError('');
		} catch (requestError) {
			setError(getApiErrorMessage(requestError, 'Corporate reports could not be loaded.'));
		} finally {
			setLoading(false);
		}
	}, [params]);
	useEffect(() => { refresh(); }, [refresh]);
	const download = async () => {
		try {
			const response = await corporateApi.exportReport(params);
			downloadBlob(response.data, 'corporate-expenses.csv');
		} catch (requestError) {
			setError(getApiErrorMessage(requestError, 'Report export could not be downloaded.'));
		}
	};
	return <div className="corporate-report-layout">
		<section className="corporate-panel">
			<div className="corporate-section-title"><div><h3>Corporate reports</h3><p>Filter, review, and export organization transactions.</p></div><button className="corporate-primary" onClick={download}>Export CSV</button></div>
			<form className="corporate-report-filters" onSubmit={event => { event.preventDefault(); setAppliedFilters(filters); }}>
				<label>From<input type="date" value={filters.start_date} onChange={event => setFilters({ ...filters, start_date: event.target.value })} /></label>
				<label>To<input type="date" value={filters.end_date} onChange={event => setFilters({ ...filters, end_date: event.target.value })} /></label>
				<label>Category<input value={filters.category} maxLength="80" onChange={event => setFilters({ ...filters, category: event.target.value })} /></label>
				<button className="corporate-primary">Apply filters</button>
			</form>
			{error && <div className="corporate-alert error" role="alert">{error}</div>}
			{loading ? <p className="corporate-loading" role="status">Loading reports…</p> : <>
				<div className="corporate-report-stats">
					{[
						['Transactions', report?.summary.submitted_count],
						['Total submitted', money(report?.summary.submitted_amount)],
						['Awaiting review', Number(report?.summary.pending_manager_count || 0) + Number(report?.summary.pending_finance_count || 0)],
						['Approved / unpaid', money(report?.summary.approved_amount)],
						['Paid', money(report?.summary.paid_amount)],
						['Rejected', report?.summary.rejected_count],
					].map(([label, value]) => <article key={label}><span>{label}</span><strong>{value ?? 0}</strong></article>)}
				</div>
				<div className="corporate-report-grid">
					<ReportBreakdown title="By department" rows={report?.by_department || []} nameKey="department_name" />
					<ReportBreakdown title="By category" rows={report?.by_category || []} nameKey="category" />
					<ReportBreakdown title="By month" rows={report?.monthly || []} nameKey="month" />
					{report?.by_employee && <ReportBreakdown title="By employee" rows={report.by_employee} nameKey="employee_name" />}
				</div>
				<div className="corporate-section-title"><div><h3>Recent transactions</h3><p>Latest 50 records matching these filters.</p></div></div>
				<DataTable headers={['Expense', 'Employee', 'Department', 'Date', 'Amount', 'Status']}>
					{transactions.map(expense => <tr key={expense.expense_id}><td><strong>{expense.merchant}</strong><small>{expense.category}</small></td><td>{expense.submitter}</td><td>{expense.department || '—'}</td><td>{expense.date}</td><td>{money(expense.amount)}</td><td>{expense.status}{expense.paid_at ? ' · Paid' : ''}</td></tr>)}
				</DataTable>
			</>}
		</section>
	</div>;
}

function ReportBreakdown({ title, rows, nameKey }) {
	return <section className="corporate-panel">
		<h3>{title}</h3>
		<DataTable headers={['Group', 'Transactions', 'Amount']}>
			{rows.map((row, index) => <tr key={`${row[nameKey]}-${index}`}><td>{row[nameKey] || 'Unassigned'}</td><td>{row.submitted_count}</td><td>{money(row.submitted_amount)}</td></tr>)}
		</DataTable>
	</section>;
}

function AdminPanel() {
	const [organization, setOrganization] = useState(null);
	const [departments, setDepartments] = useState([]);
	const [members, setMembers] = useState([]);
	const [audit, setAudit] = useState([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState('');
	const [notice, setNotice] = useState('');
	const [busy, setBusy] = useState(false);
	const [newDepartment, setNewDepartment] = useState('');
	const [member, setMember] = useState({ name: '', email: '', password: '', role: 'Employee', department_id: '' });

	const refresh = useCallback(async () => {
		setLoading(true);
		try {
			const [organizationResponse, departmentResponse, memberResponse, auditResponse] = await Promise.all([
				corporateApi.organization(),
				corporateApi.departments(),
				corporateApi.members(),
				corporateApi.auditLog(),
			]);
			setOrganization(organizationResponse.data.data.organization);
			setDepartments(departmentResponse.data.data.departments);
			setMembers(memberResponse.data.data.members);
			setAudit(auditResponse.data.data.events);
			setError('');
		} catch (requestError) {
			setError(getApiErrorMessage(requestError, 'Organization settings could not be loaded.'));
		} finally {
			setLoading(false);
		}
	}, []);
	useEffect(() => { refresh(); }, [refresh]);

	const act = async callback => {
		setBusy(true);
		setError('');
		setNotice('');
		try {
			await callback();
			setNotice('Changes saved successfully.');
			await refresh();
		} catch (requestError) {
			setError(getApiErrorMessage(requestError));
		} finally {
			setBusy(false);
		}
	};
	const saveOrganization = event => {
		event.preventDefault();
		act(() => corporateApi.updateOrganization({
			name: organization.name,
			organization_email: organization.organization_email,
			contact_phone: organization.contact_phone,
			address: organization.address,
			joining_enabled: organization.joining_enabled,
		}));
	};
	const addDepartment = event => {
		event.preventDefault();
		act(async () => {
			await corporateApi.createDepartment({ name: newDepartment });
			setNewDepartment('');
		});
	};
	const addMember = event => {
		event.preventDefault();
		act(async () => {
			await corporateApi.addMember({
				...member,
				department_id: member.department_id ? Number(member.department_id) : null,
			});
			setMember({ name: '', email: '', password: '', role: 'Employee', department_id: '' });
		});
	};
	const saveMember = (membershipId, edits) => act(() => corporateApi.updateWorkflowMember(membershipId, edits));
	const saveDepartment = (departmentId, name, managerId, status) => act(() => corporateApi.updateDepartment(departmentId, {
		name,
		manager_id: managerId ? Number(managerId) : null,
		status,
	}));
	const regenerateCode = () => act(async () => {
		const response = await corporateApi.regenerateJoiningCode();
		setOrganization(response.data.data.organization);
	});

	if (loading) return <p className="corporate-loading" role="status">Loading organization controls…</p>;
	return <div className="corporate-admin-layout">
		{error && <div className="corporate-alert error" role="alert">{error}</div>}
		{notice && <div className="corporate-alert success" role="status">{notice}</div>}
		<section className="corporate-panel">
			<div className="corporate-section-title"><div><h3>Organization settings</h3><p>Update organization contact details and joining access.</p></div></div>
			<form className="corporate-settings-form" onSubmit={saveOrganization}>
				<label>Organization name<input value={organization.name} maxLength="160" onChange={event => setOrganization({ ...organization, name: event.target.value })} required /></label>
				<label>Contact email<input type="email" value={organization.organization_email || ''} onChange={event => setOrganization({ ...organization, organization_email: event.target.value })} /></label>
				<label>Contact phone<input value={organization.contact_phone || ''} maxLength="30" onChange={event => setOrganization({ ...organization, contact_phone: event.target.value })} /></label>
				<label>Address<input value={organization.address || ''} maxLength="300" onChange={event => setOrganization({ ...organization, address: event.target.value })} /></label>
				<label className="corporate-check"><input type="checkbox" checked={organization.joining_enabled} onChange={event => setOrganization({ ...organization, joining_enabled: event.target.checked })} /> Accept new members with the joining code</label>
				<div className="corporate-code-control"><span>Joining code <strong>{organization.joining_code}</strong></span><button type="button" className="table-action" disabled={busy} onClick={regenerateCode}>Regenerate code</button></div>
				<button className="corporate-primary" disabled={busy}>Save organization settings</button>
			</form>
		</section>
		<section className="corporate-panel">
			<div className="corporate-section-title"><div><h3>Departments</h3><p>Assign a manager and control active departments.</p></div></div>
			<form className="department-form" onSubmit={addDepartment}><input aria-label="New department name" placeholder="Department name" value={newDepartment} onChange={event => setNewDepartment(event.target.value)} maxLength={100} required /><button className="corporate-primary" disabled={busy}>Add department</button></form>
			<DataTable headers={['Department', 'Members', 'Manager', 'Status', '']}>
				{departments.map(department => <DepartmentRow key={department.department_id} department={department} members={members} busy={busy} onSave={saveDepartment} />)}
			</DataTable>
		</section>
		<section className="corporate-panel">
			<div className="corporate-section-title"><div><h3>Team access</h3><p>Assign corporate roles and departments or deactivate access.</p></div></div>
			<form className="corporate-member-form" onSubmit={addMember}>
				<label>Name<input value={member.name} maxLength="120" onChange={event => setMember({ ...member, name: event.target.value })} required /></label>
				<label>Email<input type="email" value={member.email} onChange={event => setMember({ ...member, email: event.target.value })} required /></label>
				<label>Temporary password<input type="password" minLength="8" maxLength="128" value={member.password} onChange={event => setMember({ ...member, password: event.target.value })} required /></label>
				<label>Role<select value={member.role} onChange={event => setMember({ ...member, role: event.target.value })}>{ROLES.map(role => <option key={role}>{role}</option>)}</select></label>
				<label>Department<select value={member.department_id} onChange={event => setMember({ ...member, department_id: event.target.value })}><option value="">Unassigned</option>{departments.map(department => <option key={department.department_id} value={department.department_id}>{department.name}</option>)}</select></label>
				<button className="corporate-primary" disabled={busy}>Add team member</button>
			</form>
			<DataTable headers={['Team member', 'Role', 'Department', 'Access', '']}>
				{members.map(item => <MemberRow key={item.membership_id} member={item} departments={departments} busy={busy} onSave={saveMember} />)}
			</DataTable>
		</section>
		<section className="corporate-panel">
			<div className="corporate-section-title"><div><h3>Recent activity</h3><p>Administrative and approval actions from this organization.</p></div></div>
			<DataTable headers={['Actor', 'Action', 'Details', 'Date']}>
				{audit.map(item => <tr key={item.log_id}><td>{item.actor_name}</td><td>{item.action}</td><td>{item.details || '—'}</td><td>{new Date(item.created_at).toLocaleString()}</td></tr>)}
			</DataTable>
		</section>
	</div>;
}

function DepartmentRow({ department, members, busy, onSave }) {
	const [name, setName] = useState(department.name);
	const [managerId, setManagerId] = useState(department.manager_id || '');
	const [status, setStatus] = useState(department.status);
	return <tr>
		<td><input aria-label={`Name for ${department.name}`} value={name} maxLength="100" onChange={event => setName(event.target.value)} /></td><td>{department.member_count}</td>
		<td><select aria-label={`Manager for ${department.name}`} value={managerId} onChange={event => setManagerId(event.target.value)}><option value="">Unassigned</option>{members.filter(member => member.role === 'Manager' && member.membership_status === 'active').map(member => <option key={member.user_id} value={member.user_id}>{member.name}</option>)}</select></td>
		<td><select aria-label={`Status for ${department.name}`} value={status} onChange={event => setStatus(event.target.value)}><option value="active">Active</option><option value="inactive">Inactive</option></select></td>
		<td><button className="table-action" disabled={busy} onClick={() => onSave(department.department_id, name, managerId, status)}>Save</button></td>
	</tr>;
}

function MemberRow({ member, departments, busy, onSave }) {
	const [role, setRole] = useState(member.role);
	const [departmentId, setDepartmentId] = useState(member.department_id || '');
	const [status, setStatus] = useState(member.membership_status);
	return <tr>
		<td><strong>{member.name}</strong><small>{member.email}</small></td>
		<td><select aria-label={`Role for ${member.name}`} value={role} onChange={event => setRole(event.target.value)}>{ROLES.map(item => <option key={item}>{item}</option>)}</select></td>
		<td><select aria-label={`Department for ${member.name}`} value={departmentId} onChange={event => setDepartmentId(event.target.value)}><option value="">Unassigned</option>{departments.map(item => <option key={item.department_id} value={item.department_id}>{item.name}</option>)}</select></td>
		<td><select aria-label={`Access status for ${member.name}`} value={status} onChange={event => setStatus(event.target.value)}><option value="active">Active</option><option value="inactive">Inactive</option></select></td>
		<td><button className="table-action" disabled={busy} onClick={() => onSave(member.membership_id, {
			role,
			department_id: departmentId ? Number(departmentId) : null,
			membership_status: status,
		})}>Save</button></td>
	</tr>;
}

export default function CorporateWorkflowPanel({ view, user, onRefresh }) {
	if (view === 'approvals') return <ApprovalPanel role={user.role} onRefresh={onRefresh} />;
	if (view === 'reimbursements') return <ReimbursementPanel role={user.role} onRefresh={onRefresh} />;
	if (view === 'reports') return <ReportsPanel />;
	if (view === 'settings') return <AdminPanel />;
	return null;
}
