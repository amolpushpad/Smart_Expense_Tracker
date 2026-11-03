import logo from '../assets/spendwise-logo.png';

export default function BrandLogo({ className = '' }) {
	return (
		<div className={`spendwise-logo-container ${className}`.trim()}>
			<img className="spendwise-logo" src={logo} alt="SpendWise — Smart Expense Tracking & Analytics" />
		</div>
	);
}
