import { useState, type FormEvent } from "react";
import { apiJson } from "../../utils/apiFetch";

export function SettingsTab() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const inputClass = "bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white " +
    "focus:outline-none focus:border-blue-500";

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setMessage(null);
    setError(null);

    if (newPassword.length < 8) {
      setError("New password must be at least 8 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("New password and confirmation don't match.");
      return;
    }

    setSaving(true);
    try {
      await apiJson("/api/auth/password", {
        method: "PUT",
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      });
      setMessage("Password changed.");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-6 max-w-xl">
      <h2 className="text-lg font-semibold text-white mb-4">Settings</h2>
      <form onSubmit={submit} className="bg-gray-900 border border-gray-800 rounded-lg p-5 flex flex-col gap-4">
        <h3 className="text-sm font-semibold text-white">Change Password</h3>

        <label className="flex flex-col gap-1">
          <span className="text-xs text-gray-500">Current password</span>
          <input
            type="password"
            value={currentPassword}
            onChange={e => setCurrentPassword(e.target.value)}
            autoComplete="current-password"
            required
            className={inputClass}
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-xs text-gray-500">New password (min 8 characters)</span>
          <input
            type="password"
            value={newPassword}
            onChange={e => setNewPassword(e.target.value)}
            autoComplete="new-password"
            required
            className={inputClass}
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-xs text-gray-500">Confirm new password</span>
          <input
            type="password"
            value={confirmPassword}
            onChange={e => setConfirmPassword(e.target.value)}
            autoComplete="new-password"
            required
            className={inputClass}
          />
        </label>

        {message && <div className="text-sm text-green-400">{message}</div>}
        {error && <div className="text-sm text-red-400">{error}</div>}

        <button
          type="submit"
          disabled={saving}
          className="mt-2 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700
            disabled:text-gray-500 text-white font-semibold text-sm transition-colors"
        >
          {saving ? "Saving…" : "Change Password"}
        </button>
      </form>
    </div>
  );
}
