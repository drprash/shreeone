import api from './api';

const settingsAPI = {
  // Member Permissions
  getPermissions: () => api.get('/settings/permissions'),
  getUserPermission: (userId) => api.get(`/settings/permissions/${userId}`),
  setMemberPermissions: (data) => api.post('/settings/permissions', data),
  updateMemberPermissions: (userId, data) => api.put(`/settings/permissions/${userId}`, data),

  // Budget Settings
  getBudgets: () => api.get('/settings/budgets'),
  getBudget: (budgetId) => api.get(`/settings/budgets/${budgetId}`),
  createBudget: (data) => api.post('/settings/budgets', data),
  updateBudget: (budgetId, data) => api.put(`/settings/budgets/${budgetId}`, data),
  deleteBudget: (budgetId) => api.delete(`/settings/budgets/${budgetId}`),

  // Recurring Payments
  getRecurringPayments: () => api.get('/settings/recurring-payments'),
  getRecurringPayment: (paymentId) => api.get(`/settings/recurring-payments/${paymentId}`),
  createRecurringPayment: (data) => api.post('/settings/recurring-payments', data),
  updateRecurringPayment: (paymentId, data) => api.put(`/settings/recurring-payments/${paymentId}`, data),
  deactivateRecurringPayment: (paymentId) => api.delete(`/settings/recurring-payments/${paymentId}`),

  // Family Preferences
  getPreferences: () => api.get('/settings/preferences'),
  updatePreferences: (data) => api.put('/settings/preferences', data),

  // Family Profile
  getFamilyProfile: () => api.get('/settings/family-profile'),
  updateFamilyProfile: (data) => api.put('/settings/family-profile', data),

  // Member Management
  removeMember: (userId) => api.post(`/settings/remove-member/${userId}`),
  reactivateMember: (userId) => api.post(`/settings/reactivate-member/${userId}`),
  transferAdminRole: (data) => api.post('/settings/transfer-admin-role', data),

  // Secondary Currencies
  getCurrencies: () => api.get('/settings/currencies'),
  addCurrency: (currencyCode) => api.post('/settings/currencies', { currency_code: currencyCode }),
  removeCurrency: (code) => api.delete(`/settings/currencies/${code}`),

  // Exchange Rates
  getExchangeRates: () => api.get('/settings/exchange-rates'),
  setExchangeRate: (data) => api.put('/settings/exchange-rates', data),
  refreshExchangeRates: () => api.post('/settings/exchange-rates/refresh'),
};

export default settingsAPI;
