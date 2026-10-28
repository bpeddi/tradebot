import { useState } from "react";
import type { Run } from "../../types";

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

function duration(run: Run): string {
  const secs = Math.round((new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()) / 1000);
  return secs < 60 ? `${secs}s` : `${Math.floor(secs / 60)}m ${secs % 60}s`;
}

const STATUS_STYLE: Record<Run["status"], { badge: string; label: string }> = {
  success: { badge: "bg-green-900/40 text-green-300", label: "✓ Success" },
  partial: { badge: "bg-yellow-900/40 text-yellow-300", label: "⚠ Partial — some symbols errored" },
  error:   { badge: "bg-red-900/40 text-red-300",       label: "✕ Error" },
};

function RunRow({ run, defaultOpen }: { run: Run; defaultOpen: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const style = STATUS_STYLE[run.status];

  return (
    <div className="border-b border-gray-800/60 last:border-0">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-2.5 text-left hover:bg-gray-800/30 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className={`px-2 py-0.5 rounded text-xs font-medium ${style.badge}`}>{style.label}</span>
          <span className="text-xs text-gray-500">{timeAgo(run.started_at)}</span>
          <span className="text-xs text-gray-600">({duration(run)})</span>
        </div>
        <span className="text-xs text-gray-600">{open ? "Hide log" : "View log"}</span>
      </button>
      {open && (
        <div className="px-4 pb-3">
          {run.error_message && (
            <div className="mb-2 text-xs text-red-400">{run.error_message}</div>
          )}
          <pre className="bg-gray-950 border border-gray-800 rounded-lg p-3 text-xs text-gray-300
            whitespace-pre-wrap overflow-x-auto max-h-80 overflow-y-auto">
            {run.log}
          </pre>
        </div>
      )}
    </div>
  );
}

export function RunHistory({ runs, loading, onRefresh }: {
  runs: Run[] | null; loading: boolean; onRefresh: () => void;
}) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
        <h3 className="text-sm font-semibold text-white">Run History</h3>
        <button onClick={onRefresh} disabled={loading}
          className="text-xs text-blue-400 hover:text-blue-300 disabled:text-gray-600">
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>
      {!runs || runs.length === 0 ? (
        <p className="px-4 py-6 text-sm text-gray-500 text-center">
          {runs === null ? "Loading…" : "No runs yet — click Run Bot Now, or wait for the next scheduled run."}
        </p>
      ) : (
        <div>
          {runs.map((run, i) => (
            <RunRow key={run.id} run={run} defaultOpen={i === 0 && run.status !== "success"} />
          ))}
        </div>
      )}
    </div>
  );
}
