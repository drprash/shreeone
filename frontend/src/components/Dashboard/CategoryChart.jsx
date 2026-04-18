import { formatCurrency } from '../../utils/formatters';

const CategoryChart = ({ data, baseCurrency = 'USD' }) => {
  if (!data || data.length === 0) {
    return (
      <div className="bg-white rounded-xl shadow-sm p-4 sm:p-6 border border-gray-100">
        <h3 className="text-lg font-semibold mb-4">Spending by Category</h3>
        <p className="text-gray-500 text-center py-8">No data available</p>
      </div>
    );
  }

  const total = data.reduce((sum, item) => sum + Number(item.total_amount || 0), 0);

  return (
    <div className="card-hover bg-white dark:bg-slate-800 rounded-xl shadow-sm p-4 sm:p-6 border border-gray-100 dark:border-slate-700">
      <h3 className="text-lg font-semibold mb-4">Spending by Category</h3>
      <div className="space-y-3">
        {data.map((item) => {
          const amount = Number(item.total_amount || 0);
          const percent = total > 0 ? (amount / total) * 100 : 0;

          return (
            <div key={item.category_id ?? item.category_name}>
              <div className="flex items-center justify-between text-sm mb-1">
                <div className="flex items-center gap-2 min-w-0">
                  <span
                    className="inline-block w-3 h-3 rounded-full"
                    style={{ backgroundColor: item.color || '#94a3b8' }}
                  />
                  <span className="truncate text-gray-700 dark:text-slate-300">{item.category_name}</span>
                </div>
                <span className="text-gray-600 dark:text-slate-400 whitespace-nowrap">
                  {formatCurrency(amount, baseCurrency)} · {percent.toFixed(0)}%
                </span>
              </div>
              <div className="w-full h-2 bg-gray-100 dark:bg-slate-700 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full"
                  style={{ width: `${percent}%`, backgroundColor: item.color || '#3b82f6' }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default CategoryChart;
