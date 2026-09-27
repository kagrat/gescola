import { useEffect, useState } from "react";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../auth/AuthContext";

interface Assignment { id: string; teacher_id: string; class_id: string; subject_id: string; }
interface SchoolClass { id: string; name: string; }
interface Subject { id: string; name: string; }
interface Student { id: string; first_name: string; last_name: string; class_id: string | null; }

const TERMS = ["T1", "T2", "T3"];

export default function MyClassesPage() {
  const { user } = useAuth();
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [classes, setClasses] = useState<SchoolClass[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [students, setStudents] = useState<Student[]>([]);
  const [selected, setSelected] = useState<{ classId: string; subjectId: string } | null>(null);
  const [tab, setTab] = useState<"notes" | "cahier" | "devoirs">("notes");

  useEffect(() => {
    api.get<Assignment[]>("/teacher-assignments").then((all) => {
      const mine = all.filter((a) => a.teacher_id === user?.id);
      setAssignments(mine);
      if (mine.length > 0) setSelected({ classId: mine[0].class_id, subjectId: mine[0].subject_id });
    });
    api.get<SchoolClass[]>("/classes").then(setClasses);
    api.get<Subject[]>("/subjects").then(setSubjects);
    api.get<Student[]>("/students").then(setStudents);
  }, [user?.id]);

  const className = (id: string) => classes.find((c) => c.id === id)?.name ?? "—";
  const subjectName = (id: string) => subjects.find((s) => s.id === id)?.name ?? "—";

  if (assignments.length === 0) {
    return (
      <div className="px-10 py-10 max-w-2xl">
        <h1 className="font-display text-3xl font-medium text-ink">Mes classes</h1>
        <p className="mt-4 text-sm text-ink/55">
          Aucune classe ne vous est encore affectée. Contactez la Direction ou le Censeur pour être rattaché à vos classes et matières.
        </p>
      </div>
    );
  }

  return (
    <div className="px-10 py-10 max-w-4xl">
      <h1 className="font-display text-3xl font-medium text-ink">Mes classes</h1>
      <p className="text-sm text-ink/55 mt-1">Vos affectations pédagogiques.</p>

      <div className="mt-6 flex flex-wrap gap-2">
        {assignments.map((a) => {
          const isSelected = selected?.classId === a.class_id && selected?.subjectId === a.subject_id;
          return (
            <button
              key={a.id}
              onClick={() => setSelected({ classId: a.class_id, subjectId: a.subject_id })}
              className={`rounded-full px-4 py-2 text-sm font-medium border transition ${
                isSelected ? "bg-navy text-paper border-navy" : "bg-white text-ink border-line hover:border-navy/40"
              }`}
            >
              {className(a.class_id)} · {subjectName(a.subject_id)}
            </button>
          );
        })}
      </div>

      {selected && (
        <>
          <div className="mt-6 flex gap-1 border-b border-line">
            {([
              ["notes", "Notes"],
              ["cahier", "Cahier de texte"],
              ["devoirs", "Devoirs"],
            ] as const).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition ${
                  tab === key ? "border-navy text-navy" : "border-transparent text-ink/50 hover:text-ink"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {tab === "notes" && (
            <BulkGradeEntry
              classId={selected.classId}
              subjectId={selected.subjectId}
              students={students.filter((s) => s.class_id === selected.classId)}
            />
          )}
          {tab === "cahier" && <LessonLogPanel classId={selected.classId} subjectId={selected.subjectId} />}
          {tab === "devoirs" && <HomeworkPanel classId={selected.classId} subjectId={selected.subjectId} />}
        </>
      )}
    </div>
  );
}

function BulkGradeEntry({ classId, subjectId, students }: { classId: string; subjectId: string; students: Student[] }) {
  const [term, setTerm] = useState("T1");
  const [evaluationLabel, setEvaluationLabel] = useState("");
  const [coefficient, setCoefficient] = useState("1");
  const [values, setValues] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setValues({});
    setResult(null);
    setError(null);
  }, [classId, subjectId]);

  async function handleSubmit() {
    setError(null);
    setResult(null);
    if (!evaluationLabel.trim()) {
      setError("Le nom de l'évaluation est obligatoire.");
      return;
    }
    const entries = Object.entries(values).filter(([, v]) => v !== "");
    if (entries.length === 0) {
      setError("Saisissez au moins une note.");
      return;
    }
    setSubmitting(true);
    let success = 0;
    let failed = 0;
    for (const [studentId, value] of entries) {
      try {
        await api.post("/grades", {
          student_id: studentId, subject_id: subjectId, term,
          evaluation_label: evaluationLabel, value: Number(value), coefficient: Number(coefficient || 1),
        });
        success += 1;
      } catch (err) {
        failed += 1;
        if (err instanceof ApiError && failed === 1) setError(err.message);
      }
    }
    setSubmitting(false);
    setResult(`${success} note(s) enregistrée(s)${failed > 0 ? `, ${failed} échec(s)` : ""}.`);
    if (failed === 0) setValues({});
  }

  return (
    <div className="mt-6 border border-line rounded bg-white p-6">
      <div className="grid sm:grid-cols-3 gap-4">
        <div>
          <label className="block text-sm font-medium text-ink/80 mb-1.5">Période</label>
          <select value={term} onChange={(e) => setTerm(e.target.value)} className="w-full rounded border border-line bg-white px-3 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy">
            {TERMS.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-ink/80 mb-1.5">Évaluation</label>
          <input value={evaluationLabel} onChange={(e) => setEvaluationLabel(e.target.value)} placeholder="Devoir 1"
            className="w-full rounded border border-line bg-white px-3 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy" />
        </div>
        <div>
          <label className="block text-sm font-medium text-ink/80 mb-1.5">Coefficient</label>
          <input type="number" step="0.5" min="0.5" value={coefficient} onChange={(e) => setCoefficient(e.target.value)}
            className="w-full rounded border border-line bg-white px-3 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy" />
        </div>
      </div>

      <div className="mt-5 border border-line rounded overflow-hidden">
        <table className="w-full text-[14.5px]">
          <thead>
            <tr>
              <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-3 border-b border-line">Élève</th>
              <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-3 border-b border-line">Note /20</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {students.length === 0 && (
              <tr><td colSpan={2} className="px-4 py-6 text-ink/50">Aucun élève dans cette classe pour l'instant.</td></tr>
            )}
            {students.map((s) => (
              <tr key={s.id}>
                <td className="px-4 py-2 text-ink">{s.first_name} {s.last_name}</td>
                <td className="px-4 py-2">
                  <input
                    type="number" step="0.5" min="0" max="20" value={values[s.id] ?? ""}
                    onChange={(e) => setValues((prev) => ({ ...prev, [s.id]: e.target.value }))}
                    className="w-24 rounded border border-line px-2 py-1.5 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy"
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {error && <p className="mt-3 text-sm text-brick">{error}</p>}
      {result && <p className="mt-3 text-sm text-pass">{result}</p>}

      {students.length > 0 && (
        <button
          onClick={handleSubmit} disabled={submitting}
          className="mt-4 rounded bg-ochre text-navy-deep text-sm font-medium px-5 py-2.5 hover:bg-ochre-dark transition disabled:opacity-60"
        >
          {submitting ? "Enregistrement…" : "Enregistrer les notes"}
        </button>
      )}
    </div>
  );
}

// ---------------- Cahier de texte ----------------

interface LessonLogEntry { id: string; session_date: string; content: string; }

function LessonLogPanel({ classId, subjectId }: { classId: string; subjectId: string }) {
  const [entries, setEntries] = useState<LessonLogEntry[]>([]);
  const [sessionDate, setSessionDate] = useState(new Date().toISOString().slice(0, 10));
  const [content, setContent] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function reload() {
    api.get<LessonLogEntry[]>(`/classes/${classId}/lesson-log`).then(setEntries).catch(() => setEntries([]));
  }
  useEffect(reload, [classId, subjectId]);

  async function handleSubmit() {
    setError(null);
    if (!content.trim()) {
      setError("Le contenu de la séance ne peut pas être vide.");
      return;
    }
    setSubmitting(true);
    try {
      await api.post("/lesson-log", { class_id: classId, subject_id: subjectId, session_date: sessionDate, content });
      setContent("");
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible d'enregistrer.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mt-6 border border-line rounded bg-white p-6">
      <div className="grid sm:grid-cols-[160px_1fr] gap-4">
        <div>
          <label className="block text-sm font-medium text-ink/80 mb-1.5">Date</label>
          <input type="date" value={sessionDate} onChange={(e) => setSessionDate(e.target.value)}
            className="w-full rounded border border-line bg-white px-3 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy" />
        </div>
        <div>
          <label className="block text-sm font-medium text-ink/80 mb-1.5">Contenu de la séance</label>
          <textarea
            value={content} onChange={(e) => setContent(e.target.value)} rows={3}
            placeholder="Ex : Théorème de Pythagore — démonstration et exercices 1 à 5 (p.42)."
            className="w-full rounded border border-line bg-white px-3 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy resize-none"
          />
        </div>
      </div>
      {error && <p className="mt-2 text-sm text-brick">{error}</p>}
      <button onClick={handleSubmit} disabled={submitting} className="mt-3 rounded bg-ochre text-navy-deep text-sm font-medium px-5 py-2.5 hover:bg-ochre-dark transition disabled:opacity-60">
        {submitting ? "Enregistrement…" : "Ajouter au cahier de texte"}
      </button>

      <div className="mt-6 pt-5 border-t border-line space-y-3">
        {entries.length === 0 && <p className="text-sm text-ink/40">Aucune séance enregistrée pour cette classe.</p>}
        {entries.map((e) => (
          <div key={e.id} className="text-[14.5px]">
            <span className="text-ink/50 text-xs mr-2">{e.session_date}</span>
            <span className="text-ink">{e.content}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------- Devoirs ----------------

interface HomeworkItem { id: string; title: string; description: string; due_date: string; }

function HomeworkPanel({ classId, subjectId }: { classId: string; subjectId: string }) {
  const [items, setItems] = useState<HomeworkItem[]>([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function reload() {
    api.get<HomeworkItem[]>(`/classes/${classId}/homework`).then(setItems).catch(() => setItems([]));
  }
  useEffect(reload, [classId, subjectId]);

  async function handleSubmit() {
    setError(null);
    if (!title.trim() || !description.trim() || !dueDate) {
      setError("Tous les champs sont obligatoires.");
      return;
    }
    setSubmitting(true);
    try {
      await api.post("/homework", { class_id: classId, subject_id: subjectId, title, description, due_date: dueDate });
      setTitle(""); setDescription(""); setDueDate("");
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible d'enregistrer.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mt-6 border border-line rounded bg-white p-6">
      <div className="grid sm:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-ink/80 mb-1.5">Titre</label>
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Exercices chapitre 3"
            className="w-full rounded border border-line bg-white px-3 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy" />
        </div>
        <div>
          <label className="block text-sm font-medium text-ink/80 mb-1.5">À rendre le</label>
          <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)}
            className="w-full rounded border border-line bg-white px-3 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy" />
        </div>
        <div className="sm:col-span-2">
          <label className="block text-sm font-medium text-ink/80 mb-1.5">Description</label>
          <textarea
            value={description} onChange={(e) => setDescription(e.target.value)} rows={3}
            placeholder="Faire les exercices 1 à 10 page 42."
            className="w-full rounded border border-line bg-white px-3 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy resize-none"
          />
        </div>
      </div>
      {error && <p className="mt-2 text-sm text-brick">{error}</p>}
      <button onClick={handleSubmit} disabled={submitting} className="mt-3 rounded bg-ochre text-navy-deep text-sm font-medium px-5 py-2.5 hover:bg-ochre-dark transition disabled:opacity-60">
        {submitting ? "Enregistrement…" : "Donner le devoir"}
      </button>

      <div className="mt-6 pt-5 border-t border-line space-y-3">
        {items.length === 0 && <p className="text-sm text-ink/40">Aucun devoir donné pour cette classe.</p>}
        {items.map((h) => (
          <div key={h.id} className="text-[14.5px]">
            <div className="flex items-center justify-between">
              <span className="font-medium text-ink">{h.title}</span>
              <span className="text-ink/40 text-xs">à rendre le {h.due_date}</span>
            </div>
            <p className="text-ink/60 text-[13.5px] mt-0.5">{h.description}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
