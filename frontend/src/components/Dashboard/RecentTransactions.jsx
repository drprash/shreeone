import { formatAccountDisplayName, formatCurrency, formatDate } from '../../utils/formatters';
import { getTransactionIcon, getTransactionAmountColor } from '../../utils/typeHelpers';

const RecentTransactions = ({ transactions }) => {

  return (
    <div className="card-hover bg-white dark:bg-slate-800 rounded-xl shadow-sm p-4 sm:p-6 border border-gray-100 dark:border-slate-700">
      <h3 className="text-lg font-semibold mb-4">Recent Transactions</h3>

      {/* Mobile: 2-line card list (no horizontal scroll) */}
      <div className="md:hidden divide-y divide-gray-100 dark:divide-slate-700">
        {transactions.map((transaction) => (
          <div key={transaction.id} className="py-3">
            {/* Row 1: icon + description (left) · amount (right) */}
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 min-w-0 flex-1">
                {getTransactionIcon(transaction.type)}
                <span className="font-medium text-sm truncate">{transaction.description || 'No description'}</span>
              </div>
              <span className={`text-sm font-medium whitespace-nowrap shrink-0 ${getTransactionAmountColor(transaction.type)}`}>
                {transaction.type === 'EXPENSE' ? '-' : '+'}
                {formatCurrency(transaction.amount, transaction.currency)}
              </span>
            </div>
            {/* Row 2: date · category · account — no-wrap, truncates at account */}
            <div className="flex items-center gap-x-1.5 mt-1 overflow-hidden">
              <span className="text-xs text-gray-500 dark:text-slate-400 shrink-0 whitespace-nowrap">{formatDate(transaction.transaction_date)}</span>
              {transaction.category && (
                <>
                  <span className="text-gray-300 dark:text-slate-600 text-xs shrink-0">·</span>
                  <span
                    className="px-1.5 py-0.5 rounded text-white text-xs leading-none shrink-0 max-w-[96px] truncate"
                    style={{ backgroundColor: transaction.category.color }}
                  >
                    {transaction.category.name}
                  </span>
                </>
              )}
              <span className="text-gray-300 dark:text-slate-600 text-xs shrink-0">·</span>
              <span className="text-xs text-gray-500 dark:text-slate-400 truncate min-w-0">{formatAccountDisplayName(transaction.account)}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Desktop: original table */}
      <div className="hidden md:block overflow-x-auto">
        <table className="w-full min-w-[680px]">
          <thead>
            <tr className="text-left text-sm text-gray-500 border-b">
              <th className="pb-3">Date</th>
              <th className="pb-3">Description</th>
              <th className="pb-3">Category</th>
              <th className="pb-3">Account</th>
              <th className="pb-3 text-right">Amount</th>
            </tr>
          </thead>
          <tbody>
            {transactions.map((transaction) => (
              <tr key={transaction.id} className="border-b last:border-0">
                <td className="py-3 text-sm text-gray-600">
                  {formatDate(transaction.transaction_date)}
                </td>
                <td className="py-3">
                  <div className="flex items-center gap-2">
                    {getTransactionIcon(transaction.type)}
                    <span className="font-medium">{transaction.description || 'No description'}</span>
                  </div>
                </td>
                <td className="py-3 text-sm">
                  {transaction.category ? (
                    <span
                      className="px-2 py-1 rounded text-white text-xs"
                      style={{ backgroundColor: transaction.category.color }}
                    >
                      {transaction.category.name}
                    </span>
                  ) : (
                    <span className="text-gray-400">-</span>
                  )}
                </td>
                <td className="py-3 text-sm text-gray-600">
                  {formatAccountDisplayName(transaction.account)}
                </td>
                <td className={`py-3 text-right font-medium ${getTransactionAmountColor(transaction.type)}`}>
                  {transaction.type === 'EXPENSE' ? '-' : '+'}
                  {formatCurrency(transaction.amount, transaction.currency)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default RecentTransactions;
