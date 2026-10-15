import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import Login from './Login';
import Register from './Register';

const authMocks = vi.hoisted(() => ({
	login: vi.fn(),
	register: vi.fn(),
	clearError: vi.fn(),
}));

vi.mock('../context/AuthContext', () => ({
	useAuth: () => ({ ...authMocks, error: '' }),
}));

function renderAuthPage(page, initialPath) {
	return render(
		<MemoryRouter initialEntries={[initialPath]}>
			<Routes>
				<Route path="/login" element={<Login />} />
				<Route path="/register" element={page === 'register' ? <Register /> : <p>Register screen</p>} />
				<Route path="/dashboard" element={<p>Dashboard loaded</p>} />
			</Routes>
		</MemoryRouter>,
	);
}

beforeEach(() => {
	authMocks.login.mockReset();
	authMocks.register.mockReset();
	authMocks.clearError.mockReset();
});

afterEach(() => cleanup());

describe('authentication screens', () => {
	it('submits valid credentials and navigates to the dashboard', async () => {
		authMocks.login.mockResolvedValue({ name: 'Test User' });
		renderAuthPage('login', '/login');
		fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'test@example.com' } });
		fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'correct horse battery' } });
		fireEvent.click(screen.getByRole('button', { name: 'Login' }));

		expect(await screen.findByText('Dashboard loaded')).toBeInTheDocument();
		expect(authMocks.login).toHaveBeenCalledWith('test@example.com', 'correct horse battery', false);
	});

	it('shows the API error when login fails', async () => {
		authMocks.login.mockRejectedValue({ response: { data: { message: 'Invalid email or password.' } } });
		renderAuthPage('login', '/login');
		fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'test@example.com' } });
		fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'incorrect password' } });
		fireEvent.click(screen.getByRole('button', { name: 'Login' }));

		expect(await screen.findByRole('alert')).toHaveTextContent('Invalid email or password.');
	});

	it('does not submit registration when confirmation passwords differ', () => {
		renderAuthPage('register', '/register');
		fireEvent.change(screen.getByLabelText('Full name'), { target: { value: 'Test User' } });
		fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'test@example.com' } });
		fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'correct horse battery' } });
		fireEvent.change(screen.getByLabelText('Confirm password'), { target: { value: 'different password' } });
		fireEvent.click(screen.getByRole('button', { name: 'Register' }));

		expect(screen.getByRole('alert')).toHaveTextContent('Passwords do not match.');
		expect(authMocks.register).not.toHaveBeenCalled();
	});

	it('registers successfully and displays the sign-in confirmation', async () => {
		authMocks.register.mockResolvedValue({ data: { message: 'Account created. Sign in to continue.' } });
		renderAuthPage('register', '/register');
		fireEvent.change(screen.getByLabelText('Full name'), { target: { value: 'Test User' } });
		fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'test@example.com' } });
		fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'correct horse battery' } });
		fireEvent.change(screen.getByLabelText('Confirm password'), { target: { value: 'correct horse battery' } });
		fireEvent.click(screen.getByRole('button', { name: 'Register' }));

		expect(await screen.findByRole('status')).toHaveTextContent('Account created. Sign in to continue.');
		expect(authMocks.register).toHaveBeenCalledWith('Test User', 'test@example.com', 'correct horse battery');
	});
});
