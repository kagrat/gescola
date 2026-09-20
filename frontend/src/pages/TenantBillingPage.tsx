import { useEffect, useState, type FormEvent } from "react";
import { useParams, Link } from "react-router-dom";
import { api, ApiError } from "../lib/api";
import StatusPill from "../components/StatusPill";

interface Tenant {
  id: string;
  name: string;
  code: string;
}
interface Plan {
  id: string;
  name: string;
  code: string;
  price_per_month: number;
}
interface Subscription {
  id: string;
  tenant_id: string;
  plan: Plan;
  status: string;
  effective_status: string;
  trial_ends_at: string | null;
  current_period_end: string | null;
}
interface Invoice {
  id: string;
  period_start: string;
  period_end: string;
  amount_due: number;
  due_date: string;
  status: string;
  amount_paid: number;
  balance: number;
}

const STATUS_LABELS: Record<string, { label: string; tone: "ok" | "warn" | "bad" | "neutral" }> = {
  trialing: { label: "Essai en cours", tone: "warn" },
  active: { label: "Actif", tone: "ok" },
  past_due: { label: "Retard de paiement", tone: "warn" },
  suspended: { label: "Suspendu", tone: "bad" },
  canceled: { label: "Résilié", tone: "neutral" },
};

const INVOICE_STATUS_LABELS: Record<string, { label: string; tone: "ok" | "warn" | "bad" | "neutral" }> = {
  pending: { label: "En attente", tone: "warn" },
  paid: { label: "Payée", tone: "ok" },
  overdue: { label: "En retard", tone: "bad" },
  cancelled: { label: "Annulée", tone: "neutral" },
};

export default function TenantBillingPage() {
  const { tenantId } = useParams<{ tenantId: string }>();
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [subscription, setSubscription] = useState<Subscription | null | undefined>(undefined);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [payingInvoice, setPayingInvoice] = useState<Invoice | null>(null);

  function reload() {
    if (!tenantId) return;
    api.get<Tenant[]>("/tenants").then((list) => setTenant(list.find((t) => t.id === tenantId) ?? null));
    api.get<Plan[]>("/platform/plans").then(setPlans);
    api
      .get<Subscription>(`/platform/tenants/${tenantId}/subscription`)
      .then(setSubscription)
      .catch(() => setSubscription(null));
    api.get<Invoice[]>(`/platform/tenants/${tenantId}/invoices`).then(setInvoices).catch(() => setInvoices([]));
  }
  useEffect(reload, [tenantId]);

  async function handleStartSubscription() {
    setError(null);
    try {
      await api.post(`/platform/tenants/${tenantId}/subscription`);
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible de démarrer l'abonnement.");
    }
  }

  async function handleUpdateSubscription(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    const form = new FormData(e.currentTarget);
    const planId = form.get("plan_id");
    const status = form.get("status");
    try {
      await api.patch(`/platform/tenants/${tenantId}/subscription`, {
        plan_id: planId || undefined,
        status: status || undefined,
      });
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible de mettre à jour l'abonnement.");
    }
  }

  async function handleGenerateInvoice() {
    setError(null);
    try {
      await api.post(`/platform/tenants/${tenantId}/invoices/generate`);
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible de générer la facture.");
    }
  }

  async function handlePay(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!payingInvoice) return;
    setError(null);
    const form = new FormData(e.currentTarget);
    try {
      await api.post("/platform/payments", {
        invoice_id: payingInvoice.id,
        amount: Number(form.get("amount")),
        method: form.get("method"),
        reference: form.get("reference") || null,
      });
      setPayingInvoice(null);
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible d'enregistrer le paiement.");
    }
  }

  if (!tenant) return <div className="px-10 py-10 text-ink/40">Chargement…</div>;

  const statusInfo = subscription ? STATUS_LABELS[subscription.effective_status] : null;

  return (
    <div>
      <div className="px-10 py-8 border-b border-line">
        <Link to="/" className="text-sm text-ink/40 hover:text-ink transition">← Établissements</Link>
        <h1 className="font-display text-[21px] font-bold text-ink mt-1.5">{tenant.name}</h1>
        <p className="text-[12.5px] text-ink/60 mt-0.5">{tenant.code}</p>
      </div>

      <div className="px-10 py-8 max-w-3xl">
        {error && <p className="text-sm text-brick mb-4">{error}</p>}

        <section>
          <h2 className="font-display text-lg text-ink mb-3">Abonnement</h2>

          {subscription === undefined && <p className="text-sm text-ink/40">Chargement…</p>}

          {subscription === null && (
            <div className="border border-line rounded bg-white p-5">
              <p className="text-sm text-ink/60 mb-3">Aucun abonnement suivi pour cet établissement — l'accès n'est pas restreint.</p>
              <button onClick={handleStartSubscription} className="rounded bg-navy text-paper text-sm font-medium px-4 py-2 hover:bg-navy-light transition">
                Démarrer un essai
              </button>
            </div>
          )}

          {subscription && (
            <div className="border border-line rounded bg-white p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-ink">{subscription.plan.name} — {subscription.plan.price_per_month.toLocaleString("fr-FR")} F/mois</p>
                  {subscription.trial_ends_at && (
                    <p className="text-xs text-ink/50 mt-1">Essai jusqu'au {subscription.trial_ends_at}</p>
                  )}
                </div>
                {statusInfo && <StatusPill label={statusInfo.label} tone={statusInfo.tone} />}
              </div>

              <form onSubmit={handleUpdateSubscription} className="mt-4 pt-4 border-t border-line grid sm:grid-cols-3 gap-3 items-end">
                <div>
                  <label className="block text-xs font-medium text-ink/60 mb-1.5">Changer de plan</label>
                  <select name="plan_id" defaultValue="" className="w-full rounded border border-line bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy">
                    <option value="">— Ne pas changer —</option>
                    {plans.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-ink/60 mb-1.5">Changer de statut</label>
                  <select name="status" defaultValue="" className="w-full rounded border border-line bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy">
                    <option value="">— Ne pas changer —</option>
                    <option value="active">Actif</option>
                    <option value="past_due">Retard de paiement</option>
                    <option value="suspended">Suspendu</option>
                    <option value="canceled">Résilié</option>
                  </select>
                </div>
                <button type="submit" className="rounded border border-navy text-navy text-sm font-medium px-4 py-2 hover:bg-navy/5 transition">
                  Appliquer
                </button>
              </form>
            </div>
          )}
        </section>

        {subscription && (
          <section className="mt-10 mb-16">
            <div className="flex items-center justify-between">
              <h2 className="font-display text-lg text-ink">Factures</h2>
              <button onClick={handleGenerateInvoice} className="rounded bg-navy text-paper text-sm font-medium px-4 py-2 hover:bg-navy-light transition">
                Générer la facture du mois
              </button>
            </div>

            <div className="mt-4 border border-line rounded bg-white overflow-hidden">
              <table className="w-full text-[14.5px]">
                <thead>
                  <tr>
                    <Th>Période</Th>
                    <Th>Montant</Th>
                    <Th>Solde</Th>
                    <Th>Statut</Th>
                    <Th></Th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {invoices.length === 0 && <tr><td colSpan={5} className="px-5 py-6 text-ink/40">Aucune facture.</td></tr>}
                  {invoices.map((inv) => {
                    const st = INVOICE_STATUS_LABELS[inv.status];
                    return (
                      <tr key={inv.id}>
                        <td className="px-5 py-3 text-ink">{inv.period_start} → {inv.period_end}</td>
                        <td className="px-5 py-3 text-ink/60">{inv.amount_due.toLocaleString("fr-FR")} F</td>
                        <td className={`px-5 py-3 font-medium ${inv.balance > 0 ? "text-brick" : "text-pass"}`}>{inv.balance.toLocaleString("fr-FR")} F</td>
                        <td className="px-5 py-3">{st && <StatusPill label={st.label} tone={st.tone} />}</td>
                        <td className="px-5 py-3 text-right">
                          {inv.balance > 0 && (
                            <button onClick={() => setPayingInvoice(inv)} className="text-navy text-sm underline underline-offset-2 hover:text-navy-light">
                              Encaisser
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>

      {payingInvoice && (
        <div className="fixed inset-0 bg-ink/40 flex items-center justify-center z-50 px-4">
          <div className="bg-white rounded max-w-sm w-full p-6">
            <h3 className="font-display text-lg text-ink">Encaisser — solde {payingInvoice.balance.toLocaleString("fr-FR")} F</h3>
            <form onSubmit={handlePay} className="mt-4 space-y-3">
              <div>
                <label className="block text-sm font-medium text-ink/80 mb-1.5">Montant reçu (FCFA)</label>
                <input name="amount" type="number" min="1" required defaultValue={payingInvoice.balance}
                  className="w-full rounded border border-line bg-white px-3.5 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy" />
              </div>
              <div>
                <label className="block text-sm font-medium text-ink/80 mb-1.5">Moyen de paiement</label>
                <select name="method" required className="w-full rounded border border-line bg-white px-3.5 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy">
                  <option value="mobile_money">Mobile money</option>
                  <option value="bank_transfer">Virement bancaire</option>
                  <option value="cash">Espèces</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-ink/80 mb-1.5">Référence (optionnel)</label>
                <input name="reference" className="w-full rounded border border-line bg-white px-3.5 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy" />
              </div>
              {error && <p className="text-sm text-brick">{error}</p>}
              <div className="flex gap-2 pt-1">
                <button type="submit" className="rounded bg-ochre text-navy-deep text-sm font-medium px-4 py-2 hover:bg-ochre-dark transition">
                  Confirmer
                </button>
                <button type="button" onClick={() => setPayingInvoice(null)} className="text-sm text-ink/60 px-2">
                  Annuler
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

function Th({ children }: { children?: React.ReactNode }) {
  return (
    <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-5 pb-2.5 pt-4 border-b border-line">
      {children}
    </th>
  );
}
