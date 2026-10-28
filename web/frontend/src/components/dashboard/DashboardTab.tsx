import { useCallback, useEffect, useState } from "react";
import { apiJson } from "../../utils/apiFetch";
import type { Config, Position, WatchlistRow, PnlSummary as PnlSummaryType, Run } from "../../types";
import { HoldingsTable } from "./HoldingsTable";
import { WatchlistTable } from "./WatchlistTable";
import { PnLSummary } from "./PnLSummary";
import { RunHistory } from "./RunHistory";

export function DashboardTab() {
  const [holdings, setHoldings] = useState<Position[] | null>(null);
  const [watchlist, setWatchlist] = useState<WatchlistRow[] | null>(null);
  const [pnl, setPnl] = useState<PnlSummaryType | null>(null);
  const [config, setConfig] = useState<Config | null>(null);
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [loadingHoldings, setLoadingHoldings] = useState(false);
  const [loadingWatchlist, setLoadingWatchlist] = useState(false);
  const [loadingPnl, setLoadingPnl] = useState(false);
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [running, setRunning] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadHoldings = useCallback(async () => {
    setLoadingHoldings(true);
    try { setHoldings(await apiJson<Position[]>("/api/bot/holdings")); }
    catch (e) { setError((e as Error).message); }
    finally { setLoadingHoldings(false); }
  }, []);

  useEffect(() => {
    apiJson<Config>("/api/config").then(setConfig).catch(() => {});
  }, []);

  const loadWatchlist = useCallback(async () => {
    setLoadingWatchlist(true);
    try { setWatchlist(await apiJson<WatchlistRow[]>("/api/bot/watchlist")); }
    catch (e) { setError((e as Error).message); }
    finally { setLoadingWatchlist(false); }
  }, []);

  const loadPnl = useCallback(async () => {
    setLoadingPnl(true);
    try { setPnl(await apiJson<PnlSummaryType>("/api/trades/pnl")); }
    catch (e) { setError((e as Error).message); }
    finally { setLoadingPnl(false); }
  }, []);

  const loadRuns = useCallback(async () => {
    setLoadingRuns(true);
    try { setRuns(await apiJson<Run[]>("/api/bot/runs")); }
    catch (e) { setError((e as Error).message); }
    finally { setLoadingRuns(false); }
  }, []);

  // The watchlist and run history are DB reads of the last bot run, not live
  // TastyTrade calls, so they're cheap to auto-load with everything else —
  // this is what makes "was the last run OK" visible immediately on login,
  // including for scheduled (cron) runs you weren't around to watch.
  useEffect(() => {
    loadHoldings(); loadPnl(); loadWatchlist(); loadRuns();
  }, [loadHoldings, loadPnl, loadWatchlist, loadRuns]);

  const runBot = async () => {
    setRunning(true);
    setError(null);
    try {
      await apiJson<{ output: string; returncode: number }>("/api/bot/run", { method: "POST" });
      loadHoldings();
      loadPnl();
      loadWatchlist();
      loadRuns();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRunning(false);
    }
  };

  const syncFills = async () => {
    setSyncing(true);
    setSyncMessage(null);
    setError(null);
    try {
      const res = await apiJson<{ synced: number }>("/api/bot/sync", { method: "POST" });
      setSyncMessage(
        res.synced > 0 ? `Synced ${res.synced} order(s).` : "Nothing to sync — all orders already up to date."
      );
      loadHoldings();
      loadPnl();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div className="p-6 flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-white">Dashboard</h2>
          {config && holdings && (
            <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${
              holdings.length >= config.max_slots
                ? "bg-yellow-900/40 text-yellow-300"
                : "bg-gray-800 text-gray-400"
            }`}>
              Slots: {holdings.length} / {config.max_slots}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={syncFills}
            disabled={syncing}
            title="Reconcile pending orders against Alpaca's real fill status, without running the strategy"
            className="px-4 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 disabled:bg-gray-800
              disabled:text-gray-600 text-gray-300 text-sm font-medium transition-colors border border-gray-700"
          >
            {syncing ? "Syncing…" : "Sync Fills"}
          </button>
          <button
            onClick={runBot}
            disabled={running}
            className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700
              disabled:text-gray-500 text-white text-sm font-medium transition-colors"
          >
            {running ? "Running…" : "Run Bot Now"}
          </button>
        </div>
      </div>

      {syncMessage && (
        <div className="px-3 py-2 bg-gray-900 border border-gray-800 rounded-lg text-gray-400 text-sm">
          {syncMessage}
        </div>
      )}

      {error && (
        <div className="px-3 py-2 bg-red-900/40 border border-red-700 rounded-lg text-red-300 text-sm">
          {error}
        </div>
      )}

      <RunHistory runs={runs} loading={loadingRuns} onRefresh={loadRuns} />
      <PnLSummary pnl={pnl} loading={loadingPnl} onRefresh={loadPnl} />
      <HoldingsTable holdings={holdings} loading={loadingHoldings} onRefresh={loadHoldings} />
      <WatchlistTable watchlist={watchlist} loading={loadingWatchlist} onRefresh={loadWatchlist} />
    </div>
  );
}
