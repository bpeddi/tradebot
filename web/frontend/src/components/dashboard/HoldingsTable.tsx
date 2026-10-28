import type { Position } from "../../types";

export function HoldingsTable({ holdings, loading, onRefresh }: {
  holdings: Position[] | null; loading: boolean; onRefresh: () => void;
}) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
        <h3 className="text-sm font-semibold text-white">Current Holdings</h3>
        <button onClick={onRefresh} disabled={loading}
          className="text-xs text-blue-400 hover:text-blue-300 disabled:text-gray-600">
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>
      {!holdings || holdings.length === 0 ? (
        <p className="px-4 py-6 text-sm text-gray-500 text-center">
          {holdings === null ? "Loading…" : "No open positions."}
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b border-gray-800">
                <th className="px-4 py-2 font-medium">Symbol</th>
                <th className="px-4 py-2 font-medium">Qty</th>
                <th className="px-4 py-2 font-medium">Avg Entry</th>
                <th className="px-4 py-2 font-medium">Current</th>
                <th className="px-4 py-2 font-medium">Market Value</th>
                <th className="px-4 py-2 font-medium">Unrealized P&L</th>
              </tr>
            </thead>
            <tbody>
              {holdings.map(p => {
                const pl = parseFloat(p.unrealized_pl);
                return (
                  <tr key={p.symbol} className="border-b border-gray-800/60 last:border-0">
                    <td className="px-4 py-2 text-white font-medium">{p.symbol}</td>
                    <td className="px-4 py-2 text-gray-300">{p.qty}</td>
                    <td className="px-4 py-2 text-gray-300">${parseFloat(p.avg_entry_price).toFixed(2)}</td>
                    <td className="px-4 py-2 text-gray-300">${parseFloat(p.current_price).toFixed(2)}</td>
                    <td className="px-4 py-2 text-gray-300">${parseFloat(p.market_value).toFixed(2)}</td>
                    <td className={`px-4 py-2 font-medium ${pl >= 0 ? "text-green-400" : "text-red-400"}`}>
                      {pl >= 0 ? "+" : ""}{pl.toFixed(2)} ({(parseFloat(p.unrealized_plpc) * 100).toFixed(1)}%)
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
