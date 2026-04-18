import { formatCurrency } from '../../utils/formatters';

const BalanceHistoryChart = ({ data, currency }) => {
  if (!data || data.length === 0) {
    return null;
  }

  const width = 900;
  const height = 300;
  const paddingX = 28;
  const paddingY = 18;

  const balances = data.map(item => Number(item.balance || 0));
  const minBalance = Math.min(...balances);
  const maxBalance = Math.max(...balances);
  const range = maxBalance - minBalance || 1;

  const points = data.map((item, index) => {
    const x = data.length > 1
      ? paddingX + (index * (width - paddingX * 2)) / (data.length - 1)
      : width / 2;
    const y = height - paddingY - ((Number(item.balance || 0) - minBalance) / range) * (height - paddingY * 2);

    return { x, y, item };
  });

  const path = points
    .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
    .join(' ');

  const latest = data[data.length - 1];
  const earliest = data[0];

  return (
    <div className="bg-white rounded-lg shadow p-6 mb-6">
      <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
        <h2 className="text-lg font-semibold">Balance History</h2>
        <div className="text-xs text-gray-500">
          {earliest?.date} → {latest?.date}
        </div>
      </div>

      <div className="w-full overflow-x-auto">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="w-full h-auto"
          role="img"
          aria-label="Balance history chart"
        >
          <line x1={paddingX} y1={paddingY} x2={paddingX} y2={height - paddingY} stroke="#e5e7eb" strokeWidth="1" />
          <line x1={paddingX} y1={height - paddingY} x2={width - paddingX} y2={height - paddingY} stroke="#e5e7eb" strokeWidth="1" />

          <path d={path} fill="none" stroke="#2563eb" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />

          {points.map((point, index) => (
            <g key={`${point.item.date}-${index}`}>
              <circle cx={point.x} cy={point.y} r="3" fill="#2563eb" />
              <title>{`${point.item.date}: ${formatCurrency(point.item.balance, currency)}`}</title>
            </g>
          ))}
        </svg>
      </div>

      <div className="mt-3 flex items-center justify-between text-sm text-gray-600">
        <span>Min: {formatCurrency(minBalance, currency)}</span>
        <span>Max: {formatCurrency(maxBalance, currency)}</span>
      </div>
    </div>
  );
};

export default BalanceHistoryChart;
