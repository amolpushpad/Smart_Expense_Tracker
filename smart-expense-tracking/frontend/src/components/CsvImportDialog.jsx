import { useState } from 'react';
import { expenseImportApi, getApiErrorMessage } from '../services/api';

const MAX_FILE_BYTES = 5 * 1024 * 1024;
const currency = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 });

export default function CsvImportDialog({ onClose, onImported }) {
	const [preview, setPreview] = useState(null);
	const [selectedRows, setSelectedRows] = useState(new Set());
	const [uploading, setUploading] = useState(false);
	const [uploadProgress, setUploadProgress] = useState(0);
	const [importing, setImporting] = useState(false);
	const [dragging, setDragging] = useState(false);
	const [error, setError] = useState('');

	const selectFile = async file => {
		setError('');
		setPreview(null);
		setSelectedRows(new Set());
		if (!file) return;
		if (!file.name.toLowerCase().endsWith('.csv')) {
			setError('Choose a file with the .csv extension.');
			return;
		}
		if (file.size > MAX_FILE_BYTES) {
			setError('CSV files must be 5 MB or smaller.');
			return;
		}

		setUploading(true);
		setUploadProgress(0);
		try {
			const response = await expenseImportApi.preview(file, {
				onUploadProgress: event => {
					if (event.total) setUploadProgress(Math.round(event.loaded / event.total * 100));
				},
			});
			const data = response.data.data;
			setPreview(data);
			setSelectedRows(new Set(
				data.rows.filter(row => !Object.keys(row.errors).length && !row.potential_duplicate)
					.map(row => row.row_number),
			));
			setUploadProgress(100);
		} catch (requestError) {
			const rowErrors = requestError.response?.data?.errors;
			const detail = Array.isArray(rowErrors)
				? rowErrors.map(row => `Row ${row.row_number}: ${Object.values(row.errors).join(' ')}`).join(' ')
				: '';
			setError(detail || getApiErrorMessage(requestError, 'Unable to preview this CSV file.'));
		} finally {
			setUploading(false);
		}
	};

	const toggleRow = (rowNumber, checked) => {
		setSelectedRows(current => {
			const next = new Set(current);
			if (checked) next.add(rowNumber);
			else next.delete(rowNumber);
			return next;
		});
	};

	const confirmImport = async () => {
		const rows = preview.rows
			.filter(row => selectedRows.has(row.row_number))
			.map(row => ({ ...row.data, allow_duplicate: row.potential_duplicate }));
		if (!rows.length) {
			setError('Select at least one valid transaction to import.');
			return;
		}
		setImporting(true);
		setError('');
		try {
			const response = await expenseImportApi.confirm(rows);
			onImported(response.data.data.imported);
		} catch (requestError) {
			setError(getApiErrorMessage(requestError, 'Unable to import the selected transactions.'));
		} finally {
			setImporting(false);
		}
	};

	return <div className="expense-dialog-backdrop" onMouseDown={event => {
		if (event.target === event.currentTarget && !importing) onClose();
	}}>
		<section className="expense-dialog csv-import-dialog" role="dialog" aria-modal="true" aria-labelledby="csv-import-title">
			<div className="expense-dialog-header">
				<div><h3 id="csv-import-title">Import transactions from CSV</h3><p>Preview and approve valid rows before they are added to your account.</p></div>
				<button className="icon-button" type="button" onClick={onClose} disabled={importing} aria-label="Close CSV import">×</button>
			</div>

			<label
				className={`csv-import-dropzone${dragging ? ' is-dragging' : ''}`}
				onDragOver={event => { event.preventDefault(); setDragging(true); }}
				onDragLeave={() => setDragging(false)}
				onDrop={event => {
					event.preventDefault();
					setDragging(false);
					selectFile(event.dataTransfer.files[0]);
				}}
			>
				<strong>Choose a CSV file or drag it here</strong>
				<span>Required columns: date, amount, category · description and vendor are optional · 5 MB maximum</span>
				<input type="file" accept=".csv,text/csv" onChange={event => selectFile(event.target.files[0])} disabled={uploading || importing} />
			</label>

			{uploading && <div className="csv-import-progress" role="status">
				<span>Uploading and validating CSV… {uploadProgress}%</span>
				<progress max="100" value={uploadProgress} />
			</div>}
			{error && <div className="analytics-alert" role="alert">{error}</div>}

			{preview && <>
				<div className="csv-import-summary" aria-label="CSV import preview summary">
					<div><span>Total rows</span><strong>{preview.summary.rows_total}</strong></div>
					<div><span>Valid</span><strong>{preview.summary.valid_rows}</strong></div>
					<div><span>Invalid</span><strong>{preview.summary.invalid_rows}</strong></div>
					<div><span>Potential duplicates</span><strong>{preview.summary.duplicate_rows}</strong></div>
					<div><span>Valid row total</span><strong>{currency.format(Number(preview.summary.total_amount))}</strong></div>
				</div>
				<p className="csv-import-guidance">Rows that match an existing or another CSV transaction are unchecked by default. Review row errors before importing.</p>
				<div className="expense-table-wrap csv-import-table-wrap">
					<table className="expense-table csv-import-table">
						<thead><tr><th>Import</th><th>Row</th><th>Date</th><th className="amount-cell">Amount</th><th>Category</th><th>Description</th><th>Vendor</th><th>Validation</th></tr></thead>
						<tbody>{preview.rows.map(row => {
							const rowErrors = Object.values(row.errors);
							return <tr key={row.row_number} className={rowErrors.length ? 'csv-import-invalid' : row.potential_duplicate ? 'csv-import-duplicate' : ''}>
								<td><input
									type="checkbox"
									aria-label={`Import row ${row.row_number}`}
									checked={selectedRows.has(row.row_number)}
									disabled={Boolean(rowErrors.length) || importing}
									onChange={event => toggleRow(row.row_number, event.target.checked)}
								/></td>
								<td>{row.row_number}</td><td>{row.data.date}</td>
								<td className="amount-cell">{row.data.amount}</td><td>{row.data.category}</td>
								<td>{row.data.description || '—'}</td><td>{row.data.vendor || '—'}</td>
								<td>{rowErrors.length
									? rowErrors.join(' ')
									: row.potential_duplicate
										? `Possible duplicate: ${row.duplicate_reason}.`
										: 'Valid'}</td>
							</tr>;
						})}</tbody>
					</table>
				</div>
				<div className="expense-form-actions">
					<button className="secondary-button" type="button" onClick={onClose} disabled={importing}>Cancel</button>
					<button className="primary-btn" type="button" onClick={confirmImport} disabled={importing || uploading || selectedRows.size === 0}>
						{importing ? 'Importing…' : `Import ${selectedRows.size} selected`}
					</button>
				</div>
			</>}
		</section>
	</div>;
}
