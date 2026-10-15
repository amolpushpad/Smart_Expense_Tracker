import axios from 'axios';

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api';

let csrfToken = null;
let csrfRequest = null;

export const api = axios.create({
	baseURL: API_BASE_URL,
	withCredentials: true,
	headers: { 'Content-Type': 'application/json' },
});

export async function ensureCsrfToken() {
	if (csrfToken) return csrfToken;
	if (!csrfRequest) {
		csrfRequest = api.get('/auth/csrf')
			.then(response => {
				csrfToken = response.data.data.csrf_token;
				return csrfToken;
			})
			.finally(() => { csrfRequest = null; });
	}
	await csrfRequest;
	return csrfToken;
}

export function setCsrfToken(token) {
	csrfToken = token;
}

api.interceptors.request.use(async (config) => {
	if (['post', 'put', 'patch', 'delete'].includes(config.method?.toLowerCase())) {
		config.headers['X-CSRF-Token'] = await ensureCsrfToken();
	}
	return config;
});

export function getApiErrorMessage(error, fallback = 'The request could not be completed.') {
	if (error.response?.data?.message) return error.response.data.message;
	if (error.request) return 'Unable to reach the server. Check that the backend is running.';
	return fallback;
}

export const expensesApi = {
	list: (params, config = {}) => api.get('/expenses', { ...config, params }),
	get: (expenseId) => api.get(`/expenses/${expenseId}`),
	create: (expense) => api.post('/expenses', expense),
	update: (expenseId, expense) => api.put(`/expenses/${expenseId}`, expense),
	remove: (expenseId) => api.delete(`/expenses/${expenseId}`),
};

export const categoriesApi = {
	list: () => api.get('/categories'),
	create: (category) => api.post('/categories', category),
	update: (categoryId, category) => api.put(`/categories/${categoryId}`, category),
	remove: (categoryId) => api.delete(`/categories/${categoryId}`),
};

export const incomeApi = {
	list: (params, config = {}) => api.get('/income', { ...config, params }),
	get: (incomeId) => api.get(`/income/${incomeId}`),
	create: (income) => api.post('/income', income),
	update: (incomeId, income) => api.put(`/income/${incomeId}`, income),
	remove: (incomeId) => api.delete(`/income/${incomeId}`),
};

export const budgetsApi = {
	list: (params, config = {}) => api.get('/budgets', { ...config, params }),
	get: (budgetId) => api.get(`/budgets/${budgetId}`),
	create: (budget) => api.post('/budgets', budget),
	update: (budgetId, budget) => api.put(`/budgets/${budgetId}`, budget),
	remove: (budgetId) => api.delete(`/budgets/${budgetId}`),
};

export const profileApi = {
	get: (config = {}) => api.get('/users/profile', config),
	update: profile => api.put('/users/profile', profile),
	uploadPhoto: file => {
		const form = new FormData();
		form.append('photo', file);
		return api.post('/users/profile/photo', form, { headers: { 'Content-Type': 'multipart/form-data' } });
	},
	removePhoto: () => api.delete('/users/profile/photo'),
	changePassword: payload => api.post('/users/password', payload),
	photo: (url, config = {}) => api.get(url.startsWith('/api/') ? url.slice(4) : url, { ...config, responseType: 'blob' }),
};

export const dashboardSummaryApi = {
	async get({ month, year }) {
		const response = await api.get('/dashboard/summary', { params: { month, year } });
		return response.data.data.summary;
	},
};

export const dashboardApi = {
	async load({ month, year, period = 'monthly', weekDate }) {
		const params = { month, year };
		const reportParams = period === 'weekly'
			? { period, date: weekDate }
			: { period: 'monthly', month, year };
		const [summary, transactions, report, budgets] = await Promise.all([
			api.get('/dashboard/summary', { params }),
			api.get('/dashboard/recent-transactions', { params: { limit: 10 } }),
			api.get('/analytics', { params: reportParams }),
			api.get('/dashboard/budget-progress', { params }),
		]);
		let mlInsights;
		try {
			const insights = await api.get('/ml/insights', { params });
			mlInsights = insights.data.data;
		} catch (error) {
			mlInsights = { errors: { all: getApiErrorMessage(error, 'Smart insights are temporarily unavailable.') } };
		}
		return {
			summary: summary.data.data.summary,
			transactions: transactions.data.data.transactions,
			report: report.data.data,
			budgets: budgets.data.data.budgets,
			mlInsights,
		};
	},
};

export const mlApi = {
	categorize: payload => api.post('/ml/categorize', payload),
	prediction: (params, config = {}) => api.get('/ml/prediction', { ...config, params }),
	insights: (params, config = {}) => api.get('/ml/insights', { ...config, params }),
	anomalies: (params = {}, config = {}) => api.get('/ml/anomalies', { ...config, params }),
	duplicates: (params = {}, config = {}) => api.get('/ml/duplicates', { ...config, params }),
};

export const analyticsApi = {
	get: (params, config = {}) => api.get('/analytics', { ...config, params }),
	exportCsv: (params, config = {}) => api.get('/analytics/export.csv', {
		...config,
		params,
		responseType: 'blob',
	}),
};

export function notifyDashboardDataChanged() {
	window.dispatchEvent(new Event('dashboard:data-changed'));
}
