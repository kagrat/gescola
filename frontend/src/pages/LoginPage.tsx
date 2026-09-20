import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function LoginPage() {
  const { login, verifyMfa, error } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      const result = await login(email, password);
      if (result.mfaRequired && result.mfaToken) {
        setMfaToken(result.mfaToken);
      } else {
        navigate("/");
      }
    } catch {
      // erreur déjà exposée via le contexte d'auth
    } finally {
      setSubmitting(false);
    }
  }

  async function handleMfaSubmit(e: FormEvent) {
    e.preventDefault();
    if (!mfaToken) return;
    setSubmitting(true);
    try {
      await verifyMfa(mfaToken, code);
      navigate("/");
    } catch {
      // erreur déjà exposée via le contexte d'auth
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen grid lg:grid-cols-[1.1fr_1fr]">
      <div className="hidden lg:flex flex-col justify-between bg-navy-deep text-paper px-16 py-14 relative overflow-hidden">
        <div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(circle at 25% 20%, rgba(62,143,217,.20), transparent 45%), radial-gradient(circle at 80% 80%, rgba(47,166,113,.16), transparent 50%)",
          }}
        />
        <div className="relative">
          <div className="flex items-center gap-2.5">
            <span className="w-8 h-8 rounded-sm bg-ochre flex items-center justify-center font-display font-semibold text-navy-deep">
              G
            </span>
            <span className="font-display text-lg tracking-tight">GESCOLA</span>
          </div>
        </div>

        <div className="relative max-w-md">
          <p className="font-display text-[25px] leading-[1.4] font-semibold">
            "Chaque cahier, chaque frais, chaque élève — un seul tableau de bord."
          </p>
          <p className="mt-4 text-[#8C93A3] text-[12.5px] leading-relaxed">
            Conçu pour les réalités du terrain : ça continue de fonctionner sans réseau,
            et ça remonte dès que la connexion revient.
          </p>
        </div>

        <div className="relative text-[#8C93A3] text-sm">Réseau d'établissements · Bénin</div>
      </div>

      <div className="flex items-center justify-center px-6 py-16">
        <div className="w-full max-w-sm">
          <div className="lg:hidden flex items-center gap-2.5 mb-10">
            <span className="w-8 h-8 rounded-sm bg-navy flex items-center justify-center font-display font-semibold text-paper">
              G
            </span>
            <span className="font-display text-lg tracking-tight text-navy">GESCOLA</span>
          </div>

          {!mfaToken ? (
            <>
              <h1 className="font-display text-2xl font-medium text-ink">Se connecter</h1>
              <p className="mt-1.5 text-sm text-ink/60">Accédez à l'espace de votre établissement.</p>

              <form onSubmit={handleSubmit} className="mt-8 space-y-4">
                <div>
                  <label htmlFor="email" className="block text-sm font-medium text-ink/80 mb-1.5">
                    Adresse e-mail
                  </label>
                  <input
                    id="email" type="email" required autoComplete="email" value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full rounded border border-line bg-white px-3.5 py-2.5 text-[15px] text-ink placeholder:text-ink/30 focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy transition"
                    placeholder="directeur@ecole.bj"
                  />
                </div>
                <div>
                  <label htmlFor="password" className="block text-sm font-medium text-ink/80 mb-1.5">
                    Mot de passe
                  </label>
                  <input
                    id="password" type="password" required autoComplete="current-password" value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full rounded border border-line bg-white px-3.5 py-2.5 text-[15px] text-ink placeholder:text-ink/30 focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy transition"
                    placeholder="••••••••••"
                  />
                </div>
                {error && (
                  <p role="alert" className="text-sm text-brick bg-brick/10 border border-brick/20 rounded px-3 py-2">
                    {error}
                  </p>
                )}
                <button
                  type="submit" disabled={submitting}
                  className="w-full rounded bg-navy text-paper font-medium text-[15px] py-2.5 mt-2 hover:bg-navy-light transition disabled:opacity-60"
                >
                  {submitting ? "Connexion…" : "Se connecter"}
                </button>
              </form>
            </>
          ) : (
            <>
              <h1 className="font-display text-2xl font-medium text-ink">Vérification en deux étapes</h1>
              <p className="mt-1.5 text-sm text-ink/60">
                Entrez le code à 6 chiffres généré par votre application d'authentification.
              </p>
              <form onSubmit={handleMfaSubmit} className="mt-8 space-y-4">
                <div>
                  <label htmlFor="code" className="block text-sm font-medium text-ink/80 mb-1.5">
                    Code de vérification
                  </label>
                  <input
                    id="code" inputMode="numeric" pattern="[0-9]*" maxLength={6} required value={code}
                    onChange={(e) => setCode(e.target.value)} autoFocus
                    className="w-full rounded border border-line bg-white px-3.5 py-2.5 text-[20px] tracking-[0.3em] text-center text-ink focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy transition"
                    placeholder="000000"
                  />
                </div>
                {error && (
                  <p role="alert" className="text-sm text-brick bg-brick/10 border border-brick/20 rounded px-3 py-2">
                    {error}
                  </p>
                )}
                <button
                  type="submit" disabled={submitting}
                  className="w-full rounded bg-navy text-paper font-medium text-[15px] py-2.5 mt-2 hover:bg-navy-light transition disabled:opacity-60"
                >
                  {submitting ? "Vérification…" : "Valider"}
                </button>
                <button
                  type="button" onClick={() => setMfaToken(null)}
                  className="w-full text-sm text-ink/50 hover:text-ink transition"
                >
                  ← Retour
                </button>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
