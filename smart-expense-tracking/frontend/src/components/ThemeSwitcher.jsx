import { useTheme } from '../context/ThemeContext';

export default function ThemeSwitcher({ className = '' }) {
	const { preference, setPreference } = useTheme();
	return <label className={`theme-switcher${className ? ` ${className}` : ''}`}>
		<span className="theme-switcher-label">Appearance</span>
		<select value={preference} onChange={event => setPreference(event.target.value)} aria-label="Color theme">
			<option value="system">System</option>
			<option value="light">Light</option>
			<option value="dark">Dark</option>
		</select>
	</label>;
}
