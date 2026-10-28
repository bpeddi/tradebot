import { useState, type FormEvent } from "react";
import { useAuth } from "../../context/AuthContext";

type Mode = "login" | "register";

export function LoginPage() {
  const { login } = useAuth();
  const [mode, setMode]         = useState<Mode>("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError]       = useState<string | null>(null);
  const [loading, setLoading]   = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await fetch(`/api/auth/${mode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.detail ?? "Authentication failed"); return; }
      login(data.access_token, username);
    } catch {
      setError("Network error — is the server running?");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-[#0e1117]">
      <div className="w-full max-w-sm px-6 py-8 bg-gray-900 border border-gray-800 rounded-xl shadow-xl">
        <h1 className="text-xl font-bold text-white mb-1 tracking-tight">mytradebot</h1>
        <p className="text-sm text-gray-500 mb-6">
          {mode === "login" ? "Sign in to your dashboard" : "Create the admin account (one-time setup)"}
        </p>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <input
            type="text"
            placeholder="Username"
            value={username}
            onChange={e => setUsername(e.target.value)}
            required
            autoComplete="username"
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5
              text-white placeholder:text-gray-600 focus:outline-none focus:border-blue-500
              text-sm transition-colors"
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5
              text-white placeholder:text-gray-600 focus:outline-none focus:border-blue-500
              text-sm transition-colors"
          />

          {error && (
            <div className="px-3 py-2 bg-red-900/40 border border-red-700 rounded-lg text-red-300 text-sm">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !username || !password}
            className="mt-1 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500
              disabled:bg-gray-700 disabled:text-gray-500 text-white font-semibold
              text-sm transition-colors"
          >
            {loading ? "Please wait…" : mode === "login" ? "Sign In" : "Create Account"}
          </button>
        </form>

        <p className="mt-5 text-center text-xs text-gray-600">
          {mode === "login" ? "First time here? " : "Already have an account? "}
          <button
            onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(null); }}
            className="text-blue-400 hover:text-blue-300 transition-colors"
          >
            {mode === "login" ? "Set up admin account" : "Sign in"}
          </button>
        </p>
      </div>
    </div>
  );
}
