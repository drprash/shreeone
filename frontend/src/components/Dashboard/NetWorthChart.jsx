import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../../services/api';
import { formatCurrency } from '../../utils/formatters';

function fetchNetWorthHistory(months) {
  return api.get('/dashboard/net-worth-history', { params: { months } }).then(r => r.data);
}

function MiniLineChart({ points, width = 500, height = 120, baseCurrency }) {
  if (!points || points.length < 2) return null;

  const values = points.map(p => p.total_net_worth);
  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);
  const range = maxVal - minVal || 1;

  const padX = 8;
  const padY = 12;
  const chartW = width - padX * 2;
  const chartH = height - padY * 2;

  const toX = i => padX + (i / (points.length - 1)) * chartW;
  const toY = v => padY + chartH - ((v - minVal) / range) * chartH;

  const linePath = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${toX(i).toFixed(1)} ${toY(p.total_net_worth).toFixed(1)}`)
    .join(' ');

  const areaPath =
    `M ${toX(0).toFixed(1)} ${toY(points[0].total_net_worth).toFixed(1)} ` +
    points.slice(1).map((p, i) => `L ${toX(i + 1).toFixed(1)} ${toY(p.total_net_worth).toFixed(1)}`).join(' ') +
    ` L ${toX(points.length - 1).toFixed(1)} ${(padY + chartH).toFixed(1)} L ${toX(0).toFixed(1)} ${(padY + chartH).toFixed(1)} Z`;

  const lastPoint = points[points.length - 1];
  const firstPoint = points[0];
  const delta = lastPoint.total_net_worth - firstPoint.total_net_worth;
  const isUp = delta >= 0;

  return (
    <div className="w-full">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" preserveAspectRatio="none" style={{ height }}>
        <defs>
          <linearGradient id="nwGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={isUp ? '#3b82f6' : '#ef4444'} stopOpacity="0.25" />
            <stop offset="100%" stopColor={isUp ? '#3b82f6' : '#ef4444'} stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={areaPath} fill="url(#nwGrad)" />
        <path d={linePath} fill="none" stroke={isUp ? '#3b82f6' : '#ef4444'} strokeWidth="2" strokeLinejoin="round" />
        {/* latest dot */}
        <circle
          cx={toX(points.length - 1)}
          cy={toY(lastPoint.total_net_worth)}
          r="4"
          fill={isUp ? '#3b82f6' : '#ef4444'}
        />
      </svg>
      <div className="flex justify-between text-xs text-slate-400 dark:text-slate-500 mt-1 px-2">
        <span>{new Date(firstPoint.snapshot_date).toLocaleDateString(undefined, { month: 'short', year: '2-digit' })}</span>
        <span className={`font-medium ${isUp ? 'text-emerald-500' : 'text-red-400'}`}>
          {isUp ? '+' : ''}{formatCurrency(delta, baseCurrency)}
        </span>
        <span>{new Date(lastPoint.snapshot_date).toLocaleDateString(undefined, { month: 'short', year: '2-digit' })}</span>
      </div>
    </div>
  );
}

export default function NetWorthChart({ baseCurrency = 'USD' }) {
  const { data = [], isLoading, isError } = useQuery({
    queryKey: ['net-worth-history'],
    queryFn: () => fetchNetWorthHistory(12),
    staleTime: 5 * 60 * 1000,
  });

  const { data: stale = [] } = useQuery({
    queryKey: ['stale-valuations'],
    queryFn: () => api.get('/dashboard/stale-valuations').then(r => r.data),
    staleTime: 10 * 60 * 1000,
  });

  if (isLoading) {
    return (
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm p-6 border border-slate-100 dark:border-slate-700">
        <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-40 mb-4 animate-pulse" />
        <div className="h-28 bg-slate-100 dark:bg-slate-700/50 rounded animate-pulse" />
      </div>
    );
  }

  const latest = data.length > 0 ? data[data.length - 1] : null;

  return (
    <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm p-6 border border-slate-100 dark:border-slate-700">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-100">Net Worth Over Time</h3>
        {stale.length > 0 && (
          <span className="text-xs bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 px-2 py-1 rounded-full font-medium">
            {stale.length} account{stale.length > 1 ? 's' : ''} need valuation
          </span>
        )}
      </div>

      {latest && (
        <p className="text-2xl font-bold text-slate-800 dark:text-slate-100 mb-4">
          {formatCurrency(latest.total_net_worth, baseCurrency)}
          <span className="text-sm font-normal text-slate-400 dark:text-slate-500 ml-2">today</span>
        </p>
      )}

      {isError || data.length === 0 ? (
        <p className="text-sm text-slate-400 dark:text-slate-500 text-center py-8">
          {isError ? 'Could not load net worth history' : 'No snapshot data yet — check back tomorrow'}
        </p>
      ) : (
        <MiniLineChart points={data} baseCurrency={baseCurrency} />
      )}

      {stale.length > 0 && (
        <div className="mt-4 border-t dark:border-slate-700 pt-3">
          <p className="text-xs text-amber-600 dark:text-amber-400 font-medium mb-1">Accounts needing a valuation update:</p>
          <ul className="text-xs text-slate-500 dark:text-slate-400 space-y-0.5">
            {stale.map(a => (
              <li key={a.id}>• {a.name} ({a.type}) — last valued {a.last_valued_at ? new Date(a.last_valued_at).toLocaleDateString() : 'never'}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
