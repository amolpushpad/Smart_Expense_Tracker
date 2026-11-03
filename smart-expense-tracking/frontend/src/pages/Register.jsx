import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import BrandLogo from '../components/BrandLogo';
import BrandName from '../components/BrandName';

export default function Register() {
	const [form, setForm] = useState({
		name: '', email: '', password: '', confirm: '', organization_name: '', joining_code: '',
	});
	const [mode, setMode] = useState('personal');
	const [corporateAction, setCorporateAction] = useState('create');
	const [showPassword, setShowPassword] = useState(false);
	const [showConfirm, setShowConfirm] = useState(false);
	const [error, setError] = useState('');
	const [submitting, setSubmitting] = useState(false);
	const { register, registerCorporateOrganization, joinCorporateOrganization, clearError } = useAuth();
	const navigate = useNavigate();
	const update = event => setForm({ ...form, [event.target.name]: event.target.value });

	const submit = async event => {
		event.preventDefault();
		setError('');
		clearError();
		if (!form.name.trim() || !/^\S+@\S+\.\S+$/.test(form.email) || form.password.length < 8) {
			setError('Enter your name, a valid email, and a password of at least 8 characters.');
			return;
		}
		if (form.password !== form.confirm) {
			setError('Passwords do not match.');
			return;
		}
		if (mode === 'corporate' && corporateAction === 'create' && !form.organization_name.trim()) {
			setError('Enter your organization name.');
			return;
		}
		if (mode === 'corporate' && corporateAction === 'join' && !form.joining_code.trim()) {
			setError('Enter your organization joining code.');
			return;
		}
		setSubmitting(true);
		try {
			let response;
			if (mode === 'personal') {
				response = await register(form.name, form.email, form.password);
			} else {
				const payload = { name: form.name, email: form.email, password: form.password };
				response = corporateAction === 'create'
					? await registerCorporateOrganization({ ...payload, organization_name: form.organization_name })
					: await joinCorporateOrganization({ ...payload, joining_code: form.joining_code });
			}
			navigate('/login', {
				replace: true,
				state: { message: `${response.data.message} Choose ${mode === 'corporate' ? 'Corporate' : 'Personal'} Mode to sign in.` },
			});
		} catch (requestError) {
			setError(requestError.response?.data?.message || 'Unable to reach the server. Check that the backend is running.');
		} finally {
			setSubmitting(false);
		}
	};

	return <div className="auth-page"><div className="auth-card">
		<div className="auth-brand">
			<BrandLogo />
			<BrandName />
			<p className="spendwise-tagline">Smart Expense Tracking<br />&amp; Analytics</p>
		</div>
		<h1>Create account</h1><p className="muted">Choose Personal or Corporate Mode to get started.</p>
		<div className="mode-switch" role="group" aria-label="Account mode">
			<button type="button" className={mode === 'personal' ? 'selected' : ''} aria-pressed={mode === 'personal'} onClick={() => setMode('personal')}>Personal</button>
			<button type="button" className={mode === 'corporate' ? 'selected' : ''} aria-pressed={mode === 'corporate'} onClick={() => setMode('corporate')}>Corporate</button>
		</div>
		{mode === 'corporate' && <div className="corporate-choice" role="group" aria-label="Corporate account action">
			<button type="button" className={corporateAction === 'create' ? 'selected' : ''} onClick={() => setCorporateAction('create')}>Register organization</button>
			<button type="button" className={corporateAction === 'join' ? 'selected' : ''} onClick={() => setCorporateAction('join')}>Join organization</button>
		</div>}
		{error && <div className="form-error" role="alert">{error}</div>}
		<form onSubmit={submit}>
			{mode === 'corporate' && corporateAction === 'create' && <label>Organization name<input name="organization_name" value={form.organization_name} onChange={update} placeholder="Acme Inc." maxLength={160} required /></label>}
			{mode === 'corporate' && corporateAction === 'join' && <label>Organization joining code<input name="joining_code" value={form.joining_code} onChange={update} placeholder="Enter your unique code" autoCapitalize="characters" required /></label>}
			<label>Full name<input name="name" value={form.name} onChange={update} placeholder="Your full name" autoComplete="name" required /></label>
			<label>Email<input name="email" type="email" value={form.email} onChange={update} placeholder="you@example.com" autoComplete="email" required /></label>
			<label>Password<div className="password-wrap"><input name="password" type={showPassword ? 'text' : 'password'} value={form.password} onChange={update} placeholder="Minimum 8 characters" autoComplete="new-password" minLength={8} maxLength={128} required /><button type="button" onClick={() => setShowPassword(value => !value)} aria-label={showPassword ? 'Hide password' : 'Show password'}>{showPassword ? 'Hide' : 'Show'}</button></div></label>
			<label>Confirm password<div className="password-wrap"><input name="confirm" type={showConfirm ? 'text' : 'password'} value={form.confirm} onChange={update} placeholder="Repeat your password" autoComplete="new-password" required /><button type="button" onClick={() => setShowConfirm(value => !value)} aria-label={showConfirm ? 'Hide confirmation password' : 'Show confirmation password'}>{showConfirm ? 'Hide' : 'Show'}</button></div></label>
			<button className="primary-btn" type="submit" disabled={submitting}>{submitting ? 'Creating account...' : mode === 'corporate' && corporateAction === 'create' ? 'Create organization' : mode === 'corporate' ? 'Join organization' : 'Register'}</button>
		</form>
		<p className="auth-footer">Already have an account? <Link to="/login">Back to Login</Link><br /><Link to="/demo">Explore synthetic data demo</Link></p>
	</div></div>;
}
