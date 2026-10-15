import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import ConfirmDialog from './ConfirmDialog';

afterEach(() => cleanup());

describe('confirmation dialog keyboard behavior', () => {
	it('focuses Cancel, closes on Escape, and restores the previous focus', () => {
		const trigger = document.createElement('button');
		document.body.appendChild(trigger);
		trigger.focus();
		const onCancel = vi.fn();
		render(<ConfirmDialog title="Delete?" message="Confirm deletion." confirming={false} onCancel={onCancel} onConfirm={vi.fn()} />);

		const cancel = screen.getByRole('button', { name: 'Cancel' });
		const confirm = screen.getByRole('button', { name: 'Delete' });
		expect(cancel).toHaveFocus();
		fireEvent.keyDown(document, { key: 'Tab', shiftKey: true });
		expect(confirm).toHaveFocus();
		fireEvent.keyDown(document, { key: 'Escape' });
		expect(onCancel).toHaveBeenCalledOnce();

		cleanup();
		expect(trigger).toHaveFocus();
		trigger.remove();
	});
});
