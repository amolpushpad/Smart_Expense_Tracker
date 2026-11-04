import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import CsvImportDialog from './CsvImportDialog';
import { expenseImportApi } from '../services/api';

vi.mock('../services/api', () => ({
	expenseImportApi: {
		preview: vi.fn(),
		confirm: vi.fn(),
	},
	getApiErrorMessage: vi.fn((_error, fallback) => fallback),
}));

afterEach(() => cleanup());

const preview = {
	summary: { rows_total: 3, valid_rows: 2, invalid_rows: 1, duplicate_rows: 1, total_amount: '30.00' },
	rows: [
		{
			row_number: 2,
			data: { date: '2026-08-01', amount: '10.00', category: 'Food', description: 'Lunch', vendor: 'Cafe' },
			errors: {},
			potential_duplicate: false,
			duplicate_of: null,
			duplicate_reason: null,
		},
		{
			row_number: 3,
			data: { date: '2026-08-02', amount: '20.00', category: 'Food', description: 'Dinner', vendor: 'Cafe' },
			errors: {},
			potential_duplicate: true,
			duplicate_of: { type: 'expense', id: 8 },
			duplicate_reason: 'normalized vendor matches',
		},
		{
			row_number: 4,
			data: { date: 'invalid', amount: '-1', category: 'Food', description: '', vendor: '' },
			errors: { date: 'Enter a valid date.', amount: 'Amount must be positive.' },
			potential_duplicate: false,
			duplicate_of: null,
			duplicate_reason: null,
		},
	],
};

describe('CSV import dialog', () => {
	it('shows validation and duplicate warnings and confirms only selected valid rows', async () => {
		expenseImportApi.preview.mockResolvedValue({ data: { data: preview } });
		expenseImportApi.confirm.mockResolvedValue({ data: { data: { imported: 2 } } });
		const onImported = vi.fn();
		render(<CsvImportDialog onClose={vi.fn()} onImported={onImported} />);

		fireEvent.change(screen.getByLabelText(/choose a csv file or drag it here/i), {
			target: { files: [new File(['date,amount,category'], 'expenses.csv', { type: 'text/csv' })] },
		});

		expect(await screen.findByText('Possible duplicate: normalized vendor matches.')).toBeInTheDocument();
		expect(screen.getByText('Enter a valid date. Amount must be positive.')).toBeInTheDocument();
		expect(screen.getByRole('checkbox', { name: 'Import row 2' })).toBeChecked();
		expect(screen.getByRole('checkbox', { name: 'Import row 3' })).not.toBeChecked();
		expect(screen.getByRole('checkbox', { name: 'Import row 4' })).toBeDisabled();

		fireEvent.click(screen.getByRole('checkbox', { name: 'Import row 3' }));
		fireEvent.click(screen.getByRole('button', { name: 'Import 2 selected' }));

		await waitFor(() => expect(expenseImportApi.confirm).toHaveBeenCalledWith([
			{ ...preview.rows[0].data, allow_duplicate: false },
			{ ...preview.rows[1].data, allow_duplicate: true },
		]));
		expect(onImported).toHaveBeenCalledWith(2);
	});

	it('rejects a non-CSV file before upload', async () => {
		const onImported = vi.fn();
		render(<CsvImportDialog onClose={vi.fn()} onImported={onImported} />);

		fireEvent.change(screen.getByLabelText(/choose a csv file or drag it here/i), {
			target: { files: [new File(['data'], 'expenses.txt', { type: 'text/plain' })] },
		});

		expect(await screen.findByRole('alert')).toHaveTextContent('.csv extension');
		expect(expenseImportApi.preview).not.toHaveBeenCalled();
	});
});
