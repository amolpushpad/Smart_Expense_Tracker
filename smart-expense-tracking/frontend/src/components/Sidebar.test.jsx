import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import Sidebar from './Sidebar';

const authMock = vi.hoisted(() => ({
	logout: vi.fn(),
	user: { workspace_mode: 'personal' },
}));

vi.mock('../context/AuthContext', () => ({
	useAuth: () => authMock,
}));

function renderSidebar(initialPath = '/dashboard') {
	return render(
		<MemoryRouter initialEntries={[initialPath]}>
			<Sidebar />
			<Routes>
				<Route path="/login" element={<p>Login route</p>} />
				<Route path="/dashboard" element={<p>Dashboard route</p>} />
				<Route path="/expenses" element={<p>Expenses route</p>} />
				<Route path="/income" element={<p>Income route</p>} />
				<Route path="/budgets" element={<p>Budgets route</p>} />
				<Route path="/analytics" element={<p>Analytics route</p>} />
				<Route path="/reports" element={<p>Reports route</p>} />
				<Route path="/profile" element={<p>Profile route</p>} />
			</Routes>
		</MemoryRouter>,
	);
}

beforeEach(() => {
	authMock.logout.mockReset();
	authMock.user = { workspace_mode: 'personal' };
});

afterEach(() => cleanup());

describe('SpendWise sidebar', () => {
	it('shows the official logo and navigates to every personal finance section', () => {
		const { container } = renderSidebar();

		expect(screen.getByAltText('SpendWise — Smart Expense Tracking & Analytics')).toHaveAttribute(
			'src',
			expect.stringContaining('spendwise-logo'),
		);
		expect(container.querySelector('.sidebar-brand-name')).toHaveTextContent('SpendWise');
		for (const section of ['Dashboard', 'Expenses', 'Income', 'Budgets', 'Analytics', 'Reports', 'Profile']) {
			fireEvent.click(screen.getByRole('link', { name: section }));
			expect(screen.getByText(`${section} route`)).toBeInTheDocument();
		}
	});

	it('logs out and navigates to login', async () => {
		authMock.logout.mockResolvedValue(true);
		renderSidebar();

		fireEvent.click(screen.getByRole('button', { name: /logout/i }));

		expect(await screen.findByText('Login route')).toBeInTheDocument();
		expect(authMock.logout).toHaveBeenCalledOnce();
	});
});
