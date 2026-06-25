import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import { useAuthStore } from '../../store/authStore';

function fetchNetWorthHistory(params) {
  return api.get('/dashboard/net-worth-history', { params }).then(r => r.data);
}

function parseSnapshotDate(dateStr) {
  const [y, m, d] = String(dateStr).slice(0, 10).split('-').map(Number);
  return new Date(y, m - 1, d);
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
        <span>{parseSnapshotDate(firstPoint.snapshot_date).toLocaleDateString(undefined, { month: 'short', year: '2-digit' })}</span>
        <span className={`font-medium ${isUp ? 'text-emerald-500' : 'text-red-400'}`}>
          {isUp ? '+' : ''}{formatCurrency(delta, baseCurrency)}
        </span>
        <span>{parseSnapshotDate(lastPoint.snapshot_date).toLocaleDateString(undefined, { month: 'short', year: '2-digit' })}</span>
      </div>
    </div>
  );
}

export default function NetWorthChart({ baseCurrency = 'USD', selectedMemberId = 'family', currentNetWorth }) {
  const { user } = useAuthStore();
  const isAdminMemberView = user?.role === 'ADMIN' && selectedMemberId !== 'family';

  const { data = [], isLoading, isError } = useQuery({
    queryKey: ['net-worth-history', user?.id, selectedMemberId],
    queryFn: () => {
      const params = { months: 12 };
      if (isAdminMemberView) params.member_id = selectedMemberId;
      return fetchNetWorthHistory(params);
    },
    staleTime: 5 * 60 * 1000,
  });

  // Inject live "today" value as the final data point so the chart's latest
  // figure always matches the net worth tile and country breakdown (both live).
  const chartData = React.useMemo(() => {
    if (currentNetWorth == null || data.length === 0) return data;
    const _d = new Date();
    const today = `${_d.getFullYear()}-${String(_d.getMonth() + 1).padStart(2, '0')}-${String(_d.getDate()).padStart(2, '0')}`;
    const last = data[data.length - 1];
    const lastDate = String(last.snapshot_date).slice(0, 10);
    const livePoint = { ...last, snapshot_date: today, total_net_worth: Number(currentNetWorth) };
    return lastDate === today
      ? [...data.slice(0, -1), livePoint]   // replace stale today snapshot
      : [...data, livePoint];               // append when snapshot not yet written
  }, [data, currentNetWorth]);

  if (isLoading) {
    return (
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm p-6 border border-slate-100 dark:border-slate-700">
        <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-40 mb-4 animate-pulse" />
        <div className="h-28 bg-slate-100 dark:bg-slate-700/50 rounded animate-pulse" />
      </div>
    );
  }

  const latest = chartData.length > 0 ? chartData[chartData.length - 1] : null;

  return (
    <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm p-6 border border-slate-100 dark:border-slate-700">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-100">Net Worth Over Time</h3>
      </div>

      {latest && (
        <p className="text-2xl font-bold text-slate-800 dark:text-slate-100 mb-4">
          {formatCurrency(latest.total_net_worth, baseCurrency)}
          <span className="text-sm font-normal text-slate-400 dark:text-slate-500 ml-2">today</span>
        </p>
      )}

      {isError || chartData.length === 0 ? (
        <p className="text-sm text-slate-400 dark:text-slate-500 text-center py-8">
          {isError ? 'Could not load net worth history' : 'No snapshot data yet — check back tomorrow'}
        </p>
      ) : (
        <MiniLineChart points={chartData} baseCurrency={baseCurrency} />
      )}

    </div>
  );
}
