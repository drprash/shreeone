import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../utils/queryKeys';
import { getStats } from '../services/statsAPI';
import { getPeriodDates, formatDateParam, getPriorPeriodLabel } from '../utils/periodUtils';
import PeriodNavigator from '../components/Stats/PeriodNavigator';
import StatsSummaryCards from '../components/Stats/StatsSummaryCards';
import SpendingTimeline from '../components/Stats/SpendingTimeline';
import CategoryChart from '../components/Dashboard/CategoryChart';
import MemberSpending from '../components/Dashboard/MemberSpending';

const Stats = () => {
  const [mode, setMode] = useState('M');
  const [offset, setOffset] = useState(0);
  const [customStart, setCustomStart] = useState(null);
  const [customEnd, setCustomEnd] = useState(null);

  const { start, end } = useMemo(() => {
    if (mode === 'custom' && customStart && customEnd) {
      return { start: customStart, end: customEnd };
    }
    return getPeriodDates(mode, offset);
  }, [mode, offset, customStart, customEnd]);

  const startParam = formatDateParam(start);
  const endParam = formatDateParam(end);

  const { data, isLoading, isError } = useQuery({
    queryKey: queryKeys.stats(startParam, endParam),
    queryFn: () => getStats(startParam, endParam),
    enabled: !!startParam && !!endParam && startParam <= endParam,
    staleTime: 1000 * 60 * 5,
  });

  const handleModeChange = (newMode) => {
    setMode(newMode);
    setOffset(0);
  };

  const handleCustomRange = (newStart, newEnd) => {
    setCustomStart(newStart);
    setCustomEnd(newEnd);
  };

  const priorLabel = getPriorPeriodLabel(mode, start);

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-slate-100">Stats</h1>

      <PeriodNavigator
        mode={mode}
        start={start}
        end={end}
        offset={offset}
        onModeChange={handleModeChange}
        onOffsetChange={setOffset}
        onCustomRange={handleCustomRange}
      />

      {isLoading && (
        <div className="flex justify-center py-12">
          <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {isError && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-4 text-red-700 dark:text-red-400 text-sm">
          Failed to load stats. Please try again.
        </div>
      )}

      {data && !isLoading && (
        <div className="space-y-6">
          <StatsSummaryCards
            current={data.current}
            trends={data.trends}
            baseCurrency={data.base_currency}
            priorLabel={priorLabel}
          />

          <SpendingTimeline
            dailyTotals={data.current.daily_totals}
            baseCurrency={data.base_currency}
            startStr={startParam}
            endStr={endParam}
          />

          {data.current.categories.length > 0 && (
            <CategoryChart
              data={data.current.categories}
              baseCurrency={data.base_currency}
            />
          )}

          {data.current.member_spending.length > 0 && (
            <MemberSpending
              data={data.current.member_spending}
              baseCurrency={data.base_currency}
            />
          )}
        </div>
      )}
    </div>
  );
};

export default Stats;
