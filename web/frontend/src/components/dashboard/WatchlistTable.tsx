import type { WatchlistRow } from "../../types";

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export function WatchlistTable({ watchlist, loading, onRefresh }: {
  watchlist: WatchlistRow[] | null; loading: boolean; onRefresh: () => void;
}) {
  const mostRecent = watchlist?.map(w => w.evaluated_at).filter(Boolean).sort().at(-1) as string | undefined;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
        <div>
          <h3 className="text-sm font-semibold text-white">Watchlist — Last Run</h3>
          {mostRecent && (
            <p className="text-xs text-gray-500 mt-0.5">as of {timeAgo(mostRecent)}</p>
          )}
        </div>
        <button onClick={onRefresh} disabled={loading}
          className="text-xs text-blue-400 hover:text-blue-300 disabled:text-gray-600">
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>
      {!watchlist || watchlist.length === 0 ? (
        <p className="px-4 py-6 text-sm text-gray-500 text-center">Loading…</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b border-gray-800">
                <th className="px-4 py-2 font-medium">Symbol</th>
                <th className="px-4 py-2 font-medium">Close</th>
                <th className="px-4 py-2 font-medium">9 EMA</th>
                <th className="px-4 py-2 font-medium">21 EMA</th>
                <th className="px-4 py-2 font-medium">Distance to Cross</th>
                <th className="px-4 py-2 font-medium">Signal</th>
              </tr>
            </thead>
            <tbody>
              {watchlist.map(w => {
                if (w.error) {
                  return (
                    <tr key={w.symbol} className="border-b border-gray-800/60 last:border-0">
                      <td className="px-4 py-2 text-white font-medium">{w.symbol}</td>
                      <td colSpan={5} className="px-4 py-2 text-red-400">{w.error}</td>
                    </tr>
                  );
                }
                if (!w.evaluated_at) {
                  return (
                    <tr key={w.symbol} className="border-b border-gray-800/60 last:border-0">
                      <td className="px-4 py-2 text-white font-medium">{w.symbol}</td>
                      <td colSpan={5} className="px-4 py-2 text-gray-500 text-xs">
                        No data yet — run the bot once to populate this symbol.
                      </td>
                    </tr>
                  );
                }
                const dist = w.distance_pct ?? 0;
                const bullishSide = dist > 0;
                return (
                  <tr key={w.symbol} className="border-b border-gray-800/60 last:border-0">
                    <td className="px-4 py-2 text-white font-medium">{w.symbol}</td>
                    <td className="px-4 py-2 text-gray-300">${w.close?.toFixed(2)}</td>
                    <td className="px-4 py-2 text-gray-300">{w.short_ma?.toFixed(2)}</td>
                    <td className="px-4 py-2 text-gray-300">{w.long_ma?.toFixed(2)}</td>
                    <td className={`px-4 py-2 font-medium ${bullishSide ? "text-green-400" : "text-red-400"}`}>
                      {dist >= 0 ? "+" : ""}{dist.toFixed(2)}%
                    </td>
                    <td className="px-4 py-2">
                      {w.signal ? (
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                          w.signal === "bullish" ? "bg-green-900/40 text-green-300" : "bg-red-900/40 text-red-300"
                        }`}>
                          {w.signal}
                        </span>
                      ) : (
                        <span className={`text-xs ${bullishSide ? "text-green-500/70" : "text-red-500/70"}`}>
                          {bullishSide ? "uptrend (no fresh cross)" : "downtrend (no fresh cross)"}
                        </span>
                      )}
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
