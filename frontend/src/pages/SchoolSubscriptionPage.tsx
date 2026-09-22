import { useEffect, useState } from "react";
import { api } from "../lib/api";
import RequireRole from "../components/RequireRole";
import { CAN_VIEW_SCHOOL_SUBSCRIPTION } from "../lib/permissions";

interface Plan { name: string; price_per_month: number; max_students: number | null; }
interface Subscription {
  status: string; effective_status: string; trial_ends_at: string | null;
  current_period_end: string | null; plan: Plan;
}
interface Invoice {
  id: string; period_start: string; period_end: string; amount_due: number;
  due_date: string; status: string; amount_paid: number; balance: number;
}

const STATUS_LABELS: Record<string, { label: string; tone: "ok" | "warn" | "bad" | "neutral" }> = {
  trialing: { label: "Essai en cours", tone: "warn" },
  active: { label: "Actif", tone: "ok" },
  past_due: { label: "Retard de paiement", tone: "warn" },
  suspended: { label: "Suspendu", tone: "bad" },
  canceled: { label: "Résilié", tone: "neutral" },
};

function daysLeft(dateStr: string): number {
  const diff = new Date(dateStr).getTime() - new Date().setHours(0, 0, 0, 0);
  return Math.ceil(diff / (1000 * 60 * 60 * 24));
}

export default function SchoolSubscriptionPage() {
  return (
    <RequireRole roles={CAN_VIEW_SCHOOL_SUBSCRIPTION}>
      <SchoolSubscriptionPageContent />
    </RequireRole>
  );
}

function SchoolSubscriptionPageContent() {
  const [sub, setSub] = useState<Subscription | null | undefined>(undefined);
  const [invoices, setInvoices] = useState<Invoice[]>([]);

  useEffect(() => {
    api.get<Subscription>("/billing/me").then(setSub).catch(() => setSub(null));
    api.get<Invoice[]>("/billing/me/invoices").then(setInvoices).catch(() => setInvoices([]));
  }, []);

  const statusInfo = sub ? STATUS_LABELS[sub.effective_status] : null;
  const trialDays = sub?.trial_ends_at ? daysLeft(sub.trial_ends_at) : null;

  return (
    <div className="px-10 py-10 max-w-2xl">
      <h1 className="font-display text-3xl font-medium text-ink">Mon abonnement</h1>
      <p className="text-sm text-ink/55 mt-1">Statut de votre abonnement GESCOLA pour cet établissement.</p>

      {sub === undefined && <p className="mt-8 text-sm text-ink/40">Chargement…</p>}
      {sub === null && (
        <p className="mt-8 text-sm text-ink/40">
          Aucun abonnement suivi pour cet établissement — votre accès n'est pas restreint.
        </p>
      )}

      {sub && (
        <>
          <div className="mt-8 border border-line rounded bg-white p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-display text-lg text-ink">{sub.plan.name}</p>
                <p className="text-sm text-ink/60 mt-1">{sub.plan.price_per_month.toLocaleString("fr-FR")} F / mois</p>
              </div>
              {statusInfo && (
                <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${
                  statusInfo.tone === "ok" ? "bg-pass/10 text-[#1F7A52]" :
                  statusInfo.tone === "warn" ? "bg-sky/10 text-[#2568A3]" :
                  statusInfo.tone === "bad" ? "bg-brick/10 text-[#B03A32]" : "bg-ink/5 text-ink/50"
                }`}>
                  {statusInfo.label}
                </span>
              )}
            </div>

            {sub.effective_status === "trialing" && trialDays !== null && (
              <p className={`mt-4 text-sm ${trialDays <= 3 ? "text-brick font-medium" : "text-ink/60"}`}>
                {trialDays > 0
                  ? `${trialDays} jour${trialDays > 1 ? "s" : ""} restant${trialDays > 1 ? "s" : ""} avant la fin de l'essai gratuit.`
                  : "Votre essai gratuit se termine aujourd'hui."}
              </p>
            )}
            {sub.effective_status === "suspended" && (
              <p className="mt-4 text-sm text-brick font-medium">
                L'accès est suspendu pour impayé. Contactez l'éditeur GESCOLA pour régulariser votre situation.
              </p>
            )}
            {sub.effective_status === "past_due" && (
              <p className="mt-4 text-sm text-ochre-dark font-medium">
                Une facture est en retard de paiement. Contactez l'éditeur GESCOLA pour éviter une suspension.
              </p>
            )}
          </div>

          <section className="mt-10 mb-16">
            <h2 className="font-display text-lg text-ink mb-3">Historique des factures</h2>
            <div className="border border-line rounded bg-white overflow-hidden">
              <table className="w-full text-[14.5px]">
                <thead>
                  <tr>
                    <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-3 border-b border-line">Période</th>
                    <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-3 border-b border-line">Montant</th>
                    <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-3 border-b border-line">Statut</th>
                  </tr>
                </thead>
                <tbody>
                  {invoices.length === 0 && <tr><td colSpan={3} className="px-4 py-6 text-ink/40">Aucune facture pour l'instant.</td></tr>}
                  {invoices.map((inv) => (
                    <tr key={inv.id} className="border-b border-line last:border-none">
                      <td className="px-4 py-2.5 text-ink">{inv.period_start} → {inv.period_end}</td>
                      <td className="px-4 py-2.5 text-ink/60">{inv.amount_due.toLocaleString("fr-FR")} F</td>
                      <td className="px-4 py-2.5 text-ink/60">{inv.status === "paid" ? "Payée" : inv.status === "overdue" ? "En retard" : inv.status === "cancelled" ? "Annulée" : "En attente"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
