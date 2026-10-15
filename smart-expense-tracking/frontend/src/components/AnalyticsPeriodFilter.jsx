export default function AnalyticsPeriodFilter({
	period,
	setPeriod,
	weekDate,
	setWeekDate,
	selectedMonth,
	setSelectedMonth,
	startDate,
	setStartDate,
	endDate,
	setEndDate,
}) {
	const changeWeek = offset => {
		const date = new Date(`${weekDate}T12:00:00`);
		date.setDate(date.getDate() + offset * 7);
		const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
		setWeekDate(local);
	};
	const changeMonth = offset => {
		const [year, month] = selectedMonth.split('-').map(Number);
		const date = new Date(year, month - 1 + offset, 1);
		setSelectedMonth(`${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`);
	};

	return <section className="analytics-filters" aria-label="Analytics date filters">
		<label className="analytics-period-select">Period
			<select value={period} onChange={event => setPeriod(event.target.value)}>
				<option value="weekly">Weekly</option>
				<option value="monthly">Monthly</option>
				<option value="custom">Custom date range</option>
			</select>
		</label>
		{period === 'weekly' && <div className="analytics-period-control">
			<button type="button" className="secondary-button" aria-label="Previous week" onClick={() => changeWeek(-1)}>←</button>
			<label>Week containing<input type="date" value={weekDate} onChange={event => setWeekDate(event.target.value)} /></label>
			<button type="button" className="secondary-button" aria-label="Next week" onClick={() => changeWeek(1)}>→</button>
		</div>}
		{period === 'monthly' && <div className="analytics-period-control">
			<button type="button" className="secondary-button" aria-label="Previous month" onClick={() => changeMonth(-1)}>←</button>
			<label>Month<input type="month" value={selectedMonth} onChange={event => { if (event.target.value) setSelectedMonth(event.target.value); }} /></label>
			<button type="button" className="secondary-button" aria-label="Next month" onClick={() => changeMonth(1)}>→</button>
		</div>}
		{period === 'custom' && <div className="analytics-period-control custom-range-control">
			<label>From<input type="date" value={startDate} onChange={event => setStartDate(event.target.value)} /></label>
			<label>To<input type="date" value={endDate} onChange={event => setEndDate(event.target.value)} /></label>
		</div>}
	</section>;
}
