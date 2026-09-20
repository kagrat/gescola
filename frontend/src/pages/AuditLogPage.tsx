import { useEffect, useState } from "react";
import { api } from "../lib/api";

interface AuditLogEntry {
  id: string;
  actor_user_id: string | null;
  action: string;
  target_type: string;
  target_id: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

const ACTION_LABELS: Record<string, string> = {
  "auth.login_success": "Connexion réussie",
  "auth.account_locked": "Compte verrouillé (échecs répétés)",
  "auth.mfa_enabled": "MFA activé",
  "auth.mfa_disabled": "MFA désactivé",
  "auth.mfa_login_success": "Connexion MFA réussie",
  "auth.mfa_code_rejected": "Code MFA rejeté",
  "grade.lock_term": "Verrouillage des notes d'une période",
  "grade.override_after_lock": "Modification d'une note verrouillée",
  "guardian_link.create": "Rattachement parent créé",
  "invoice.reminder_sent": "Relance de facture envoyée",
  "canteen.subscribe": "Abonnement cantine créé",
  "library.loan_created": "Emprunt de livre",
};

export default function AuditLogPage() {
  const [logs, setLogs] = useState<AuditLogEntry[] | null>(null);

  useEffect(() => {
    api.get<AuditLogEntry[]>("/audit-logs").then(setLogs);
  }, []);

  return (
    <div className="px-10 py-10 max-w-4xl">
      <h1 className="font-display text-3xl font-medium text-ink">Journal d'audit</h1>
      <p className="text-sm text-ink/55 mt-1">Historique des actions sensibles de l'établissement (100 dernières).</p>

      <div className="mt-8 border border-line rounded bg-white overflow-hidden">
        <table className="w-full text-[14px]">
          <thead>
            <tr>
              <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-4 border-b border-line">Date</th>
              <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-4 border-b border-line">Action</th>
              <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-4 border-b border-line">Cible</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {logs === null && (
              <tr><td colSpan={3} className="px-4 py-6 text-ink/50">Chargement…</td></tr>
            )}
            {logs?.length === 0 && (
              <tr><td colSpan={3} className="px-4 py-6 text-ink/50">Aucune entrée pour l'instant.</td></tr>
            )}
            {logs?.map((log) => (
              <tr key={log.id}>
                <td className="px-4 py-2.5 text-ink/60 whitespace-nowrap">
                  {new Date(log.created_at).toLocaleString("fr-FR")}
                </td>
                <td className="px-4 py-2.5 text-ink">{ACTION_LABELS[log.action] ?? log.action}</td>
                <td className="px-4 py-2.5 text-ink/50">{log.target_type}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
