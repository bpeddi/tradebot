import {
  createContext, useCallback, useContext, useEffect, useState, type ReactNode,
} from "react";
import { clearToken, getToken, setToken } from "../utils/apiFetch";

interface AuthState {
  token: string | null;
  username: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (token: string, username: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthState>({
  token: null, username: null, isAuthenticated: false, isLoading: true,
  login: () => {}, logout: () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState]  = useState<string | null>(getToken);
  const [username, setUsername] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const logout = useCallback(() => {
    clearToken();
    setTokenState(null);
    setUsername(null);
    setIsLoading(false);
  }, []);

  const login = useCallback((newToken: string, newUsername: string) => {
    setToken(newToken);
    setTokenState(newToken);
    setUsername(newUsername);
    setIsLoading(false);
  }, []);

  // Listen for 401s fired by apiFetch from anywhere in the app
  useEffect(() => {
    window.addEventListener("auth:logout", logout);
    return () => window.removeEventListener("auth:logout", logout);
  }, [logout]);

  // On mount: validate any stored token with /api/auth/me
  useEffect(() => {
    const stored = getToken();
    if (!stored) { setIsLoading(false); return; }
    fetch("/api/auth/me", { headers: { Authorization: `Bearer ${stored}` } })
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(d => { setUsername(d.username); setIsLoading(false); })
      .catch(() => { clearToken(); setTokenState(null); setIsLoading(false); });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <AuthContext.Provider value={{
      token, username,
      isAuthenticated: !!token && !!username,
      isLoading,
      login, logout,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
