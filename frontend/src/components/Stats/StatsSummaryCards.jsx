import React from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { formatCurrency } from '../../utils/formatters';

const TrendBadge = ({ pct, invertColor }) => {
  if (pct == null) return null;
  const isPositive = pct > 0;
  const isGood = invertColor ? !isPositive : isPositive;
  const Icon = isPositive ? TrendingUp : TrendingDown;
  return (
    <span className={`flex items-center gap-0.5 text-xs font-medium ${isGood ? 'text-green-600' : 'text-red-500'}`}>
      <Icon className="w-3 h-3" />
      {Math.abs(pct).toFixed(1)}%
    </span>
  );
};

const StatsSummaryCards = ({ current, trends, baseCurrency, priorLabel }) => {
  const cards = [
    {
      label: 'Income',
      value: current.income,
      pct: trends.income_change_pct,
      invertColor: false,
    },
    {
      label: 'Expenses',
      value: current.expenses,
      pct: trends.expense_change_pct,
      invertColor: true,
    },
    {
      label: 'Savings',
      value: current.savings,
      pct: trends.savings_change_pct,
      invertColor: false,
    },
    {
      label: 'Savings Rate',
      rate: current.savings_rate,
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map(card => (
        <div
          key={card.label}
          className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700 p-4"
        >
          <p className="text-sm text-gray-500 dark:text-slate-400 mb-1">{card.label}</p>
          <p className="text-xl font-bold text-gray-900 dark:text-slate-100">
            {card.rate != null
              ? `${Number(card.rate).toFixed(1)}%`
              : formatCurrency(card.value, baseCurrency)}
          </p>
          {card.pct != null && (
            <div className="flex items-center gap-1 mt-1">
              <TrendBadge pct={card.pct} invertColor={card.invertColor} />
              <span className="text-xs text-gray-400 dark:text-slate-500">vs {priorLabel}</span>
            </div>
          )}
        </div>
      ))}
    </div>
  );
};

export default StatsSummaryCards;
