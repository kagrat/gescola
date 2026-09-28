import { useState } from "react";

/** Affiche UNE SEULE FOIS un mot de passe provisoire généré par le serveur. */
export default function TemporaryPasswordDialog({ name, password, onClose }: { name: string; password: string; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(password);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }
  return (
    <div className="fixed inset-0 bg-ink/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg w-full max-w-md p-6" role="dialog" aria-modal="true" aria-label="Mot de passe provisoire">
        <h3 className="font-display text-lg text-ink">Mot de passe provisoire</h3>
        <p className="text-sm text-ink/60 mt-1">Compte de <b className="text-ink">{name}</b>. Ses sessions en cours ont été fermées.</p>
        <div className="mt-4 flex items-center gap-3 border border-line rounded bg-paper px-4 py-3">
          <code data-testid="temporary-password" className="flex-1 text-[17px] tracking-wide font-semibold text-ink select-all">{password}</code>
          <button onClick={copy} className="text-sm text-navy underline underline-offset-2">{copied ? "Copié" : "Copier"}</button>
        </div>
        <p className="mt-3 text-xs text-ochre-dark bg-ochre/10 border border-ochre/20 rounded px-3 py-2">
          Communiquez-le en personne. Il ne sera <b>plus jamais affiché</b> : la personne devra le remplacer dès sa première connexion.
        </p>
        <div className="mt-5 flex justify-end">
          <button onClick={onClose} className="rounded bg-navy text-paper text-sm font-medium px-5 py-2 hover:bg-navy-light transition">J'ai noté le mot de passe</button>
        </div>
      </div>
    </div>
  );
}
