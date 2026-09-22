import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Search, Plus } from "lucide-react";
import { api, ApiError } from "../lib/api";
import Avatar from "../components/Avatar";
import StatusPill from "../components/StatusPill";
import { useAuth } from "../auth/AuthContext";
import { CAN_MANAGE_REGISTRY, roleCan } from "../lib/permissions";

interface Student {
  id: string;
  first_name: string;
  last_name: string;
  class_id: string | null;
  guardian_name: string | null;
  guardian_phone: string | null;
  status: string;
}
interface SchoolClass {
  id: string;
  name: string;
}

const STATUS_PILL: Record<string, { label: string; tone: "ok" | "warn" | "bad" | "neutral" }> = {
  active: { label: "Actif", tone: "ok" },
  transferred: { label: "Transféré", tone: "warn" },
  graduated: { label: "Diplômé", tone: "warn" },
  archived: { label: "Archivé", tone: "neutral" },
};

export default function StudentsPage() {
  const { user } = useAuth();
  const canManage = roleCan(user?.role, CAN_MANAGE_REGISTRY);
  const [students, setStudents] = useState<Student[]>([]);
  const [classes, setClasses] = useState<SchoolClass[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function reload() {
    setLoading(true);
    api
      .get<Student[]>("/students")
      .then(setStudents)
      .finally(() => setLoading(false));
    api.get<SchoolClass[]>("/classes").then(setClasses).catch(() => setClasses([]));
  }

  useEffect(reload, []);

  const className = (id: string | null) => classes.find((c) => c.id === id)?.name ?? "—";

  async function handleCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setFormError(null);
    setSubmitting(true);
    const form = new FormData(e.currentTarget);
    try {
      await api.post("/students", {
        first_name: form.get("first_name"),
        last_name: form.get("last_name"),
        class_id: form.get("class_id") || null,
        guardian_name: form.get("guardian_name") || null,
        guardian_phone: form.get("guardian_phone") || null,
      });
      setShowForm(false);
      reload();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Impossible d'enregistrer l'élève.");
    } finally {
      setSubmitting(false);
    }
  }

  const filtered = students.filter((s) =>
    `${s.first_name} ${s.last_name}`.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div>
      <div className="px-10 py-8 border-b border-line flex items-center justify-between">
        <div>
          <h1 className="font-display text-[21px] font-bold text-ink">Élèves</h1>
          <p className="text-[12.5px] text-ink/60 mt-0.5">
            {students.length} élève{students.length > 1 ? "s" : ""} inscrit{students.length > 1 ? "s" : ""}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-white border border-line rounded-lg px-3 py-2 text-[13px] text-ink/40 min-w-[220px]">
            <Search className="w-4 h-4" strokeWidth={1.8} />
            <input
              value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Rechercher un élève…"
              className="flex-1 outline-none text-ink placeholder:text-ink/40 bg-transparent"
            />
          </div>
          {canManage && (
            <button
              onClick={() => setShowForm((v) => !v)}
              className="flex items-center gap-1.5 rounded-lg bg-pass text-white text-[13.5px] font-semibold px-4 py-2.5 hover:opacity-90 transition"
            >
              <Plus className="w-4 h-4" strokeWidth={2} />
              {showForm ? "Annuler" : "Nouvel élève"}
            </button>
          )}
        </div>
      </div>

      <div className="px-10 py-8">
        {showForm && (
          <form onSubmit={handleCreate} className="mb-6 border border-line rounded-lg bg-white p-5 grid sm:grid-cols-2 gap-4">
            <Field name="first_name" label="Prénom" required />
            <Field name="last_name" label="Nom" required />
            <div>
              <label htmlFor="class_id" className="block text-sm font-medium text-ink/80 mb-1.5">Classe</label>
              <select
                id="class_id" name="class_id"
                className="w-full rounded-lg border border-line bg-white px-3.5 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-sky/30 focus:border-sky transition"
              >
                <option value="">— Non affecté —</option>
                {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <Field name="guardian_name" label="Tuteur / tutrice" />
            <Field name="guardian_phone" label="Téléphone du tuteur" />
            {formError && <p className="sm:col-span-2 text-sm text-brick">{formError}</p>}
            <div className="sm:col-span-2">
              <button
                type="submit" disabled={submitting}
                className="rounded-lg bg-navy-deep text-sky-200 text-sm font-semibold px-4 py-2.5 hover:bg-navy transition disabled:opacity-60"
              >
                {submitting ? "Enregistrement…" : "Enregistrer l'élève"}
              </button>
            </div>
          </form>
        )}

        <div className="border border-line rounded-lg bg-white overflow-hidden">
          <table className="w-full text-[13.5px]">
            <thead>
              <tr>
                <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-5 pb-2.5 pt-4">Élève</th>
                <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-5 pb-2.5 pt-4">Classe</th>
                <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-5 pb-2.5 pt-4">Tuteur</th>
                <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-5 pb-2.5 pt-4">Contact</th>
                <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-5 pb-2.5 pt-4">Statut</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {loading && (
                <tr><td colSpan={5} className="px-5 py-6 text-ink/50">Chargement…</td></tr>
              )}
              {!loading && filtered.length === 0 && (
                <tr><td colSpan={5} className="px-5 py-8 text-ink/50">Aucun élève trouvé.</td></tr>
              )}
              {filtered.map((s) => {
                const pill = STATUS_PILL[s.status] ?? { label: s.status, tone: "neutral" as const };
                return (
                  <tr key={s.id} className="hover:bg-paper/60 transition">
                    <td className="px-5 py-3">
                      <Link to={`/eleves/${s.id}`} className="flex items-center gap-2.5 group">
                        <Avatar firstName={s.first_name} lastName={s.last_name} />
                        <span className="text-ink font-semibold group-hover:text-navy group-hover:underline underline-offset-2">
                          {s.first_name} {s.last_name}
                        </span>
                      </Link>
                    </td>
                    <td className="px-5 py-3 text-ink/70">{className(s.class_id)}</td>
                    <td className="px-5 py-3 text-ink/70">{s.guardian_name || "—"}</td>
                    <td className="px-5 py-3 text-ink/70">{s.guardian_phone || "—"}</td>
                    <td className="px-5 py-3"><StatusPill label={pill.label} tone={pill.tone} /></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function Field({ name, label, required }: { name: string; label: string; required?: boolean }) {
  return (
    <div>
      <label htmlFor={name} className="block text-sm font-medium text-ink/80 mb-1.5">
        {label}
      </label>
      <input
        id={name}
        name={name}
        required={required}
        className="w-full rounded-lg border border-line bg-white px-3.5 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-sky/30 focus:border-sky transition"
      />
    </div>
  );
}
