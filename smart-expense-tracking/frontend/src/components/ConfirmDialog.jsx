import { useEffect, useRef } from 'react';

export default function ConfirmDialog({ title, message, confirming, onCancel, onConfirm }) {
	const dialogRef = useRef(null);
	const cancelRef = useRef(null);

	useEffect(() => {
		const dialog = dialogRef.current;
		const previousFocus = document.activeElement;
		cancelRef.current?.focus();
		const handleKeyDown = event => {
			if (event.key === 'Escape' && !confirming) {
				event.preventDefault();
				onCancel();
			}
			if (event.key !== 'Tab' || !dialog) return;
			const focusable = [...dialog.querySelectorAll('button:not(:disabled)')];
			if (focusable.length < 2) {
				event.preventDefault();
				return;
			}
			if (event.shiftKey && document.activeElement === focusable[0]) {
				event.preventDefault();
				focusable.at(-1).focus();
			} else if (!event.shiftKey && document.activeElement === focusable.at(-1)) {
				event.preventDefault();
				focusable[0].focus();
			}
		};
		document.addEventListener('keydown', handleKeyDown);
		return () => {
			document.removeEventListener('keydown', handleKeyDown);
			if (previousFocus instanceof HTMLElement && previousFocus.isConnected) previousFocus.focus();
		};
	}, [confirming, onCancel]);

	return <div className="expense-dialog-backdrop" role="presentation">
		<section ref={dialogRef} className="expense-dialog confirm-dialog" role="alertdialog" aria-modal="true" aria-labelledby="confirm-dialog-title">
			<div className="expense-dialog-header">
				<div><h3 id="confirm-dialog-title">{title}</h3><p>{message}</p></div>
			</div>
			<div className="expense-form-actions">
				<button ref={cancelRef} type="button" className="secondary-button" onClick={onCancel} disabled={confirming}>Cancel</button>
				<button type="button" className="danger-button" onClick={onConfirm} disabled={confirming}>{confirming ? 'Deleting...' : 'Delete'}</button>
			</div>
		</section>
	</div>;
}
