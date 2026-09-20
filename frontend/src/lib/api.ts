const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

let accessToken: string | null = localStorage.getItem("gescola_access_token");
let refreshToken: string | null = localStorage.getItem("gescola_refresh_token");

export function setTokens(access: string | null, refresh: string | null) {
  accessToken = access;
  refreshToken = refresh;
  if (access && refresh) {
    localStorage.setItem("gescola_access_token", access);
    localStorage.setItem("gescola_refresh_token", refresh);
  } else {
    localStorage.removeItem("gescola_access_token");
    localStorage.removeItem("gescola_refresh_token");
  }
}

export function getAccessToken() {
  return accessToken;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}, retried = false): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

  const resp = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (resp.status === 401 && refreshToken && !retried) {
    // Tentative de rafraîchissement transparent du token avant d'abandonner.
    const refreshResp = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (refreshResp.ok) {
      const body = await refreshResp.json();
      setTokens(body.access_token, body.refresh_token);
      return request<T>(path, options, true);
    }
    setTokens(null, null);
  }

  if (!resp.ok) {
    let message = `Erreur ${resp.status}`;
    try {
      const body = await resp.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail)) message = body.detail.map((d: any) => d.message).join(" ");
    } catch {
      // réponse non-JSON : on garde le message générique
    }
    throw new ApiError(resp.status, message);
  }

  if (resp.status === 204) return undefined as T;
  return resp.json();
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
