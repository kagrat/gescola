import { useState, type FormEvent } from "react";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../auth/AuthContext";

export default function SecurityPage() {
  const { user, refreshUser } = useAuth();
  const [step, setStep] = useState<"idle" | "setup" | "disable">("idle");
  const [secret, setSecret] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function startSetup() {
    setError(null);
    setSuccess(null);
    try {
      const resp = await api.post<{ secret: string; provisioning_uri: string }>("/auth/mfa/setup");
      setSecret(resp.secret);
      setStep("setup");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible de démarrer l'activation.");
    }
  }

  async function confirmSetup(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/auth/mfa/confirm", { code });
      setSuccess("Authentification à deux facteurs activée.");
      setStep("idle");
      setCode("");
      setSecret(null);
      await refreshUser();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Code invalide.");
    }
  }

  async function disable(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/auth/mfa/disable", { code });
      setSuccess("Authentification à deux facteurs désactivée.");
      setStep("idle");
      setCode("");
      await refreshUser();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Code invalide.");
    }
  }

  return (
    <div className="px-10 py-10 max-w-2xl">
      <h1 className="font-display text-3xl font-medium text-ink">Sécurité du compte</h1>
      <p className="text-sm text-ink/55 mt-1">{user?.email}</p>

      <section className="mt-8 border border-line rounded bg-white p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-display text-lg text-ink">Authentification à deux facteurs</h2>
            <p className="text-sm text-ink/55 mt-1">
              {user?.mfa_enabled
                ? "Activée — un code est demandé à chaque connexion, en plus du mot de passe."
                : "Recommandée pour les comptes Direction et Super Administrateur."}
            </p>
          </div>
          <span className={`text-xs uppercase tracking-wide px-2.5 py-1 rounded ${user?.mfa_enabled ? "bg-pass/10 text-pass" : "bg-ink/5 text-ink/50"}`}>
            {user?.mfa_enabled ? "Activée" : "Désactivée"}
          </span>
        </div>

        {success && <p className="mt-4 text-sm text-pass">{success}</p>}
        {error && step === "idle" && <p className="mt-4 text-sm text-brick">{error}</p>}

        {step === "idle" && (
          <div className="mt-4">
            {!user?.mfa_enabled ? (
              <button onClick={startSetup} className="rounded bg-navy text-paper text-sm font-medium px-4 py-2 hover:bg-navy-light transition">
                Activer le MFA
              </button>
            ) : (
              <button onClick={() => setStep("disable")} className="rounded border border-brick text-brick text-sm font-medium px-4 py-2 hover:bg-brick/5 transition">
                Désactiver le MFA
              </button>
            )}
          </div>
        )}

        {step === "setup" && secret && (
          <form onSubmit={confirmSetup} className="mt-4 space-y-4">
            <div className="bg-paper border border-line rounded p-4">
              <p className="text-sm text-ink/70 mb-2">
                Ajoutez ce compte dans votre application d'authentification (Google Authenticator, Authy…) en saisissant la clé manuellement :
              </p>
              <p className="font-mono text-sm tracking-wider bg-white border border-line rounded px-3 py-2 inline-block">{secret}</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-ink/80 mb-1.5">Code affiché par l'application</label>
              <input
                value={code} onChange={(e) => setCode(e.target.value)} maxLength={6} required autoFocus
                className="w-full max-w-[160px] rounded border border-line bg-white px-3.5 py-2 text-[18px] tracking-[0.3em] text-center focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy"
                placeholder="000000"
              />
            </div>
            {error && <p className="text-sm text-brick">{error}</p>}
            <div className="flex gap-2">
              <button type="submit" className="rounded bg-ochre text-navy-deep text-sm font-medium px-4 py-2 hover:bg-ochre-dark transition">
                Confirmer l'activation
              </button>
              <button type="button" onClick={() => { setStep("idle"); setSecret(null); setCode(""); }} className="text-sm text-ink/50 px-2">
                Annuler
              </button>
            </div>
          </form>
        )}

        {step === "disable" && (
          <form onSubmit={disable} className="mt-4 space-y-4">
            <p className="text-sm text-ink/70">Confirmez avec un code actuel de votre application d'authentification.</p>
            <input
              value={code} onChange={(e) => setCode(e.target.value)} maxLength={6} required autoFocus
              className="w-full max-w-[160px] rounded border border-line bg-white px-3.5 py-2 text-[18px] tracking-[0.3em] text-center focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy"
              placeholder="000000"
            />
            {error && <p className="text-sm text-brick">{error}</p>}
            <div className="flex gap-2">
              <button type="submit" className="rounded bg-brick text-white text-sm font-medium px-4 py-2 hover:bg-brick/90 transition">
                Confirmer la désactivation
              </button>
              <button type="button" onClick={() => { setStep("idle"); setCode(""); }} className="text-sm text-ink/50 px-2">
                Annuler
              </button>
            </div>
          </form>
        )}
      </section>
    </div>
  );
}
