import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../lib/api";
import StatusPill from "../components/StatusPill";

interface Tenant {
  id: string;
  name: string;
  code: string;
  is_active: boolean;
  network_id: string | null;
}

interface Plan {
  id: string;
  name: string;
  code: string;
  price_per_month: number;
  max_students: number | null;
}

interface Subscription {
  id: string;
  tenant_id: string;
  plan: Plan;
  status: string;
  effective_status: string;
}

interface SchoolNetwork {
  id: string;
  name: string;
  code: string;
}

const STATUS_LABELS: Record<string, { label: string; tone: "ok" | "warn" | "bad" | "neutral" }> = {
  trialing: { label: "Essai en cours", tone: "warn" },
  active: { label: "Actif", tone: "ok" },
  past_due: { label: "Retard de paiement", tone: "warn" },
  suspended: { label: "Suspendu", tone: "bad" },
  canceled: { label: "Résilié", tone: "neutral" },
};

export default function SuperAdminPage() {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [subscriptions, setSubscriptions] = useState<Record<string, Subscription | null>>({});
  const [networks, setNetworks] = useState<SchoolNetwork[]>([]);
  const [showTenantForm, setShowTenantForm] = useState(false);
  const [showPlanForm, setShowPlanForm] = useState(false);
  const [showNetworkForm, setShowNetworkForm] = useState(false);
  const [adminFormForNetwork, setAdminFormForNetwork] = useState<string | null>(null);
  const [tenantError, setTenantError] = useState<string | null>(null);
  const [planError, setPlanError] = useState<string | null>(null);
  const [networkError, setNetworkError] = useState<string | null>(null);
  const [adminError, setAdminError] = useState<string | null>(null);
  const [adminSuccess, setAdminSuccess] = useState<string | null>(null);

  function reload() {
    api.get<Tenant[]>("/tenants").then((list) => {
      setTenants(list);
      list.forEach((t) => {
        api
          .get<Subscription>(`/platform/tenants/${t.id}/subscription`)
          .then((sub) => setSubscriptions((prev) => ({ ...prev, [t.id]: sub })))
          .catch(() => setSubscriptions((prev) => ({ ...prev, [t.id]: null })));
      });
    });
    api.get<Plan[]>("/platform/plans").then(setPlans);
    api.get<SchoolNetwork[]>("/networks").then(setNetworks);
  }
  useEffect(reload, []);

  async function handleCreateTenant(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setTenantError(null);
    const form = new FormData(e.currentTarget);
    try {
      await api.post("/tenants", {
        name: form.get("name"),
        code: form.get("code"),
        admin_full_name: form.get("admin_full_name"),
        admin_email: form.get("admin_email"),
        admin_password: form.get("admin_password"),
      });
      setShowTenantForm(false);
      reload();
    } catch (err) {
      setTenantError(err instanceof ApiError ? err.message : "Impossible de créer cet établissement.");
    }
  }

  async function handleCreatePlan(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setPlanError(null);
    const form = new FormData(e.currentTarget);
    try {
      await api.post("/platform/plans", {
        name: form.get("name"),
        code: form.get("code"),
        price_per_month: Number(form.get("price_per_month")),
        max_students: form.get("max_students") ? Number(form.get("max_students")) : null,
      });
      setShowPlanForm(false);
      reload();
    } catch (err) {
      setPlanError(err instanceof ApiError ? err.message : "Impossible de créer ce plan.");
    }
  }

  async function handleCreateNetwork(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setNetworkError(null);
    const form = new FormData(e.currentTarget);
    try {
      await api.post("/networks", { name: form.get("name"), code: form.get("code") });
      setShowNetworkForm(false);
      reload();
    } catch (err) {
      setNetworkError(err instanceof ApiError ? err.message : "Impossible de créer ce réseau.");
    }
  }

  async function handleCreateNetworkAdmin(e: FormEvent<HTMLFormElement>, networkId: string) {
    e.preventDefault();
    setAdminError(null);
    setAdminSuccess(null);
    const form = new FormData(e.currentTarget);
    try {
      await api.post(`/networks/${networkId}/admins`, {
        full_name: form.get("full_name"), email: form.get("email"), password: form.get("password"),
      });
      setAdminSuccess("Compte promoteur créé.");
      setAdminFormForNetwork(null);
    } catch (err) {
      setAdminError(err instanceof ApiError ? err.message : "Impossible de créer ce compte.");
    }
  }

  async function handleAssignTenant(tenantId: string, networkId: string) {
    if (!networkId) return;
    await api.post(`/networks/${networkId}/tenants/${tenantId}`);
    reload();
  }

  const activeSubs = Object.values(subscriptions).filter((s): s is Subscription => !!s);
  const mrr = activeSubs
    .filter((s) => s.effective_status === "active")
    .reduce((sum, s) => sum + s.plan.price_per_month, 0);
  const trialCount = activeSubs.filter((s) => s.effective_status === "trialing").length;

  return (
    <div>
      <div className="px-10 py-8 border-b border-line flex items-center justify-between">
        <div>
          <h1 className="font-display text-[21px] font-bold text-ink">Console Super Admin</h1>
          <p className="text-[12.5px] text-ink/60 mt-0.5">Établissements, abonnements et facturation plateforme.</p>
        </div>
      </div>

      <div className="px-10 py-8">
        <div className="grid sm:grid-cols-3 gap-4">
          <StatCard label="Établissements" value={String(tenants.length)} accent="navy" />
          <StatCard label="Revenu mensuel récurrent (MRR)" value={`${mrr.toLocaleString("fr-FR")} F`} accent="pass" />
          <StatCard label="Essais en cours" value={String(trialCount)} accent="ochre" />
        </div>

        {/* --- Établissements --- */}
        <section className="mt-10">
          <div className="flex items-center justify-between">
            <h2 className="font-display text-lg text-ink">Établissements</h2>
            <button
              onClick={() => setShowTenantForm((v) => !v)}
              className="rounded bg-navy text-paper text-sm font-medium px-4 py-2 hover:bg-navy-light transition"
            >
              {showTenantForm ? "Annuler" : "+ Établissement"}
            </button>
          </div>

          {showTenantForm && (
            <form onSubmit={handleCreateTenant} className="mt-4 border border-line rounded bg-white p-5 grid sm:grid-cols-2 gap-4">
              <TextField name="name" label="Nom de l'établissement" placeholder="École La Colombe" required />
              <TextField name="code" label="Code (identifiant court)" placeholder="colombe" required />
              <div className="sm:col-span-2 pt-2 border-t border-line" />
              <TextField name="admin_full_name" label="Nom complet du Fondateur" placeholder="M. Le Fondateur" required />
              <TextField name="admin_email" label="E-mail de connexion du Fondateur" type="email" placeholder="fondateur@ecole.bj" required />
              <TextField name="admin_password" label="Mot de passe provisoire" type="password" required />
              {tenantError && <p className="sm:col-span-2 text-sm text-brick">{tenantError}</p>}
              <div className="sm:col-span-2">
                <button type="submit" className="rounded bg-ochre text-navy-deep text-sm font-medium px-4 py-2 hover:bg-ochre-dark transition">
                  Créer l'établissement et son compte Fondateur
                </button>
              </div>
            </form>
          )}

          <div className="mt-4 border border-line rounded bg-white overflow-hidden">
            <table className="w-full text-[14.5px]">
              <thead>
                <tr>
                  <Th>Établissement</Th>
                  <Th>Code</Th>
                  <Th>Abonnement</Th>
                  <Th>Plan</Th>
                  <Th>Réseau</Th>
                  <Th></Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {tenants.length === 0 && (
                  <tr><td colSpan={6} className="px-5 py-6 text-ink/40">Aucun établissement pour l'instant.</td></tr>
                )}
                {tenants.map((t) => {
                  const sub = subscriptions[t.id];
                  const statusInfo = sub ? STATUS_LABELS[sub.effective_status] : null;
                  return (
                    <tr key={t.id}>
                      <td className="px-5 py-3 font-medium text-ink">{t.name}</td>
                      <td className="px-5 py-3 text-ink/60">{t.code}</td>
                      <td className="px-5 py-3">
                        {sub === undefined && <span className="text-ink/30 text-xs">Chargement…</span>}
                        {sub === null && <span className="text-ink/40 text-xs italic">Aucun abonnement suivi</span>}
                        {statusInfo && <StatusPill label={statusInfo.label} tone={statusInfo.tone} />}
                      </td>
                      <td className="px-5 py-3 text-ink/60">{sub ? sub.plan.name : "—"}</td>
                      <td className="px-5 py-3">
                        {t.network_id ? (
                          <span className="text-ink/60">{networks.find((n) => n.id === t.network_id)?.name ?? "—"}</span>
                        ) : (
                          <select
                            defaultValue=""
                            onChange={(e) => handleAssignTenant(t.id, e.target.value)}
                            className="rounded border border-line bg-white px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy"
                          >
                            <option value="">— Rattacher —</option>
                            {networks.map((n) => <option key={n.id} value={n.id}>{n.name}</option>)}
                          </select>
                        )}
                      </td>
                      <td className="px-5 py-3 text-right">
                        <Link to={`/etablissements/${t.id}`} className="text-navy text-sm underline underline-offset-2 hover:text-navy-light">
                          Gérer →
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>

        {/* --- Plans --- */}
        <section className="mt-10 mb-16">
          <div className="flex items-center justify-between">
            <h2 className="font-display text-lg text-ink">Plans tarifaires</h2>
            <button
              onClick={() => setShowPlanForm((v) => !v)}
              className="rounded border border-navy text-navy text-sm font-medium px-4 py-2 hover:bg-navy/5 transition"
            >
              {showPlanForm ? "Annuler" : "Nouveau plan"}
            </button>
          </div>

          {showPlanForm && (
            <form onSubmit={handleCreatePlan} className="mt-4 border border-line rounded bg-white p-5 grid sm:grid-cols-4 gap-4">
              <TextField name="name" label="Nom" placeholder="Pro" required />
              <TextField name="code" label="Code" placeholder="pro" required />
              <TextField name="price_per_month" label="Prix / mois (FCFA)" type="number" min="0" required />
              <TextField name="max_students" label="Élèves max (vide = illimité)" type="number" min="1" />
              {planError && <p className="sm:col-span-4 text-sm text-brick">{planError}</p>}
              <div className="sm:col-span-4">
                <button type="submit" className="rounded bg-ochre text-navy-deep text-sm font-medium px-4 py-2 hover:bg-ochre-dark transition">
                  Créer le plan
                </button>
              </div>
            </form>
          )}

          <div className="mt-4 border border-line rounded bg-white overflow-hidden">
            <table className="w-full text-[14.5px]">
              <thead>
                <tr>
                  <Th>Plan</Th>
                  <Th>Prix / mois</Th>
                  <Th>Élèves max</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {plans.length === 0 && <tr><td colSpan={3} className="px-5 py-6 text-ink/40">Aucun plan.</td></tr>}
                {plans.map((p) => (
                  <tr key={p.id}>
                    <td className="px-5 py-3 font-medium text-ink">{p.name}</td>
                    <td className="px-5 py-3 text-ink/60">{p.price_per_month.toLocaleString("fr-FR")} F</td>
                    <td className="px-5 py-3 text-ink/60">{p.max_students ?? "Illimité"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="mt-10 mb-16">
          <div className="flex items-center justify-between">
            <h2 className="font-display text-lg text-ink">Réseaux</h2>
            <button
              onClick={() => setShowNetworkForm((v) => !v)}
              className="rounded border border-navy text-navy text-sm font-medium px-4 py-2 hover:bg-navy/5 transition"
            >
              {showNetworkForm ? "Annuler" : "Nouveau réseau"}
            </button>
          </div>
          <p className="text-sm text-ink/55 mt-1">
            Regroupe plusieurs établissements sous un même promoteur, avec une vue consolidée en lecture seule.
          </p>

          {showNetworkForm && (
            <form onSubmit={handleCreateNetwork} className="mt-4 border border-line rounded bg-white p-5 grid sm:grid-cols-3 gap-4">
              <TextField name="name" label="Nom du réseau" placeholder="Groupe Scolaire La Colombe" required />
              <TextField name="code" label="Code" placeholder="groupe-colombe" required />
              {networkError && <p className="sm:col-span-3 text-sm text-brick">{networkError}</p>}
              <div className="sm:col-span-3">
                <button type="submit" className="rounded bg-ochre text-navy-deep text-sm font-medium px-4 py-2 hover:bg-ochre-dark transition">
                  Créer le réseau
                </button>
              </div>
            </form>
          )}

          {adminSuccess && <p className="mt-3 text-sm text-pass">{adminSuccess}</p>}

          <div className="mt-4 space-y-3">
            {networks.length === 0 && <p className="text-sm text-ink/40">Aucun réseau pour l'instant.</p>}
            {networks.map((n) => (
              <div key={n.id} className="border border-line rounded bg-white p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-ink">{n.name}</p>
                    <p className="text-xs text-ink/40 mt-0.5">{n.code}</p>
                  </div>
                  <button
                    onClick={() => setAdminFormForNetwork(adminFormForNetwork === n.id ? null : n.id)}
                    className="text-navy text-sm underline underline-offset-2 hover:text-navy-light"
                  >
                    {adminFormForNetwork === n.id ? "Annuler" : "+ Compte promoteur"}
                  </button>
                </div>
                {adminFormForNetwork === n.id && (
                  <form onSubmit={(e) => handleCreateNetworkAdmin(e, n.id)} className="mt-4 pt-4 border-t border-line grid sm:grid-cols-3 gap-3">
                    <TextField name="full_name" label="Nom complet" placeholder="M. Le Promoteur" required />
                    <TextField name="email" label="E-mail" type="email" required />
                    <TextField name="password" label="Mot de passe provisoire" type="password" required />
                    {adminError && <p className="sm:col-span-3 text-sm text-brick">{adminError}</p>}
                    <div className="sm:col-span-3">
                      <button type="submit" className="rounded bg-ochre text-navy-deep text-sm font-medium px-4 py-2 hover:bg-ochre-dark transition">
                        Créer le compte
                      </button>
                    </div>
                  </form>
                )}
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

function StatCard({ label, value, accent }: { label: string; value: string; accent: "ochre" | "navy" | "pass" }) {
  const accentClass = { ochre: "text-ochre-dark", navy: "text-navy", pass: "text-pass" }[accent];
  return (
    <div className="border border-line rounded bg-white px-5 py-4">
      <p className="text-xs text-ink/50 uppercase tracking-wide">{label}</p>
      <p className={`font-display text-2xl mt-1.5 ${accentClass}`}>{value}</p>
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

function TextField({
  name, label, type = "text", placeholder, required, min,
}: { name: string; label: string; type?: string; placeholder?: string; required?: boolean; min?: string }) {
  return (
    <div>
      <label htmlFor={name} className="block text-sm font-medium text-ink/80 mb-1.5">{label}</label>
      <input
        id={name} name={name} type={type} placeholder={placeholder} required={required} min={min}
        className="w-full rounded border border-line bg-white px-3.5 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy transition"
      />
    </div>
  );
}
