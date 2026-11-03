import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import BrandLogo from './BrandLogo';
import BrandName from './BrandName';

const personalLinks = [
	['/dashboard', 'grid', 'Dashboard'],
	['/expenses', 'expense', 'Expenses'],
	['/income', 'income', 'Income'],
	['/budgets', 'budget', 'Budgets'],
	['/analytics', 'analytics', 'Analytics'],
	['/reports', 'report', 'Reports'],
	['/profile', 'profile', 'Profile'],
];

function NavigationIcon({ name }) {
	const paths = {
		grid: <><rect x="3.5" y="3.5" width="7" height="7" rx="1.5" /><rect x="13.5" y="3.5" width="7" height="7" rx="1.5" /><rect x="3.5" y="13.5" width="7" height="7" rx="1.5" /><rect x="13.5" y="13.5" width="7" height="7" rx="1.5" /></>,
		expense: <><path d="M7 7h10v10" /><path d="m17 7-10 10" /><path d="M5 5v14h14" /></>,
		income: <><path d="M7 17 17 7" /><path d="M7 7h10v10" /><path d="M5 19h14" /></>,
		budget: <><rect x="4" y="4" width="16" height="16" rx="2" /><path d="M8 8h8M8 12h8M8 16h4" /></>,
		analytics: <><path d="M4 19V5M4 19h16" /><path d="m7 15 4-4 3 2 5-6" /></>,
		report: <><path d="M7 3.5h7l4 4V20a1 1 0 0 1-1 1H7a2 2 0 0 1-2-2V5.5a2 2 0 0 1 2-2Z" /><path d="M14 4v4h4M8 12h8M8 16h8" /></>,
		profile: <><circle cx="12" cy="8" r="3.5" /><path d="M5 20a7 7 0 0 1 14 0" /></>,
		corporate: <><rect x="3.5" y="7" width="17" height="13" rx="2" /><path d="M8 7V4h8v3M3.5 12h17M10 12v2h4v-2" /></>,
		logout: <><path d="M10 17l5-5-5-5M15 12H3" /><path d="M12 3h6a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-6" /></>,
	};
	return <svg className="navigation-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

export default function Sidebar({ open = false, onClose = () => {} }) {
	const { logout, user } = useAuth();
	const navigate = useNavigate();
	const links = user?.workspace_mode === 'corporate'
		? [['/corporate', 'corporate', 'Corporate workspace']]
		: personalLinks;

	return <>
		{open && <button className="sidebar-backdrop" type="button" aria-label="Close navigation" onClick={onClose} />}
		<aside className={`sidebar${open ? ' is-open' : ''}`} aria-label="Application sidebar">
		<div className="brand">
			<div className="brand-lockup sidebar-brand-lockup">
				<BrandLogo className="sidebar-brand-logo" />
				<BrandName className="sidebar-brand-name" />
			</div>
			<button className="sidebar-close" type="button" aria-label="Close navigation" onClick={onClose}>×</button>
		</div>
		<nav aria-label="Main navigation">
			{links.map(([to, icon, label]) => (
				<NavLink key={to} to={to} className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
					<NavigationIcon name={icon} /><span>{label}</span>
				</NavLink>
			))}
		</nav>
		<button className="logout" onClick={async () => { if (await logout()) navigate('/login'); }}>
			<NavigationIcon name="logout" /><span>Logout</span>
		</button>
		</aside>
	</>;
}
