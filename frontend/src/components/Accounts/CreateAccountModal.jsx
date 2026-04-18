import { useForm } from 'react-hook-form';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { X } from 'lucide-react';
import api from '../../services/api';
import toast from 'react-hot-toast';
import { getCurrencySymbol } from '../../utils/formatters';

const ACCOUNT_TYPES = [
  { value: 'CASH', label: 'Cash', icon: '💵' },
  { value: 'BANK', label: 'Bank Account', icon: '🏦' },
  { value: 'CREDIT_CARD', label: 'Credit Card', icon: '💳' },
  { value: 'INVESTMENT', label: 'Investment', icon: '📈' }
];

const ACCOUNT_TYPE_TOOLTIPS = {
  BANK: 'Savings accounts, current/checking accounts, NRE accounts, NRO accounts',
  INVESTMENT: 'Fixed deposits (incl. FCNR), mutual funds, stocks, EPF/PPF/NPS, property',
  CREDIT_CARD: 'Credit cards and charge cards in any currency',
  CASH: 'Physical cash, digital wallets (Paytm, PhonePe, Wise balance)',
};

const COUNTRIES = [
  { code: 'IN', name: 'India', flag: '🇮🇳' },
  { code: 'US', name: 'United States', flag: '🇺🇸' },
  { code: 'GB', name: 'United Kingdom', flag: '🇬🇧' },
  { code: 'AE', name: 'UAE', flag: '🇦🇪' },
  { code: 'SG', name: 'Singapore', flag: '🇸🇬' },
  { code: 'CA', name: 'Canada', flag: '🇨🇦' },
  { code: 'AU', name: 'Australia', flag: '🇦🇺' },
  { code: 'NZ', name: 'New Zealand', flag: '🇳🇿' },
  { code: 'QA', name: 'Qatar', flag: '🇶🇦' },
  { code: 'SA', name: 'Saudi Arabia', flag: '🇸🇦' },
  { code: 'DE', name: 'Germany', flag: '🇩🇪' },
  { code: 'FR', name: 'France', flag: '🇫🇷' },
  { code: 'NL', name: 'Netherlands', flag: '🇳🇱' },
  { code: 'CH', name: 'Switzerland', flag: '🇨🇭' },
  { code: 'HK', name: 'Hong Kong', flag: '🇭🇰' },
  { code: 'JP', name: 'Japan', flag: '🇯🇵' },
  { code: 'MY', name: 'Malaysia', flag: '🇲🇾' },
  { code: 'TH', name: 'Thailand', flag: '🇹🇭' },
];

const CreateAccountModal = ({ isOpen, onClose, user }) => {
  const queryClient = useQueryClient();
  const { register, handleSubmit, watch, reset, formState: { errors } } = useForm({
    defaultValues: {
      type: 'BANK',
      owner_type: 'SHARED',
      currency: 'USD',
      include_in_family_overview: true,
      opening_balance: 0
    }
  });

  const ownerType = watch('owner_type');
  const selectedCurrency = watch('currency');

  const mutation = useMutation({
    mutationFn: (data) => api.post('/accounts/', data),
    onSuccess: () => {
      toast.success('Account created successfully');
      queryClient.invalidateQueries(['accounts']);
      reset();
      onClose();
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to create account');
    }
  });

  const onSubmit = (data) => {
    const payload = {
      ...data,
      opening_balance: parseFloat(data.opening_balance) || 0,
      country_code: data.country_code || null,
    };
    mutation.mutate(payload);
  };

  if (!isOpen) return null;

  return (
    <div className="modal-backdrop fixed inset-0 flex items-center justify-center z-50">
      <div className="glass-panel bg-white dark:bg-slate-800 rounded-lg shadow-xl w-full max-w-md mx-4 slide-in">
        <div className="flex items-center justify-between p-6 border-b">
          <h2 className="text-xl font-semibold">Create New Account</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-6 h-6" />
          </button>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="p-6 space-y-4">
          {/* Account Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Account Name *
            </label>
            <input
              {...register('name', { required: 'Account name is required' })}
              type="text"
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
              placeholder="e.g., Main Checking Account"
            />
            {errors.name && (
              <p className="text-red-500 text-sm mt-1">{errors.name.message}</p>
            )}
          </div>

          {/* Account Type */}
          <div>
            <div className="flex items-center gap-1 mb-1">
              <label className="block text-sm font-medium text-gray-700">
                Account Type *
              </label>
              <span
                className="text-gray-400 cursor-help text-xs"
                title={Object.entries(ACCOUNT_TYPE_TOOLTIPS).map(([k, v]) => `${k}: ${v}`).join('\n')}
              >
                ℹ
              </span>
            </div>
            <select
              {...register('type', { required: true })}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            >
              {ACCOUNT_TYPES.map(type => (
                <option key={type.value} value={type.value}>
                  {type.icon} {type.label}
                </option>
              ))}
            </select>
          </div>

          {/* Owner Type */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Ownership *
            </label>
            <div className="flex gap-4">
              <label className="flex items-center">
                <input
                  {...register('owner_type')}
                  type="radio"
                  value="SHARED"
                  className="mr-2 text-blue-600"
                />
                <span>Shared (Family)</span>
              </label>
              <label className="flex items-center">
                <input
                  {...register('owner_type')}
                  type="radio"
                  value="PERSONAL"
                  className="mr-2 text-blue-600"
                />
                <span>Personal</span>
              </label>
            </div>
          </div>

          {/* Currency */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Currency *
            </label>
            <select
              {...register('currency', { required: true })}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            >
              <option value="AED">AED - UAE Dirham</option>
              <option value="INR">INR - Indian Rupee</option>
              <option value="USD">USD - US Dollar</option>
              <option value="EUR">EUR - Euro</option>
              <option value="GBP">GBP - British Pound</option>
              <option value="THB">THB - Thai Baht</option>
              <option value="JPY">JPY - Japanese Yen</option>
            </select>
          </div>

          {/* Opening Balance */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Opening Balance
            </label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">{getCurrencySymbol(selectedCurrency)}</span>
              <input
                {...register('opening_balance')}
                type="number"
                step="0.01"
                className="w-full pl-8 pr-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                placeholder="0.00"
              />
            </div>
          </div>

          {/* Country */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Country <span className="text-gray-400 font-normal">(optional)</span>
            </label>
            <select
              {...register('country_code')}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            >
              <option value="">— Not specified —</option>
              {COUNTRIES.map(c => (
                <option key={c.code} value={c.code}>
                  {c.flag} {c.name}
                </option>
              ))}
            </select>
          </div>

          {/* Include in Family Overview */}
          <div className="flex items-center">
            <input
              {...register('include_in_family_overview')}
              type="checkbox"
              className="mr-2 text-blue-600"
            />
            <label className="text-sm text-gray-700">
              Include in family dashboard overview
            </label>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border rounded-lg hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={mutation.isLoading}
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {mutation.isLoading ? 'Creating...' : 'Create Account'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default CreateAccountModal;
