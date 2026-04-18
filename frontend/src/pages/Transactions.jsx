import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import api from '../services/api';
import { useAuthStore } from '../store/authStore';
import { Plus, X, Clock, Pencil, Trash2 } from 'lucide-react';
import { formatAccountDisplayName, formatCurrency, formatDate, getCurrencySymbol } from '../utils/formatters';
import { formatDateForInput, parseDateForPicker, toNaiveDateTimeString } from '../utils/dateUtils';
import { queryKeys } from '../utils/queryKeys';
import { getTransactionIcon, getTransactionAmountColor } from '../utils/typeHelpers';
import LoadingSpinner from '../components/LoadingSpinner';
import toast from 'react-hot-toast';
import { useCreateTransaction } from '../hooks/useCreateTransaction';
import { useUpdateTransaction, useDeleteTransaction } from '../hooks/useTransactionMutations';
import { useOfflineQueue } from '../context/OfflineQueueContext';

const PrivacyIndicator = React.lazy(() => import('../components/Dashboard/PrivacyIndicator'));

const TX_DEFAULT_RATES = { USD:1.0, EUR:1.1, GBP:1.28, INR:0.012, CAD:0.74, AUD:0.67, JPY:0.0067, AED:0.272, THB:0.028 };
function getTxConversionRate(from, to) {
  if (from === to) return 1.0;
  const f = TX_DEFAULT_RATES[from] ?? 1.0, t = TX_DEFAULT_RATES[to] ?? 1.0;
  return t === 0 ? 1.0 : parseFloat((f / t).toFixed(6));
}

const Transactions = () => {
  const { user } = useAuthStore();
  const [searchParams] = useSearchParams();
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [filter, setFilter] = useState({ type: 'all', account: 'all', category: 'all' });
  
  // Pre-populate account filter if coming from AccountDetail page
  useEffect(() => {
    const accountParam = searchParams.get('account');
    if (accountParam) {
      setFilter(prev => ({ ...prev, account: accountParam }));
    }
  }, [searchParams]);
  
  const [formData, setFormData] = useState({
    type: 'EXPENSE',
    amount: '',
    description: '',
    account_id: '',
    category_id: '',
    target_account_id: '',
    transfer_conversion_rate: '1.00',
    tx_currency: '',
    exchange_rate_to_base: '',
    transaction_date: new Date()
  });

  // Fetch family settings to get privacy level
  const { data: familySettings } = useQuery({
    queryKey: queryKeys.familySettings(),
    queryFn: () => api.get('/settings/family-profile').then(res => res.data),
    staleTime: 1000 * 60 * 5  // 5 minutes
  });

  // Fetch accounts
  const { data: accounts } = useQuery({
    queryKey: queryKeys.accounts(),
    queryFn: () => api.get('/accounts/').then(res => res.data)
  });

  // Fetch all transactions with filters
  const { data: transactions, isLoading: txLoading } = useQuery({
    queryKey: queryKeys.transactionsList(filter, user?.id),
    queryFn: () => {
      // Build query parameters based on filters
      const params = {};
      if (filter.type !== 'all') params.type = filter.type;
      
      // If account filter is selected, use the account endpoint
      // (type param is also supported by the account endpoint)
      if (filter.account !== 'all') {
        return api.get(`/transactions/account/${filter.account}`, { params }).then(res => res.data);
      }
      
      // Otherwise get all transactions for the family
      return api.get(`/transactions/`, { params }).then(res => res.data);
    }
  });

  const { data: categories } = useQuery({
    queryKey: queryKeys.categories(),
    queryFn: () => api.get('/categories/').then(res => res.data)
  });

  const { data: txSecondaryCurrencies = [] } = useQuery({
    queryKey: ['settings', 'currencies'],
    queryFn: () => api.get('/settings/currencies').then(r => r.data),
    staleTime: 1000 * 60 * 5,
  });

  const { data: txStoredRates = [] } = useQuery({
    queryKey: ['settings', 'exchange-rates'],
    queryFn: () => api.get('/settings/exchange-rates').then(r => r.data),
    staleTime: 1000 * 60 * 5,
  });

  const { mutate: createTransaction, isPending: createPending } = useCreateTransaction({
    onSuccess: () => { setShowModal(false); resetForm(); },
  });
  const { mutate: updateTransaction, isPending: updatePending } = useUpdateTransaction({
    onSuccess: () => { setShowModal(false); resetForm(); },
  });
  const { mutate: deleteTransaction } = useDeleteTransaction();
  const { pendingOps } = useOfflineQueue();

  const resetForm = () => {
    setFormData({
      type: 'EXPENSE',
      amount: '',
      description: '',
      account_id: '',
      category_id: '',
      target_account_id: '',
      transfer_conversion_rate: '1.00',
      tx_currency: '',
      exchange_rate_to_base: '',
      transaction_date: new Date()
    });
    setEditingId(null);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    
    // Validate required fields
    if (!formData.account_id) {
      toast.error('Please select an account');
      return;
    }
    
    if (!formData.amount || parseFloat(formData.amount) < 0.01) {
      toast.error('Please enter a valid amount');
      return;
    }
    
    if (formData.type !== 'TRANSFER' && !formData.category_id) {
      toast.error('Please select a category');
      return;
    }
    
    if (formData.type === 'TRANSFER' && !formData.target_account_id) {
      toast.error('Please select a target account for transfer');
      return;
    }
    
    // Get the selected account to extract currency
    const selectedAccount = accounts?.find(acc => acc.id === formData.account_id);
    if (!selectedAccount) {
      toast.error('Invalid account selected');
      return;
    }
    
    const txCurrency = formData.type !== 'TRANSFER'
      ? (formData.tx_currency || selectedAccount.currency)
      : selectedAccount.currency;

    const payload = {
      type: formData.type,
      amount: parseFloat(formData.amount),
      currency: txCurrency,
      description: formData.description || '',
      transaction_date: toNaiveDateTimeString(formData.transaction_date),
      account_id: formData.account_id
    };

    if (formData.type !== 'TRANSFER' && formData.exchange_rate_to_base && parseFloat(formData.exchange_rate_to_base) > 0) {
      payload.exchange_rate_to_base = parseFloat(formData.exchange_rate_to_base);
    }

    // Only add category_id if provided and not transferring
    if (formData.type !== 'TRANSFER' && formData.category_id) {
      payload.category_id = formData.category_id;
    }
    
    // For transfers, include target_account_id and conversion rate
    if (formData.type === 'TRANSFER' && formData.target_account_id) {
      payload.target_account_id = formData.target_account_id;
      if (isCrossCurrency && formData.transfer_conversion_rate) {
        payload.transfer_conversion_rate = parseFloat(formData.transfer_conversion_rate);
      }
    }
    
    if (editingId) {
      // Update existing transaction (offline-aware)
      updateTransaction({ id: editingId, data: payload });
      setEditingId(null);
    } else {
      // Create new transaction (offline-aware)
      createTransaction(payload);
    }
  };

  // Check if categories exist
  const hasCategories = categories && categories.length > 0;
  const expenseCategories = categories?.filter(c => c.type === 'EXPENSE') || [];
  const incomeCategories = categories?.filter(c => c.type === 'INCOME') || [];
  const selectedAccount = accounts?.find(a => a.id === formData.account_id);
  const selectedAccountCurrency = selectedAccount?.currency;
  const targetAccount = accounts?.find(a => a.id === formData.target_account_id);
  const isCrossCurrency = formData.type === 'TRANSFER' && selectedAccount && targetAccount &&
    selectedAccount.currency !== targetAccount.currency;
  const txReceivedAmount = isCrossCurrency && formData.amount && formData.transfer_conversion_rate
    ? (parseFloat(formData.amount) * parseFloat(formData.transfer_conversion_rate)).toFixed(2)
    : null;

  const txResolvedBase = familySettings?.base_currency;
  const lookupTxStoredRate = (currency) => {
    if (!currency || !txResolvedBase) return null;
    if (currency === txResolvedBase) return { rate: '1.000000', date: null };
    const row = txStoredRates.find(r => r.from_currency === currency && r.to_currency === txResolvedBase);
    if (row) return { rate: parseFloat(row.rate).toFixed(6), date: row.valid_date };
    const approx = getTxConversionRate(currency, txResolvedBase);
    return approx !== 1.0 ? { rate: String(approx), date: null } : null;
  };
  const txCurrencyOptions = txResolvedBase
    ? [
        { code: txResolvedBase, label: `${txResolvedBase} (Primary)` },
        ...txSecondaryCurrencies.map(c => ({ code: c.currency_code, label: c.currency_code })),
      ]
    : txSecondaryCurrencies.map(c => ({ code: c.currency_code, label: c.currency_code }));
  const effectiveTxCurrency = formData.tx_currency || selectedAccountCurrency;
  const showTxExchangeRateField = formData.type !== 'TRANSFER' && effectiveTxCurrency && selectedAccountCurrency &&
    effectiveTxCurrency !== selectedAccountCurrency;

  if (!hasCategories) {
    return (
      <div className="max-w-7xl mx-auto">
        <h1 className="text-2xl md:text-3xl font-bold text-gray-900 mb-6">Transactions</h1>
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-6 text-center">
          <p className="text-amber-800 text-lg mb-4">
            ⚠️ You need to create categories before adding transactions
          </p>
          <a 
            href="/categories" 
            className="inline-block bg-blue-600 text-white px-6 py-2.5 rounded-lg hover:bg-blue-700"
          >
            Go to Categories
          </a>
        </div>
      </div>
    );
  }

  if (txLoading) {
    return <LoadingSpinner />;
  }

  return (
    <div className="max-w-7xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3 mb-6">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-gray-900">Transactions</h1>
          <p className="text-gray-600 mt-1">Manage your income and expenses</p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="w-full sm:w-auto bg-blue-600 text-white px-4 py-2.5 rounded-lg flex items-center justify-center gap-2 hover:bg-blue-700"
        >
          <Plus className="w-5 h-5" />
          Add Transaction
        </button>
      </div>

      {/* Show privacy level indicator for non-admin members */}
      {user?.role !== 'ADMIN' && (
        <React.Suspense fallback={<div className="h-[74px] mb-6" />}>
          <PrivacyIndicator privacyLevel={familySettings?.privacy_level || 'FAMILY'} userRole={user?.role} />
        </React.Suspense>
      )}

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-4 mb-6 flex flex-wrap gap-3 sm:gap-4">
        <select
          value={filter.type}
          onChange={(e) => setFilter({...filter, type: e.target.value})}
          className="w-full sm:w-auto px-3 py-2 border rounded-lg"
        >
          <option value="all">All Types</option>
          <option value="INCOME">Income</option>
          <option value="EXPENSE">Expense</option>
          <option value="TRANSFER">Transfer</option>
        </select>
        
        <select
          value={filter.account}
          onChange={(e) => setFilter({...filter, account: e.target.value})}
          className="w-full sm:w-auto px-3 py-2 border rounded-lg"
        >
          <option value="all">All Accounts</option>
          {[
            { type: 'BANK', label: 'Bank Accounts' },
            { type: 'CREDIT_CARD', label: 'Credit Cards' },
            { type: 'CASH', label: 'Cash & Wallets' },
            { type: 'INVESTMENT', label: 'Investments' },
          ].map(group => {
            const groupAccounts = accounts?.filter(a => a.type === group.type) || [];
            if (!groupAccounts.length) return null;
            return (
              <optgroup key={group.type} label={group.label}>
                {groupAccounts.map(a => (
                  <option key={a.id} value={a.id}>
                    {formatAccountDisplayName(a)}
                  </option>
                ))}
              </optgroup>
            );
          })}
        </select>
      </div>

      {/* Transactions List */}
      <div className="bg-white dark:bg-slate-800 rounded-lg shadow">

        {/* Mobile: 2-line card list (no horizontal scroll) */}
        <div className="md:hidden divide-y divide-gray-100 dark:divide-slate-700">
          {pendingOps.map((op) => {
            const acc = accounts?.find(a => a.id === op.payload.account_id);
            const cat = categories?.find(c => c.id === op.payload.category_id);
            return (
              <div key={op.id} className="px-4 py-3 bg-amber-50 dark:bg-amber-900/10 opacity-75">
                {/* Row 1: icon + description + pending badge (left) · amount (right) */}
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0 flex-1">
                    {getTransactionIcon(op.payload.type, 'w-4 h-4')}
                    <span className="text-sm font-medium truncate">{op.payload.description || 'No description'}</span>
                    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs bg-amber-100 text-amber-700 dark:bg-amber-800 dark:text-amber-200 shrink-0">
                      <Clock className="w-3 h-3" /> pending
                    </span>
                  </div>
                  <span className={`text-sm font-medium whitespace-nowrap shrink-0 ${getTransactionAmountColor(op.payload.type)}`}>
                    {op.payload.type === 'INCOME' ? '+' : op.payload.type === 'EXPENSE' ? '-' : ''}
                    {formatCurrency(op.payload.amount, op.payload.currency)}
                  </span>
                </div>
                {/* Row 2: date · category · account — no-wrap, truncates at account */}
                <div className="flex items-center gap-x-1.5 mt-1 overflow-hidden">
                  <span className="text-xs text-gray-500 shrink-0 whitespace-nowrap">{formatDate(op.payload.transaction_date)}</span>
                  {cat && (
                    <>
                      <span className="text-gray-300 text-xs shrink-0">·</span>
                      <span className="px-1.5 py-0.5 rounded text-white text-xs leading-none shrink-0 max-w-[96px] truncate" style={{ backgroundColor: cat.color }}>{cat.name}</span>
                    </>
                  )}
                  <span className="text-gray-300 text-xs shrink-0">·</span>
                  <span className="text-xs text-gray-400 truncate min-w-0">{acc ? formatAccountDisplayName(acc) : op.payload.account_id}</span>
                </div>
              </div>
            );
          })}
          {transactions?.map((t) => (
            <div key={t.id} className="px-4 py-3 hover:bg-gray-50 dark:hover:bg-slate-700/50">
              {/* Row 1: icon + description (left) · amount (right) */}
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0 flex-1">
                  {getTransactionIcon(t.type, 'w-4 h-4')}
                  <span className="text-sm font-medium truncate">{t.description || 'No description'}</span>
                </div>
                <span className={`text-sm font-medium whitespace-nowrap shrink-0 ${getTransactionAmountColor(t.type)}`}>
                  {t.type === 'INCOME' ? '+' : t.type === 'EXPENSE' ? '-' : ''}
                  {formatCurrency(t.amount, t.currency)}
                </span>
              </div>
              {/* Row 2: date · category · account (left) · edit/delete icons (right) */}
              <div className="flex items-center justify-between gap-2 mt-1">
                <div className="flex items-center gap-x-1.5 overflow-hidden min-w-0 flex-1">
                  <span className="text-xs text-gray-500 shrink-0 whitespace-nowrap">{formatDate(t.transaction_date)}</span>
                  {t.category && (
                    <>
                      <span className="text-gray-300 text-xs shrink-0">·</span>
                      <span
                        className="px-1.5 py-0.5 rounded text-white text-xs leading-none shrink-0 max-w-[96px] truncate"
                        style={{ backgroundColor: t.category.color }}
                      >
                        {t.category.name}
                      </span>
                    </>
                  )}
                  <span className="text-gray-300 text-xs shrink-0">·</span>
                  <span className="text-xs text-gray-500 truncate min-w-0">{formatAccountDisplayName(t.account)}</span>
                </div>
                <div className="flex items-center gap-0.5 shrink-0">
                  <button
                    onClick={() => {
                      setFormData({
                        type: t.type,
                        amount: t.amount.toString(),
                        description: t.description || '',
                        account_id: t.account_id,
                        category_id: t.category_id || '',
                        target_account_id: t.linked_transaction_id ? t.target_account_id : '',
                        transfer_conversion_rate: '1.00',
                        tx_currency: '',
                        exchange_rate_to_base: '',
                        transaction_date: parseDateForPicker(t.transaction_date)
                      });
                      setEditingId(t.id);
                      setShowModal(true);
                    }}
                    className="p-1.5 text-blue-400 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded"
                    title="Edit"
                  >
                    <Pencil className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => {
                      if (window.confirm('Are you sure you want to delete this transaction?')) {
                        deleteTransaction(t.id);
                      }
                    }}
                    className="p-1.5 text-red-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30 rounded"
                    title="Delete"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>
          ))}
          {(!transactions || transactions.length === 0) && pendingOps.length === 0 && (
            <div className="text-center py-12 text-gray-500">
              No transactions yet. Add your first one!
            </div>
          )}
        </div>

        {/* Desktop: original table */}
        <div className="hidden md:block overflow-x-auto">
          <table className="w-full min-w-[720px]">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 sm:px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                <th className="px-3 sm:px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Description</th>
                <th className="px-3 sm:px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Category</th>
                <th className="px-3 sm:px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Account</th>
                <th className="px-3 sm:px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Amount</th>
                <th className="px-3 sm:px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {pendingOps.map((op) => {
                const acc = accounts?.find(a => a.id === op.payload.account_id);
                const cat = categories?.find(c => c.id === op.payload.category_id);
                return (
                  <tr key={op.id} className="bg-amber-50 dark:bg-amber-900/10 opacity-75">
                    <td className="px-3 sm:px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatDate(op.payload.transaction_date)}
                    </td>
                    <td className="px-3 sm:px-6 py-4 text-sm text-gray-500">
                      <div className="flex items-center gap-2">
                        {getTransactionIcon(op.payload.type, 'w-4 h-4')}
                        {op.payload.description || 'No description'}
                        <span className="ml-1 inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs bg-amber-100 text-amber-700 dark:bg-amber-800 dark:text-amber-200">
                          <Clock className="w-3 h-3" /> pending
                        </span>
                      </div>
                    </td>
                    <td className="px-3 sm:px-6 py-4 text-sm">
                      {cat ? (
                        <span className="px-2 py-1 rounded text-white text-xs" style={{ backgroundColor: cat.color }}>
                          {cat.name}
                        </span>
                      ) : <span className="text-gray-400">-</span>}
                    </td>
                    <td className="px-3 sm:px-6 py-4 text-sm text-gray-400">
                      {acc ? formatAccountDisplayName(acc) : op.payload.account_id}
                    </td>
                    <td className={`px-3 sm:px-6 py-4 text-sm text-right font-medium ${getTransactionAmountColor(op.payload.type)}`}>
                      {op.payload.type === 'INCOME' ? '+' : op.payload.type === 'EXPENSE' ? '-' : ''}
                      {formatCurrency(op.payload.amount, op.payload.currency)}
                    </td>
                    <td className="px-3 sm:px-6 py-4 text-sm text-gray-400">—</td>
                  </tr>
                );
              })}
              {transactions?.map((t) => (
                <tr key={t.id} className="hover:bg-gray-50">
                  <td className="px-3 sm:px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {formatDate(t.transaction_date)}
                  </td>
                  <td className="px-3 sm:px-6 py-4 text-sm text-gray-900">
                    <div className="flex items-center gap-2">
                      {getTransactionIcon(t.type, 'w-4 h-4')}
                      {t.description || 'No description'}
                    </div>
                  </td>
                  <td className="px-3 sm:px-6 py-4 text-sm">
                    {t.category ? (
                      <span
                        className="px-2 py-1 rounded text-white text-xs"
                        style={{ backgroundColor: t.category.color }}
                      >
                        {t.category.name}
                      </span>
                    ) : (
                      <span className="text-gray-400">-</span>
                    )}
                  </td>
                  <td className="px-3 sm:px-6 py-4 text-sm text-gray-500">
                    {formatAccountDisplayName(t.account)}
                  </td>
                  <td className={`px-3 sm:px-6 py-4 text-sm text-right font-medium ${getTransactionAmountColor(t.type)}`}>
                    {t.type === 'INCOME' ? '+' : t.type === 'EXPENSE' ? '-' : ''}
                    {formatCurrency(t.amount, t.currency)}
                  </td>
                  <td className="px-3 sm:px-6 py-4 text-sm flex gap-2">
                    <button
                      onClick={() => {
                        setFormData({
                          type: t.type,
                          amount: t.amount.toString(),
                          description: t.description || '',
                          account_id: t.account_id,
                          category_id: t.category_id || '',
                          target_account_id: t.linked_transaction_id ? t.target_account_id : '',
                          transfer_conversion_rate: '1.00',
                          tx_currency: '',
                          exchange_rate_to_base: '',
                          transaction_date: parseDateForPicker(t.transaction_date)
                        });
                        setEditingId(t.id);
                        setShowModal(true);
                      }}
                      className="text-blue-600 hover:text-blue-800"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => {
                        if (window.confirm('Are you sure you want to delete this transaction?')) {
                          deleteTransaction(t.id);
                        }
                      }}
                      className="text-red-600 hover:text-red-800"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {(!transactions || transactions.length === 0) && pendingOps.length === 0 && (
            <div className="text-center py-12 text-gray-500">
              No transactions yet. Add your first one!
            </div>
          )}
        </div>

      </div>

      {/* Add Transaction Modal */}
      {showModal && (
        <div className="modal-backdrop fixed inset-0 flex items-start sm:items-center justify-center z-50 p-3 sm:p-4 overflow-y-auto">
          <div className="glass-panel bg-white dark:bg-slate-800 rounded-lg shadow-xl w-full max-w-md mx-3 sm:mx-4 p-4 sm:p-6 max-h-[92vh] overflow-y-auto slide-in">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold">{editingId ? 'Edit Transaction' : 'Add Transaction'}</h2>
              <button 
                onClick={() => {
                  setShowModal(false);
                  resetForm();
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Date */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Date *</label>
                <input
                  type="date"
                  value={formatDateForInput(formData.transaction_date)}
                  onChange={(e) => setFormData({...formData, transaction_date: parseDateForPicker(e.target.value)})}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>

              {/* Account */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {formData.type === 'TRANSFER' ? 'From Account' : 'Account'} *
                </label>
                <select
                  required
                  value={formData.account_id}
                  onChange={(e) => setFormData({...formData, account_id: e.target.value})}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">Select account...</option>
                  {[
                    { type: 'BANK', label: 'Bank Accounts' },
                    { type: 'CREDIT_CARD', label: 'Credit Cards' },
                    { type: 'CASH', label: 'Cash & Wallets' },
                    { type: 'INVESTMENT', label: 'Investments' },
                  ].map(group => {
                    const groupAccounts = accounts?.filter(a => a.type === group.type) || [];
                    if (!groupAccounts.length) return null;
                    return (
                      <optgroup key={group.type} label={group.label}>
                        {groupAccounts.map(a => (
                          <option key={a.id} value={a.id}>
                            {`${formatAccountDisplayName(a)} (${a.currency})`}
                          </option>
                        ))}
                      </optgroup>
                    );
                  })}
                </select>
              </div>

              {/* Target Account (for transfers) */}
              {formData.type === 'TRANSFER' && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">To Account *</label>
                  <select
                    required
                    value={formData.target_account_id}
                    onChange={(e) => {
                      const dest = accounts?.find(a => a.id === e.target.value);
                      const src = accounts?.find(a => a.id === formData.account_id);
                      const rate = (dest && src && dest.currency !== src.currency)
                        ? String(getTxConversionRate(src.currency, dest.currency))
                        : '1.00';
                      setFormData({...formData, target_account_id: e.target.value, transfer_conversion_rate: rate});
                    }}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">Select target account...</option>
                    {[
                      { type: 'BANK', label: 'Bank Accounts' },
                      { type: 'CREDIT_CARD', label: 'Credit Cards' },
                      { type: 'CASH', label: 'Cash & Wallets' },
                      { type: 'INVESTMENT', label: 'Investments' },
                    ].map(group => {
                      const groupAccounts = accounts?.filter(a => a.type === group.type && a.id !== formData.account_id) || [];
                      if (!groupAccounts.length) return null;
                      return (
                        <optgroup key={group.type} label={group.label}>
                          {groupAccounts.map(a => (
                            <option key={a.id} value={a.id}>
                              {`${formatAccountDisplayName(a)} (${a.currency})`}
                            </option>
                          ))}
                        </optgroup>
                      );
                    })}
                  </select>
                </div>
              )}

              {/* Conversion Rate — only shown for cross-currency transfers */}
              {isCrossCurrency && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Conversion Rate
                    <span className="ml-1 text-xs font-normal text-gray-500">
                      (1 {selectedAccount.currency} = ? {targetAccount.currency})
                    </span>
                  </label>
                  <input
                    type="number"
                    step="0.000001"
                    min="0.000001"
                    value={formData.transfer_conversion_rate}
                    onChange={(e) => setFormData({...formData, transfer_conversion_rate: e.target.value})}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  />
                  {txReceivedAmount && (
                    <p className="text-sm text-gray-600 mt-1">
                      Recipient gets: <span className="font-medium">{formatCurrency(txReceivedAmount, targetAccount.currency)}</span>
                    </p>
                  )}
                </div>
              )}

              {/* Type Selection */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Type *</label>
                <div className="flex gap-4 flex-wrap">
                  <label className="flex items-center">
                    <input
                      type="radio"
                      value="EXPENSE"
                      checked={formData.type === 'EXPENSE'}
                      onChange={(e) => setFormData({...formData, type: e.target.value, category_id: '', target_account_id: ''})}
                      className="mr-2"
                    />
                    <span className="text-red-600 font-medium">Expense</span>
                  </label>
                  <label className="flex items-center">
                    <input
                      type="radio"
                      value="INCOME"
                      checked={formData.type === 'INCOME'}
                      onChange={(e) => setFormData({...formData, type: e.target.value, category_id: '', target_account_id: ''})}
                      className="mr-2"
                    />
                    <span className="text-green-600 font-medium">Income</span>
                  </label>
                  <label className="flex items-center">
                    <input
                      type="radio"
                      value="TRANSFER"
                      checked={formData.type === 'TRANSFER'}
                      onChange={(e) => setFormData({...formData, type: e.target.value, category_id: '', target_account_id: ''})}
                      className="mr-2"
                    />
                    <span className="text-blue-600 font-medium">Transfer</span>
                  </label>
                </div>
              </div>

              {/* Category - Only for income/expense */}
              {formData.type !== 'TRANSFER' && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Category *
                  </label>
                  <select
                    required
                    value={formData.category_id}
                    onChange={(e) => setFormData({...formData, category_id: e.target.value})}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">
                      {formData.type === 'EXPENSE' ? 'Select expense category...' : 'Select income category...'}
                    </option>
                    {(formData.type === 'EXPENSE' ? expenseCategories : incomeCategories).map(c => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                  {(formData.type === 'EXPENSE' ? expenseCategories : incomeCategories).length === 0 && (
                    <p className="text-sm text-red-600 mt-1">
                      No {formData.type.toLowerCase()} categories. Create one first!
                    </p>
                  )}
                </div>
              )}

              {/* Currency override — income/expense only, when family has secondary currencies */}
              {formData.type !== 'TRANSFER' && txCurrencyOptions.length > 1 && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Transaction Currency
                    <span className="ml-1 text-xs font-normal text-gray-400">(optional override)</span>
                  </label>
                  <select
                    value={formData.tx_currency}
                    onChange={(e) => {
                      const selected = e.target.value;
                      const looked = lookupTxStoredRate(selected);
                      setFormData({...formData, tx_currency: selected, exchange_rate_to_base: looked ? looked.rate : ''});
                    }}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">Account currency ({selectedAccountCurrency || '—'})</option>
                    {txCurrencyOptions
                      .filter(c => c.code !== selectedAccountCurrency)
                      .map(c => (
                        <option key={c.code} value={c.code}>{c.label}</option>
                      ))
                    }
                  </select>
                </div>
              )}

              {/* Exchange rate — shown when transaction currency ≠ account currency */}
              {showTxExchangeRateField && (() => {
                const rateInfo = lookupTxStoredRate(effectiveTxCurrency);
                return (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Exchange Rate to {txResolvedBase}
                      {rateInfo?.date && (
                        <span className="ml-1 text-xs font-normal text-gray-400">ECB rate as of {rateInfo.date}</span>
                      )}
                      {!rateInfo?.date && rateInfo && (
                        <span className="ml-1 text-xs font-normal text-gray-400">approx. — edit if needed</span>
                      )}
                    </label>
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-gray-500 whitespace-nowrap">1 {effectiveTxCurrency} =</span>
                      <input
                        type="number"
                        step="0.000001"
                        min="0.000001"
                        value={formData.exchange_rate_to_base}
                        onChange={(e) => setFormData({...formData, exchange_rate_to_base: e.target.value})}
                        className="flex-1 px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                        placeholder="enter rate"
                      />
                      <span className="text-sm text-gray-500">{txResolvedBase}</span>
                    </div>
                  </div>
                );
              })()}

              {/* Amount */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Amount *</label>
                <div className="relative">
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={formData.amount}
                    onChange={(e) => setFormData({...formData, amount: e.target.value})}
                    className="w-full pl-3 pr-16 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                    placeholder="0.00"
                  />
                  {(effectiveTxCurrency || selectedAccountCurrency) && (
                    <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs font-medium text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded">
                      {effectiveTxCurrency || selectedAccountCurrency}
                    </span>
                  )}
                </div>
              </div>

              {/* Description */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <input
                  type="text"
                  value={formData.description}
                  onChange={(e) => setFormData({...formData, description: e.target.value})}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  placeholder="What was this for?"
                />
              </div>

              <div className="flex gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => {
                    setShowModal(false);
                    resetForm();
                  }}
                  className="flex-1 px-4 py-2.5 border rounded-lg hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={(createPending || updatePending) ||
                           (formData.type !== 'TRANSFER' && !formData.category_id) ||
                           (formData.type === 'TRANSFER' && !formData.target_account_id)}
                  className="flex-1 px-4 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  {editingId ? (
                    updatePending ? 'Updating...' : 'Update Transaction'
                  ) : (
                    createPending ? 'Adding...' : 'Add Transaction'
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Transactions;
