import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../lib/api";

interface Plan {
  id: string;
  name: string;
  price_per_month: number;
}
interface Student {
  id: string;
  first_name: string;
  last_name: string;
}

export default function CanteenPage() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [students, setStudents] = useState<Student[]>([]);
  const [showPlanForm, setShowPlanForm] = useState(false);
  const [showSubForm, setShowSubForm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  function reload() {
    api.get<Plan[]>("/canteen/plans").then(setPlans);
    api.get<Student[]>("/students").then(setStudents);
  }
  useEffect(reload, []);

  async function handleCreatePlan(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    const form = new FormData(e.currentTarget);
    try {
      await api.post("/canteen/plans", { name: form.get("name"), price_per_month: Number(form.get("price_per_month")) });
      setShowPlanForm(false);
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible de créer la formule.");
    }
  }

  async function handleSubscribe(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    const form = new FormData(e.currentTarget);
    try {
      await api.post("/canteen/subscriptions", {
        student_id: form.get("student_id"),
        plan_id: form.get("plan_id"),
        month: form.get("month"),
      });
      setSuccess("Abonnement créé — la facture correspondante est disponible sur la fiche de l'élève.");
      setShowSubForm(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible de créer l'abonnement.");
    }
  }

  return (
    <div className="px-10 py-10 max-w-3xl">
      <h1 className="font-display text-3xl font-medium text-ink">Cantine</h1>
      <p className="text-sm text-ink/55 mt-1">Formules et abonnements — chaque abonnement génère automatiquement sa facture.</p>

      <section className="mt-8">
        <div className="flex items-center justify-between">
          <h2 className="font-display text-lg text-ink">Formules</h2>
          <button onClick={() => setShowPlanForm((v) => !v)} className="rounded bg-navy text-paper text-sm font-medium px-3.5 py-2 hover:bg-navy-light transition">
            {showPlanForm ? "Annuler" : "+ Formule"}
          </button>
        </div>
        {showPlanForm && (
          <form onSubmit={handleCreatePlan} className="mt-4 border border-line rounded bg-white p-5 grid sm:grid-cols-2 gap-4">
            <TextField name="name" label="Nom de la formule" placeholder="5 jours / semaine" required />
            <TextField name="price_per_month" label="Prix mensuel (FCFA)" type="number" min="1" required />
            <div className="sm:col-span-2">
              <button type="submit" className="rounded bg-ochre text-navy-deep text-sm font-medium px-4 py-2 hover:bg-ochre-dark transition">
                Créer
              </button>
            </div>
          </form>
        )}
        <div className="mt-4 border border-line rounded bg-white overflow-hidden">
          <table className="w-full text-[14.5px]">
            <thead>
              <tr>
                <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-4 border-b border-line">Formule</th>
                <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-4 border-b border-line">Prix / mois</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {plans.length === 0 && <tr><td colSpan={2} className="px-4 py-6 text-ink/50">Aucune formule.</td></tr>}
              {plans.map((p) => (
                <tr key={p.id}>
                  <td className="px-4 py-2.5 text-ink">{p.name}</td>
                  <td className="px-4 py-2.5 text-ink/70">{p.price_per_month.toLocaleString("fr-FR")} F</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mt-10 mb-16">
        <div className="flex items-center justify-between">
          <h2 className="font-display text-lg text-ink">Abonner un élève</h2>
          <button onClick={() => setShowSubForm((v) => !v)} className="rounded border border-navy text-navy text-sm font-medium px-3.5 py-2 hover:bg-navy/5 transition">
            {showSubForm ? "Annuler" : "Nouvel abonnement"}
          </button>
        </div>
        {showSubForm && (
          <form onSubmit={handleSubscribe} className="mt-4 border border-line rounded bg-white p-5 grid sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-ink/80 mb-1.5">Élève</label>
              <select name="student_id" required className="w-full rounded border border-line bg-white px-3 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy">
                <option value="">—</option>
                {students.map((s) => <option key={s.id} value={s.id}>{s.first_name} {s.last_name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-ink/80 mb-1.5">Formule</label>
              <select name="plan_id" required className="w-full rounded border border-line bg-white px-3 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy">
                <option value="">—</option>
                {plans.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
            <TextField name="month" label="Mois" type="month" required />
            {error && <p className="sm:col-span-3 text-sm text-brick">{error}</p>}
            {success && <p className="sm:col-span-3 text-sm text-pass">{success}</p>}
            <div className="sm:col-span-3">
              <button type="submit" className="rounded bg-ochre text-navy-deep text-sm font-medium px-4 py-2 hover:bg-ochre-dark transition">
                Créer l'abonnement
              </button>
            </div>
          </form>
        )}
      </section>
    </div>
  );
}

function TextField({ name, label, type = "text", required, placeholder, min }: { name: string; label: string; type?: string; required?: boolean; placeholder?: string; min?: string }) {
  return (
    <div>
      <label className="block text-sm font-medium text-ink/80 mb-1.5">{label}</label>
      <input name={name} type={type} required={required} placeholder={placeholder} min={min}
        className="w-full rounded border border-line bg-white px-3 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy transition" />
    </div>
  );
}
