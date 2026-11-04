import axios from 'axios';

const defaultApiHost = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL || `http://${defaultApiHost}:5000/api`;
const apiBaseUrl = new URL(configuredApiBaseUrl);
const localHosts = ['localhost', '127.0.0.1'];
if (typeof window !== 'undefined' && localHosts.includes(defaultApiHost) && localHosts.includes(apiBaseUrl.hostname)) {
	apiBaseUrl.hostname = defaultApiHost;
}
export const API_BASE_URL = apiBaseUrl.toString().replace(/\/$/, '');

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

export const expenseImportApi = {
	preview: (file, config = {}) => {
		const form = new FormData();
		form.append('file', file);
		return api.post('/expenses/import/preview', form, {
			...config,
			headers: { ...config.headers, 'Content-Type': 'multipart/form-data' },
		});
	},
	confirm: rows => api.post('/expenses/import/confirm', { rows }),
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

export const corporateApi = {
  overview: () => api.get('/corporate/overview'),
  submitExpense: payload => api.post('/corporate/expenses', payload),
  submitExpenseWithReceipt: (payload, config = {}) => {
    const form = new FormData();
    Object.entries(payload).forEach(([key, value]) => {
      if (value !== undefined && value !== null) form.append(key, value);
    });
    return api.post('/corporate/expenses/with-receipt', form, {
      ...config,
      headers: { ...config.headers, 'Content-Type': 'multipart/form-data' },
    });
  },
  expenses: params => api.get('/corporate/expenses', { params }),
  decideExpense: (expenseId, payload) => api.post(`/corporate/expenses/${expenseId}/decision`, payload),
  createDepartment: payload => api.post('/corporate/departments', payload),
  updateMember: (membershipId, payload) => api.patch(`/corporate/members/${membershipId}`, payload),
  organization: () => api.get('/corporate/organization'),
  updateOrganization: payload => api.put('/corporate/organization', payload),
  regenerateJoiningCode: () => api.post('/corporate/organization/regenerate-code'),
  members: params => api.get('/corporate/members/search', { params }),
  addMember: payload => api.post('/corporate/members', payload),
  updateWorkflowMember: (membershipId, payload) => api.put(`/corporate/members/${membershipId}`, payload),
  departments: () => api.get('/corporate/departments'),
  updateDepartment: (departmentId, payload) => api.put(`/corporate/departments/${departmentId}`, payload),
  departmentMembers: departmentId => api.get(`/corporate/departments/${departmentId}/members`),
  expense: expenseId => api.get(`/corporate/expenses/${expenseId}`),
  updateExpense: (expenseId, payload) => api.put(`/corporate/expenses/${expenseId}`, payload),
  uploadReceipt: (expenseId, file) => {
    const form = new FormData();
    form.append('receipt', file);
    return api.post(`/corporate/expenses/${expenseId}/receipt`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  receipt: (expenseId, config = {}) => api.get(`/corporate/expenses/${expenseId}/receipt`, {
    ...config,
    responseType: 'blob',
  }),
  approvals: params => api.get('/corporate/approvals', { params }),
  review: (expenseId, action, payload = {}) => api.post(`/corporate/approvals/${expenseId}/${action}`, payload),
  reimbursements: params => api.get('/corporate/reimbursements', { params }),
  dashboard: role => api.get(`/corporate/dashboard/${role}`),
  reportSummary: params => api.get('/corporate/reports/summary', { params }),
  transactions: params => api.get('/corporate/reports/transactions', { params }),
  exportReport: params => api.get('/corporate/reports/export', { params, responseType: 'blob' }),
  auditLog: () => api.get('/corporate/audit-log'),
  profile: () => api.get('/corporate/profile'),
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

export const demoApi = {
	analytics: () => api.get('/demo/analytics'),
	modelEvaluation: () => api.get('/demo/ml/evaluation'),
	estimateMonthlyExpenses: profile => api.post('/demo/ml/estimate-monthly-expenses', profile),
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
