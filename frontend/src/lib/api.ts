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

type RequestOptions = RequestInit & { responseType?: "json" | "blob" | "page" };

export interface Page<T> {
  items: T[];
  total: number;
}

async function request<T>(path: string, options: RequestOptions = {}, retried = false): Promise<T> {
  const { responseType = "json", ...fetchOptions } = options;
  const headers = new Headers(fetchOptions.headers);
  // Un envoi de fichier (FormData) doit laisser le navigateur écrire l'en-tête avec sa « boundary ».
  if (!(fetchOptions.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

  const resp = await fetch(`${API_BASE}${path}`, { ...fetchOptions, headers });

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
    // La session a pris fin côté serveur (compte désactivé, mot de passe changé ailleurs…) :
    // on prévient l'application pour qu'elle ramène à la connexion au lieu de laisser des écrans en erreur.
    window.dispatchEvent(new Event("gescola:session-ended"));
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
  if (responseType === "blob") return (await resp.blob()) as T;
  if (responseType === "page") {
    const items = await resp.json();
    return { items, total: Number(resp.headers.get("X-Total-Count") ?? items.length) } as T;
  }
  return resp.json();
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PUT", body: body ? JSON.stringify(body) : undefined }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  /** Liste paginée : renvoie la page et le total (en-tête X-Total-Count). */
  page: <T>(path: string) => request<Page<T>>(path, { method: "GET", responseType: "page" }),
  /** Envoi de fichier (multipart). */
  upload: <T>(path: string, form: FormData) => request<T>(path, { method: "POST", body: form }),
  /** Toutes les pages d'une liste, par blocs de 500 : pour les listes de sélection (jamais plus de 500 lignes par requête). */
  all: async <T>(path: string): Promise<T[]> => {
    const sep = path.includes("?") ? "&" : "?";
    const out: T[] = [];
    for (let offset = 0; offset < 100000; offset += 500) {
      const page = await request<Page<T>>(`${path}${sep}limit=500&offset=${offset}`, { method: "GET", responseType: "page" });
      out.push(...page.items);
      if (out.length >= page.total || page.items.length === 0) break;
    }
    return out;
  },
  /** Téléchargement authentifié d'un fichier (ex. PDF) — un simple lien <a href> n'enverrait pas le jeton. */
  blob: (path: string) => request<Blob>(path, { method: "GET", responseType: "blob" }),
};
