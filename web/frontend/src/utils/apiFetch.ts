const TOKEN_KEY = "mtb_token";

export const getToken   = (): string | null => localStorage.getItem(TOKEN_KEY);
export const setToken   = (t: string): void  => { localStorage.setItem(TOKEN_KEY, t); };
export const clearToken = (): void           => { localStorage.removeItem(TOKEN_KEY); };

/**
 * Drop-in replacement for fetch() that injects the Authorization header
 * and fires "auth:logout" on 401 so AuthContext can react anywhere.
 */
export async function apiFetch(
  input: string,
  init: RequestInit = {},
): Promise<Response> {
  const token = getToken();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(input, { ...init, headers });

  if (response.status === 401) {
    clearToken();
    window.dispatchEvent(new Event("auth:logout"));
  }

  return response;
}

export async function apiJson<T = unknown>(input: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const res = await apiFetch(input, { ...init, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error((data as { detail?: string }).detail ?? `Request failed (${res.status})`);
  return data as T;
}
