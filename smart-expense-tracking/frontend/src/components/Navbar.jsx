import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import UserAvatar from './UserAvatar';
import BrandName from './BrandName';

const pageTitles = {
	'/dashboard': 'Personal overview',
	'/expenses': 'Expense management',
	'/income': 'Income tracking',
	'/budgets': 'Monthly budgets',
	'/analytics': 'Financial analytics',
	'/reports': 'Reports and exports',
	'/profile': 'Account settings',
	'/corporate': 'Corporate workspace',
};

export default function Navbar({ onMenuClick = () => {}, navigationOpen = false }) {
	const { user, logout } = useAuth();
	const navigate = useNavigate();
	const location = useLocation();
	const signOut = async () => {
		if (await logout()) navigate('/login');
	};
	return <header className="navbar">
		<button className="nav-menu-toggle" type="button" onClick={onMenuClick} aria-label={navigationOpen ? 'Close navigation menu' : 'Open navigation menu'} aria-expanded={navigationOpen}>
			<span /><span /><span />
		</button>
		<div className="navbar-copy"><span className="navbar-eyebrow"><span className="navbar-brand-name"><BrandName /></span><span aria-hidden="true">/</span>{user?.workspace_mode === 'corporate' ? user.role : 'Personal workspace'}</span><h1>{pageTitles[location.pathname] || (user?.workspace_mode === 'corporate' ? 'Corporate workspace' : 'Personal overview')}</h1><p>Welcome back, {user?.name || 'User'}.</p></div>
		<details className="profile-menu">
			<summary aria-label="Open account menu"><UserAvatar user={user} /><span className="navbar-user-name">{user?.name || 'User'}</span><span className="profile-menu-chevron" aria-hidden="true">⌄</span></summary>
			<div className="profile-menu-popover">
				<strong>{user?.name || 'User'}</strong>
				<span>{user?.email}</span>
				{user?.workspace_mode !== 'corporate' && <><Link to="/profile">View / Edit Profile</Link><Link to="/profile#security">Account &amp; Security</Link></>}
				<button type="button" onClick={signOut}>Log out</button>
			</div>
		</details>
	</header>;
}
