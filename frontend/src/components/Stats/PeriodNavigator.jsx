import React from 'react';
import { ChevronLeft, ChevronRight, Calendar } from 'lucide-react';
import {
  getPeriodLabel,
  isFuturePeriodEnd,
  offsetForDate,
  formatDateParam,
} from '../../utils/periodUtils';

const MODES = [
  { key: 'W', label: 'W' },
  { key: 'M', label: 'M' },
  { key: 'Q', label: 'Q' },
  { key: 'Y', label: 'Y' },
  { key: 'custom', label: 'Custom' },
];

const PeriodNavigator = ({ mode, start, end, offset, onModeChange, onOffsetChange, onCustomRange }) => {
  const label = mode !== 'custom' ? getPeriodLabel(mode, start) : null;
  const nextDisabled = mode !== 'custom' && isFuturePeriodEnd(end);

  const handleCalendarPick = (e) => {
    if (!e.target.value) return;
    const picked = new Date(e.target.value + 'T00:00:00');
    onOffsetChange(offsetForDate(mode, picked));
  };

  return (
    <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700 p-4">
      <div className="flex flex-wrap gap-1 mb-4">
        {MODES.map(m => (
          <button
            key={m.key}
            onClick={() => onModeChange(m.key)}
            className={`px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
              mode === m.key
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 dark:bg-slate-700 text-gray-600 dark:text-slate-300 hover:bg-gray-200 dark:hover:bg-slate-600'
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>

      {mode === 'custom' ? (
        <div className="flex flex-wrap gap-4 items-end">
          <div>
            <label className="block text-xs text-gray-500 dark:text-slate-400 mb-1">From</label>
            <input
              type="date"
              value={formatDateParam(start)}
              max={formatDateParam(end)}
              onChange={e => onCustomRange(new Date(e.target.value + 'T00:00:00'), end)}
              className="px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-700 text-gray-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 dark:text-slate-400 mb-1">To</label>
            <input
              type="date"
              value={formatDateParam(end)}
              min={formatDateParam(start)}
              max={formatDateParam(new Date())}
              onChange={e => onCustomRange(start, new Date(e.target.value + 'T00:00:00'))}
              className="px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-700 text-gray-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500 focus:outline-none"
            />
          </div>
        </div>
      ) : (
        <div className="flex items-center gap-3">
          <button
            onClick={() => onOffsetChange(offset - 1)}
            className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-slate-700 text-gray-600 dark:text-slate-300"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>

          <span className={`flex-1 text-center font-semibold text-base ${
            offset === 0
              ? 'text-blue-600 dark:text-blue-400'
              : 'text-gray-800 dark:text-slate-100'
          }`}>
            {label}
          </span>

          <button
            onClick={() => !nextDisabled && onOffsetChange(offset + 1)}
            disabled={nextDisabled}
            className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-slate-700 text-gray-600 dark:text-slate-300 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <ChevronRight className="w-5 h-5" />
          </button>

          <div className="relative">
            <input
              type="date"
              max={formatDateParam(new Date())}
              className="absolute inset-0 opacity-0 w-8 cursor-pointer"
              onChange={handleCalendarPick}
            />
            <Calendar className="w-5 h-5 text-gray-400 hover:text-blue-600 cursor-pointer" />
          </div>
        </div>
      )}
    </div>
  );
};

export default PeriodNavigator;
