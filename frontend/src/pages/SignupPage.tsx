import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function SignupPage() {
  const { signup, error } = useAuth();
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    const form = new FormData(e.currentTarget);
    try {
      await signup({
        school_name: String(form.get("school_name")),
        admin_full_name: String(form.get("admin_full_name")),
        admin_email: String(form.get("admin_email")),
        admin_password: String(form.get("admin_password")),
      });
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
            « Votre établissement en ligne en moins de deux minutes — 14 jours d'essai gratuit, sans carte bancaire. »
          </p>
          <p className="mt-4 text-[#8C93A3] text-[12.5px] leading-relaxed">
            Élèves, notes, présences, finances et communication — tout ce dont votre équipe a besoin, dès aujourd'hui.
          </p>
        </div>

        <div className="relative text-[#8C93A3] text-sm">Réseau d'établissements · Bénin</div>
      </div>

      <div className="flex items-center justify-center px-6 py-14">
        <div className="w-full max-w-sm">
          <div className="lg:hidden flex items-center gap-2.5 mb-8">
            <span className="w-8 h-8 rounded-sm bg-navy flex items-center justify-center font-display font-semibold text-paper">
              G
            </span>
            <span className="font-display text-lg tracking-tight text-navy">GESCOLA</span>
          </div>

          <h1 className="font-display text-2xl font-medium text-ink">Créer mon établissement</h1>
          <p className="mt-1.5 text-sm text-ink/60">Essai gratuit de 14 jours, aucune carte requise.</p>

          <form onSubmit={handleSubmit} className="mt-7 space-y-4">
            <Field name="school_name" label="Nom de l'établissement" placeholder="École La Colombe" required />
            <Field name="admin_full_name" label="Votre nom complet" placeholder="Mme Directrice" required />
            <Field name="admin_email" label="Adresse e-mail" type="email" placeholder="directeur@ecole.bj" required />
            <div>
              <Field name="admin_password" label="Mot de passe" type="password" placeholder="••••••••••" required />
              <p className="mt-1.5 text-xs text-ink/40">
                Au moins 10 caractères, avec majuscule, minuscule, chiffre et caractère spécial.
              </p>
            </div>

            {error && (
              <p role="alert" className="text-sm text-brick bg-brick/10 border border-brick/20 rounded px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="submit" disabled={submitting}
              className="w-full rounded bg-ochre text-navy-deep font-medium text-[15px] py-2.5 mt-2 hover:bg-ochre-dark transition disabled:opacity-60"
            >
              {submitting ? "Création…" : "Démarrer mon essai gratuit"}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-ink/50">
            Déjà un compte ?{" "}
            <Link to="/connexion" className="text-navy font-medium hover:underline">
              Se connecter
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}

function Field({
  name, label, type = "text", placeholder, required,
}: { name: string; label: string; type?: string; placeholder?: string; required?: boolean }) {
  return (
    <div>
      <label htmlFor={name} className="block text-sm font-medium text-ink/80 mb-1.5">
        {label}
      </label>
      <input
        id={name} name={name} type={type} required={required} placeholder={placeholder}
        className="w-full rounded border border-line bg-white px-3.5 py-2.5 text-[15px] text-ink placeholder:text-ink/30 focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy transition"
      />
    </div>
  );
}
