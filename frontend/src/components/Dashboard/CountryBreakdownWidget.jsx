import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { RefreshCw } from 'lucide-react';
import api from '../../services/api';
import { formatCurrency } from '../../utils/formatters';

const COUNTRY_FLAGS = {
  IN: '🇮🇳', US: '🇺🇸', GB: '🇬🇧', AE: '🇦🇪', SG: '🇸🇬',
  CA: '🇨🇦', AU: '🇦🇺', NZ: '🇳🇿', QA: '🇶🇦', SA: '🇸🇦',
  DE: '🇩🇪', FR: '🇫🇷', NL: '🇳🇱', CH: '🇨🇭', HK: '🇭🇰',
  JP: '🇯🇵', MY: '🇲🇾', TH: '🇹🇭',
};

export default function CountryBreakdownWidget() {
  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['dashboard', 'country-breakdown'],
    queryFn: () => api.get('/dashboard/country-breakdown').then(r => r.data),
    staleTime: 5 * 60 * 1000,
  });

  const breakdown = data?.country_breakdown || [];
  const ratesAsOf = data?.rates_as_of;
  const baseCurrency = data?.summary?.base_currency || '';

  if (isLoading) {
    return (
      <div className="card-hover bg-white dark:bg-slate-800 rounded-xl shadow-sm p-4 sm:p-6 border border-gray-100 dark:border-slate-700 animate-pulse">
        <div className="h-5 bg-gray-200 dark:bg-slate-700 rounded w-48 mb-4" />
        <div className="space-y-3">
          {[1, 2, 3].map(i => <div key={i} className="h-8 bg-gray-100 dark:bg-slate-700 rounded" />)}
        </div>
      </div>
    );
  }

  if (breakdown.length === 0) return null;

  const total = breakdown.reduce((sum, r) => sum + parseFloat(r.total_in_base), 0);

  return (
    <div className="card-hover bg-white dark:bg-slate-800 rounded-xl shadow-sm p-4 sm:p-6 border border-gray-100 dark:border-slate-700">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-slate-100">Net Worth by Country</h3>
        <div className="flex items-center gap-2">
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-slate-300 p-1 rounded transition-colors"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${isFetching ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Total row */}
      <div className="flex items-center justify-between py-2 border-b border-gray-100 dark:border-slate-700 mb-3">
        <span className="text-sm font-medium text-gray-500 dark:text-slate-400">Total</span>
        <span className="text-sm font-semibold text-gray-900 dark:text-slate-100">{formatCurrency(total, baseCurrency)}</span>
      </div>

      {/* Country rows */}
      <div className="space-y-3">
        {breakdown.map((row) => {
          const pct = total > 0 ? (parseFloat(row.total_in_base) / total) * 100 : 0;
          const flag = row.country_code ? COUNTRY_FLAGS[row.country_code] || '🌍' : null;
          const label = row.country_code
            ? `${flag} ${row.country_name || row.country_code}`
            : 'Other / Unassigned';
          return (
            <div key={row.country_code ?? '__none__'}>
              <div className="flex items-center justify-between text-sm mb-1">
                <span className="text-gray-700 dark:text-slate-300 truncate">{label}</span>
                <span className="text-gray-600 dark:text-slate-400 whitespace-nowrap ml-2">
                  {formatCurrency(parseFloat(row.total_in_base), baseCurrency)} · {pct.toFixed(0)}%
                </span>
              </div>
              <div className="w-full h-2.5 bg-gray-100 dark:bg-slate-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500 dark:bg-blue-400 rounded-full"
                  style={{ width: `${pct.toFixed(1)}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {ratesAsOf && (
        <p className="text-xs text-gray-400 dark:text-slate-500 mt-4">Rates as of {ratesAsOf}</p>
      )}
    </div>
  );
}
