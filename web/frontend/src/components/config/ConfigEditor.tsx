import { useEffect, useState } from "react";
import { apiJson } from "../../utils/apiFetch";
import type { Config } from "../../types";

export function ConfigEditor() {
  const [config, setConfig] = useState<Config | null>(null);
  const [symbolsText, setSymbolsText] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiJson<Config>("/api/config")
      .then(c => { setConfig(c); setSymbolsText(c.symbols.join(", ")); })
      .catch(e => setError((e as Error).message));
  }, []);

  if (error && !config) return <div className="p-6 text-red-400 text-sm">{error}</div>;
  if (!config) return <div className="p-6 text-gray-500 text-sm">Loading…</div>;

  const update = <K extends keyof Config>(key: K, value: Config[K]) =>
    setConfig(c => c ? { ...c, [key]: value } : c);

  const save = async () => {
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      const symbols = symbolsText.split(",").map(s => s.trim()).filter(Boolean);
      const saved = await apiJson<Config>("/api/config", {
        method: "PUT",
        body: JSON.stringify({ ...config, symbols }),
      });
      setConfig(saved);
      setSymbolsText(saved.symbols.join(", "));
      setMessage("Saved.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const inputClass = "bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white " +
    "focus:outline-none focus:border-blue-500";

  return (
    <div className="p-6 max-w-xl">
      <h2 className="text-lg font-semibold text-white mb-4">Config</h2>
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 flex flex-col gap-4">
        <label className="flex flex-col gap-1">
          <span className="text-xs text-gray-500">
            Symbols (comma-separated, evaluated in this order)
            {" — "}{symbolsText.split(",").map(s => s.trim()).filter(Boolean).length} listed
          </span>
          <textarea
            value={symbolsText}
            onChange={e => setSymbolsText(e.target.value)}
            rows={3}
            className={inputClass + " resize-y"}
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-xs text-gray-500">Candle interval (e.g. 4h, 1d)</span>
          <input
            value={config.candle_interval}
            onChange={e => update("candle_interval", e.target.value)}
            className={inputClass}
          />
        </label>

        <div className="grid grid-cols-2 gap-4">
          <label className="flex flex-col gap-1">
            <span className="text-xs text-gray-500">Short EMA window</span>
            <input
              type="number"
              value={config.short_window}
              onChange={e => update("short_window", Number(e.target.value))}
              className={inputClass}
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs text-gray-500">Long EMA window</span>
            <input
              type="number"
              value={config.long_window}
              onChange={e => update("long_window", Number(e.target.value))}
              className={inputClass}
            />
          </label>
        </div>

        <label className="flex flex-col gap-1">
          <span className="text-xs text-gray-500">Lookback days</span>
          <input
            type="number"
            value={config.lookback_days}
            onChange={e => update("lookback_days", Number(e.target.value))}
            className={inputClass}
          />
        </label>

        <div className="grid grid-cols-2 gap-4">
          <label className="flex flex-col gap-1">
            <span className="text-xs text-gray-500">Max investment ($)</span>
            <input
              type="number"
              value={config.max_investment}
              onChange={e => update("max_investment", Number(e.target.value))}
              className={inputClass}
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs text-gray-500">Max slots (max concurrent positions)</span>
            <input
              type="number"
              min={1}
              value={config.max_slots}
              onChange={e => update("max_slots", Number(e.target.value))}
              className={inputClass}
            />
          </label>
        </div>

        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={config.rotation_enabled}
            onChange={e => update("rotation_enabled", e.target.checked)}
            className="h-4 w-4 accent-blue-600"
          />
          <span className="text-xs text-gray-500">
            Rotation enabled — when off, a full portfolio simply skips new buys instead of selling a
            weak holding to make room; a slot only frees up via a real bearish crossover sell
          </span>
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-xs text-gray-500">Rotation weakness threshold (%)</span>
          <input
            type="number"
            step="0.1"
            disabled={!config.rotation_enabled}
            value={config.rotation_weakness_pct}
            onChange={e => update("rotation_weakness_pct", Number(e.target.value))}
            className={inputClass + (config.rotation_enabled ? "" : " opacity-50")}
          />
        </label>

        <p className="text-xs text-gray-600">
          {config.max_slots > 0
            ? <>≈ <span className="text-gray-300 font-medium">
                ${(config.max_investment / config.max_slots).toLocaleString(undefined, { maximumFractionDigits: 2 })}
              </span> per slot. The bot buys symbols top-to-bottom from the list above until all {config.max_slots} slots
              are filled.{" "}
              {config.rotation_enabled
                ? <>Once full, a new signal rotates in — but only among held positions that are
                    ALSO technically weak (price below its own short EMA, or distance to crossover
                    under the threshold above), confirmed over two separate runs (a single noisy bar
                    isn't enough); the weakest of those confirmed candidates by unrealized P&L % is
                    sold to fund the new buy. If nothing qualifies (or the portfolio is only "full"
                    due to unfilled pending orders), the new buy is skipped and retried next run.</>
                : <>Rotation is off — once full, every new signal is skipped and retried next run
                    instead. A slot only opens up when a real bearish crossover sells a held
                    position outright.</>}</>
            : "Set max slots to at least 1."}
        </p>

        {message && <div className="text-sm text-green-400">{message}</div>}
        {error && <div className="text-sm text-red-400">{error}</div>}

        <button
          onClick={save}
          disabled={saving}
          className="mt-2 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700
            disabled:text-gray-500 text-white font-semibold text-sm transition-colors"
        >
          {saving ? "Saving…" : "Save Config"}
        </button>
      </div>
    </div>
  );
}
