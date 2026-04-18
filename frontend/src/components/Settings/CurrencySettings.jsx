import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Trash2, RefreshCw, Info } from 'lucide-react';
import api from '../../services/api';
import toast from 'react-hot-toast';

const COMMON_CURRENCIES = [
  // Major global
  { code: 'USD', name: 'US Dollar' },
  { code: 'EUR', name: 'Euro' },
  { code: 'GBP', name: 'British Pound' },
  { code: 'CHF', name: 'Swiss Franc' },
  { code: 'JPY', name: 'Japanese Yen' },
  { code: 'CNY', name: 'Chinese Yuan' },
  // South Asia
  { code: 'INR', name: 'Indian Rupee' },
  { code: 'BDT', name: 'Bangladeshi Taka' },
  { code: 'PKR', name: 'Pakistani Rupee' },
  { code: 'LKR', name: 'Sri Lankan Rupee' },
  { code: 'NPR', name: 'Nepalese Rupee' },
  // Gulf / Middle East
  { code: 'AED', name: 'UAE Dirham' },
  { code: 'SAR', name: 'Saudi Riyal' },
  { code: 'QAR', name: 'Qatari Riyal' },
  { code: 'KWD', name: 'Kuwaiti Dinar' },
  { code: 'BHD', name: 'Bahraini Dinar' },
  { code: 'OMR', name: 'Omani Rial' },
  // Asia-Pacific
  { code: 'SGD', name: 'Singapore Dollar' },
  { code: 'AUD', name: 'Australian Dollar' },
  { code: 'NZD', name: 'New Zealand Dollar' },
  { code: 'HKD', name: 'Hong Kong Dollar' },
  { code: 'MYR', name: 'Malaysian Ringgit' },
  { code: 'THB', name: 'Thai Baht' },
  { code: 'PHP', name: 'Philippine Peso' },
  { code: 'IDR', name: 'Indonesian Rupiah' },
  // Americas
  { code: 'CAD', name: 'Canadian Dollar' },
  // Europe (non-EUR)
  { code: 'SEK', name: 'Swedish Krona' },
  { code: 'NOK', name: 'Norwegian Krone' },
  { code: 'DKK', name: 'Danish Krone' },
  // Africa
  { code: 'ZAR', name: 'South African Rand' },
  { code: 'KES', name: 'Kenyan Shilling' },
];

export default function CurrencySettings({ user, familyProfile }) {
  const queryClient = useQueryClient();
  const [selectedCode, setSelectedCode] = useState('');

  const { data: currencies = [], isLoading } = useQuery({
    queryKey: ['settings', 'currencies'],
    queryFn: () => api.get('/settings/currencies').then(r => r.data),
  });

  const { data: rates = [] } = useQuery({
    queryKey: ['settings', 'exchange-rates'],
    queryFn: () => api.get('/settings/exchange-rates').then(r => r.data),
  });

  const addMutation = useMutation({
    mutationFn: (code) => api.post('/settings/currencies', { currency_code: code }),
    onSuccess: () => {
      toast.success('Currency added');
      setSelectedCode('');
      queryClient.invalidateQueries(['settings', 'currencies']);
      queryClient.invalidateQueries(['settings', 'exchange-rates']);
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Failed to add currency'),
  });

  const removeMutation = useMutation({
    mutationFn: (code) => api.delete(`/settings/currencies/${code}`),
    onSuccess: () => {
      toast.success('Currency removed');
      queryClient.invalidateQueries(['settings', 'currencies']);
      queryClient.invalidateQueries(['settings', 'exchange-rates']);
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Failed to remove currency'),
  });

  const refreshMutation = useMutation({
    mutationFn: () => api.post('/settings/exchange-rates/refresh'),
    onSuccess: (res) => {
      toast.success(res.data.message || 'Rates refreshed');
      queryClient.invalidateQueries(['settings', 'currencies']);
      queryClient.invalidateQueries(['settings', 'exchange-rates']);
    },
    onError: () => toast.error('Rate refresh failed'),
  });

  const isAdmin = user?.role === 'ADMIN';
  const base = familyProfile?.base_currency || '—';

  const existingCodes = new Set(currencies.map(c => c.currency_code));
  const available = COMMON_CURRENCIES
    .filter(c => c.code !== base && !existingCodes.has(c.code))
    .sort((a, b) => a.code.localeCompare(b.code));

  // Latest rate date
  const latestDate = rates.length > 0
    ? rates.reduce((max, r) => r.valid_date > max ? r.valid_date : max, rates[0].valid_date)
    : null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Currencies</h3>
          <p className="text-sm text-gray-500 mt-1">
            Exchange rates are fetched daily from the ECB feed for base + secondary currency pairs.
          </p>
        </div>
        {isAdmin && (
          <button
            onClick={() => refreshMutation.mutate()}
            disabled={refreshMutation.isLoading || currencies.length === 0}
            className="flex items-center gap-2 px-3 py-2 text-sm border rounded-lg hover:bg-gray-50 disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${refreshMutation.isLoading ? 'animate-spin' : ''}`} />
            Refresh Rates
          </button>
        )}
      </div>

      {/* Base currency info */}
      <div className="flex items-start gap-2 p-3 bg-blue-50 rounded-lg text-sm text-blue-800">
        <Info className="w-4 h-4 mt-0.5 shrink-0" />
        <span>
          Primary currency: <strong>{base}</strong> — set in Family Profile. Secondary currencies below
          are used to scope exchange rate fetching and display.
        </span>
      </div>

      {latestDate && (
        <p className="text-xs text-gray-500">Rates as of {latestDate}</p>
      )}

      {/* Secondary currencies list */}
      {isLoading ? (
        <p className="text-sm text-gray-500">Loading...</p>
      ) : currencies.length === 0 ? (
        <p className="text-sm text-gray-500">No secondary currencies added yet.</p>
      ) : (
        <ul className="divide-y border rounded-lg overflow-hidden">
          {[...currencies].sort((a, b) => a.currency_code.localeCompare(b.currency_code)).map((fc) => {
            const rateRow = rates.find(
              r => r.from_currency === fc.currency_code && r.to_currency === base
            );
            return (
              <li key={fc.id} className="flex items-center justify-between px-4 py-3 bg-white">
                <div>
                  <span className="font-medium">{fc.currency_code}</span>
                  {rateRow && (
                    <span className="text-sm text-gray-500 ml-2">
                      1 {fc.currency_code} = {parseFloat(rateRow.rate).toFixed(4)} {base}
                    </span>
                  )}
                  {fc.current_rate && !rateRow && (
                    <span className="text-sm text-gray-400 ml-2">
                      ≈ {parseFloat(fc.current_rate).toFixed(4)} {base} (approx)
                    </span>
                  )}
                </div>
                {isAdmin && (
                  <button
                    onClick={() => removeMutation.mutate(fc.currency_code)}
                    disabled={removeMutation.isLoading}
                    className="text-red-500 hover:text-red-700 p-1"
                    title="Remove currency"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {/* Add currency (admin only) */}
      {isAdmin && (
        <div className="flex gap-2">
          <select
            value={selectedCode}
            onChange={e => setSelectedCode(e.target.value)}
            className="flex-1 px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
          >
            <option value="">— Select currency to add —</option>
            {available.map(c => (
              <option key={c.code} value={c.code}>
                {c.code} — {c.name}
              </option>
            ))}
          </select>
          <button
            onClick={() => selectedCode && addMutation.mutate(selectedCode)}
            disabled={!selectedCode || addMutation.isLoading}
            className="flex items-center gap-1 px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            <Plus className="w-4 h-4" />
            Add
          </button>
        </div>
      )}
    </div>
  );
}
