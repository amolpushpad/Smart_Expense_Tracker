export default function SummaryCard({ title, value, icon, tone, detail, loading = false }) {
	return <article className={`summary-card${loading ? ' summary-card-loading' : ''}`} aria-busy={loading}>
		<div className={`card-icon ${tone || ''}`}>{icon}</div>
		<div className="summary-card-content">
			<p>{title}</p>
			{loading ? <><span className="summary-skeleton-value" /><span className="summary-skeleton-detail" /></> : <><h3>{value}</h3><small>{detail}</small></>}
		</div>
	</article>;
}
