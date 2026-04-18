import { Wallet, CreditCard, PiggyBank, TrendingUp, TrendingDown, DollarSign, Landmark, LineChart } from 'lucide-react';
import { formatCurrency } from '../../utils/formatters';

const SummaryCards = ({ data }) => {
  const {
    total_net_worth,
    total_investments,
    total_cash,
    total_bank_balance,
    total_credit_liability,
    monthly_income,
    monthly_expense,
    monthly_savings,
    base_currency
  } = data;

  const creditLiabilityAmount = Math.max(0, Number(total_credit_liability ?? 0));

  const resolveValueColorClass = (value) => {
    const numericValue = Number(value);
    if (!Number.isFinite(numericValue) || numericValue === 0) return 'text-gray-900';
    return numericValue > 0 ? 'text-green-600' : 'text-red-600';
  };

  const resolveTrendColorClass = (metric, trend) => {
    if (trend === null || trend === undefined || trend === 0) return 'text-gray-500';

    if (metric === 'EXPENSE') {
      return trend > 0 ? 'text-red-600' : 'text-green-600';
    }

    return trend > 0 ? 'text-green-600' : 'text-red-600';
  };

  const cards = [
    {
      title: 'Net Worth',
      value: total_net_worth,
      icon: DollarSign,
      color: 'bg-blue-500',
      trend: null
    },
    {
      title: 'Investments',
      value: total_investments,
      icon: LineChart,
      color: 'bg-violet-500',
      trend: null
    },
    {
      title: 'Bank Balance',
      value: total_bank_balance,
      icon: Landmark,
      color: 'bg-indigo-500',
      trend: null
    },
    {
      title: 'Cash',
      value: total_cash,
      icon: Wallet,
      color: 'bg-green-500',
      trend: null
    },
    {
      title: 'Monthly Income',
      value: monthly_income,
      icon: TrendingUp,
      color: 'bg-emerald-500',
      trend: data.monthly_income_trend,
      trendMetric: 'INCOME',
      isPercentage: true
    },
    {
      title: 'Monthly Expense',
      value: monthly_expense,
      icon: TrendingDown,
      color: 'bg-orange-500',
      trend: data.monthly_expense_trend,
      trendMetric: 'EXPENSE',
      isNegative: true,
      isPercentage: true
    },
    {
      title: 'Monthly Savings',
      value: monthly_savings,
      icon: PiggyBank,
      color: 'bg-blue-500',
      useDynamicValueColor: true,
      trend: null
    },
    {
      title: 'Credit Liability',
      value: -creditLiabilityAmount,
      icon: CreditCard,
      color: 'bg-red-500',
      useDynamicValueColor: true,
      trend: null
    }
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      {cards.map((card, index) => (
        <div key={index} className="card-hover bg-white dark:bg-slate-800 rounded-xl shadow-sm p-4 sm:p-6 border border-gray-100 dark:border-slate-700">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">{card.title}</p>
              <p className={`text-xl sm:text-2xl font-bold ${card.useDynamicValueColor ? resolveValueColorClass(card.value) : (card.isNegative ? 'text-red-600' : 'text-gray-900')}`}>
                {formatCurrency(card.value, base_currency)}
              </p>
              {card.trend !== null && card.trend !== undefined && (
                <span className={`text-xs ${resolveTrendColorClass(card.trendMetric, card.trend)}`}>
                  {card.trend > 0 ? '+' : ''}{card.trend.toFixed(1)}% vs last month
                </span>
              )}
            </div>
            <div className={`${card.color} p-2.5 sm:p-3 rounded-lg`}>
              <card.icon className="w-6 h-6 text-white" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

export default SummaryCards;
