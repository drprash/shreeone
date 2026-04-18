import React, { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { X } from 'lucide-react';
import api from '../../services/api';
import toast from 'react-hot-toast';
import { getCurrencySymbol } from '../../utils/formatters';

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

const EditAccountModal = ({ isOpen, onClose, account, user }) => {
  const queryClient = useQueryClient();
  const { register, handleSubmit, reset, formState: { errors } } = useForm();

  // Reset form when account changes
  useEffect(() => {
    if (account) {
      reset({
        name: account.name,
        opening_balance: account.opening_balance,
        include_in_family_overview: account.include_in_family_overview,
        country_code: account.country_code || '',
      });
    }
  }, [account, reset]);

  const mutation = useMutation({
    mutationFn: (data) => api.put(`/accounts/${account.id}`, data),
    onSuccess: () => {
      toast.success('Account updated successfully');
      queryClient.invalidateQueries(['accounts']);
      onClose();
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to update account');
    }
  });

  const onSubmit = (data) => {
    const payload = {
      name: data.name,
      opening_balance: parseFloat(data.opening_balance) || 0,
      include_in_family_overview: data.include_in_family_overview,
      country_code: data.country_code || null,
    };
    mutation.mutate(payload);
  };

  if (!isOpen || !account) return null;

  const canEdit = user?.role === 'ADMIN' || account.owner_type === 'PERSONAL';

  return (
    <div className="modal-backdrop fixed inset-0 flex items-center justify-center z-50">
      <div className="glass-panel bg-white dark:bg-slate-800 rounded-lg shadow-xl w-full max-w-md mx-4 slide-in">
        <div className="flex items-center justify-between p-6 border-b">
          <h2 className="text-xl font-semibold">Edit Account</h2>
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
              disabled={!canEdit}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
            />
            {errors.name && (
              <p className="text-red-500 text-sm mt-1">{errors.name.message}</p>
            )}
          </div>

          {/* Read-only fields */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Type
              </label>
              <input
                type="text"
                value={account.type}
                disabled
                className="w-full px-3 py-2 border rounded-lg bg-gray-100"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Currency
              </label>
              <input
                type="text"
                value={account.currency}
                disabled
                className="w-full px-3 py-2 border rounded-lg bg-gray-100"
              />
            </div>
          </div>

          {/* Opening Balance */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Opening Balance
            </label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">{getCurrencySymbol(account?.currency)}</span>
              <input
                {...register('opening_balance')}
                type="number"
                step="0.01"
                disabled={!canEdit}
                className="w-full pl-8 pr-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
              />
            </div>
            <p className="text-xs text-gray-500 mt-1">
              Current balance will be recalculated based on transactions
            </p>
          </div>

          {/* Country */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Country <span className="text-gray-400 font-normal">(optional)</span>
            </label>
            <select
              {...register('country_code')}
              disabled={!canEdit}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
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
              disabled={!canEdit}
              className="mr-2 text-blue-600 disabled:opacity-50"
            />
            <label className="text-sm text-gray-700">
              Include in family dashboard overview
            </label>
          </div>

          {/* Info for non-admins */}
          {!canEdit && (
            <p className="text-sm text-amber-600 bg-amber-50 p-3 rounded">
              Only admins can edit shared accounts. Contact your family admin for changes.
            </p>
          )}

          {/* Actions */}
          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border rounded-lg hover:bg-gray-50"
            >
              Cancel
            </button>
            {canEdit && (
              <button
                type="submit"
                disabled={mutation.isLoading}
                className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {mutation.isLoading ? 'Saving...' : 'Save Changes'}
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  );
};

export default EditAccountModal;
