import React, { useState, useEffect } from 'react';
import settingsAPI from '../../services/settingsAPI';
import api from '../../services/api';
import { useAuthStore } from '../../store/authStore';

const BudgetSettings = () => {
  const user = useAuthStore((state) => state.user);
  const [budgets, setBudgets] = useState([]);
  const [categories, setCategories] = useState([]);
  const [members, setMembers] = useState([]);
  const [showBudgetAlerts, setShowBudgetAlerts] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [editingBudget, setEditingBudget] = useState(null);

  const [budgetType, setBudgetType] = useState('category');
  const [formData, setFormData] = useState({
    category_id: null,
    user_id: null,
    limit_amount: '',
    period: 'MONTHLY',
    alert_threshold: 0.8,
    notify_channels: 'IN_APP',
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const requestsToMake = [
        settingsAPI.getBudgets(),
        api.get('/categories/'),
        settingsAPI.getPreferences(),
      ];

      // Only fetch members list if user is admin (needed for displaying member names)
      if (user?.role === 'ADMIN') {
        requestsToMake.push(api.get('/admin/users'));
      }

      const responses = await Promise.all(requestsToMake);

      setBudgets(responses[0].data);
      setCategories(responses[1].data.filter(c => c.type === 'EXPENSE'));
      setShowBudgetAlerts(responses[2].data.show_budget_alerts ?? true);

      if (user?.role === 'ADMIN') {
        setMembers(responses[3].data);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load budgets');
    } finally {
      setLoading(false);
    }
  };

  const handleOpenModal = (budget = null) => {
    if (budget) {
      setEditingBudget(budget);
      setBudgetType(budget.user_id ? 'user' : 'category');
      setFormData({
        category_id: budget.category_id,
        user_id: budget.user_id,
        limit_amount: budget.limit_amount,
        period: budget.period,
        alert_threshold: budget.alert_threshold,
        notify_channels: budget.notify_channels,
      });
    } else {
      setEditingBudget(null);
      setBudgetType('category');
      setFormData({
        category_id: categories[0]?.id || null,
        user_id: null,
        limit_amount: '',
        period: 'MONTHLY',
        alert_threshold: 0.8,
        notify_channels: 'IN_APP',
      });
    }
    setShowModal(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.limit_amount) {
      setError('Please enter a limit amount');
      return;
    }

    try {
      setError(null);
      const data = {
        ...formData,
        limit_amount: parseFloat(formData.limit_amount),
        alert_threshold: parseFloat(formData.alert_threshold),
      };

      if (editingBudget) {
        await settingsAPI.updateBudget(editingBudget.id, data);
        setSuccessMessage('Budget updated successfully!');
      } else {
        await settingsAPI.createBudget(data);
        setSuccessMessage('Budget created successfully!');
      }

      setShowModal(false);
      fetchData();
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save budget');
    }
  };

  const handleDelete = async (budgetId) => {
    if (!window.confirm('Are you sure you want to delete this budget?')) return;

    try {
      setError(null);
      await settingsAPI.deleteBudget(budgetId);
      setSuccessMessage('Budget deleted successfully!');
      fetchData();
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete budget');
    }
  };

  const getBudgetStatus = (budget) => {
    const percentage = (budget.spent_amount / budget.limit_amount) * 100;
    if (percentage >= 100) return { color: 'red', status: 'Over Budget' };
    if (percentage >= parseFloat(budget.alert_threshold) * 100) return { color: 'yellow', status: 'Warning' };
    return { color: 'green', status: 'On Track' };
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  // Filter budgets based on user role
  let displayedBudgets = budgets;
  if (user?.role !== 'ADMIN') {
    // Members only see category budgets and their personal budget
    displayedBudgets = budgets.filter(budget => !budget.user_id || String(budget.user_id) === String(user?.id));
  }

  return (
    <div className="p-6">
      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          {error}
        </div>
      )}

      {successMessage && (
        <div className="mb-4 p-4 bg-green-50 border border-green-200 rounded-lg text-green-700">
          {successMessage}
        </div>
      )}

      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-slate-900">Budget & Spending Controls</h2>
        {user?.role === 'ADMIN' && (
          <button
            onClick={() => handleOpenModal()}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium"
          >
            + Set Budget
          </button>
        )}
      </div>

      {/* Member Personal Budget Alert */}
      {user?.role !== 'ADMIN' && displayedBudgets.length > 0 && (
        <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <p className="text-blue-900 font-semibold">📖 View Only</p>
          <p className="text-blue-800 text-sm mt-1">
            You can view your assigned budget below. Contact your family admin to change budget limits.
          </p>
        </div>
      )}

      {/* Budget Overview Cards */}
      {displayedBudgets.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
          {displayedBudgets.map((budget) => {
            const percentage = (budget.spent_amount / budget.limit_amount) * 100;
            const status = getBudgetStatus(budget);
            let budgetLabel = '';
            
            if (budget.category?.name) {
              budgetLabel = budget.category.name;
            } else if (budget.user_id) {
              // This is a member budget
              if (user?.role === 'ADMIN') {
                // Admin: show whose budget it is
                const memberName = members.find(m => String(m.id) === String(budget.user_id))
                  ? `${members.find(m => String(m.id) === String(budget.user_id)).first_name} ${members.find(m => String(m.id) === String(budget.user_id)).last_name}'s Budget`
                  : 'Member Budget';
                budgetLabel = memberName;
              } else {
                // Member: show "Your Personal Budget"
                budgetLabel = 'Your Personal Budget';
              }
            } else {
              budgetLabel = 'Family Budget';
            }

            return (
              <div key={budget.id} className="bg-slate-50 border border-slate-200 rounded-lg p-4">
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <h3 className="font-semibold text-slate-900">{budgetLabel}</h3>
                    <p className="text-sm text-slate-500">{budget.period}</p>
                  </div>
                  {user?.role === 'ADMIN' && (
                    <div className="flex gap-1">
                      <button
                        onClick={() => handleOpenModal(budget)}
                        className="text-blue-600 hover:text-blue-700 text-sm"
                      >
                        ✏️
                      </button>
                      <button
                        onClick={() => handleDelete(budget.id)}
                        className="text-red-600 hover:text-red-700 text-sm"
                      >
                        🗑️
                      </button>
                    </div>
                  )}
                </div>

                <div className="mb-3">
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-slate-600">Spent: ₹{parseFloat(budget.spent_amount).toFixed(2)}</span>
                    <span className="font-semibold">${parseFloat(budget.limit_amount).toFixed(2)}</span>
                  </div>
                  <div className="w-full bg-slate-200 rounded-full h-2 overflow-hidden">
                    <div
                      className={`h-full transition-all ${
                        !showBudgetAlerts
                          ? 'bg-slate-400'
                          : status.color === 'red'
                          ? 'bg-red-500'
                          : status.color === 'yellow'
                          ? 'bg-yellow-500'
                          : 'bg-green-500'
                      }`}
                      style={{ width: `${Math.min(percentage, 100)}%` }}
                    ></div>
                  </div>
                  <div className="flex justify-between text-xs text-slate-500 mt-1">
                    <span>{percentage.toFixed(1)}%</span>
                    {showBudgetAlerts && (
                      <span className={`font-semibold ${
                        status.color === 'red'
                          ? 'text-red-600'
                          : status.color === 'yellow'
                          ? 'text-yellow-600'
                          : 'text-green-600'
                      }`}>
                        {status.status}
                      </span>
                    )}
                  </div>
                </div>

                <div className="text-xs text-slate-600">
                  {showBudgetAlerts
                    ? <p>🔔 In-App Alerts Enabled</p>
                    : <p className="text-slate-400">🔕 Alerts disabled</p>
                  }
                  <p>Threshold: {(parseFloat(budget.alert_threshold) * 100).toFixed(0)}%</p>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="text-center py-8 bg-slate-50 rounded-lg border border-slate-200 mb-8">
          <p className="text-slate-600">
            {user?.role === 'ADMIN' 
              ? 'No budgets set yet. Create one to start monitoring spending.'
              : 'No budgets have been set for you yet. Contact your family admin to set up a budget.'
            }
          </p>
        </div>
      )}

      {/* Budget Guidelines */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h3 className="font-semibold text-blue-900 mb-2">💡 Budget Tips</h3>
        <ul className="text-sm text-blue-800 space-y-1">
          <li>• Set budgets for categories to track spending patterns</li>
          <li>• Configure individual member budgets to manage personal spending</li>
          <li>• Adjust alert thresholds to get notified before exceeding limits</li>
          <li>• Review budgets monthly to optimize family finances</li>
        </ul>
      </div>

      {/* Budget Modal */}
      {showModal && (
        <div className="modal-backdrop fixed inset-0 flex items-center justify-center z-50">
          <div className="glass-panel bg-white dark:bg-slate-800 rounded-lg p-6 max-w-md w-full mx-4 slide-in">
            <h3 className="text-xl font-bold text-slate-900 mb-4">
              {editingBudget ? 'Edit Budget' : 'Create Budget'}
            </h3>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Budget Type
                </label>
                <select
                  value={budgetType}
                  onChange={(e) => {
                    setBudgetType(e.target.value);
                    if (e.target.value === 'category') {
                      setFormData({ ...formData, category_id: categories[0]?.id || null, user_id: null });
                    } else {
                      setFormData({ ...formData, category_id: null, user_id: members[0]?.id || null });
                    }
                  }}
                  className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:border-indigo-500"
                >
                  <option value="category">Category Budget</option>
                  <option value="user">Member Budget</option>
                </select>
              </div>

              {budgetType === 'category' && (
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    Category
                  </label>
                  <select
                    value={formData.category_id || ''}
                    onChange={(e) => setFormData({ ...formData, category_id: e.target.value })}
                    className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:border-indigo-500"
                    required
                  >
                    <option value="">Select Category</option>
                    {categories.map((cat) => (
                      <option key={cat.id} value={cat.id}>{cat.name}</option>
                    ))}
                  </select>
                </div>
              )}

              {budgetType === 'user' && (
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    Member
                  </label>
                  <select
                    value={formData.user_id || ''}
                    onChange={(e) => setFormData({ ...formData, user_id: e.target.value })}
                    className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:border-indigo-500"
                    required
                  >
                    <option value="">Select Member</option>
                    {members.map((mem) => (
                      <option key={mem.id} value={mem.id}>{mem.first_name} {mem.last_name}</option>
                    ))}
                  </select>
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Budget Limit Amount
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={formData.limit_amount}
                  onChange={(e) => setFormData({ ...formData, limit_amount: e.target.value })}
                  placeholder="0.00"
                  className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:border-indigo-500"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Period
                </label>
                <select
                  value={formData.period}
                  onChange={(e) => setFormData({ ...formData, period: e.target.value })}
                  className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:border-indigo-500"
                >
                  <option value="MONTHLY">Monthly</option>
                  <option value="QUARTERLY">Quarterly</option>
                  <option value="YEARLY">Yearly</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Alert Threshold ({(parseFloat(formData.alert_threshold) * 100).toFixed(0)}%)
                </label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={formData.alert_threshold}
                  onChange={(e) => setFormData({ ...formData, alert_threshold: parseFloat(e.target.value) })}
                  className="w-full"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Notification Channels
                </label>
                <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
                  <p className="text-sm text-blue-800">
                    ✓ In-App notifications are enabled
                  </p>
                  <p className="text-xs text-blue-700 mt-1">
                    📧 Email notifications coming soon
                  </p>
                </div>
                <input
                  type="hidden"
                  value="IN_APP"
                  onChange={(e) => setFormData({ ...formData, notify_channels: e.target.value })}
                />
              </div>

              <div className="flex gap-2">
                <button
                  type="submit"
                  className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium"
                >
                  {editingBudget ? 'Update Budget' : 'Create Budget'}
                </button>
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="flex-1 px-4 py-2 bg-slate-200 text-slate-700 rounded-lg hover:bg-slate-300 transition-colors font-medium"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default BudgetSettings;
