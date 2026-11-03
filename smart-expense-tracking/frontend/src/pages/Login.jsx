import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import BrandLogo from '../components/BrandLogo';
import BrandName from '../components/BrandName';

export default function Login() {
	const [email, setEmail] = useState('');
	const [password, setPassword] = useState('');
	const [remember, setRemember] = useState(false);
	const [mode, setMode] = useState('personal');
	const [show, setShow] = useState(false);
	const [error, setError] = useState('');
	const [submitting, setSubmitting] = useState(false);
	const { login, clearError, error: authError } = useAuth();
	const navigate = useNavigate();
	const location = useLocation();

	const submit = async (event) => {
		event.preventDefault();
		setError('');
		clearError();
		if (!email.trim() || !/^\S+@\S+\.\S+$/.test(email) || !password) {
			setError('Enter a valid email address and your password.');
			return;
		}
		setSubmitting(true);
		try {
			const user = mode === 'corporate'
				? await login(email, password, remember, mode)
				: await login(email, password, remember);
			navigate(user.workspace_mode === 'corporate' ? '/corporate' : '/dashboard', { replace: true });
		} catch (requestError) {
			setError(requestError.response?.data?.message || 'Unable to reach the server. Check that the backend is running.');
		} finally {
			setSubmitting(false);
		}
	};

	return <div className="auth-page"><div className="auth-card">
		<div className="auth-brand">
			<div className="brand-lockup auth-brand-lockup">
				<BrandLogo />
				<BrandName />
			</div>
			<p className="spendwise-tagline">Smart Expense Tracking &amp; Analytics</p>
		</div>
		<h1>Welcome back</h1><p className="muted">Choose a workspace to continue.</p>
		<div className="mode-switch" role="group" aria-label="Workspace mode">
			<button type="button" className={mode === 'personal' ? 'selected' : ''} aria-pressed={mode === 'personal'} onClick={() => setMode('personal')}>Personal</button>
			<button type="button" className={mode === 'corporate' ? 'selected' : ''} aria-pressed={mode === 'corporate'} onClick={() => setMode('corporate')}>Corporate</button>
		</div>
		{mode === 'corporate' && <p className="workspace-hint">Sign in to your organization with your assigned corporate role.</p>}
		{location.state?.message && <div className="form-success" role="status">{location.state.message}</div>}
		{(error || authError) && <div className="form-error" role="alert">{error || authError}</div>}
		<form onSubmit={submit}>
			<label>Email<input type="email" value={email} onChange={event => setEmail(event.target.value)} placeholder="you@example.com" autoComplete="email" required /></label>
			<label>Password<div className="password-wrap"><input type={show ? 'text' : 'password'} value={password} onChange={event => setPassword(event.target.value)} placeholder="Enter your password" autoComplete="current-password" required /><button type="button" onClick={() => setShow(!show)} aria-label={show ? 'Hide password' : 'Show password'}>{show ? 'Hide' : 'Show'}</button></div></label>
			<div className="form-row"><label className="check"><input type="checkbox" checked={remember} onChange={event => setRemember(event.target.checked)} /> Remember me</label><span className="password-help">Forgot password? Change it in Profile after signing in.</span></div>
			<button className="primary-btn" type="submit" disabled={submitting}>{submitting ? 'Signing in...' : 'Login'}</button>
		</form>
		<p className="auth-footer">Don't have an account? <Link to="/register">Create one</Link><br /><Link to="/demo">Explore synthetic data demo</Link></p>
	</div></div>;
}
