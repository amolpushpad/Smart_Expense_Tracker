import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
	Bar,
	BarChart,
	CartesianGrid,
	Cell,
	Legend,
	Pie,
	PieChart,
	ResponsiveContainer,
	Tooltip,
	XAxis,
	YAxis,
} from 'recharts';
import BrandLogo from '../components/BrandLogo';
import BrandName from '../components/BrandName';
import { demoApi, getApiErrorMessage } from '../services/api';
import '../styles/demo.css';

const currency = new Intl.NumberFormat('en-IN', {
	style: 'currency',
	currency: 'INR',
	maximumFractionDigits: 0,
});
const pieColors = ['#7C3AED', '#A78BFA', '#C4B5FD', '#DDD6FE', '#EDE9FE'];

function MetricCard({ label, value, note }) {
	return <article className="demo-metric">
		<span>{label}</span>
		<strong>{value}</strong>
		<small>{note}</small>
	</article>;
}

export default function DatasetDemo() {
	const [demo, setDemo] = useState(null);
	const [evaluation, setEvaluation] = useState(null);
	const [loadError, setLoadError] = useState('');
	const [profile, setProfile] = useState({
		age: '30',
		monthly_income_inr: '',
		savings_inr: '',
		employment_status: 'Employed',
		has_loan: false,
	});
	const [estimate, setEstimate] = useState(null);
	const [estimateError, setEstimateError] = useState('');
	const [estimating, setEstimating] = useState(false);

	useEffect(() => {
		let cancelled = false;
		Promise.all([demoApi.analytics(), demoApi.modelEvaluation()])
			.then(([analyticsResponse, evaluationResponse]) => {
				if (cancelled) return;
				setDemo(analyticsResponse.data.data);
				setEvaluation(evaluationResponse.data.data);
			})
			.catch(error => {
				if (!cancelled) setLoadError(getApiErrorMessage(error, 'Synthetic dataset analytics are unavailable.'));
			});
		return () => { cancelled = true; };
	}, []);

	const submitEstimate = async event => {
		event.preventDefault();
		setEstimateError('');
		setEstimate(null);
		setEstimating(true);
		try {
			const response = await demoApi.estimateMonthlyExpenses({
				...profile,
				age: Number(profile.age),
				monthly_income_inr: Number(profile.monthly_income_inr),
				savings_inr: Number(profile.savings_inr),
			});
			setEstimate(response.data.data);
		} catch (error) {
			setEstimateError(getApiErrorMessage(error, 'The synthetic estimate is unavailable.'));
		} finally {
			setEstimating(false);
		}
	};

	const updateProfile = event => {
		const { name, value, type, checked } = event.target;
		setProfile(current => ({ ...current, [name]: type === 'checkbox' ? checked : value }));
	};

	return <main className="demo-page">
		<header className="demo-header">
			<Link className="demo-brand" to="/login" aria-label="SpendWise home">
				<BrandLogo className="demo-brand-logo" />
				<BrandName className="demo-brand-name" />
			</Link>
			<Link className="demo-login-link" to="/login">Sign in</Link>
		</header>

		<div className="demo-content">
			<section className="demo-intro">
				<p className="demo-eyebrow">SEPARATE SAMPLE VIEW · INR</p>
				<h1>Synthetic finance data demo</h1>
				<p>Explore aggregate summaries from a synthetic profile dataset. This is separate from signed-in accounts and their financial records.</p>
			</section>

			<aside className="demo-disclaimer" role="note">
				<strong>Illustrative data only</strong>
				<p>Each row is one synthetic user profile snapshot. Monthly amounts are profile totals—not transaction history, category spending, or a forecast. These figures are kept separate from all signed-in users' financial data.</p>
			</aside>

			{loadError && <div className="demo-error" role="alert">{loadError}<p>Ensure the Flask API is running and the isolated snapshots have been imported.</p></div>}
			{!demo && !loadError && <p className="demo-loading" role="status">Loading imported synthetic dataset…</p>}
			{demo && <>
				<section className="demo-metrics" aria-label="Synthetic dataset overview">
					<MetricCard label="Synthetic profiles" value={demo.overview.synthetic_profiles.toLocaleString('en-IN')} note="One snapshot per profile" />
					<MetricCard label="Average monthly income" value={currency.format(demo.overview.average_monthly_income_inr)} note="INR · all profiles" />
					<MetricCard label="Average monthly expenses" value={currency.format(demo.overview.average_monthly_expenses_inr)} note="INR · reported profile total" />
					<MetricCard label="Median monthly expenses" value={currency.format(demo.overview.median_monthly_expenses_inr)} note="INR · reported profile total" />
					<MetricCard label="Profiles with a loan" value={`${demo.overview.profiles_with_loan_percent}%`} note={`${demo.overview.profiles_with_loan.toLocaleString('en-IN')} synthetic profiles`} />
				</section>

				<section className="demo-panels">
					<article className="demo-panel">
						<div className="demo-panel-heading">
							<h2>Average monthly amounts by employment</h2>
							<p>Converted USD totals · INR · cross-sectional, not a time series</p>
						</div>
						<div className="demo-chart">
							<ResponsiveContainer width="100%" height="100%">
								<BarChart data={demo.employment_groups.map(group => ({
									name: group.employment_status,
									Income: group.average_monthly_income_inr,
									Expenses: group.average_monthly_expenses_inr,
								}))} margin={{ top: 8, right: 8, left: 4, bottom: 4 }}>
									<CartesianGrid stroke="#EEEAF5" vertical={false} />
									<XAxis dataKey="name" tick={{ fontSize: 11 }} />
									<YAxis tick={{ fontSize: 10 }} tickFormatter={value => `₹${Math.round(value / 1000)}k`} />
									<Tooltip formatter={value => currency.format(value)} />
									<Legend />
									<Bar dataKey="Income" fill="#7C3AED" radius={[4, 4, 0, 0]} />
									<Bar dataKey="Expenses" fill="#A78BFA" radius={[4, 4, 0, 0]} />
								</BarChart>
							</ResponsiveContainer>
						</div>
					</article>

					<article className="demo-panel">
						<div className="demo-panel-heading">
							<h2>Loan profile distribution</h2>
							<p>Synthetic snapshot counts</p>
						</div>
						<div className="demo-loan-chart">
							<ResponsiveContainer width="100%" height="100%">
								<PieChart>
									<Pie data={demo.loan_types} dataKey="records" nameKey="loan_type" innerRadius="54%" outerRadius="82%" paddingAngle={2}>
										{demo.loan_types.map((entry, index) => <Cell key={entry.loan_type} fill={pieColors[index % pieColors.length]} />)}
									</Pie>
									<Tooltip formatter={value => Number(value).toLocaleString('en-IN')} />
									<Legend />
								</PieChart>
							</ResponsiveContainer>
						</div>
					</article>

					<article className="demo-panel demo-employment-panel">
						<div className="demo-panel-heading">
							<h2>Employment group aggregates</h2>
							<p>Snapshot profiles grouped by reported employment status</p>
						</div>
						<div className="demo-table-wrap">
							<table className="demo-table">
								<thead><tr><th>Employment</th><th>Profiles</th><th>Avg. monthly income</th><th>Avg. monthly expenses</th><th>Median monthly expenses</th></tr></thead>
								<tbody>{demo.employment_groups.map(group => (
									<tr key={group.employment_status}>
										<th scope="row">{group.employment_status}</th>
										<td>{group.records.toLocaleString('en-IN')}</td>
										<td>{currency.format(group.average_monthly_income_inr)}</td>
										<td>{currency.format(group.average_monthly_expenses_inr)}</td>
										<td>{currency.format(group.median_monthly_expenses_inr)}</td>
									</tr>
								))}</tbody>
							</table>
						</div>
					</article>

					<article className="demo-panel demo-model-panel">
						<div className="demo-panel-heading">
							<h2>Experimental cross-sectional model</h2>
							<p>Estimates reported monthly expense totals from profile attributes; this is not a forecast.</p>
						</div>
						{evaluation ? <div className="demo-model-evaluation">
							<MetricCard label="Held-out MAE" value={currency.format(evaluation.metrics.mae_inr)} note={`Mean baseline: ${currency.format(evaluation.metrics.mean_baseline_mae_inr)}`} />
							<MetricCard label="Held-out RMSE" value={currency.format(evaluation.metrics.rmse_inr)} note={`Mean baseline: ${currency.format(evaluation.metrics.mean_baseline_rmse_inr)}`} />
							<MetricCard label="Held-out R²" value={evaluation.metrics.r2.toFixed(3)} note={`${evaluation.held_out_records.toLocaleString('en-IN')} held-out profiles`} />
						</div> : <p className="demo-model-unavailable">Model evaluation is unavailable. At least 100 imported snapshots are required.</p>}
						<p className="demo-model-status">
							{evaluation?.beats_mean_baseline_mae
								? 'This model reduced held-out MAE versus the mean baseline on this synthetic dataset only.'
								: 'This model did not outperform the held-out mean baseline by MAE; treat estimates as an illustration only.'}
						</p>
						<form className="demo-estimate-form" onSubmit={submitEstimate}>
							<label>Age<input name="age" type="number" min="18" max="120" value={profile.age} onChange={updateProfile} required /></label>
							<label>Employment status<select name="employment_status" value={profile.employment_status} onChange={updateProfile} required>
								{demo.employment_groups.map(group => <option key={group.employment_status}>{group.employment_status}</option>)}
							</select></label>
							<label>Monthly income (INR)<input name="monthly_income_inr" type="number" min="0" step="0.01" value={profile.monthly_income_inr} onChange={updateProfile} required /></label>
							<label>Savings (INR)<input name="savings_inr" type="number" min="0" step="0.01" value={profile.savings_inr} onChange={updateProfile} required /></label>
							<label className="demo-loan-check"><input name="has_loan" type="checkbox" checked={profile.has_loan} onChange={updateProfile} /> Has a loan</label>
							<button type="submit" disabled={estimating || !evaluation}>{estimating ? 'Estimating…' : 'Estimate synthetic profile'}</button>
						</form>
						{estimateError && <p className="demo-form-error" role="alert">{estimateError}</p>}
						{estimate && <div className="demo-estimate-result" role="status">
							<span>Illustrative estimated monthly expenses</span>
							<strong>{currency.format(estimate.estimate_monthly_expenses_inr)}</strong>
							<p>{estimate.notice}</p>
						</div>}
					</article>

					<article className="demo-panel demo-limitations">
						<div className="demo-panel-heading"><h2>What this dataset cannot support</h2></div>
						<p>No transaction descriptions, merchants, categories, or per-user history are present. Transaction categorization, duplicate detection, personal anomaly detection, and next-month forecasting are not run on this dataset.</p>
						<p>All imported USD amounts use the fixed conversion rate ₹{demo.dataset.usd_inr_rate} per USD. Snapshot dates: {demo.dataset.snapshot_date_range.start} – {demo.dataset.snapshot_date_range.end}.</p>
					</article>
				</section>
			</>}

			<footer className="demo-footer">
				<span>Source file hash: {demo?.dataset.source_sha256.slice(0, 12) || 'Not loaded'}</span>
				<span>Original publisher and redistribution license were not provided.</span>
			</footer>
		</div>
	</main>;
}
