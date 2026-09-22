import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../auth/AuthContext";
import { CAN_MANAGE_REGISTRY, roleCan } from "../lib/permissions";

interface SchoolClass {
  id: string;
  name: string;
  level: string;
  cycle: string;
}
interface Subject {
  id: string;
  name: string;
  default_coefficient: number;
}

const CYCLE_LABELS: Record<string, string> = {
  maternelle: "Maternelle",
  primaire: "Primaire",
  secondaire: "Secondaire",
};

const inputCls = "w-full rounded border border-line bg-white px-3.5 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy transition";

export default function AcademicPage() {
  const { user } = useAuth();
  const canManage = roleCan(user?.role, CAN_MANAGE_REGISTRY);
  const [classes, setClasses] = useState<SchoolClass[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [showClassForm, setShowClassForm] = useState(false);
  const [showSubjectForm, setShowSubjectForm] = useState(false);
  const [classError, setClassError] = useState<string | null>(null);
  const [subjectError, setSubjectError] = useState<string | null>(null);

  function reload() {
    api.get<SchoolClass[]>("/classes").then(setClasses);
    api.get<Subject[]>("/subjects").then(setSubjects);
  }
  useEffect(reload, []);

  async function handleCreateClass(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setClassError(null);
    const form = new FormData(e.currentTarget);
    try {
      await api.post("/classes", { name: form.get("name"), level: form.get("level"), cycle: form.get("cycle") });
      setShowClassForm(false);
      reload();
    } catch (err) {
      setClassError(err instanceof ApiError ? err.message : "Impossible de créer la classe.");
    }
  }

  async function handleCreateSubject(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubjectError(null);
    const form = new FormData(e.currentTarget);
    try {
      await api.post("/subjects", { name: form.get("name"), default_coefficient: Number(form.get("default_coefficient") || 1) });
      setShowSubjectForm(false);
      reload();
    } catch (err) {
      setSubjectError(err instanceof ApiError ? err.message : "Impossible de créer la matière.");
    }
  }

  const classesByCycle: Record<string, SchoolClass[]> = { maternelle: [], primaire: [], secondaire: [] };
  classes.forEach((c) => classesByCycle[c.cycle]?.push(c));

  return (
    <div className="px-10 py-10 max-w-4xl">
      <h1 className="font-display text-3xl font-medium text-ink">Classes & Matières</h1>
      <p className="text-sm text-ink/55 mt-1">Référentiel pédagogique de l'établissement.</p>

      <section className="mt-8">
        <div className="flex items-center justify-between">
          <h2 className="font-display text-lg text-ink">Classes</h2>
          {canManage && (
            <button onClick={() => setShowClassForm((v) => !v)} className="rounded bg-navy text-paper text-sm font-medium px-4 py-2 hover:bg-navy-light transition">
              {showClassForm ? "Annuler" : "+ Classe"}
            </button>
          )}
        </div>

        {canManage && showClassForm && (
          <form onSubmit={handleCreateClass} className="mt-4 border border-line rounded bg-white p-5 grid sm:grid-cols-3 gap-4">
            <Field name="name" label="Nom" placeholder="6ème A" required />
            <Field name="level" label="Niveau" placeholder="6ème" required />
            <div>
              <label className="block text-sm font-medium text-ink/80 mb-1.5">Cycle</label>
              <select name="cycle" defaultValue="primaire" className={inputCls}>
                <option value="maternelle">Maternelle</option>
                <option value="primaire">Primaire</option>
                <option value="secondaire">Secondaire</option>
              </select>
            </div>
            {classError && <p className="sm:col-span-3 text-sm text-brick">{classError}</p>}
            <div className="sm:col-span-3">
              <button type="submit" className="rounded bg-ochre text-navy-deep text-sm font-medium px-4 py-2 hover:bg-ochre-dark transition">
                Créer la classe
              </button>
            </div>
          </form>
        )}

        <div className="mt-4 space-y-5">
          {(["maternelle", "primaire", "secondaire"] as const).map((cycle) => (
            <div key={cycle}>
              <p className="text-xs font-semibold text-ink/40 uppercase tracking-wide mb-2">{CYCLE_LABELS[cycle]}</p>
              <div className="border border-line rounded bg-white overflow-hidden">
                <table className="w-full text-[14.5px]">
                  <thead>
                    <tr>
                      <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-3 border-b border-line">Classe</th>
                      <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-3 border-b border-line">Niveau</th>
                    </tr>
                  </thead>
                  <tbody>
                    {classesByCycle[cycle].length === 0 && (
                      <tr><td colSpan={2} className="px-4 py-4 text-ink/40">Aucune classe.</td></tr>
                    )}
                    {classesByCycle[cycle].map((c) => (
                      <tr key={c.id} className="border-b border-line last:border-none">
                        <td className="px-4 py-2.5 font-medium">{c.name}</td>
                        <td className="px-4 py-2.5 text-ink/60">{c.level}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-10 mb-16">
        <div className="flex items-center justify-between">
          <h2 className="font-display text-lg text-ink">Matières</h2>
          {canManage && (
            <button onClick={() => setShowSubjectForm((v) => !v)} className="rounded border border-navy text-navy text-sm font-medium px-4 py-2 hover:bg-navy/5 transition">
              {showSubjectForm ? "Annuler" : "+ Matière"}
            </button>
          )}
        </div>

        {canManage && showSubjectForm && (
          <form onSubmit={handleCreateSubject} className="mt-4 border border-line rounded bg-white p-5 grid sm:grid-cols-2 gap-4">
            <Field name="name" label="Nom" placeholder="Mathématiques" required />
            <Field name="default_coefficient" label="Coefficient par défaut" type="number" step="0.5" min="0.5" defaultValue="1" />
            {subjectError && <p className="sm:col-span-2 text-sm text-brick">{subjectError}</p>}
            <div className="sm:col-span-2">
              <button type="submit" className="rounded bg-ochre text-navy-deep text-sm font-medium px-4 py-2 hover:bg-ochre-dark transition">
                Créer la matière
              </button>
            </div>
          </form>
        )}

        <div className="mt-4 border border-line rounded bg-white overflow-hidden">
          <table className="w-full text-[14.5px]">
            <thead>
              <tr>
                <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-3 border-b border-line">Matière</th>
                <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-3 border-b border-line">Coefficient par défaut</th>
              </tr>
            </thead>
            <tbody>
              {subjects.length === 0 && <tr><td colSpan={2} className="px-4 py-4 text-ink/40">Aucune matière.</td></tr>}
              {subjects.map((s) => (
                <tr key={s.id} className="border-b border-line last:border-none">
                  <td className="px-4 py-2.5 font-medium">{s.name}</td>
                  <td className="px-4 py-2.5 text-ink/60">{s.default_coefficient}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function Field({
  name, label, type = "text", placeholder, required, step, min, defaultValue,
}: { name: string; label: string; type?: string; placeholder?: string; required?: boolean; step?: string; min?: string; defaultValue?: string }) {
  return (
    <div>
      <label className="block text-sm font-medium text-ink/80 mb-1.5">{label}</label>
      <input name={name} type={type} placeholder={placeholder} required={required} step={step} min={min} defaultValue={defaultValue} className={inputCls} />
    </div>
  );
}
