import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { corporateApi } = vi.hoisted(() => ({
	corporateApi: {
		overview: vi.fn(),
		dashboard: vi.fn(),
		organization: vi.fn(),
		departments: vi.fn(),
		members: vi.fn(),
		auditLog: vi.fn(),
		reimbursements: vi.fn(),
	},
}));

vi.mock('../services/api', () => ({
	corporateApi,
	getApiErrorMessage: (_error, fallback) => fallback,
}));

import CorporateDashboard from './CorporateDashboard';

const response = data => ({ data: { data } });
const user = role => ({ role, name: 'Taylor User', department: 'Engineering' });

function overviewResponse() {
	return response({
		organization: { name: 'Acme Co', joining_code: 'ACME-CODE' },
		summary: { expense_count: 0, total_amount: '0.00', pending_manager: 0, pending_finance: 0 },
		departments: [],
		expenses: [],
		approvals: [],
		members: [],
	});
}

function dashboardResponse() {
	return response({
		summary: {
			expense_count: 0,
			total_amount: '0.00',
			pending_manager: 0,
			pending_finance: 0,
			approved: 0,
			paid: 0,
			rejected: 0,
		},
	});
}

beforeEach(() => {
	vi.clearAllMocks();
	corporateApi.overview.mockResolvedValue(overviewResponse());
	corporateApi.dashboard.mockResolvedValue(dashboardResponse());
	corporateApi.organization.mockResolvedValue(response({ organization: {
		name: 'Acme Co',
		organization_name: 'Acme Co',
		organization_email: '',
		contact_phone: '',
		address: '',
		joining_enabled: true,
		joining_code: 'ACME-CODE',
	} }));
	corporateApi.departments.mockResolvedValue(response({ departments: [] }));
	corporateApi.members.mockResolvedValue(response({ members: [] }));
	corporateApi.auditLog.mockResolvedValue(response({ events: [] }));
	corporateApi.reimbursements.mockResolvedValue(response({ reimbursements: [] }));
});

describe('CorporateDashboard', () => {
	it('shows role-specific corporate sections without exposing admin settings to employees', async () => {
		render(<CorporateDashboard user={user('Employee')} />);

		expect(await screen.findByRole('heading', { name: 'Acme Co' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Reimbursements' })).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: 'Approvals' })).not.toBeInTheDocument();
		expect(screen.queryByRole('button', { name: 'Organization settings' })).not.toBeInTheDocument();
	});

	it('loads organization controls only after an administrator opens that section', async () => {
		render(<CorporateDashboard user={user('Admin')} />);
		await screen.findByRole('heading', { name: 'Acme Co' });
		fireEvent.click(screen.getByRole('button', { name: 'Organization settings' }));

		expect(await screen.findByRole('heading', { name: 'Organization settings' })).toBeInTheDocument();
		await waitFor(() => expect(corporateApi.auditLog).toHaveBeenCalledTimes(1));
		expect(screen.getAllByText('ACME-CODE')).toHaveLength(2);
	});
});
