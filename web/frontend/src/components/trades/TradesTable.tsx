import { useEffect, useState } from "react";
import { apiJson } from "../../utils/apiFetch";
import type { Trade } from "../../types";

export function TradesTable() {
  const [trades, setTrades] = useState<Trade[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    apiJson<Trade[]>("/api/trades").then(setTrades).catch(e => setError((e as Error).message));
  };

  useEffect(load, []);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-white">Trades</h2>
        <button onClick={load} className="text-xs text-blue-400 hover:text-blue-300">Refresh</button>
      </div>
      {error && <div className="text-sm text-red-400 mb-4">{error}</div>}
      {!trades ? (
        <div className="text-sm text-gray-500">Loading…</div>
      ) : trades.length === 0 ? (
        <div className="text-sm text-gray-500">No trades logged yet.</div>
      ) : (
        <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b border-gray-800">
                <th className="px-4 py-2 font-medium">Submitted</th>
                <th className="px-4 py-2 font-medium">Symbol</th>
                <th className="px-4 py-2 font-medium">Side</th>
                <th className="px-4 py-2 font-medium">Qty</th>
                <th className="px-4 py-2 font-medium">Notional</th>
                <th className="px-4 py-2 font-medium">Filled Qty</th>
                <th className="px-4 py-2 font-medium">Filled Price</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Reason</th>
              </tr>
            </thead>
            <tbody>
              {trades.map(t => (
                <tr key={t.id} className="border-b border-gray-800/60 last:border-0">
                  <td className="px-4 py-2 text-gray-400 whitespace-nowrap">
                    {t.submitted_at ? new Date(t.submitted_at).toLocaleString() : "—"}
                  </td>
                  <td className="px-4 py-2 text-white font-medium">{t.symbol}</td>
                  <td className={`px-4 py-2 font-medium ${t.side === "buy" ? "text-green-400" : "text-red-400"}`}>
                    {t.side}
                  </td>
                  <td className="px-4 py-2 text-gray-300">{t.qty ?? "—"}</td>
                  <td className="px-4 py-2 text-gray-300">{t.notional ? `$${t.notional}` : "—"}</td>
                  <td className="px-4 py-2 text-gray-300">{t.filled_qty ?? "—"}</td>
                  <td className="px-4 py-2 text-gray-300">
                    {t.filled_avg_price ? `$${t.filled_avg_price.toFixed(2)}` : "—"}
                  </td>
                  <td className="px-4 py-2 text-gray-300">{t.status}</td>
                  <td className="px-4 py-2 text-gray-500 text-xs">{t.reason ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
