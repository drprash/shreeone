import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useQuery } from '@tanstack/react-query';
import { Plus, ArrowRightLeft } from 'lucide-react';
import { formatDateForInput, parseDateForPicker, toNaiveDateTimeString } from '../../utils/dateUtils';
import { formatAccountDisplayName, formatCurrency } from '../../utils/formatters';
import toast from 'react-hot-toast';
import { useCreateTransaction } from '../../hooks/useCreateTransaction';
import api from '../../services/api';

const QA_DEFAULT_RATES = { USD:1.0, EUR:1.1, GBP:1.28, INR:0.012, CAD:0.74, AUD:0.67, JPY:0.0067, AED:0.272, THB:0.028 };
function getQAConversionRate(from, to) {
  if (from === to) return 1.0;
  const f = QA_DEFAULT_RATES[from] ?? 1.0, t = QA_DEFAULT_RATES[to] ?? 1.0;
  return t === 0 ? 1.0 : parseFloat((f / t).toFixed(6));
}

const QuickAdd = ({ accounts, categories, baseCurrency }) => {
  const [isTransfer, setIsTransfer] = useState(false);

  const { data: familyProfile } = useQuery({
    queryKey: ['settings', 'family-profile'],
    queryFn: () => api.get('/settings/family-profile').then(r => r.data),
    staleTime: 1000 * 60 * 5,
  });
  const { data: secondaryCurrencies = [] } = useQuery({
    queryKey: ['settings', 'currencies'],
    queryFn: () => api.get('/settings/currencies').then(r => r.data),
    staleTime: 1000 * 60 * 5,
  });
  const { data: storedRates = [] } = useQuery({
    queryKey: ['settings', 'exchange-rates'],
    queryFn: () => api.get('/settings/exchange-rates').then(r => r.data),
    staleTime: 1000 * 60 * 5,
  });

  const resolvedBase = baseCurrency || familyProfile?.base_currency;

  // Look up stored ECB rate for a currency vs base; returns { rate, date } or null
  const lookupStoredRate = (txCurrency) => {
    if (!txCurrency || !resolvedBase) return null;
    if (txCurrency === resolvedBase) return { rate: '1.000000', date: null };
    const row = storedRates.find(
      r => r.from_currency === txCurrency && r.to_currency === resolvedBase
    );
    if (row) return { rate: parseFloat(row.rate).toFixed(6), date: row.valid_date };
    // Fallback to QA_DEFAULT_RATES approximation
    const approx = getQAConversionRate(txCurrency, resolvedBase);
    return approx !== 1.0 ? { rate: String(approx), date: null } : null;
  };
  // All currencies available for ad-hoc transactions: base + secondary
  const txCurrencyOptions = resolvedBase
    ? [
        { code: resolvedBase, label: `${resolvedBase} (Primary)` },
        ...secondaryCurrencies.map(c => ({ code: c.currency_code, label: c.currency_code })),
      ]
    : secondaryCurrencies.map(c => ({ code: c.currency_code, label: c.currency_code }));

  if (!categories || categories.length === 0) {
    return (
      <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6">
        <p className="text-amber-800 text-sm">
          ⚠️ <a href="/categories" className="underline font-medium">Create categories</a> first to add transactions
        </p>
      </div>
    );
  }

  const { register, handleSubmit, reset, watch, setValue } = useForm({
    defaultValues: {
      type: 'EXPENSE',
      amount: '',
      description: '',
      transaction_date: new Date(),
      account_id: '',
      category_id: '',
      target_account_id: '',
      transfer_conversion_rate: '1.00',
      tx_currency: '',        // '' means use account's own currency
      exchange_rate_to_base: '', // '' means auto-calculate
    }
  });

  const type = watch('type');
  const watchedAccountId = watch('account_id');
  const watchedTargetId = watch('target_account_id');
  const watchedRate = watch('transfer_conversion_rate');
  const watchedAmount = watch('amount');
  const watchedTxCurrency = watch('tx_currency');
  const selectedAccountCurrency = accounts?.find(a => a.id === watchedAccountId)?.currency;
  const qaTargetAccount = accounts?.find(a => a.id === watchedTargetId);
  // For income/expense: effective transaction currency
  const effectiveTxCurrency = watchedTxCurrency || selectedAccountCurrency;
  // Show exchange rate field when currency override differs from account currency
  const showExchangeRateField = !isTransfer && effectiveTxCurrency && selectedAccountCurrency &&
    effectiveTxCurrency !== selectedAccountCurrency;
  const qaIsCrossCurrency = isTransfer && selectedAccountCurrency && qaTargetAccount &&
    selectedAccountCurrency !== qaTargetAccount.currency;
  const qaReceivedAmount = qaIsCrossCurrency && watchedAmount && watchedRate
    ? (parseFloat(watchedAmount) * parseFloat(watchedRate)).toFixed(2)
    : null;

  const { mutate: createTransaction, isPending } = useCreateTransaction({ onSuccess: () => reset() });

  const onSubmit = (data) => {
    // Validate form data before submission
    if (isTransfer && !data.target_account_id) {
      toast.error('Please select a target account for transfer');
      return;
    }
    
    if (!data.account_id) {
      toast.error('Please select an account');
      return;
    }
    
    if (!data.amount || parseFloat(data.amount) < 0.01) {
      toast.error('Please enter a valid amount');
      return;
    }
    
    // Get the selected account to extract currency
    const selectedAccount = accounts?.find(acc => acc.id === data.account_id);
    if (!selectedAccount) {
      toast.error('Invalid account selected');
      return;
    }
    
    // For income/expense, currency can be overridden
    const txCurrency = isTransfer ? selectedAccount.currency : (data.tx_currency || selectedAccount.currency);

    const payload = {
      type: isTransfer ? 'TRANSFER' : data.type,
      amount: parseFloat(data.amount),
      currency: txCurrency,
      description: data.description || '',
      transaction_date: toNaiveDateTimeString(data.transaction_date),
      account_id: data.account_id
    };

    // If an explicit exchange rate is provided for a currency override, include it
    if (!isTransfer && data.exchange_rate_to_base && parseFloat(data.exchange_rate_to_base) > 0) {
      payload.exchange_rate_to_base = parseFloat(data.exchange_rate_to_base);
    }

    // Only add category_id if provided and not transferring
    if (!isTransfer && data.category_id) {
      payload.category_id = data.category_id;
    }

    // For transfers, include target_account_id and conversion rate
    if (isTransfer && data.target_account_id) {
      payload.target_account_id = data.target_account_id;
      if (qaIsCrossCurrency && data.transfer_conversion_rate) {
        payload.transfer_conversion_rate = parseFloat(data.transfer_conversion_rate);
      }
    }
    
    createTransaction(payload);
  };

  const filteredCategories = categories?.filter(c => 
    isTransfer ? true : c.type === type
  ) || [];

  return (
    <div className="card-hover bg-white dark:bg-slate-800 rounded-xl shadow-sm p-4 sm:p-6 border border-gray-100 dark:border-slate-700 mb-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Plus className="w-5 h-5" />
          Quick Add Transaction
        </h3>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setIsTransfer(false)}
            className={`px-3 py-1 rounded-lg text-sm ${!isTransfer ? 'bg-blue-100 text-blue-700' : 'bg-gray-100'}`}
          >
            Income/Expense
          </button>
          <button
            type="button"
            onClick={() => setIsTransfer(true)}
            className={`px-3 py-1 rounded-lg text-sm flex items-center gap-1 ${isTransfer ? 'bg-blue-100 text-blue-700' : 'bg-gray-100'}`}
          >
            <ArrowRightLeft className="w-4 h-4" />
            Transfer
          </button>
        </div>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Date</label>
            <input
              type="date"
              value={formatDateForInput(watch('transaction_date'))}
              onChange={(e) => setValue('transaction_date', parseDateForPicker(e.target.value))}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {isTransfer ? 'From Account' : 'Account'}
            </label>
            <select
              {...register('account_id', { required: true })}
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
                    {groupAccounts.map(acc => (
                      <option key={acc.id} value={acc.id}>
                        {`${formatAccountDisplayName(acc)} (${acc.currency})`}
                      </option>
                    ))}
                  </optgroup>
                );
              })}
            </select>
          </div>
        </div>

        {isTransfer && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">To Account</label>
            <select
              {...register('target_account_id', { required: isTransfer })}
              onChange={(e) => {
                setValue('target_account_id', e.target.value);
                const dest = accounts?.find(a => a.id === e.target.value);
                const src = accounts?.find(a => a.id === watchedAccountId);
                const rate = (dest && src && dest.currency !== src.currency)
                  ? String(getQAConversionRate(src.currency, dest.currency))
                  : '1.00';
                setValue('transfer_conversion_rate', rate);
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
                const groupAccounts = accounts?.filter(a => a.type === group.type && a.id !== watchedAccountId) || [];
                if (!groupAccounts.length) return null;
                return (
                  <optgroup key={group.type} label={group.label}>
                    {groupAccounts.map(acc => (
                      <option key={acc.id} value={acc.id}>
                        {`${formatAccountDisplayName(acc)} (${acc.currency})`}
                      </option>
                    ))}
                  </optgroup>
                );
              })}
            </select>
          </div>
        )}

        {/* Conversion Rate — only shown for cross-currency transfers */}
        {qaIsCrossCurrency && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Conversion Rate
              <span className="ml-1 text-xs font-normal text-gray-500">
                (1 {selectedAccountCurrency} = ? {qaTargetAccount.currency})
              </span>
            </label>
            <input
              {...register('transfer_conversion_rate')}
              type="number"
              step="0.000001"
              min="0.000001"
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            />
            {qaReceivedAmount && (
              <p className="text-sm text-gray-600 mt-1">
                Recipient gets: <span className="font-medium">{formatCurrency(qaReceivedAmount, qaTargetAccount.currency)}</span>
              </p>
            )}
          </div>
        )}

        {!isTransfer && (
          <div className="flex gap-4">
            <label className="flex items-center">
              <input
                {...register('type')}
                type="radio"
                value="EXPENSE"
                className="mr-2 text-blue-600"
              />
              <span className="text-red-600 font-medium">Expense</span>
            </label>
            <label className="flex items-center">
              <input
                {...register('type')}
                type="radio"
                value="INCOME"
                className="mr-2 text-blue-600"
              />
              <span className="text-green-600 font-medium">Income</span>
            </label>
          </div>
        )}

        {!isTransfer && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
            <select
              {...register('category_id')}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select category...</option>
              {filteredCategories.map(cat => (
                <option key={cat.id} value={cat.id}>
                  {cat.name}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Currency override — income/expense only, shown when family has secondary currencies */}
        {!isTransfer && txCurrencyOptions.length > 1 && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Transaction Currency
              <span className="ml-1 text-xs font-normal text-gray-400">(optional override)</span>
            </label>
            <select
              {...register('tx_currency')}
              onChange={(e) => {
                const selected = e.target.value;
                setValue('tx_currency', selected);
                // Pre-populate exchange rate from stored ECB rates (user can override)
                const looked = lookupStoredRate(selected);
                setValue('exchange_rate_to_base', looked ? looked.rate : '');
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

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Amount</label>
          <div className="relative">
            <input
              {...register('amount', { required: true, min: 0.01 })}
              type="number"
              step="0.01"
              className="w-full pl-3 pr-16 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
              placeholder="0.00"
            />
            <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs font-medium text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded">
              {effectiveTxCurrency || selectedAccountCurrency || ''}
            </span>
          </div>
        </div>

        {/* Exchange rate — shown when transaction currency ≠ account currency */}
        {showExchangeRateField && (() => {
          const rateInfo = lookupStoredRate(effectiveTxCurrency);
          return (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Exchange Rate to {resolvedBase}
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
                  {...register('exchange_rate_to_base')}
                  type="number"
                  step="0.000001"
                  min="0.000001"
                  className="flex-1 px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  placeholder="enter rate"
                />
                <span className="text-sm text-gray-500">{resolvedBase}</span>
              </div>
            </div>
          );
        })()}

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
          <input
            {...register('description')}
            type="text"
            className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            placeholder="What was this for?"
          />
        </div>

        <button
          type="submit"
          disabled={isPending}
          className="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center justify-center gap-2"
        >
          {isPending ? (
            'Adding...'
          ) : (
            <>
              <Plus className="w-4 h-4" />
              Add Transaction
            </>
          )}
        </button>
      </form>
    </div>
  );
};

export default QuickAdd;
