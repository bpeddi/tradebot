import type { PnlSummary as PnlSummaryType } from "../../types";

export function PnLSummary({ pnl, loading, onRefresh }: {
  pnl: PnlSummaryType | null; loading: boolean; onRefresh: () => void;
}) {
  const total = pnl?.total_realized_pnl ?? 0;
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
        <h3 className="text-sm font-semibold text-white">Realized P&L</h3>
        <button onClick={onRefresh} disabled={loading}
          className="text-xs text-blue-400 hover:text-blue-300 disabled:text-gray-600">
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>
      <div className="px-4 py-3 border-b border-gray-800">
        <span className="text-xs text-gray-500">Total realized (filled buys/sells, FIFO-matched)</span>
        <div className={`text-2xl font-semibold ${total >= 0 ? "text-green-400" : "text-red-400"}`}>
          {total >= 0 ? "+" : ""}${total.toFixed(2)}
        </div>
      </div>
      {pnl && pnl.realized.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b border-gray-800">
                <th className="px-4 py-2 font-medium">Symbol</th>
                <th className="px-4 py-2 font-medium">Matched Qty</th>
                <th className="px-4 py-2 font-medium">Realized P&L</th>
              </tr>
            </thead>
            <tbody>
              {pnl.realized.map(r => (
                <tr key={r.symbol} className="border-b border-gray-800/60 last:border-0">
                  <td className="px-4 py-2 text-white font-medium">{r.symbol}</td>
                  <td className="px-4 py-2 text-gray-300">{r.matched_qty}</td>
                  <td className={`px-4 py-2 font-medium ${r.realized_pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                    {r.realized_pnl >= 0 ? "+" : ""}${r.realized_pnl.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {pnl && pnl.realized.length === 0 && (
        <p className="px-4 py-4 text-sm text-gray-500 text-center">No closed (filled buy+sell) trades yet.</p>
      )}
    </div>
  );
}
