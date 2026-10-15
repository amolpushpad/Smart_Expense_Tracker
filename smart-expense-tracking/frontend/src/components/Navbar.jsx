import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import UserAvatar from './UserAvatar';

export default function Navbar() {
	const { user, logout } = useAuth();
	const navigate = useNavigate();
	const signOut = async () => {
		if (await logout()) navigate('/login');
	};
	return <header className="navbar">
		<div><span className="mobile-brand">SmartExpense</span><h1>Financial Overview</h1><p>Welcome back, {user?.name || 'User'}.</p></div>
		<details className="profile-menu">
			<summary aria-label="Open account menu"><UserAvatar user={user} /></summary>
			<div className="profile-menu-popover">
				<strong>{user?.name || 'User'}</strong>
				<span>{user?.email}</span>
				<Link to="/profile">View / Edit Profile</Link>
				<Link to="/profile#security">Account &amp; Security</Link>
				<button type="button" onClick={signOut}>Log out</button>
			</div>
		</details>
	</header>;
}
