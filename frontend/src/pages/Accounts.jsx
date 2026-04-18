import { useNavigate } from 'react-router-dom';
import React, { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import settingsAPI from '../services/settingsAPI';
import { useAuthStore } from '../store/authStore';
import { Plus, Trash2, Edit, X, GripVertical, ArrowLeftRight } from 'lucide-react';
import { formatAccountDisplayName, formatCurrency } from '../utils/formatters';
import { queryKeys } from '../utils/queryKeys';
import { getAccountIcon, getAccountColor, getCountryDisplay } from '../utils/typeHelpers';
import LoadingSpinner from '../components/LoadingSpinner';
import toast from 'react-hot-toast';
import { useCreateAccount, useUpdateAccount, useDeleteAccount } from '../hooks/useAccountMutations';

const ACCOUNT_GROUPS = [
  { type: 'BANK', label: 'Bank Accounts' },
  { type: 'CREDIT_CARD', label: 'Credit Cards' },
  { type: 'CASH', label: 'Cash & Wallets' },
  { type: 'INVESTMENT', label: 'Investments' },
];

const COUNTRIES = [
  { code: 'AE', name: 'UAE', flag: '🇦🇪' },
  { code: 'AU', name: 'Australia', flag: '🇦🇺' },
  { code: 'CA', name: 'Canada', flag: '🇨🇦' },
  { code: 'CH', name: 'Switzerland', flag: '🇨🇭' },
  { code: 'DE', name: 'Germany', flag: '🇩🇪' },
  { code: 'FR', name: 'France', flag: '🇫🇷' },
  { code: 'GB', name: 'United Kingdom', flag: '🇬🇧' },
  { code: 'HK', name: 'Hong Kong', flag: '🇭🇰' },
  { code: 'IN', name: 'India', flag: '🇮🇳' },
  { code: 'JP', name: 'Japan', flag: '🇯🇵' },
  { code: 'MY', name: 'Malaysia', flag: '🇲🇾' },
  { code: 'NL', name: 'Netherlands', flag: '🇳🇱' },
  { code: 'NZ', name: 'New Zealand', flag: '🇳🇿' },
  { code: 'QA', name: 'Qatar', flag: '🇶🇦' },
  { code: 'SA', name: 'Saudi Arabia', flag: '🇸🇦' },
  { code: 'SG', name: 'Singapore', flag: '🇸🇬' },
  { code: 'TH', name: 'Thailand', flag: '🇹🇭' },
  { code: 'US', name: 'United States', flag: '🇺🇸' },
];

const Accounts = () => {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const queryClient = useQueryClient();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingAccount, setEditingAccount] = useState(null);
  const [isReordering, setIsReordering] = useState(false);
  const [orderedAccounts, setOrderedAccounts] = useState([]);
  const draggedId = useRef(null);

  // Form state for create
  const [createForm, setCreateForm] = useState({
    name: '',
    type: 'BANK',
    currency: '',
    owner_type: 'SHARED',
    opening_balance: '',
    country_code: '',
    include_in_family_overview: true
  });

  // Form state for edit
  const [editForm, setEditForm] = useState({
    name: '',
    current_balance: '',
    country_code: '',
    include_in_family_overview: true
  });

  const { data: accounts, isLoading } = useQuery({
    queryKey: queryKeys.accounts(),
    queryFn: () => api.get('/accounts/').then(res => res.data)
  });

  const { data: familyProfile, isLoading: profileLoading } = useQuery({
    queryKey: ['settings', 'family-profile'],
    queryFn: () => settingsAPI.getFamilyProfile().then(r => r.data),
    staleTime: 1000 * 60 * 5,
  });

  const { data: secondaryCurrencies = [], isLoading: currLoading } = useQuery({
    queryKey: ['settings', 'currencies'],
    queryFn: () => settingsAPI.getCurrencies().then(r => r.data),
    staleTime: 1000 * 60 * 5,
  });

  const currenciesLoading = profileLoading || currLoading;

  // Build ordered list: base currency first, then secondary currencies
  const baseCurrency = familyProfile?.base_currency;
  const availableCurrencies = baseCurrency
    ? [
        { code: baseCurrency, label: `${baseCurrency} (Primary)` },
        ...secondaryCurrencies.map(c => ({ code: c.currency_code, label: c.currency_code })),
      ]
    : secondaryCurrencies.map(c => ({ code: c.currency_code, label: c.currency_code }));

  const { mutate: createAccountMutate, isPending: createPending } = useCreateAccount({
    onSuccess: () => {
      setShowCreateModal(false);
      setCreateForm({
        name: '',
        type: 'BANK',
        currency: baseCurrency || '',
        owner_type: 'SHARED',
        opening_balance: '',
        country_code: '',
        include_in_family_overview: true
      });
    },
  });

  const { mutate: updateAccountMutate, isPending: updatePending } = useUpdateAccount({
    onSuccess: () => {
      setShowEditModal(false);
      setEditingAccount(null);
    },
  });

  const { mutate: deleteAccountMutate } = useDeleteAccount();

  const reorderMutation = useMutation({
    mutationFn: (items) => api.put('/accounts/reorder', items),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts() });
      toast.success('Order saved');
    },
    onError: () => {
      toast.error('Failed to save order');
    }
  });

  // Default create form currency to base currency when it loads
  useEffect(() => {
    if (baseCurrency && !createForm.currency) {
      setCreateForm(f => ({ ...f, currency: baseCurrency }));
    }
  }, [baseCurrency]); // eslint-disable-line react-hooks/exhaustive-deps

  // Load edit form when editing account changes
  useEffect(() => {
    if (editingAccount) {
      setEditForm({
        name: editingAccount.name,
        current_balance: editingAccount.current_balance,
        country_code: editingAccount.country_code || '',
        include_in_family_overview: editingAccount.include_in_family_overview
      });
      setShowEditModal(true);
    }
  }, [editingAccount]);

  // Sync orderedAccounts when entering reorder mode or accounts data changes
  useEffect(() => {
    if (accounts) {
      setOrderedAccounts([...accounts]);
    }
  }, [accounts]);

  const handleCreateSubmit = (e) => {
    e.preventDefault();
    const formData = {
      ...createForm,
      opening_balance: parseFloat(createForm.opening_balance) || 0
    };

    // For members, always create personal accounts
    if (user?.role === 'MEMBER') {
      formData.owner_type = 'PERSONAL';
    }

    createAccountMutate(formData);
  };

  const [adjustBalancePending, setAdjustBalancePending] = useState(false);

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    if (!editingAccount) return;

    const newBalance = parseFloat(editForm.current_balance) || 0;
    const oldBalance = parseFloat(editingAccount.current_balance) || 0;
    const balanceChanged = Math.abs(newBalance - oldBalance) > 0.001;

    // Update account name/settings
    updateAccountMutate({
      id: editingAccount.id,
      data: {
        name: editForm.name,
        country_code: editForm.country_code || null,
        include_in_family_overview: editForm.include_in_family_overview
      }
    });

    // Adjust balance if changed
    if (balanceChanged) {
      setAdjustBalancePending(true);
      try {
        await api.post(`/accounts/${editingAccount.id}/adjust-balance`, {
          new_balance: newBalance
        });
        queryClient.invalidateQueries({ queryKey: queryKeys.accounts() });
        queryClient.invalidateQueries({ queryKey: queryKeys.dashboardAll() });
      } catch (err) {
        toast.error(err.response?.data?.detail || 'Failed to adjust balance');
      } finally {
        setAdjustBalancePending(false);
      }
    }
  };

  const canEditAccount = (account) => {
    if (user?.role === 'ADMIN') return true;
    if (account.owner_type === 'PERSONAL' && account.owner_user_id === user?.id) return true;
    return false;
  };

  const canDeleteAccount = (account) => {
    if (user?.role === 'ADMIN') return true;
    if (account.owner_type === 'PERSONAL' && account.owner_user_id === user?.id) return true;
    return false;
  };

  // Drag-and-drop handlers (within same type group)
  const handleDragStart = (e, id) => {
    draggedId.current = id;
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  };

  const handleDrop = (e, targetId, groupType) => {
    e.preventDefault();
    if (!draggedId.current || draggedId.current === targetId) return;

    const newOrdered = [...orderedAccounts];
    const dragIdx = newOrdered.findIndex(a => a.id === draggedId.current);
    const targetIdx = newOrdered.findIndex(a => a.id === targetId);

    // Only allow drops within same type group
    if (newOrdered[dragIdx]?.type !== groupType || newOrdered[targetIdx]?.type !== groupType) return;

    const [dragged] = newOrdered.splice(dragIdx, 1);
    newOrdered.splice(targetIdx, 0, dragged);
    setOrderedAccounts(newOrdered);

    // Re-assign sort_order within this group and save
    const groupAccounts = newOrdered.filter(a => a.type === groupType);
    const reorderItems = groupAccounts.map((a, i) => ({ id: a.id, sort_order: i }));
    reorderMutation.mutate(reorderItems);

    draggedId.current = null;
  };

  const handleDragEnd = () => {
    draggedId.current = null;
  };

  if (isLoading) {
    return <LoadingSpinner />;
  }

  const renderAccountCard = (account) => (
    <div
      key={account.id}
      onClick={() => navigate(`/accounts/${account.id}`)}
      className="card-hover bg-white dark:bg-slate-800 rounded-lg shadow p-4 sm:p-6 border border-gray-100 dark:border-slate-700 cursor-pointer"
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className={`p-2 sm:p-3 rounded-lg ${getAccountColor(account.type)}`}>
            {getAccountIcon(account.type)}
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">
              {formatAccountDisplayName(account)}
            </h3>
            <p className="text-sm text-gray-500">
              {account.owner_type === 'SHARED' ? '👥 Shared' : '👤 Personal'} • {account.currency}
              {account.country_code && ` • ${getCountryDisplay(account.country_code)}`}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          {canEditAccount(account) && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                setEditingAccount(account);
              }}
              className="text-gray-400 hover:text-blue-600 p-1"
              title="Edit account"
            >
              <Edit className="w-4 h-4" />
            </button>
          )}
          {canDeleteAccount(account) && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                if (confirm('Are you sure you want to delete this account?')) {
                  deleteAccountMutate(account.id);
                }
              }}
              className="text-gray-400 hover:text-red-600 p-1"
              title="Delete account"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
      <div className="mt-4">
        <p className={`text-xl sm:text-2xl font-bold ${
          account.account_class === 'LIABILITY' && parseFloat(account.current_balance) > 0
            ? 'text-red-600'
            : 'text-gray-900'
        }`}>
          {formatCurrency(account.current_balance, account.currency)}
        </p>
        <p className="text-xs text-gray-500">
          {account.account_class === 'LIABILITY'
            ? (parseFloat(account.current_balance) > 0 ? 'Amount owed' : 'No balance owed')
            : `Opening: ${formatCurrency(account.opening_balance, account.currency)}`}
        </p>
      </div>
      {account.include_in_family_overview && (
        <span className="inline-block mt-2 text-xs bg-green-100 text-green-700 px-2 py-1 rounded">
          In Overview
        </span>
      )}
    </div>
  );

  const renderReorderRow = (account) => (
    <div
      key={account.id}
      draggable
      onDragStart={(e) => handleDragStart(e, account.id)}
      onDragOver={handleDragOver}
      onDrop={(e) => handleDrop(e, account.id, account.type)}
      onDragEnd={handleDragEnd}
      className="flex items-center gap-3 bg-white dark:bg-slate-800 rounded-lg border border-gray-200 dark:border-slate-700 px-4 py-3 cursor-grab active:cursor-grabbing select-none"
      style={{ opacity: draggedId.current === account.id ? 0.4 : 1 }}
    >
      <GripVertical className="w-5 h-5 text-gray-400 flex-shrink-0" />
      <div className={`p-2 rounded-lg ${getAccountColor(account.type)}`}>
        {getAccountIcon(account.type)}
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-medium text-gray-900 truncate">{formatAccountDisplayName(account)}</p>
        <p className="text-xs text-gray-500">{account.owner_type === 'SHARED' ? '👥 Shared' : '👤 Personal'} • {account.currency}</p>
      </div>
      <p className="text-sm font-semibold text-gray-700 flex-shrink-0">
        {formatCurrency(account.current_balance, account.currency)}
      </p>
    </div>
  );

  return (
    <div className="max-w-7xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3 mb-6">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-gray-900">Accounts</h1>
          <p className="text-gray-600 mt-1">Manage your family accounts and wallets</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          {user?.role === 'ADMIN' && (
            <button
              onClick={() => setIsReordering(!isReordering)}
              className={`px-4 py-2.5 rounded-lg flex items-center gap-2 border ${
                isReordering
                  ? 'bg-green-600 text-white border-green-600 hover:bg-green-700'
                  : 'bg-white dark:bg-slate-800 text-gray-700 dark:text-slate-200 border-gray-300 dark:border-slate-600 hover:bg-gray-50'
              }`}
            >
              <ArrowLeftRight className="w-4 h-4" />
              {isReordering ? 'Done Reordering' : 'Reorder'}
            </button>
          )}
          {(user?.role === 'ADMIN' || user?.role === 'MEMBER') && !isReordering && (
            <button
              onClick={() => setShowCreateModal(true)}
              className="bg-blue-600 text-white px-4 py-2.5 rounded-lg flex items-center gap-2 hover:bg-blue-700"
            >
              <Plus className="w-5 h-5" />
              {user?.role === 'ADMIN' ? 'Add Account' : 'Add Personal Account'}
            </button>
          )}
        </div>
      </div>

      {isReordering && (
        <div className="mb-4 p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
          <p className="text-sm text-blue-700 dark:text-blue-300">
            Drag accounts within each group to reorder. Changes save automatically.
          </p>
        </div>
      )}

      {/* Account Sections */}
      {ACCOUNT_GROUPS.map(({ type, label }) => {
        const groupAccounts = orderedAccounts.filter(a => a.type === type);
        if (groupAccounts.length === 0) return null;
        return (
          <div key={type} className="mb-8">
            <h2 className="text-lg font-semibold text-gray-700 mb-4">{label}</h2>
            {isReordering ? (
              <div className="space-y-2">
                {groupAccounts.map(renderReorderRow)}
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {groupAccounts.map(renderAccountCard)}
              </div>
            )}
          </div>
        );
      })}

      {accounts?.length === 0 && (
        <div className="text-center py-12 bg-white dark:bg-slate-800 rounded-lg shadow border border-gray-100 dark:border-slate-700">
          <h3 className="text-lg font-medium text-gray-900 dark:text-slate-100 mb-2">No accounts yet</h3>
          <p className="text-gray-500 dark:text-slate-400 mb-4">Create your first account to start tracking</p>
        </div>
      )}

      {/* Create Account Modal */}
      {showCreateModal && (
        <div className="modal-backdrop fixed inset-0 flex items-start sm:items-center justify-center z-50 p-3 sm:p-4 overflow-y-auto">
          <div className="glass-panel bg-white dark:bg-slate-800 rounded-lg shadow-xl w-full max-w-md mx-3 sm:mx-4 p-4 sm:p-6 max-h-[92vh] overflow-y-auto slide-in">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold">Create New Account</h2>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            <form onSubmit={handleCreateSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Account Name *</label>
                <input
                  type="text"
                  required
                  value={createForm.name}
                  onChange={(e) => setCreateForm({...createForm, name: e.target.value})}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g., Main Checking"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Type *</label>
                <select
                  value={createForm.type}
                  onChange={(e) => setCreateForm({...createForm, type: e.target.value})}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                >
                  <option value="BANK">Bank Account</option>
                  <option value="CASH">Cash</option>
                  <option value="CREDIT_CARD">Credit Card</option>
                  <option value="INVESTMENT">Investment</option>
                </select>
              </div>

              {user?.role === 'ADMIN' && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Ownership *</label>
                  <select
                    value={createForm.owner_type}
                    onChange={(e) => setCreateForm({...createForm, owner_type: e.target.value})}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="SHARED">Shared (Family)</option>
                    <option value="PERSONAL">Personal</option>
                  </select>
                </div>
              )}

              {user?.role !== 'ADMIN' && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                  <p className="text-sm text-blue-800">
                    <strong>Account Type:</strong> Personal (visible only to you and admins)
                  </p>
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Currency *</label>
                {currenciesLoading ? (
                  <select disabled className="w-full px-3 py-2 border rounded-lg bg-gray-50 text-gray-400">
                    <option>Loading currencies…</option>
                  </select>
                ) : availableCurrencies.length === 0 ? (
                  <p className="text-sm text-amber-600 bg-amber-50 p-2 rounded">
                    No currencies configured. Admin must set up currencies in Settings first.
                  </p>
                ) : (
                  <select
                    value={createForm.currency}
                    onChange={(e) => setCreateForm({...createForm, currency: e.target.value})}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                    required
                  >
                    <option value="">— Select currency —</option>
                    {availableCurrencies.map(c => (
                      <option key={c.code} value={c.code}>{c.label}</option>
                    ))}
                  </select>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Opening Balance</label>
                <input
                  type="number"
                  step="0.01"
                  value={createForm.opening_balance}
                  onChange={(e) => setCreateForm({...createForm, opening_balance: e.target.value})}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  placeholder="0.00"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Country <span className="text-gray-400 font-normal">(optional)</span>
                </label>
                <select
                  value={createForm.country_code}
                  onChange={(e) => setCreateForm({...createForm, country_code: e.target.value})}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">— Not specified —</option>
                  {COUNTRIES.map(c => (
                    <option key={c.code} value={c.code}>{c.flag} {c.name}</option>
                  ))}
                </select>
              </div>

              <div className="flex items-center">
                <input
                  type="checkbox"
                  checked={createForm.include_in_family_overview}
                  onChange={(e) => setCreateForm({...createForm, include_in_family_overview: e.target.checked})}
                  className="mr-2"
                />
                <label className="text-sm text-gray-700">Include in family overview</label>
              </div>

              <div className="flex gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="flex-1 px-4 py-2.5 border rounded-lg hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createPending}
                  className="flex-1 px-4 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  {createPending ? 'Creating...' : 'Create Account'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Account Modal */}
      {showEditModal && editingAccount && (
        <div className="modal-backdrop fixed inset-0 flex items-start sm:items-center justify-center z-50 p-3 sm:p-4 overflow-y-auto">
          <div className="glass-panel bg-white dark:bg-slate-800 rounded-lg shadow-xl w-full max-w-md mx-3 sm:mx-4 p-4 sm:p-6 max-h-[92vh] overflow-y-auto slide-in">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold">Edit Account</h2>
              <button
                onClick={() => {
                  setShowEditModal(false);
                  setEditingAccount(null);
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            <form onSubmit={handleEditSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Account Name *</label>
                <input
                  type="text"
                  required
                  value={editForm.name}
                  onChange={(e) => setEditForm({...editForm, name: e.target.value})}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Type</label>
                  <input
                    type="text"
                    value={editingAccount.type}
                    disabled
                    className="w-full px-3 py-2 border rounded-lg bg-gray-100"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Currency</label>
                  <input
                    type="text"
                    value={editingAccount.currency}
                    disabled
                    className="w-full px-3 py-2 border rounded-lg bg-gray-100"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Opening Balance</label>
                <input
                  type="text"
                  value={formatCurrency(editingAccount.opening_balance, editingAccount.currency)}
                  disabled
                  className="w-full px-3 py-2 border rounded-lg bg-gray-100 text-gray-500"
                />
                <p className="text-xs text-gray-400 mt-1">Set at account creation, cannot be changed</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Current Balance</label>
                <input
                  type="number"
                  step="0.01"
                  value={editForm.current_balance}
                  onChange={(e) => setEditForm({...editForm, current_balance: e.target.value})}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Changing this will create an Income or Expense adjustment transaction
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Country <span className="text-gray-400 font-normal">(optional)</span>
                </label>
                <select
                  value={editForm.country_code}
                  onChange={(e) => setEditForm({...editForm, country_code: e.target.value})}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">— Not specified —</option>
                  {COUNTRIES.map(c => (
                    <option key={c.code} value={c.code}>{c.flag} {c.name}</option>
                  ))}
                </select>
              </div>

              <div className="flex items-center">
                <input
                  type="checkbox"
                  checked={editForm.include_in_family_overview}
                  onChange={(e) => setEditForm({...editForm, include_in_family_overview: e.target.checked})}
                  className="mr-2"
                />
                <label className="text-sm text-gray-700">Include in family overview</label>
              </div>

              {user?.role !== 'ADMIN' && editingAccount.owner_type === 'SHARED' && (
                <p className="text-sm text-amber-600 bg-amber-50 p-3 rounded">
                  Only admins can edit shared accounts.
                </p>
              )}

              <div className="flex gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => {
                    setShowEditModal(false);
                    setEditingAccount(null);
                  }}
                  className="flex-1 px-4 py-2.5 border rounded-lg hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={updatePending || adjustBalancePending}
                  className="flex-1 px-4 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  {(updatePending || adjustBalancePending) ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Accounts;
