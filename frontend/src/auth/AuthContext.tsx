import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, ApiError, setTokens, getAccessToken } from "../lib/api";

interface CurrentUser {
  id: string;
  tenant_id: string | null;
  role:
    | "super_admin"
    | "network_admin"
    | "school_admin"
    | "censor"
    | "supervisor"
    | "accountant"
    | "staff"
    | "teacher"
    | "parent";
  email: string;
  mfa_enabled: boolean;
}

interface LoginResult {
  mfaRequired: boolean;
  mfaToken?: string;
}

interface AuthState {
  user: CurrentUser | null;
  loading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<LoginResult>;
  verifyMfa: (mfaToken: string, code: string) => Promise<void>;
  signup: (data: SignupData) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

interface SignupData {
  school_name: string;
  admin_full_name: string;
  admin_email: string;
  admin_password: string;
}

const AuthContext = createContext<AuthState | null>(null);

interface LoginResponse {
  mfa_required: boolean;
  mfa_token: string | null;
  access_token: string | null;
  refresh_token: string | null;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadMe() {
    const me = await api.get<CurrentUser>("/auth/me");
    setUser(me);
  }

  useEffect(() => {
    if (!getAccessToken()) {
      setLoading(false);
      return;
    }
    loadMe()
      .catch(() => setTokens(null, null))
      .finally(() => setLoading(false));
  }, []);

  async function login(email: string, password: string): Promise<LoginResult> {
    setError(null);
    try {
      const resp = await api.post<LoginResponse>("/auth/login", { email, password });
      if (resp.mfa_required && resp.mfa_token) {
        return { mfaRequired: true, mfaToken: resp.mfa_token };
      }
      setTokens(resp.access_token!, resp.refresh_token!);
      await loadMe();
      return { mfaRequired: false };
    } catch (e) {
      setErrorFromException(e);
      throw e;
    }
  }

  async function verifyMfa(mfaToken: string, code: string) {
    setError(null);
    try {
      const tokens = await api.post<{ access_token: string; refresh_token: string }>("/auth/mfa/login-verify", {
        mfa_token: mfaToken,
        code,
      });
      setTokens(tokens.access_token, tokens.refresh_token);
      await loadMe();
    } catch (e) {
      setErrorFromException(e);
      throw e;
    }
  }

  function setErrorFromException(e: unknown) {    if (e instanceof ApiError) {
      if (e.status === 423) setError("Compte temporairement verrouillé suite à plusieurs échecs. Réessayez plus tard.");
      else if (e.status === 429) setError("Trop de tentatives. Merci de patienter avant de réessayer.");
      else if (e.status === 401) setError("Code invalide ou identifiants incorrects.");
      else setError(e.message);
    } else {
      setError("Impossible de contacter le serveur.");
    }
  }

  async function signup(data: SignupData) {
    setError(null);
    try {
      const resp = await api.post<{ access_token: string; refresh_token: string }>("/auth/signup", data);
      setTokens(resp.access_token, resp.refresh_token);
      await loadMe();
    } catch (e) {
      setErrorFromException(e);
      throw e;
    }
  }

  function logout() {
    setTokens(null, null);
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, error, login, verifyMfa, signup, logout, refreshUser: loadMe }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth doit être utilisé à l'intérieur de <AuthProvider>");
  return ctx;
}
