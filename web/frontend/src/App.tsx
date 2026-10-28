import { useState } from "react";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { LoginPage } from "./components/auth/LoginPage";
import { DashboardTab } from "./components/dashboard/DashboardTab";
import { ConfigEditor } from "./components/config/ConfigEditor";
import { ScheduleEditor } from "./components/schedule/ScheduleEditor";
import { TradesTable } from "./components/trades/TradesTable";
import { SettingsTab } from "./components/settings/SettingsTab";

type Tab = "dashboard" | "config" | "schedule" | "trades" | "settings";

const TABS: { id: Tab; label: string }[] = [
  { id: "dashboard", label: "Dashboard" },
  { id: "config",    label: "Config" },
  { id: "schedule",  label: "Schedule" },
  { id: "trades",    label: "Trades" },
  { id: "settings",  label: "Settings" },
];

function AppInner() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const { username, logout } = useAuth();

  return (
    <div className="min-h-screen bg-[#0e1117] text-gray-200">
      <header className="sticky top-0 z-10 flex items-center gap-1 px-4 py-2 border-b border-gray-800 bg-[#0e1117]">
        <span className="text-lg font-semibold text-white mr-4">mytradebot</span>
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
              tab === t.id ? "bg-blue-600 text-white" : "text-gray-400 hover:text-white hover:bg-gray-800"
            }`}
          >
            {t.label}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-2">
          <span className="text-xs text-gray-600">{username}</span>
          <button
            onClick={logout}
            className="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors
              bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-white border border-gray-700"
          >
            Sign Out
          </button>
        </div>
      </header>

      {/* The page itself scrolls naturally — no nested scroll containers. */}
      <main>
        {tab === "dashboard" && <DashboardTab />}
        {tab === "config" && <ConfigEditor />}
        {tab === "schedule" && <ScheduleEditor />}
        {tab === "trades" && <TradesTable />}
        {tab === "settings" && <SettingsTab />}
      </main>
    </div>
  );
}

function AuthGate() {
  const { isAuthenticated, isLoading, token } = useAuth();
  if (isLoading || (token && !isAuthenticated)) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-[#0e1117] text-gray-500 text-sm">
        Verifying session…
      </div>
    );
  }
  if (!isAuthenticated) return <LoginPage />;
  return <AppInner />;
}

export default function App() {
  return (
    <AuthProvider>
      <AuthGate />
    </AuthProvider>
  );
}
