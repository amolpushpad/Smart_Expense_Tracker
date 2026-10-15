import { useEffect, useMemo, useState } from 'react';
import { analyticsApi, getApiErrorMessage } from '../services/api';

function localIsoDate(value = new Date()) {
	const date = new Date(value);
	date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
	return date.toISOString().slice(0, 10);
}

function initialMonth() {
	return localIsoDate().slice(0, 7);
}

export function useAnalyticsReport() {
	const [period, setPeriod] = useState('monthly');
	const [weekDate, setWeekDate] = useState(localIsoDate);
	const [selectedMonth, setSelectedMonth] = useState(initialMonth);
	const [startDate, setStartDate] = useState(() => `${initialMonth()}-01`);
	const [endDate, setEndDate] = useState(localIsoDate);
	const [loadedReport, setLoadedReport] = useState({ queryKey: null, data: null });
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState('');
	const [refreshKey, setRefreshKey] = useState(0);

	const [year, month] = selectedMonth.split('-');
	const params = useMemo(() => {
		if (period === 'weekly') return { period, date: weekDate };
		if (period === 'custom') return { period, start_date: startDate, end_date: endDate };
		return { period: 'monthly', month: Number(month), year: Number(year) };
	}, [period, weekDate, startDate, endDate, month, year]);
	const queryKey = JSON.stringify(params);

	useEffect(() => {
		const controller = new AbortController();
		setLoading(true);
		setError('');
		analyticsApi.get(params, { signal: controller.signal })
			.then(response => setLoadedReport({ queryKey, data: response.data.data }))
			.catch(requestError => {
				if (requestError.name === 'CanceledError') return;
				setLoadedReport({ queryKey, data: null });
				setError(getApiErrorMessage(requestError));
			})
			.finally(() => { if (!controller.signal.aborted) setLoading(false); });
		return () => controller.abort();
	}, [queryKey, refreshKey]);

	const report = loadedReport.queryKey === queryKey ? loadedReport.data : null;
	return {
		period, setPeriod, weekDate, setWeekDate, selectedMonth, setSelectedMonth,
		startDate, setStartDate, endDate, setEndDate, params,
		report, loading, error,
		refresh: () => setRefreshKey(value => value + 1),
	};
}
