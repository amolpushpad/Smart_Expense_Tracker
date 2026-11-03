import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { demoApi } from '../services/api';
import DatasetDemo from './DatasetDemo';

vi.mock('../services/api', () => ({
	demoApi: {
		analytics: vi.fn(),
		modelEvaluation: vi.fn(),
		estimateMonthlyExpenses: vi.fn(),
	},
	getApiErrorMessage: (_error, fallback) => fallback,
}));

afterEach(() => cleanup());

const analytics = {
	dataset: {
		currency: 'INR',
		usd_inr_rate: '95.0000',
		source_sha256: 'abc123',
		snapshot_date_range: { start: '2021-07-23', end: '2025-07-22' },
	},
	overview: {
		synthetic_profiles: 32424,
		average_monthly_income_inr: 100000,
		average_monthly_expenses_inr: 50000,
		median_monthly_expenses_inr: 45000,
		profiles_with_loan: 100,
		profiles_with_loan_percent: 25,
	},
	employment_groups: [{
		employment_status: 'Employed',
		records: 100,
		average_monthly_income_inr: 100000,
		average_monthly_expenses_inr: 50000,
		median_monthly_expenses_inr: 45000,
	}],
	loan_types: [{ loan_type: 'No loan', records: 300 }],
};

beforeEach(() => {
	demoApi.analytics.mockResolvedValue({ data: { data: analytics } });
	demoApi.modelEvaluation.mockResolvedValue({ data: { data: null } });
});

describe('synthetic dataset demo', () => {
	it('labels aggregate data as synthetic and keeps the sign-in flow separate', async () => {
		render(<MemoryRouter><DatasetDemo /></MemoryRouter>);

		expect(screen.getByRole('heading', { name: 'Synthetic finance data demo' })).toBeInTheDocument();
		expect(screen.getByRole('note')).toHaveTextContent('not transaction history');
		await waitFor(() => expect(screen.getByText('32,424')).toBeInTheDocument());
		expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login');
		expect(screen.getByRole('heading', { name: 'Average monthly amounts by employment' })).toBeInTheDocument();
		expect(screen.getByRole('heading', { name: 'Loan profile distribution' })).toBeInTheDocument();
	});

	it('displays INR and does not present transaction records', async () => {
		render(<MemoryRouter><DatasetDemo /></MemoryRouter>);

		expect(screen.getByText('SEPARATE SAMPLE VIEW · INR')).toBeInTheDocument();
		await waitFor(() => expect(screen.getByRole('table')).toBeInTheDocument());
		expect(screen.queryByText('Recent transactions')).not.toBeInTheDocument();
	});
});
