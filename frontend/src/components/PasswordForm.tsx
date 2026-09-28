import { useState, type FormEvent } from "react";
import { ApiError } from "../lib/api";
import { useAuth } from "../auth/AuthContext";

const inputCls = "w-full rounded border border-line bg-white px-3.5 py-2.5 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy transition";

/** Formulaire de changement de SON mot de passe — utilisé en changement volontaire (page Sécurité)
 *  et en changement obligatoire (mot de passe provisoire). */
export default function PasswordForm({ onDone }: { onDone?: () => void }) {
  const { changePassword } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setSuccess(false);
    const form = new FormData(e.currentTarget);
    const current = String(form.get("current_password") || "");
    const next = String(form.get("new_password") || "");
    if (next !== String(form.get("confirm_password") || "")) {
      setError("Les deux nouveaux mots de passe ne correspondent pas.");
      return;
    }
    setSubmitting(true);
    try {
      await changePassword(current, next);
      setSuccess(true);
      (e.target as HTMLFormElement).reset();
      onDone?.();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible de changer le mot de passe.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="current_password" className="block text-sm font-medium text-ink/80 mb-1.5">Mot de passe actuel</label>
        <input id="current_password" name="current_password" type="password" autoComplete="current-password" required className={inputCls} />
      </div>
      <div>
        <label htmlFor="new_password" className="block text-sm font-medium text-ink/80 mb-1.5">Nouveau mot de passe</label>
        <input id="new_password" name="new_password" type="password" autoComplete="new-password" required minLength={10} className={inputCls} />
        <p className="text-xs text-ink/45 mt-1">Au moins 10 caractères, avec majuscule, minuscule, chiffre et caractère spécial.</p>
      </div>
      <div>
        <label htmlFor="confirm_password" className="block text-sm font-medium text-ink/80 mb-1.5">Confirmer le nouveau mot de passe</label>
        <input id="confirm_password" name="confirm_password" type="password" autoComplete="new-password" required className={inputCls} />
      </div>
      {error && <p className="text-sm text-brick">{error}</p>}
      {success && <p className="text-sm text-pass">Mot de passe modifié. Vos autres sessions ont été fermées.</p>}
      <button type="submit" disabled={submitting} className="rounded bg-navy text-paper text-sm font-medium px-5 py-2.5 hover:bg-navy-light transition disabled:opacity-60">
        {submitting ? "Enregistrement…" : "Changer le mot de passe"}
      </button>
    </form>
  );
}
