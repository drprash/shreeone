import React, { useState } from 'react';
import { formatCurrency } from '../../utils/formatters';
import { aggregateDailyTotals, getGranularity } from '../../utils/periodUtils';

const W = 600;
const H = 180;
const PAD_L = 8;
const PAD_R = 8;
const PAD_T = 10;
const PAD_B = 28;
const CHART_W = W - PAD_L - PAD_R;
const CHART_H = H - PAD_T - PAD_B;

const SpendingTimeline = ({ dailyTotals, baseCurrency, startStr, endStr }) => {
  const [tooltip, setTooltip] = useState(null);

  if (!dailyTotals || dailyTotals.length === 0) {
    return (
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700 p-4 sm:p-6">
        <h3 className="text-base font-semibold text-gray-900 dark:text-slate-100 mb-4">Spending Timeline</h3>
        <p className="text-sm text-gray-400 dark:text-slate-500 text-center py-10">No transactions in this period</p>
      </div>
    );
  }

  const granularity = getGranularity(startStr, endStr);
  const data = aggregateDailyTotals(dailyTotals, granularity);
  const maxVal = Math.max(...data.flatMap(d => [Number(d.income), Number(d.expenses)]), 1);
  const groupW = CHART_W / data.length;
  const barW = Math.max(2, Math.min(14, groupW * 0.35));
  const toY = v => PAD_T + CHART_H - (v / maxVal) * CHART_H;
  const labelEvery = Math.ceil(data.length / 8);

  const formatLabel = (dateStr) => {
    const d = new Date(dateStr + 'T00:00:00');
    if (granularity === 'day') return String(d.getDate());
    if (granularity === 'week') return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
    return d.toLocaleDateString('en-US', { month: 'short' });
  };

  return (
    <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700 p-4 sm:p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-semibold text-gray-900 dark:text-slate-100">Spending Timeline</h3>
        <div className="flex gap-4 text-xs text-gray-500 dark:text-slate-400">
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-3 h-2 rounded-sm bg-green-500" />
            Income
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-3 h-2 rounded-sm bg-red-400" />
            Expenses
          </span>
        </div>
      </div>

      <div className="relative" onMouseLeave={() => setTooltip(null)}>
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: 200 }}>
          <line
            x1={PAD_L} y1={PAD_T + CHART_H}
            x2={W - PAD_R} y2={PAD_T + CHART_H}
            stroke="#e5e7eb" strokeWidth="1"
          />

          {data.map((d, i) => {
            const cx = PAD_L + (i + 0.5) * groupW;
            const incH = Math.max(1, (Number(d.income) / maxVal) * CHART_H);
            const expH = Math.max(1, (Number(d.expenses) / maxVal) * CHART_H);

            return (
              <g key={d.date}>
                <rect
                  x={cx - barW - 1}
                  y={toY(Number(d.income))}
                  width={barW}
                  height={incH}
                  fill="#22c55e"
                  rx={2}
                  className="cursor-pointer opacity-90 hover:opacity-100"
                  onMouseEnter={() => setTooltip({ ...d, x: cx })}
                />
                <rect
                  x={cx + 1}
                  y={toY(Number(d.expenses))}
                  width={barW}
                  height={expH}
                  fill="#f87171"
                  rx={2}
                  className="cursor-pointer opacity-90 hover:opacity-100"
                  onMouseEnter={() => setTooltip({ ...d, x: cx })}
                />
                {i % labelEvery === 0 && (
                  <text x={cx} y={H - 6} textAnchor="middle" fontSize="10" fill="#9ca3af">
                    {formatLabel(d.date)}
                  </text>
                )}
              </g>
            );
          })}
        </svg>

        {tooltip && (
          <div
            className="absolute pointer-events-none bg-white dark:bg-slate-700 border border-gray-200 dark:border-slate-600 rounded-lg shadow-lg px-3 py-2 text-xs z-10 whitespace-nowrap"
            style={{ left: `${(tooltip.x / W) * 100}%`, top: 0, transform: 'translateX(-50%)' }}
          >
            <p className="font-medium text-gray-700 dark:text-slate-300 mb-1">{tooltip.date}</p>
            <p className="text-green-600">Income: {formatCurrency(tooltip.income, baseCurrency)}</p>
            <p className="text-red-500">Expenses: {formatCurrency(tooltip.expenses, baseCurrency)}</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default SpendingTimeline;
