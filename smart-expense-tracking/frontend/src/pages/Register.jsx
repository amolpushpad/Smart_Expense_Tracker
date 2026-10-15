import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function Register() {
	const [form, setForm] = useState({ name: '', email: '', password: '', confirm: '' });
	const [error, setError] = useState('');
	const [submitting, setSubmitting] = useState(false);
	const { register, clearError } = useAuth();
	const navigate = useNavigate();
	const update = (event) => setForm({ ...form, [event.target.name]: event.target.value });

	const submit = async (event) => {
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
		setSubmitting(true);
		try {
			const response = await register(form.name, form.email, form.password);
			navigate('/login', { replace: true, state: { message: response.data.message } });
		} catch (requestError) {
			setError(requestError.response?.data?.message || 'Unable to reach the server. Check that the backend is running.');
		} finally {
			setSubmitting(false);
		}
	};

	return <div className="auth-page"><div className="auth-card">
		<div className="auth-brand"><span>₹</span><strong>SmartExpense</strong></div>
		<h1>Create account</h1><p className="muted">Set up your account to start exploring the dashboard.</p>
		{error && <div className="form-error" role="alert">{error}</div>}
		<form onSubmit={submit}>
			<label>Full name<input name="name" value={form.name} onChange={update} placeholder="Your full name" autoComplete="name" required /></label>
			<label>Email<input name="email" type="email" value={form.email} onChange={update} placeholder="you@example.com" autoComplete="email" required /></label>
			<label>Password<input name="password" type="password" value={form.password} onChange={update} placeholder="Minimum 8 characters" autoComplete="new-password" minLength={8} maxLength={128} required /></label>
			<label>Confirm password<input name="confirm" type="password" value={form.confirm} onChange={update} placeholder="Repeat your password" autoComplete="new-password" required /></label>
			<button className="primary-btn" type="submit" disabled={submitting}>{submitting ? 'Creating account...' : 'Register'}</button>
		</form>
		<p className="auth-footer">Already have an account? <Link to="/login">Back to Login</Link></p>
	</div></div>;
}
