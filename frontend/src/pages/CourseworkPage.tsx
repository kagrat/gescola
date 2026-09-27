import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../auth/AuthContext";
import { CAN_MANAGE_COURSEWORK, roleCan } from "../lib/permissions";

interface SchoolClass { id: string; name: string; }
interface Subject { id: string; name: string; }
interface LessonLogEntry { id: string; subject_id: string; session_date: string; content: string; }
interface HomeworkItem { id: string; subject_id: string; title: string; description: string; due_date: string; }

export default function CourseworkPage() {
  const { user } = useAuth();
  const canManage = roleCan(user?.role, CAN_MANAGE_COURSEWORK);
  const [classes, setClasses] = useState<SchoolClass[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [selectedClass, setSelectedClass] = useState("");
  const [tab, setTab] = useState<"cahier" | "devoirs">("cahier");
  const [entries, setEntries] = useState<LessonLogEntry[]>([]);
  const [homework, setHomework] = useState<HomeworkItem[]>([]);

  useEffect(() => {
    api.get<SchoolClass[]>("/classes").then((list) => {
      setClasses(list);
      if (list.length > 0) setSelectedClass(list[0].id);
    });
    api.get<Subject[]>("/subjects").then(setSubjects);
  }, []);

  useEffect(() => {
    if (!selectedClass) return;
    api.get<LessonLogEntry[]>(`/classes/${selectedClass}/lesson-log`).then(setEntries).catch(() => setEntries([]));
    api.get<HomeworkItem[]>(`/classes/${selectedClass}/homework`).then(setHomework).catch(() => setHomework([]));
  }, [selectedClass]);

  const subjectName = (id: string) => subjects.find((s) => s.id === id)?.name ?? "—";

  return (
    <div className="px-10 py-10 max-w-4xl">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-display text-3xl font-medium text-ink">Cahier de texte & devoirs</h1>
          <p className="text-sm text-ink/55 mt-1">
            {canManage ? "Consultez ou complétez le suivi pédagogique de chaque classe." : "Consultez le suivi pédagogique de chaque classe."}
          </p>
        </div>
        <select value={selectedClass} onChange={(e) => setSelectedClass(e.target.value)}
          className="rounded border border-line bg-white px-3 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy">
          {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </div>

      <div className="mt-6 flex gap-1 border-b border-line">
        {([["cahier", "Cahier de texte"], ["devoirs", "Devoirs"]] as const).map(([key, label]) => (
          <button key={key} onClick={() => setTab(key)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition ${
              tab === key ? "border-navy text-navy" : "border-transparent text-ink/50 hover:text-ink"
            }`}>
            {label}
          </button>
        ))}
      </div>

      {tab === "cahier" && (
        <div className="mt-5 space-y-3">
          {entries.length === 0 && <p className="text-sm text-ink/40">Aucune séance enregistrée pour cette classe.</p>}
          {entries.map((e) => (
            <div key={e.id} className="border border-line rounded bg-white p-4">
              <div className="flex items-center gap-2 text-xs text-ink/50">
                <span>{e.session_date}</span><span>·</span><span>{subjectName(e.subject_id)}</span>
              </div>
              <p className="text-[14.5px] text-ink mt-1">{e.content}</p>
            </div>
          ))}
        </div>
      )}

      {tab === "devoirs" && (
        <div className="mt-5 space-y-3">
          {homework.length === 0 && <p className="text-sm text-ink/40">Aucun devoir donné pour cette classe.</p>}
          {homework.map((h) => (
            <div key={h.id} className="border border-line rounded bg-white p-4">
              <div className="flex items-center justify-between">
                <span className="font-medium text-ink">{h.title}</span>
                <span className="text-ink/40 text-xs">{subjectName(h.subject_id)} · à rendre le {h.due_date}</span>
              </div>
              <p className="text-ink/60 text-[13.5px] mt-1">{h.description}</p>
            </div>
          ))}
        </div>
      )}

      {!canManage && (
        <p className="mt-6 text-xs text-ink/40">
          Lecture seule — la saisie est réservée aux enseignants de la classe, à la Direction et au Fondateur.
        </p>
      )}
    </div>
  );
}
