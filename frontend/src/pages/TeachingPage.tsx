import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../lib/api";

interface StaffUser { id: string; full_name: string; email: string; role: string; }
interface SchoolClass { id: string; name: string; }
interface Subject { id: string; name: string; }
interface Assignment { id: string; teacher_id: string; class_id: string; subject_id: string; }

const inputCls = "w-full rounded border border-line bg-white px-3.5 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy transition";

export default function TeachingPage() {
  const [teachers, setTeachers] = useState<StaffUser[]>([]);
  const [classes, setClasses] = useState<SchoolClass[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function reload() {
    api.get<StaffUser[]>("/users").then((all) => setTeachers(all.filter((u) => u.role === "teacher")));
    api.get<SchoolClass[]>("/classes").then(setClasses);
    api.get<Subject[]>("/subjects").then(setSubjects);
    api.get<Assignment[]>("/teacher-assignments").then(setAssignments);
  }
  useEffect(reload, []);

  const teacherName = (id: string) => teachers.find((t) => t.id === id)?.full_name ?? "—";
  const className = (id: string) => classes.find((c) => c.id === id)?.name ?? "—";
  const subjectName = (id: string) => subjects.find((s) => s.id === id)?.name ?? "—";

  async function handleCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    const form = new FormData(e.currentTarget);
    try {
      await api.post("/teacher-assignments", {
        teacher_id: form.get("teacher_id"), class_id: form.get("class_id"), subject_id: form.get("subject_id"),
      });
      setShowForm(false);
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible de créer cette affectation.");
    }
  }

  async function handleDelete(id: string) {
    await api.del(`/teacher-assignments/${id}`);
    reload();
  }

  return (
    <div className="px-10 py-10 max-w-3xl">
      <h1 className="font-display text-3xl font-medium text-ink">Affectations pédagogiques</h1>
      <p className="text-sm text-ink/55 mt-1">
        Un enseignant ayant au moins une affectation ne peut noter que ses classes et matières assignées.
      </p>

      <div className="mt-8 flex items-center justify-between">
        <h2 className="font-display text-lg text-ink">Affectations</h2>
        <button onClick={() => setShowForm((v) => !v)} className="rounded bg-navy text-paper text-sm font-medium px-4 py-2 hover:bg-navy-light transition">
          {showForm ? "Annuler" : "+ Affectation"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="mt-4 border border-line rounded bg-white p-5 grid sm:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-ink/80 mb-1.5">Enseignant</label>
            <select name="teacher_id" required className={inputCls}>
              <option value="">—</option>
              {teachers.map((t) => <option key={t.id} value={t.id}>{t.full_name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-ink/80 mb-1.5">Classe</label>
            <select name="class_id" required className={inputCls}>
              <option value="">—</option>
              {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-ink/80 mb-1.5">Matière</label>
            <select name="subject_id" required className={inputCls}>
              <option value="">—</option>
              {subjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          {error && <p className="sm:col-span-3 text-sm text-brick">{error}</p>}
          <div className="sm:col-span-3">
            <button type="submit" className="rounded bg-ochre text-navy-deep text-sm font-medium px-4 py-2 hover:bg-ochre-dark transition">
              Créer l'affectation
            </button>
          </div>
        </form>
      )}

      <div className="mt-4 border border-line rounded bg-white overflow-hidden">
        <table className="w-full text-[14.5px]">
          <thead>
            <tr>
              <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-3 border-b border-line">Enseignant</th>
              <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-3 border-b border-line">Classe</th>
              <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-3 border-b border-line">Matière</th>
              <th className="border-b border-line"></th>
            </tr>
          </thead>
          <tbody>
            {assignments.length === 0 && <tr><td colSpan={4} className="px-4 py-6 text-ink/40">Aucune affectation pour l'instant.</td></tr>}
            {assignments.map((a) => (
              <tr key={a.id} className="border-b border-line last:border-none">
                <td className="px-4 py-2.5 font-medium">{teacherName(a.teacher_id)}</td>
                <td className="px-4 py-2.5 text-ink/60">{className(a.class_id)}</td>
                <td className="px-4 py-2.5 text-ink/60">{subjectName(a.subject_id)}</td>
                <td className="px-4 py-2.5 text-right">
                  <button
                    onClick={() => handleDelete(a.id)}
                    className="text-brick text-sm hover:underline"
                  >
                    Retirer
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
