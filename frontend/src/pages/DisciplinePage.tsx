import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../auth/AuthContext";
import RequireRole from "../components/RequireRole";
import StatusPill from "../components/StatusPill";
import { CAN_MANAGE_DISCIPLINE, CAN_READ_INCIDENTS, roleCan } from "../lib/permissions";

interface Student { id: string; first_name: string; last_name: string; }
interface Sanction { id: string; sanction_type: string; details: string | null; start_date: string | null; end_date: string | null; }
interface Incident {
  id: string; student_id: string; occurred_at: string; category: string; severity: string;
  description: string; status: string; sanctions: Sanction[];
}

export const CATEGORY_LABELS: Record<string, string> = {
  behavior: "Comportement", violence: "Violence", property_damage: "Dégradation de matériel",
  cheating: "Triche", repeated_lateness: "Retards répétés", other: "Autre",
};
export const SEVERITY: Record<string, { label: string; tone: "ok" | "warn" | "bad" | "neutral" }> = {
  minor: { label: "Mineur", tone: "neutral" }, moderate: { label: "Modéré", tone: "warn" }, serious: { label: "Grave", tone: "bad" },
};
export const STATUS: Record<string, { label: string; tone: "ok" | "warn" | "bad" | "neutral" }> = {
  reported: { label: "Signalé", tone: "warn" }, under_review: { label: "En cours de traitement", tone: "neutral" }, resolved: { label: "Clos", tone: "ok" },
};
export const SANCTION_LABELS: Record<string, string> = {
  warning: "Avertissement", detention: "Retenue", extra_work: "Travail supplémentaire",
  parent_summon: "Convocation des parents", temporary_exclusion: "Exclusion temporaire", other: "Autre",
};

const inputCls = "w-full rounded border border-line bg-white px-3.5 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy transition";

export default function DisciplinePage() {
  return (
    <RequireRole roles={CAN_READ_INCIDENTS}>
      <DisciplinePageContent />
    </RequireRole>
  );
}

function DisciplinePageContent() {
  const { user } = useAuth();
  const canManage = roleCan(user?.role, CAN_MANAGE_DISCIPLINE);
  const [students, setStudents] = useState<Student[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [filter, setFilter] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sanctionFor, setSanctionFor] = useState<string | null>(null);

  function reload() {
    api.get<Incident[]>(`/incidents${filter ? `?status=${filter}` : ""}`).then(setIncidents).catch(() => setIncidents([]));
  }
  useEffect(() => { api.get<Student[]>("/students").then(setStudents).catch(() => setStudents([])); }, []);
  useEffect(reload, [filter]);

  const studentName = (id: string) => {
    const s = students.find((x) => x.id === id);
    return s ? `${s.first_name} ${s.last_name}` : "—";
  };

  async function handleReport(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    const form = new FormData(e.currentTarget);
    try {
      await api.post("/incidents", {
        student_id: form.get("student_id"),
        occurred_at: new Date(String(form.get("occurred_at"))).toISOString(),
        category: form.get("category"),
        severity: form.get("severity"),
        description: form.get("description"),
      });
      setShowForm(false);
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible d'enregistrer l'incident.");
    }
  }

  async function changeStatus(id: string, status: string) {
    await api.patch(`/incidents/${id}/status`, { status });
    reload();
  }

  async function handleSanction(e: FormEvent<HTMLFormElement>, incidentId: string) {
    e.preventDefault();
    setError(null);
    const form = new FormData(e.currentTarget);
    try {
      await api.post(`/incidents/${incidentId}/sanctions`, {
        sanction_type: form.get("sanction_type"),
        details: form.get("details") || null,
        start_date: form.get("start_date") || null,
        end_date: form.get("end_date") || null,
      });
      setSanctionFor(null);
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible d'enregistrer la sanction.");
    }
  }

  return (
    <div className="px-10 py-10 max-w-4xl">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-display text-3xl font-medium text-ink">Discipline</h1>
          <p className="text-sm text-ink/55 mt-1">
            {canManage
              ? "Suivez les incidents signalés, traitez-les et posez les sanctions."
              : "Signalez un incident — le traitement et les sanctions relèvent du censeur et de la direction."}
          </p>
        </div>
        <button onClick={() => setShowForm((v) => !v)} className="rounded bg-navy text-paper text-sm font-medium px-4 py-2 hover:bg-navy-light transition">
          {showForm ? "Annuler" : "Signaler un incident"}
        </button>
      </div>

      {user?.role === "teacher" && (
        <p className="mt-3 text-xs text-ink/45">Vous ne voyez que les incidents que vous avez vous-même signalés.</p>
      )}

      {showForm && (
        <form onSubmit={handleReport} className="mt-6 border border-line rounded bg-white p-5 grid sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-ink/80 mb-1.5">Élève</label>
            <select name="student_id" required className={inputCls}>
              <option value="">—</option>
              {students.map((s) => <option key={s.id} value={s.id}>{s.first_name} {s.last_name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-ink/80 mb-1.5">Date et heure</label>
            <input name="occurred_at" type="datetime-local" required defaultValue={new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16)} className={inputCls} />
          </div>
          <div>
            <label className="block text-sm font-medium text-ink/80 mb-1.5">Nature</label>
            <select name="category" className={inputCls}>
              {Object.entries(CATEGORY_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-ink/80 mb-1.5">Gravité</label>
            <select name="severity" defaultValue="moderate" className={inputCls}>
              {Object.entries(SEVERITY).map(([v, s]) => <option key={v} value={v}>{s.label}</option>)}
            </select>
          </div>
          <div className="sm:col-span-2">
            <label className="block text-sm font-medium text-ink/80 mb-1.5">Description des faits</label>
            <textarea name="description" required rows={3} className={`${inputCls} resize-none`} placeholder="Ce qui s'est passé, où, avec qui." />
          </div>
          {error && <p className="sm:col-span-2 text-sm text-brick">{error}</p>}
          <div className="sm:col-span-2">
            <button type="submit" className="rounded bg-ochre text-navy-deep text-sm font-medium px-4 py-2 hover:bg-ochre-dark transition">Enregistrer le signalement</button>
          </div>
        </form>
      )}

      <div className="mt-8 flex gap-2">
        {([["", "Tous"], ["reported", "Signalés"], ["under_review", "En cours"], ["resolved", "Clos"]] as const).map(([v, l]) => (
          <button key={v} onClick={() => setFilter(v)}
            className={`rounded-full px-3.5 py-1.5 text-xs font-semibold border transition ${filter === v ? "bg-navy text-paper border-navy" : "bg-white text-ink/60 border-line hover:border-navy/40"}`}>
            {l}
          </button>
        ))}
      </div>

      <div className="mt-4 space-y-3 mb-16">
        {incidents.length === 0 && <p className="text-sm text-ink/40">Aucun incident.</p>}
        {incidents.map((inc) => (
          <div key={inc.id} className="border border-line rounded bg-white p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="font-medium text-ink">{studentName(inc.student_id)}</p>
                <p className="text-xs text-ink/45 mt-0.5">
                  {new Date(inc.occurred_at).toLocaleString("fr-FR", { dateStyle: "medium", timeStyle: "short" })} · {CATEGORY_LABELS[inc.category] ?? inc.category}
                </p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <StatusPill label={SEVERITY[inc.severity]?.label ?? inc.severity} tone={SEVERITY[inc.severity]?.tone ?? "neutral"} />
                <StatusPill label={STATUS[inc.status]?.label ?? inc.status} tone={STATUS[inc.status]?.tone ?? "neutral"} />
              </div>
            </div>
            <p className="text-[14.5px] text-ink/80 mt-3">{inc.description}</p>

            {inc.sanctions.length > 0 && (
              <ul className="mt-3 pt-3 border-t border-line space-y-1">
                {inc.sanctions.map((s) => (
                  <li key={s.id} className="text-[13.5px] text-ink/70">
                    <span className="font-semibold text-ink">{SANCTION_LABELS[s.sanction_type] ?? s.sanction_type}</span>
                    {s.details && ` — ${s.details}`}
                    {s.start_date && ` (${s.start_date}${s.end_date && s.end_date !== s.start_date ? ` → ${s.end_date}` : ""})`}
                  </li>
                ))}
              </ul>
            )}

            {canManage && (
              <div className="mt-4 pt-3 border-t border-line flex flex-wrap items-center gap-3 text-sm">
                {inc.status === "reported" && <button onClick={() => changeStatus(inc.id, "under_review")} className="text-navy underline underline-offset-2 hover:text-navy-light">Prendre en charge</button>}
                {inc.status !== "resolved" && <button onClick={() => changeStatus(inc.id, "resolved")} className="text-pass underline underline-offset-2">Clore</button>}
                {inc.status === "resolved" && <button onClick={() => changeStatus(inc.id, "under_review")} className="text-ink/50 underline underline-offset-2">Rouvrir</button>}
                <button onClick={() => setSanctionFor(sanctionFor === inc.id ? null : inc.id)} className="text-ochre-dark underline underline-offset-2">
                  {sanctionFor === inc.id ? "Annuler" : "Ajouter une sanction"}
                </button>
              </div>
            )}

            {canManage && sanctionFor === inc.id && (
              <form onSubmit={(e) => handleSanction(e, inc.id)} className="mt-3 grid sm:grid-cols-4 gap-3 items-end">
                <div className="sm:col-span-2">
                  <label className="block text-xs font-medium text-ink/60 mb-1">Sanction</label>
                  <select name="sanction_type" className={inputCls}>
                    {Object.entries(SANCTION_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                </div>
                <div><label className="block text-xs font-medium text-ink/60 mb-1">Du</label><input name="start_date" type="date" className={inputCls} /></div>
                <div><label className="block text-xs font-medium text-ink/60 mb-1">Au</label><input name="end_date" type="date" className={inputCls} /></div>
                <div className="sm:col-span-3"><input name="details" placeholder="Précisions (facultatif)" className={inputCls} /></div>
                <button type="submit" className="rounded bg-ochre text-navy-deep text-sm font-medium px-4 py-2 hover:bg-ochre-dark transition">Enregistrer</button>
                {error && <p className="sm:col-span-4 text-sm text-brick">{error}</p>}
              </form>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
