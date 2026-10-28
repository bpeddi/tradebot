import { useEffect, useState } from "react";
import { apiJson } from "../../utils/apiFetch";
import type { Schedule } from "../../types";

export function ScheduleEditor() {
  const [sched, setSched] = useState<Schedule | null>(null);
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState<Schedule | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiJson<Schedule>("/api/schedule")
      .then(s => { setSched(s); setResult(s); })
      .catch(e => setError((e as Error).message));
  }, []);

  if (error && !sched) return <div className="p-6 text-red-400 text-sm">{error}</div>;
  if (!sched) return <div className="p-6 text-gray-500 text-sm">Loading…</div>;

  const save = async () => {
    setSaving(true);
    setError(null);
    setResult(null);
    try {
      const res = await apiJson<Schedule>("/api/schedule", { method: "PUT", body: JSON.stringify(sched) });
      setResult(res);
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
      <h2 className="text-lg font-semibold text-white mb-4">Schedule</h2>
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-4">
          <label className="flex flex-col gap-1">
            <span className="text-xs text-gray-500">Run time 1 (CST)</span>
            <input
              type="time"
              value={sched.time1}
              onChange={e => setSched(s => s ? { ...s, time1: e.target.value } : s)}
              className={inputClass}
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs text-gray-500">Run time 2 (CST)</span>
            <input
              type="time"
              value={sched.time2}
              onChange={e => setSched(s => s ? { ...s, time2: e.target.value } : s)}
              className={inputClass}
            />
          </label>
        </div>

        <label className="flex items-center gap-2 text-sm text-gray-300">
          <input
            type="checkbox"
            checked={sched.enabled}
            onChange={e => setSched(s => s ? { ...s, enabled: e.target.checked } : s)}
          />
          Enable scheduled runs (Mon–Fri)
        </label>

        <p className="text-xs text-gray-600">
          Runs Monday–Friday at the times above. An in-process scheduler inside the dashboard's
          own server checks this every 30 seconds — no OS cron involved, so this works the same
          on every host. The app process has to stay running for scheduled runs to fire (it
          already does, via <code>--restart unless-stopped</code> in production).
        </p>

        {result?.next_run && (
          <div className="text-sm text-green-400">
            Next run: {new Date(result.next_run).toLocaleString()}
          </div>
        )}
        {result && !result.next_run && (
          <div className="text-sm text-gray-500">Saved — scheduling disabled.</div>
        )}
        {error && <div className="text-sm text-red-400">{error}</div>}

        <button
          onClick={save}
          disabled={saving}
          className="mt-2 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700
            disabled:text-gray-500 text-white font-semibold text-sm transition-colors"
        >
          {saving ? "Applying…" : "Apply Schedule"}
        </button>
      </div>
    </div>
  );
}
