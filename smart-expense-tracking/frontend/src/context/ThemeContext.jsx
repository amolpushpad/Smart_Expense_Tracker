import { createContext, useContext, useEffect, useMemo, useState } from 'react';

const STORAGE_KEY = 'spendwise-theme';
const ThemeContext = createContext(null);

function readPreference() {
	try {
		const preference = window.localStorage.getItem(STORAGE_KEY);
		return ['light', 'dark', 'system'].includes(preference) ? preference : 'system';
	} catch (error) {
		if (error instanceof DOMException && error.name === 'SecurityError') return 'system';
		throw error;
	}
}

function resolveTheme(preference, systemPrefersDark) {
	return preference === 'system' ? (systemPrefersDark ? 'dark' : 'light') : preference;
}

export function ThemeProvider({ children }) {
	const [preference, setPreference] = useState(readPreference);
	const [systemPrefersDark, setSystemPrefersDark] = useState(
		() => window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false,
	);

	useEffect(() => {
		const media = window.matchMedia?.('(prefers-color-scheme: dark)');
		if (!media) return undefined;
		const updateSystemTheme = event => setSystemPrefersDark(event.matches);
		if (media.addEventListener) {
			media.addEventListener('change', updateSystemTheme);
			return () => media.removeEventListener('change', updateSystemTheme);
		}
		media.addListener(updateSystemTheme);
		return () => media.removeListener(updateSystemTheme);
	}, []);

	useEffect(() => {
		const theme = resolveTheme(preference, systemPrefersDark);
		document.documentElement.dataset.theme = theme;
		document.documentElement.style.colorScheme = theme;
		try {
			window.localStorage.setItem(STORAGE_KEY, preference);
		} catch (error) {
			if (!(error instanceof DOMException && error.name === 'SecurityError')) throw error;
		}
	}, [preference, systemPrefersDark]);

	const value = useMemo(() => ({ preference, setPreference }), [preference]);
	return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
	const context = useContext(ThemeContext);
	if (!context) throw new Error('useTheme must be used within a ThemeProvider.');
	return context;
}
