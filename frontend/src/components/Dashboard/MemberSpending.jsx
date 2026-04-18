import { formatCurrency } from '../../utils/formatters';

const MemberSpending = ({ data, baseCurrency = 'USD' }) => {
  if (!data || data.length === 0) {
    return (
      <div className="bg-white rounded-xl shadow-sm p-4 sm:p-6 border border-gray-100">
        <h3 className="text-lg font-semibold mb-4">Member Spending</h3>
        <p className="text-gray-500 text-center py-8">No data available</p>
      </div>
    );
  }

  const maxExpense = Math.max(...data.map(item => Number(item.total_expense || 0)), 0);

  return (
    <div className="card-hover bg-white dark:bg-slate-800 rounded-xl shadow-sm p-4 sm:p-6 border border-gray-100 dark:border-slate-700">
      <h3 className="text-lg font-semibold mb-4">Member Spending</h3>
      <div className="space-y-3">
        {data.map((item) => {
          const totalExpense = Number(item.total_expense || 0);
          const widthPercent = maxExpense > 0 ? (totalExpense / maxExpense) * 100 : 0;

          return (
            <div key={item.user_id ?? item.user_name}>
              <div className="flex items-center justify-between text-sm mb-1">
                <span className="text-gray-700 dark:text-slate-300 truncate">{item.user_name}</span>
                <span className="text-gray-600 dark:text-slate-400 whitespace-nowrap">{formatCurrency(totalExpense, baseCurrency)}</span>
              </div>
              <div className="w-full h-2.5 bg-gray-100 dark:bg-slate-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500 dark:bg-blue-400 rounded-full"
                  style={{ width: `${widthPercent}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default MemberSpending;
