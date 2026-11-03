import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import ThemeSwitcher from '../components/ThemeSwitcher';
import { ThemeProvider } from './ThemeContext';

describe('theme preference', () => {
	afterEach(() => {
		cleanup();
		window.localStorage.clear();
		document.documentElement.removeAttribute('data-theme');
		document.documentElement.style.removeProperty('color-scheme');
		vi.unstubAllGlobals();
	});

	it('persists the selected theme and applies it to the document', () => {
		render(<ThemeProvider><ThemeSwitcher /></ThemeProvider>);
		fireEvent.change(screen.getByLabelText('Color theme'), { target: { value: 'dark' } });

		expect(document.documentElement.dataset.theme).toBe('dark');
		expect(document.documentElement.style.colorScheme).toBe('dark');
		expect(window.localStorage.getItem('spendwise-theme')).toBe('dark');
	});

	it('restores a saved preference when mounted', () => {
		window.localStorage.setItem('spendwise-theme', 'light');
		render(<ThemeProvider><ThemeSwitcher /></ThemeProvider>);

		expect(screen.getByLabelText('Color theme')).toHaveValue('light');
		expect(document.documentElement.dataset.theme).toBe('light');
	});

	it('follows operating system changes when System is selected', () => {
		const listeners = new Set();
		let prefersDark = true;
		vi.stubGlobal('matchMedia', () => ({
			get matches() { return prefersDark; },
			addEventListener: (_event, listener) => listeners.add(listener),
			removeEventListener: (_event, listener) => listeners.delete(listener),
		}));
		window.localStorage.setItem('spendwise-theme', 'system');
		render(<ThemeProvider><ThemeSwitcher /></ThemeProvider>);
		expect(document.documentElement.dataset.theme).toBe('dark');

		prefersDark = false;
		act(() => listeners.forEach(listener => listener({ matches: false })));
		expect(document.documentElement.dataset.theme).toBe('light');
	});
});
