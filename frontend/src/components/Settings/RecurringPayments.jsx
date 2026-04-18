import React, { useState, useEffect } from 'react';
import settingsAPI from '../../services/settingsAPI';
import api from '../../services/api';
import { useAuthStore } from '../../store/authStore';
import { formatAccountDisplayName, formatDate } from '../../utils/formatters';
import { formatDateForInput, parseDateForPicker, toNaiveDateTimeString } from '../../utils/dateUtils';

const RecurringPayments = () => {
  const user = useAuthStore((state) => state.user);
  const [payments, setPayments] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [editingPayment, setEditingPayment] = useState(null);

  const [formData, setFormData] = useState({
    name: '',
    amount: '',
    account_id: '',
    category_id: '',
    pattern: 'MONTHLY',
    next_due_date: '',
    notify_before_days: '3',
    assigned_to_user_id: null,
    description: '',
    end_date: null,
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const requestsToMake = [
        settingsAPI.getRecurringPayments(),
        api.get('/accounts/'),
        api.get('/categories/'),
      ];
      
      // Only fetch members list if user is admin (needed for displaying member names)
      if (user?.role === 'ADMIN') {
        requestsToMake.push(api.get('/admin/users'));
      }
      
      const responses = await Promise.all(requestsToMake);
      
      setPayments(responses[0].data);
      setAccounts(responses[1].data);
      setCategories(responses[2].data.filter(c => c.type === 'EXPENSE'));
      
      if (user?.role === 'ADMIN') {
        setMembers(responses[3].data);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load recurring payments');
    } finally {
      setLoading(false);
    }
  };

  const handleOpenModal = (payment = null) => {
    if (payment) {
      setEditingPayment(payment);
      setFormData({
        name: payment.name,
        amount: payment.amount,
        account_id: payment.account_id,
        category_id: payment.category_id,
        pattern: payment.pattern,
        next_due_date: formatDateForInput(payment.next_due_date),
        notify_before_days: payment.notify_before_days,
        assigned_to_user_id: payment.assigned_to_user_id,
        description: payment.description || '',
        end_date: payment.end_date ? formatDateForInput(payment.end_date) : null,
      });
    } else {
      setEditingPayment(null);
      const tomorrow = new Date();
      tomorrow.setDate(tomorrow.getDate() + 1);
      setFormData({
        name: '',
        amount: '',
        account_id: accounts[0]?.id || '',
        category_id: categories[0]?.id || '',
        pattern: 'MONTHLY',
        next_due_date: formatDateForInput(tomorrow),
        notify_before_days: '3',
        assigned_to_user_id: user?.role === 'ADMIN' ? null : user?.id,
        description: '',
        end_date: null,
      });
    }
    setShowModal(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.name || !formData.amount || !formData.account_id || !formData.category_id) {
      setError('Please fill in all required fields');
      return;
    }

    try {
      setError(null);
      const data = {
        ...formData,
        amount: parseFloat(formData.amount),
        next_due_date: toNaiveDateTimeString(formData.next_due_date),
        ...(formData.end_date && { end_date: toNaiveDateTimeString(formData.end_date) }),
      };

      if (editingPayment) {
        await settingsAPI.updateRecurringPayment(editingPayment.id, data);
        setSuccessMessage('Recurring payment updated successfully!');
      } else {
        await settingsAPI.createRecurringPayment(data);
        setSuccessMessage('Recurring payment created successfully!');
      }

      setShowModal(false);
      fetchData();
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save recurring payment');
    }
  };

  const handleDeactivate = async (paymentId) => {
    if (!window.confirm('Are you sure you want to deactivate this recurring payment?')) return;

    try {
      setError(null);
      await settingsAPI.deactivateRecurringPayment(paymentId);
      setSuccessMessage('Recurring payment deactivated!');
      fetchData();
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to deactivate payment');
    }
  };

  const getDaysUntilDue = (dueDate) => {
    const today = new Date();
    const todayDateOnly = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    const due = parseDateForPicker(dueDate);
    const dueDateOnly = new Date(due.getFullYear(), due.getMonth(), due.getDate());
    const diffTime = dueDateOnly - todayDateOnly;
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return diffDays;
  };

  const getDueStatus = (payment) => {
    const daysUntilDue = getDaysUntilDue(payment.next_due_date);
    if (daysUntilDue < 0) return { label: 'Overdue', color: 'red', emoji: '⚠️' };
    if (daysUntilDue === 0) return { label: 'Due Today', color: 'yellow', emoji: '📌' };
    if (daysUntilDue <= parseInt(payment.notify_before_days)) return { label: `Due in ${daysUntilDue} day(s)`, color: 'orange', emoji: '🔔' };
    return { label: `Due in ${daysUntilDue} day(s)`, color: 'green', emoji: '✓' };
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  // Filter payments based on user role
  let displayedPayments = payments;
  if (user?.role !== 'ADMIN') {
    // Members only see their own payments (assigned to them)
    displayedPayments = payments.filter(
      p => String(p.assigned_to_user_id) === String(user?.id)
    );
  }

  // Check if member can edit a payment
  const canEditPayment = (payment) => {
    if (user?.role === 'ADMIN') return true;
    return String(payment.assigned_to_user_id) === String(user?.id);
  };

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
        <h2 className="text-2xl font-bold text-slate-900">Recurring Payments</h2>
        <button
          onClick={() => handleOpenModal()}
          className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium"
        >
          + Add Recurring Payment
        </button>
      </div>

      {user?.role !== 'ADMIN' && (
        <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <p className="text-blue-900 font-semibold">📋 Your Recurring Payments</p>
          <p className="text-blue-800 text-sm mt-1">
            Add and manage your recurring payment schedules.
          </p>
        </div>
      )}

      {/* Upcoming Payments Section */}
      {displayedPayments.length > 0 ? (
        <>
          <div className="mb-6">
            <h3 className="text-lg font-semibold text-slate-900 mb-3">Upcoming Payments</h3>
            <div className="space-y-2">
              {displayedPayments
                .filter(p => getDaysUntilDue(p.next_due_date) <= parseInt(p.notify_before_days))
                .sort((a, b) => parseDateForPicker(a.next_due_date) - parseDateForPicker(b.next_due_date))
                .map((payment) => {
                  const status = getDueStatus(payment);
                  return (
                    <div
                      key={payment.id}
                      className={`p-3 rounded-lg border-l-4 flex justify-between items-center ${
                        status.color === 'red'
                          ? 'border-red-400 bg-red-50'
                          : status.color === 'yellow'
                          ? 'border-yellow-400 bg-yellow-50'
                          : status.color === 'orange'
                          ? 'border-orange-400 bg-orange-50'
                          : 'border-green-400 bg-green-50'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-2xl">{status.emoji}</span>
                        <div>
                          <p className="font-semibold text-slate-900">{payment.name}</p>
                          <p className="text-sm text-slate-600">₹{parseFloat(payment.amount).toFixed(2)} • {status.label}</p>
                        </div>
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>

          {/* All Recurring Payments Table */}
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50">
                  <th className="px-4 py-3 text-left font-semibold text-slate-700">Payment Name</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-700">Amount</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-700">Frequency</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-700">Next Due</th>
                  {user?.role === 'ADMIN' && <th className="px-4 py-3 text-left font-semibold text-slate-700">Assigned To</th>}
                  <th className="px-4 py-3 text-left font-semibold text-slate-700">Status</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-700">Actions</th>
                </tr>
              </thead>
              <tbody>
                {displayedPayments.map((payment) => {
                  const status = getDueStatus(payment);
                  const assignedMember = members.find(m => String(m.id) === String(payment.assigned_to_user_id));
                  return (
                    <tr key={payment.id} className="border-b border-slate-200 hover:bg-slate-50 transition-colors">
                      <td className="px-4 py-3">
                        <div>
                          <p className="font-semibold text-slate-900">{payment.name}</p>
                          {payment.description && <p className="text-sm text-slate-600">{payment.description}</p>}
                        </div>
                      </td>
                      <td className="px-4 py-3 font-semibold">₹{parseFloat(payment.amount).toFixed(2)}</td>
                      <td className="px-4 py-3">{payment.pattern}</td>
                      <td className="px-4 py-3">
                        <div>
                          <p>{formatDate(payment.next_due_date)}</p>
                          <p className="text-sm text-slate-600">{status.label}</p>
                        </div>
                      </td>
                      {user?.role === 'ADMIN' && (
                        <td className="px-4 py-3">
                          {assignedMember ? `${assignedMember.first_name} ${assignedMember.last_name}` : '—'}
                        </td>
                      )}
                      <td className="px-4 py-3">
                        <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                          payment.is_active
                            ? 'bg-green-100 text-green-700'
                            : 'bg-slate-100 text-slate-700'
                        }`}>
                          {payment.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex gap-2">
                          {canEditPayment(payment) ? (
                            <>
                              <button
                                onClick={() => handleOpenModal(payment)}
                                className="px-3 py-1 bg-blue-100 text-blue-700 rounded text-sm hover:bg-blue-200 transition-colors"
                              >
                                Edit
                              </button>
                              {payment.is_active && (
                                <button
                                  onClick={() => handleDeactivate(payment.id)}
                                  className="px-3 py-1 bg-red-100 text-red-700 rounded text-sm hover:bg-red-200 transition-colors"
                                >
                                  Deactivate
                                </button>
                              )}
                            </>
                          ) : (
                            <span className="text-sm text-slate-500">No actions available</span>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <div className="text-center py-8 bg-slate-50 rounded-lg border border-slate-200">
          <p className="text-slate-600">
            {user?.role === 'ADMIN'
              ? 'No recurring payments set up yet. Create one to automate regular payments.'
              : 'No recurring payments assigned to you. Click "Add Recurring Payment" to set one up.'}
          </p>
        </div>
      )}

      {/* Recurring Payment Modal */}
      {showModal && (
        <div className="modal-backdrop fixed inset-0 flex items-center justify-center z-50 p-4">
          <div className="glass-panel bg-white dark:bg-slate-800 rounded-lg p-6 max-w-md w-full max-h-96 overflow-y-auto slide-in">
            <h3 className="text-xl font-bold text-slate-900 mb-4">
              {editingPayment ? 'Edit Recurring Payment' : 'Add Recurring Payment'}
            </h3>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Payment Name *
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g., Monthly Rent"
                  className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:border-indigo-500"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Amount *
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={formData.amount}
                  onChange={(e) => setFormData({ ...formData, amount: e.target.value })}
                  placeholder="0.00"
                  className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:border-indigo-500"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Account *
                </label>
                <select
                  value={formData.account_id}
                  onChange={(e) => setFormData({ ...formData, account_id: e.target.value })}
                  className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:border-indigo-500"
                  required
                >
                  <option value="">Select Account</option>
                  {[
                    { type: 'BANK', label: 'Bank Accounts' },
                    { type: 'CREDIT_CARD', label: 'Credit Cards' },
                    { type: 'CASH', label: 'Cash & Wallets' },
                    { type: 'INVESTMENT', label: 'Investments' },
                  ].map(group => {
                    const groupAccounts = accounts.filter(a => a.type === group.type);
                    if (!groupAccounts.length) return null;
                    return (
                      <optgroup key={group.type} label={group.label}>
                        {groupAccounts.map(acc => (
                          <option key={acc.id} value={acc.id}>
                            {formatAccountDisplayName(acc)}
                          </option>
                        ))}
                      </optgroup>
                    );
                  })}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Category *
                </label>
                <select
                  value={formData.category_id}
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

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Frequency
                </label>
                <select
                  value={formData.pattern}
                  onChange={(e) => setFormData({ ...formData, pattern: e.target.value })}
                  className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:border-indigo-500"
                >
                  <option value="DAILY">Daily</option>
                  <option value="WEEKLY">Weekly</option>
                  <option value="BIWEEKLY">Bi-Weekly</option>
                  <option value="MONTHLY">Monthly</option>
                  <option value="QUARTERLY">Quarterly</option>
                  <option value="YEARLY">Yearly</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Next Due Date
                </label>
                <input
                  type="date"
                  value={formData.next_due_date}
                  onChange={(e) => setFormData({ ...formData, next_due_date: e.target.value })}
                  className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:border-indigo-500"
                  required
                />
              </div>

              {user?.role === 'ADMIN' && (
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    Assigned To (Optional)
                  </label>
                  <select
                    value={formData.assigned_to_user_id || ''}
                    onChange={(e) => setFormData({ ...formData, assigned_to_user_id: e.target.value || null })}
                    className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:border-indigo-500"
                  >
                    <option value="">Not assigned</option>
                    {members.map((mem) => (
                      <option key={mem.id} value={mem.id}>{mem.first_name} {mem.last_name}</option>
                    ))}
                  </select>
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Notify Before (Days)
                </label>
                <input
                  type="number"
                  value={formData.notify_before_days}
                  onChange={(e) => setFormData({ ...formData, notify_before_days: e.target.value })}
                  className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="flex gap-2">
                <button
                  type="submit"
                  className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium"
                >
                  {editingPayment ? 'Update' : 'Add'} Payment
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

export default RecurringPayments;
