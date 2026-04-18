import React, { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import { useAuthStore } from '../store/authStore';
import { 
  ArrowLeft, 
  Plus, 
  ArrowRightLeft, 
  TrendingUp, 
  TrendingDown,
  X
} from 'lucide-react';
import { formatAccountDisplayName, formatCurrency, formatDate } from '../utils/formatters';
import { getCountryDisplay } from '../utils/typeHelpers';
import { toNaiveDateTimeString, toNaiveLocalDateTimeString } from '../utils/dateUtils';
import { queryKeys } from '../utils/queryKeys';
import LoadingSpinner from '../components/LoadingSpinner';
import toast from 'react-hot-toast';

const BalanceHistoryChart = React.lazy(() => import('../components/Accounts/BalanceHistoryChart'));

const AccountDetail = () => {
  const { accountId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const queryClient = useQueryClient();
  const [showTransferModal, setShowTransferModal] = useState(false);
  const [showTransactionModal, setShowTransactionModal] = useState(false);
  const [dateFilter, setDateFilter] = useState('all'); // all, month, quarter, year
  const [typeFilter, setTypeFilter] = useState('all'); // all, INCOME, EXPENSE, TRANSFER
  const [transactionForm, setTransactionForm] = useState({
    type: 'EXPENSE',
    amount: '',
    description: '',
    category_id: '',
    transaction_date: new Date(),
    tx_currency: '',
    exchange_rate_to_base: '',
  });

  // Fetch account details
  const { data: account, isLoading: accountLoading } = useQuery({
    queryKey: queryKeys.account(accountId),
    queryFn: () => api.get(`/accounts/${accountId}`).then(res => res.data)
  });

  // Fetch account transactions
  const { data: transactions, isLoading: transactionsLoading } = useQuery({
    queryKey: queryKeys.transactionsByAccount(accountId, dateFilter, typeFilter),
    queryFn: () => {
      const params = {};
      // Send dates without timezone suffix to match timezone-naive DB column
      if (dateFilter === 'month') {
        params.start_date = toNaiveLocalDateTimeString(new Date(Date.now() - 30 * 24 * 60 * 60 * 1000));
      } else if (dateFilter === 'quarter') {
        params.start_date = toNaiveLocalDateTimeString(new Date(Date.now() - 90 * 24 * 60 * 60 * 1000));
      } else if (dateFilter === 'year') {
        params.start_date = toNaiveLocalDateTimeString(new Date(Date.now() - 365 * 24 * 60 * 60 * 1000));
      }
      if (typeFilter !== 'all') {
        params.type = typeFilter;
      }
      return api.get(`/transactions/account/${accountId}`, { params }).then(res => res.data);
    }
  });

  // Fetch categories for transaction form
  const { data: categories } = useQuery({
    queryKey: queryKeys.categories(),
    queryFn: () => api.get('/categories/').then(res => res.data),
    enabled: showTransactionModal
  });

  // Fetch all accounts for transfer
  const { data: allAccounts } = useQuery({
    queryKey: queryKeys.accounts(),
    queryFn: () => api.get('/accounts/').then(res => res.data),
    enabled: showTransferModal
  });

  const { data: txFamilyProfile } = useQuery({
    queryKey: ['settings', 'family-profile'],
    queryFn: () => api.get('/settings/family-profile').then(r => r.data),
    staleTime: 1000 * 60 * 5,
    enabled: showTransactionModal,
  });

  const { data: txSecondaryCurrencies = [] } = useQuery({
    queryKey: ['settings', 'currencies'],
    queryFn: () => api.get('/settings/currencies').then(r => r.data),
    staleTime: 1000 * 60 * 5,
    enabled: showTransactionModal,
  });

  const { data: txStoredRates = [] } = useQuery({
    queryKey: ['settings', 'exchange-rates'],
    queryFn: () => api.get('/settings/exchange-rates').then(r => r.data),
    staleTime: 1000 * 60 * 5,
    enabled: showTransactionModal,
  });

  // Create transaction mutation
  const createTransactionMutation = useMutation({
    mutationFn: (data) => api.post('/transactions/', data),
    onSuccess: () => {
      toast.success('Transaction created');
      queryClient.invalidateQueries({ queryKey: queryKeys.transactionsByAccountAll(accountId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.account(accountId) });
      setShowTransactionModal(false);
      setTransactionForm({
        type: 'EXPENSE',
        amount: '',
        description: '',
        category_id: '',
        transaction_date: new Date(),
        tx_currency: '',
        exchange_rate_to_base: '',
      });
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to create transaction');
    }
  });

  // Calculate transactions with running balance
  const transactionsWithBalance = React.useMemo(() => {
    if (!transactions || !account) return [];

    const isLiability = account.account_class === 'LIABILITY';
    let runningBalance = parseFloat(account.opening_balance);
    const sorted = [...transactions].sort((a, b) =>
      new Date(a.transaction_date) - new Date(b.transaction_date)
    );

    return sorted.map(t => {
      const amount = parseFloat(t.amount);
      if (isLiability) {
        // Liability accounts: expenses increase debt, income/payments decrease debt.
        // For transfers, is_source_transaction=true means this account initiated the
        // transfer out (cash advance → more debt); false means it received a payment.
        if (t.type === 'INCOME') {
          runningBalance -= amount;
        } else if (t.type === 'EXPENSE') {
          runningBalance += amount;
        } else if (t.type === 'TRANSFER') {
          if (t.is_source_transaction) {
            runningBalance += amount; // Cash advance: debt increases
          } else {
            runningBalance -= amount; // Payment received: debt decreases
          }
        }
      } else {
        if (t.type === 'INCOME') {
          runningBalance += amount;
        } else if (t.type === 'EXPENSE') {
          runningBalance -= amount;
        } else if (t.type === 'TRANSFER') {
          if (t.is_source_transaction) {
            runningBalance -= amount; // Outgoing transfer
          } else {
            runningBalance += amount; // Incoming transfer
          }
        }
      }

      return {
        ...t,
        runningBalance: runningBalance
      };
    });
  }, [transactions, account, accountId]);

  // Calculate balance history
  const balanceHistory = React.useMemo(() => {
    return transactionsWithBalance.map(t => ({
      date: formatDate(t.transaction_date),
      balance: t.runningBalance,
      amount: parseFloat(t.amount),
      type: t.type
    }));
  }, [transactionsWithBalance]);

  // Calculate stats
  const stats = React.useMemo(() => {
    if (!transactions) return { income: 0, expense: 0, transfers: 0 };
    
    return transactions.reduce((acc, t) => {
      const amount = parseFloat(t.amount);
      if (t.type === 'INCOME') acc.income += amount;
      else if (t.type === 'EXPENSE') acc.expense += amount;
      else if (t.type === 'TRANSFER') acc.transfers += amount;
      return acc;
    }, { income: 0, expense: 0, transfers: 0 });
  }, [transactions]);

  const txResolvedBase = txFamilyProfile?.base_currency;
  const lookupTxStoredRate = (currency) => {
    if (!currency || !txResolvedBase) return null;
    if (currency === txResolvedBase) return { rate: '1.000000', date: null };
    const row = txStoredRates.find(r => r.from_currency === currency && r.to_currency === txResolvedBase);
    if (row) return { rate: parseFloat(row.rate).toFixed(6), date: row.valid_date };
    const approx = getDefaultConversionRate(currency, txResolvedBase);
    return approx !== 1.0 ? { rate: String(approx), date: null } : null;
  };
  const txCurrencyOptions = txResolvedBase
    ? [
        { code: txResolvedBase, label: `${txResolvedBase} (Primary)` },
        ...txSecondaryCurrencies.map(c => ({ code: c.currency_code, label: c.currency_code })),
      ]
    : txSecondaryCurrencies.map(c => ({ code: c.currency_code, label: c.currency_code }));
  const effectiveTxCurrency = transactionForm.tx_currency || account?.currency;
  const showTxExchangeRateField = effectiveTxCurrency && account?.currency &&
    effectiveTxCurrency !== account?.currency;

  if (accountLoading) {
    return <LoadingSpinner />;
  }

  if (!account) {
    return (
      <div className="max-w-7xl mx-auto">
        <div className="text-center py-12">
          <h2 className="text-xl font-semibold text-gray-900">Account not found</h2>
          <Link to="/accounts" className="text-blue-600 hover:underline mt-4 inline-block">
            Back to Accounts
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-wrap items-start gap-3 mb-6">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <button
            onClick={() => navigate('/accounts')}
            className="p-2 hover:bg-gray-100 rounded-lg shrink-0"
          >
            <ArrowLeft className="w-6 h-6" />
          </button>
          <div className="min-w-0">
            <h1 className="text-xl sm:text-3xl font-bold text-gray-900 truncate">
              {formatAccountDisplayName(account)}
            </h1>
            <p className="text-sm text-gray-600 truncate">
              {account.type} • {account.currency} • {account.owner_type === 'SHARED' ? 'Shared' : 'Personal'}
              {account.country_code && ` • ${getCountryDisplay(account.country_code)}`}
            </p>
          </div>
        </div>
        <div className="flex gap-2 shrink-0">
          <button
            onClick={() => setShowTransferModal(true)}
            className="bg-green-600 text-white px-3 sm:px-4 py-2 sm:py-2.5 rounded-lg flex items-center gap-2 hover:bg-green-700 text-sm sm:text-base"
          >
            <ArrowRightLeft className="w-4 h-4 sm:w-5 sm:h-5" />
            <span className="hidden xs:inline">Transfer</span>
          </button>
          <button
            onClick={() => setShowTransactionModal(true)}
            className="bg-blue-600 text-white px-3 sm:px-4 py-2 sm:py-2.5 rounded-lg flex items-center gap-2 hover:bg-blue-700 text-sm sm:text-base"
          >
            <Plus className="w-4 h-4 sm:w-5 sm:h-5" />
            <span className="hidden xs:inline">Add</span>
            <span className="hidden sm:inline"> Transaction</span>
          </button>
        </div>
      </div>

      {/* Balance Card */}
      {(() => {
        const isLiability = account.account_class === 'LIABILITY';
        const hasDebt = isLiability && parseFloat(account.current_balance) > 0;
        const cardGradient = isLiability
          ? 'bg-gradient-to-r from-red-600 to-red-800'
          : 'bg-gradient-to-r from-blue-600 to-blue-800';
        return (
          <div className={`${cardGradient} rounded-xl shadow-lg p-6 text-white mb-6`}>
            <div className="flex justify-between items-start">
              <div>
                <p className="text-red-100 text-sm" style={{ color: 'rgba(255,255,255,0.8)' }}>
                  {isLiability ? 'Amount Owed' : 'Current Balance'}
                </p>
                <p className="text-2xl sm:text-4xl font-bold mt-1">
                  {formatCurrency(account.current_balance, account.currency)}
                </p>
                {isLiability && (
                  <p className="text-xs mt-1 opacity-75">
                    {hasDebt ? 'Liability — outstanding debt' : 'No balance owed'}
                  </p>
                )}
              </div>
              <div className="text-right">
                <p className="text-sm opacity-80">Opening Balance</p>
                <p className="text-xl mt-1">
                  {formatCurrency(account.opening_balance, account.currency)}
                </p>
              </div>
            </div>
          </div>
        );
      })()}

      {/* Stats Row */}
      {(() => {
        const isLiability = account.account_class === 'LIABILITY';
        return (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <div className="bg-white rounded-lg shadow p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-green-100 rounded-lg">
                  <TrendingUp className="w-5 h-5 text-green-600" />
                </div>
                <div>
                  <p className="text-sm text-gray-600">{isLiability ? 'Payments' : 'Income'}</p>
                  <p className="text-xl font-bold text-green-600">
                    +{formatCurrency(stats.income, account.currency)}
                  </p>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-red-100 rounded-lg">
                  <TrendingDown className="w-5 h-5 text-red-600" />
                </div>
                <div>
                  <p className="text-sm text-gray-600">{isLiability ? 'Charges' : 'Expenses'}</p>
                  <p className="text-xl font-bold text-red-600">
                    -{formatCurrency(stats.expense, account.currency)}
                  </p>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-100 rounded-lg">
                  <ArrowRightLeft className="w-5 h-5 text-blue-600" />
                </div>
                <div>
                  <p className="text-sm text-gray-600">Transfers</p>
                  <p className="text-xl font-bold text-blue-600">
                    {formatCurrency(stats.transfers, account.currency)}
                  </p>
                </div>
              </div>
            </div>
          </div>
        );
      })()}

      {/* Balance History Chart */}
      {balanceHistory.length > 0 && (
        <React.Suspense fallback={<div className="bg-white rounded-lg shadow p-6 mb-6 h-[356px]" />}>
          <BalanceHistoryChart data={balanceHistory} currency={account.currency} />
        </React.Suspense>
      )}

      {/* Transactions List */}
      <div className="bg-white rounded-lg shadow">
        <div className="flex flex-col sm:flex-row sm:items-center gap-3 p-4 sm:p-6 border-b">
          <h2 className="text-lg font-semibold shrink-0">Recent Transactions</h2>
          <div className="flex flex-wrap items-center gap-2 sm:ml-auto">
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="px-2 sm:px-3 py-2 border rounded-lg text-sm flex-1 sm:flex-none"
            >
              <option value="all">All Types</option>
              <option value="INCOME">{account.account_class === 'LIABILITY' ? 'Payment' : 'Income'}</option>
              <option value="EXPENSE">{account.account_class === 'LIABILITY' ? 'Charge' : 'Expense'}</option>
              <option value="TRANSFER">Transfer</option>
            </select>
            <select
              value={dateFilter}
              onChange={(e) => setDateFilter(e.target.value)}
              className="px-2 sm:px-3 py-2 border rounded-lg text-sm flex-1 sm:flex-none"
            >
              <option value="all">All Time</option>
              <option value="month">Last 30 Days</option>
              <option value="quarter">Last 90 Days</option>
              <option value="year">Last Year</option>
            </select>
          </div>
        </div>

        {transactionsLoading ? (
          <div className="p-6 text-center">Loading...</div>
        ) : transactions?.length === 0 ? (
          <div className="p-6 text-center text-gray-500">
            No transactions yet. Add your first transaction!
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-3 sm:px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                  <th className="px-3 sm:px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Description</th>
                  <th className="hidden sm:table-cell px-3 sm:px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Category</th>
                  <th className="px-3 sm:px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Amount</th>
                  <th className="hidden sm:table-cell px-3 sm:px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Balance</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {[...transactionsWithBalance].reverse().map((transaction) => (
                  <tr key={transaction.id} className="hover:bg-gray-50">
                    <td className="px-3 sm:px-6 py-3 sm:py-4 whitespace-nowrap text-xs sm:text-sm text-gray-900">
                      {formatDate(transaction.transaction_date)}
                    </td>
                    <td className="px-3 sm:px-6 py-3 sm:py-4 text-xs sm:text-sm text-gray-900 max-w-[140px] sm:max-w-none">
                      <div className="flex items-center gap-1 sm:gap-2">
                        {transaction.type === 'INCOME' && <TrendingUp className="w-3 h-3 sm:w-4 sm:h-4 text-green-600 shrink-0" />}
                        {transaction.type === 'EXPENSE' && <TrendingDown className="w-3 h-3 sm:w-4 sm:h-4 text-red-600 shrink-0" />}
                        {transaction.type === 'TRANSFER' && <ArrowRightLeft className="w-3 h-3 sm:w-4 sm:h-4 text-blue-600 shrink-0" />}
                        <span className="truncate">{transaction.description || 'No description'}</span>
                      </div>
                    </td>
                    <td className="hidden sm:table-cell px-3 sm:px-6 py-3 sm:py-4 text-sm">
                      {transaction.category ? (
                        <span
                          className="px-2 py-1 rounded text-white text-xs"
                          style={{ backgroundColor: transaction.category.color }}
                        >
                          {transaction.category.name}
                        </span>
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </td>
                    <td className={`px-3 sm:px-6 py-3 sm:py-4 text-xs sm:text-sm text-right font-medium whitespace-nowrap ${
                      transaction.type === 'INCOME' ? 'text-green-600' :
                      transaction.type === 'EXPENSE' ? 'text-red-600' : 'text-blue-600'
                    }`}>
                      {transaction.type === 'INCOME' ? '+' :
                       transaction.type === 'EXPENSE' ? '-' : ''}
                      {formatCurrency(transaction.amount, transaction.currency)}
                    </td>
                    <td className="hidden sm:table-cell px-3 sm:px-6 py-3 sm:py-4 text-sm text-right text-gray-900 whitespace-nowrap">
                      {formatCurrency(transaction.runningBalance, account.currency)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Transaction Modal */}
      {showTransactionModal && (
        <div className="modal-backdrop fixed inset-0 flex items-start sm:items-center justify-center z-50 p-3 sm:p-4 overflow-y-auto">
          <div className="glass-panel bg-white dark:bg-slate-800 rounded-lg shadow-xl w-full max-w-md mx-3 sm:mx-4 max-h-[92vh] overflow-y-auto slide-in">
            <div className="flex items-center justify-between p-4 sm:p-6 border-b">
              <h2 className="text-xl font-semibold">Add Transaction</h2>
              <button 
                onClick={() => setShowTransactionModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            <form onSubmit={(e) => {
              e.preventDefault();
              if (!transactionForm.amount) {
                toast.error('Please enter an amount');
                return;
              }
              if (transactionForm.type !== 'TRANSFER' && !transactionForm.category_id) {
                toast.error('Please select a category');
                return;
              }
              const payload = {
                type: transactionForm.type,
                amount: parseFloat(transactionForm.amount),
                currency: transactionForm.tx_currency || account.currency,
                description: transactionForm.description || '',
                transaction_date: toNaiveDateTimeString(transactionForm.transaction_date),
                account_id: accountId
              };
              if (transactionForm.exchange_rate_to_base && parseFloat(transactionForm.exchange_rate_to_base) > 0) {
                payload.exchange_rate_to_base = parseFloat(transactionForm.exchange_rate_to_base);
              }
              if (transactionForm.type !== 'TRANSFER' && transactionForm.category_id) {
                payload.category_id = transactionForm.category_id;
              }
              createTransactionMutation.mutate(payload);
            }} className="p-4 sm:p-6 space-y-4">
              {/* Type Selection */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Type *</label>
                <div className="flex gap-4">
                  <label className="flex items-center">
                    <input
                      type="radio"
                      value="EXPENSE"
                      checked={transactionForm.type === 'EXPENSE'}
                      onChange={(e) => setTransactionForm({...transactionForm, type: e.target.value, category_id: ''})}
                      className="mr-2"
                    />
                    <span className="text-red-600">
                      {account.account_class === 'LIABILITY' ? 'Charge / Spend' : 'Expense'}
                    </span>
                  </label>
                  <label className="flex items-center">
                    <input
                      type="radio"
                      value="INCOME"
                      checked={transactionForm.type === 'INCOME'}
                      onChange={(e) => setTransactionForm({...transactionForm, type: e.target.value, category_id: ''})}
                      className="mr-2"
                    />
                    <span className="text-green-600">
                      {account.account_class === 'LIABILITY' ? 'Payment / Refund' : 'Income'}
                    </span>
                  </label>
                </div>
              </div>

              {/* Category */}
              {transactionForm.type !== 'TRANSFER' && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Category *</label>
                  <select
                    value={transactionForm.category_id}
                    onChange={(e) => setTransactionForm({...transactionForm, category_id: e.target.value})}
                    required
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">Select a category...</option>
                    {categories?.filter(c => c.type === transactionForm.type).map(cat => (
                      <option key={cat.id} value={cat.id}>{cat.name}</option>
                    ))}
                  </select>
                </div>
              )}

              {/* Currency override — shown when family has secondary currencies */}
              {txCurrencyOptions.length > 1 && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Transaction Currency
                    <span className="ml-1 text-xs font-normal text-gray-400">(optional override)</span>
                  </label>
                  <select
                    value={transactionForm.tx_currency}
                    onChange={(e) => {
                      const selected = e.target.value;
                      const looked = lookupTxStoredRate(selected);
                      setTransactionForm({...transactionForm, tx_currency: selected, exchange_rate_to_base: looked ? looked.rate : ''});
                    }}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">Account currency ({account?.currency || '—'})</option>
                    {txCurrencyOptions
                      .filter(c => c.code !== account?.currency)
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
                        value={transactionForm.exchange_rate_to_base}
                        onChange={(e) => setTransactionForm({...transactionForm, exchange_rate_to_base: e.target.value})}
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
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">
                    {effectiveTxCurrency || account.currency}
                  </span>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={transactionForm.amount}
                    onChange={(e) => setTransactionForm({...transactionForm, amount: e.target.value})}
                    className="w-full pl-12 pr-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                    placeholder="0.00"
                  />
                </div>
              </div>

              {/* Description */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <input
                  type="text"
                  value={transactionForm.description}
                  onChange={(e) => setTransactionForm({...transactionForm, description: e.target.value})}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  placeholder="What's this for?"
                />
              </div>

              {/* Actions */}
              <div className="flex gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => setShowTransactionModal(false)}
                  className="flex-1 px-4 py-2.5 border rounded-lg hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createTransactionMutation.isPending || !transactionForm.amount}
                  className="flex-1 px-4 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  {createTransactionMutation.isPending ? 'Adding...' : 'Add'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Transfer Modal */}
      {showTransferModal && (
        <TransferModal
          fromAccount={account}
          accounts={allAccounts?.filter(a => a.id !== accountId) || []}
          onClose={() => setShowTransferModal(false)}
          onSuccess={() => {
            queryClient.invalidateQueries(['transactions', accountId]);
            queryClient.invalidateQueries(['account', accountId]);
          }}
        />
      )}
    </div>
  );
};

// Default exchange rates (mirrors backend DEFAULT_RATES, used for initial display only)
const DEFAULT_RATES = {
  USD: 1.0, EUR: 1.1, GBP: 1.28, INR: 0.012,
  CAD: 0.74, AUD: 0.67, JPY: 0.0067, AED: 0.272, THB: 0.028
};

function getDefaultConversionRate(fromCurrency, toCurrency) {
  if (fromCurrency === toCurrency) return 1.0;
  const fromRate = DEFAULT_RATES[fromCurrency] ?? 1.0;
  const toRate = DEFAULT_RATES[toCurrency] ?? 1.0;
  if (toRate === 0) return 1.0;
  return parseFloat((fromRate / toRate).toFixed(6));
}

// Transfer Modal Component
const TransferModal = ({ fromAccount, accounts, onClose, onSuccess }) => {
  const [toAccountId, setToAccountId] = useState('');
  const [amount, setAmount] = useState('');
  const [description, setDescription] = useState('');
  const [conversionRate, setConversionRate] = useState('1.00');
  const [loading, setLoading] = useState(false);

  const toAccount = accounts.find(a => a.id === toAccountId);
  const isCrossCurrency = toAccount && toAccount.currency !== fromAccount.currency;

  const handleToAccountChange = (e) => {
    const id = e.target.value;
    setToAccountId(id);
    const dest = accounts.find(a => a.id === id);
    if (dest && dest.currency !== fromAccount.currency) {
      setConversionRate(String(getDefaultConversionRate(fromAccount.currency, dest.currency)));
    } else {
      setConversionRate('1.00');
    }
  };

  const receivedAmount = isCrossCurrency && amount && conversionRate
    ? (parseFloat(amount) * parseFloat(conversionRate)).toFixed(2)
    : amount;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!toAccountId || !amount) return;

    const payload = {
      type: 'TRANSFER',
      amount: parseFloat(amount),
      currency: fromAccount.currency,
      account_id: fromAccount.id,
      target_account_id: toAccountId,
      description: description || `Transfer from ${formatAccountDisplayName(fromAccount)}`,
      transaction_date: toNaiveDateTimeString(new Date())
    };

    if (isCrossCurrency && conversionRate) {
      payload.transfer_conversion_rate = parseFloat(conversionRate);
    }

    setLoading(true);
    try {
      await api.post('/transactions/', payload);
      toast.success('Transfer completed successfully');
      onSuccess();
      onClose();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Transfer failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-backdrop fixed inset-0 flex items-start sm:items-center justify-center z-50 p-3 sm:p-4 overflow-y-auto">
      <div className="glass-panel bg-white dark:bg-slate-800 rounded-lg shadow-xl w-full max-w-md mx-3 sm:mx-4 max-h-[92vh] overflow-y-auto slide-in">
        <div className="flex items-center justify-between p-4 sm:p-6 border-b">
          <h2 className="text-xl font-semibold">Transfer Money</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-6 h-6" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-4 sm:p-6 space-y-4">
          {/* From Account */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">From</label>
            <div className="p-3 bg-gray-100 rounded-lg">
              <p className="font-medium">{formatAccountDisplayName(fromAccount)}</p>
              <p className="text-sm text-gray-600">
                Balance: {formatCurrency(fromAccount.current_balance, fromAccount.currency)}
              </p>
            </div>
          </div>

          {/* To Account */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              To Account *
            </label>
            <select
              value={toAccountId}
              onChange={handleToAccountChange}
              required
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select destination account...</option>
              {accounts.map(acc => (
                <option key={acc.id} value={acc.id}>
                  {formatAccountDisplayName(acc)} ({acc.currency}) - {formatCurrency(acc.current_balance, acc.currency)}
                </option>
              ))}
            </select>
          </div>

          {/* Amount */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Amount *
            </label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">
                {fromAccount.currency}
              </span>
              <input
                type="number"
                step="0.01"
                required
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="w-full pl-12 pr-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                placeholder="0.00"
              />
            </div>
          </div>

          {/* Conversion Rate — only shown for cross-currency transfers */}
          {isCrossCurrency && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Conversion Rate
                <span className="ml-1 text-xs font-normal text-gray-500">
                  (1 {fromAccount.currency} = ? {toAccount.currency})
                </span>
              </label>
              <input
                type="number"
                step="0.000001"
                min="0.000001"
                required
                value={conversionRate}
                onChange={(e) => setConversionRate(e.target.value)}
                className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
              />
              {amount && (
                <p className="text-sm text-gray-600 mt-1">
                  Recipient gets: <span className="font-medium">{formatCurrency(receivedAmount, toAccount.currency)}</span>
                </p>
              )}
            </div>
          )}

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Description
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
              placeholder="What's this transfer for?"
            />
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2.5 border rounded-lg hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || !toAccountId || !amount}
              className="flex-1 px-4 py-2.5 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
            >
              {loading ? 'Processing...' : 'Transfer'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AccountDetail;
