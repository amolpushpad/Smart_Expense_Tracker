export default function BrandName({ className = '' }) {
	return (
		<span className={`spendwise-brand-name ${className}`.trim()}>
			<span>Spend</span><span>Wise</span>
		</span>
	);
}
