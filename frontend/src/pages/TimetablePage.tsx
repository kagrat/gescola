import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../lib/api";

interface SchoolClass { id: string; name: string; }
interface Subject { id: string; name: string; }
interface StaffUser { id: string; full_name: string; role: string; }
interface Slot {
  id: string; class_id: string; subject_id: string; teacher_id: string;
  day_of_week: string; start_time: string; end_time: string; room: string | null;
}

const DAY_LABELS: Record<string, string> = {
  monday: "Lundi", tuesday: "Mardi", wednesday: "Mercredi", thursday: "Jeudi", friday: "Vendredi", saturday: "Samedi",
};
const DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"];
const inputCls = "w-full rounded border border-line bg-white px-3.5 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy transition";

export default function TimetablePage() {
  const [classes, setClasses] = useState<SchoolClass[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [teachers, setTeachers] = useState<StaffUser[]>([]);
  const [selectedClass, setSelectedClass] = useState<string>("");
  const [slots, setSlots] = useState<Slot[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<SchoolClass[]>("/classes").then((list) => {
      setClasses(list);
      if (list.length > 0) setSelectedClass(list[0].id);
    });
    api.get<Subject[]>("/subjects").then(setSubjects);
    api.get<StaffUser[]>("/users").then((all) => setTeachers(all.filter((u) => u.role === "teacher")));
  }, []);

  function reloadSlots() {
    if (!selectedClass) return;
    api.get<Slot[]>(`/classes/${selectedClass}/timetable`).then(setSlots);
  }
  useEffect(reloadSlots, [selectedClass]);

  const subjectName = (id: string) => subjects.find((s) => s.id === id)?.name ?? "—";
  const teacherName = (id: string) => teachers.find((t) => t.id === id)?.full_name ?? "—";

  async function handleCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    const form = new FormData(e.currentTarget);
    try {
      await api.post("/timetable", {
        class_id: selectedClass,
        subject_id: form.get("subject_id"),
        teacher_id: form.get("teacher_id"),
        day_of_week: form.get("day_of_week"),
        start_time: form.get("start_time"),
        end_time: form.get("end_time"),
        room: form.get("room") || null,
      });
      setShowForm(false);
      reloadSlots();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible de créer ce créneau.");
    }
  }

  async function handleDelete(id: string) {
    await api.del(`/timetable/${id}`);
    reloadSlots();
  }

  return (
    <div className="px-10 py-10 max-w-4xl">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-display text-3xl font-medium text-ink">Emploi du temps</h1>
          <p className="text-sm text-ink/55 mt-1">Créneaux hebdomadaires récurrents, par classe.</p>
        </div>
        <select value={selectedClass} onChange={(e) => setSelectedClass(e.target.value)} className={`${inputCls} w-48`}>
          {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </div>

      <div className="mt-6 flex items-center justify-between">
        <h2 className="font-display text-lg text-ink">Créneaux</h2>
        <button onClick={() => setShowForm((v) => !v)} className="rounded bg-navy text-paper text-sm font-medium px-4 py-2 hover:bg-navy-light transition">
          {showForm ? "Annuler" : "+ Créneau"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="mt-4 border border-line rounded bg-white p-5 grid sm:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-ink/80 mb-1.5">Jour</label>
            <select name="day_of_week" required className={inputCls}>
              {DAYS.map((d) => <option key={d} value={d}>{DAY_LABELS[d]}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-ink/80 mb-1.5">Matière</label>
            <select name="subject_id" required className={inputCls}>
              <option value="">—</option>
              {subjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-ink/80 mb-1.5">Enseignant</label>
            <select name="teacher_id" required className={inputCls}>
              <option value="">—</option>
              {teachers.map((t) => <option key={t.id} value={t.id}>{t.full_name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-ink/80 mb-1.5">Début</label>
            <input name="start_time" type="time" required className={inputCls} />
          </div>
          <div>
            <label className="block text-sm font-medium text-ink/80 mb-1.5">Fin</label>
            <input name="end_time" type="time" required className={inputCls} />
          </div>
          <div>
            <label className="block text-sm font-medium text-ink/80 mb-1.5">Salle (optionnel)</label>
            <input name="room" className={inputCls} />
          </div>
          {error && <p className="sm:col-span-3 text-sm text-brick">{error}</p>}
          <div className="sm:col-span-3">
            <button type="submit" className="rounded bg-ochre text-navy-deep text-sm font-medium px-4 py-2 hover:bg-ochre-dark transition">
              Ajouter le créneau
            </button>
          </div>
        </form>
      )}

      <div className="mt-4 space-y-5">
        {DAYS.map((day) => {
          const daySlots = slots.filter((s) => s.day_of_week === day).sort((a, b) => a.start_time.localeCompare(b.start_time));
          if (daySlots.length === 0) return null;
          return (
            <div key={day}>
              <p className="text-xs font-semibold text-ink/40 uppercase tracking-wide mb-2">{DAY_LABELS[day]}</p>
              <div className="border border-line rounded bg-white overflow-hidden">
                <table className="w-full text-[14.5px]">
                  <tbody>
                    {daySlots.map((s) => (
                      <tr key={s.id} className="border-b border-line last:border-none">
                        <td className="px-4 py-2.5 text-ink/60 whitespace-nowrap">{s.start_time.slice(0, 5)} – {s.end_time.slice(0, 5)}</td>
                        <td className="px-4 py-2.5 font-medium">{subjectName(s.subject_id)}</td>
                        <td className="px-4 py-2.5 text-ink/60">{teacherName(s.teacher_id)}</td>
                        <td className="px-4 py-2.5 text-ink/40">{s.room ?? ""}</td>
                        <td className="px-4 py-2.5 text-right">
                          <button onClick={() => handleDelete(s.id)} className="text-brick text-sm hover:underline">Retirer</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          );
        })}
        {slots.length === 0 && <p className="text-sm text-ink/40">Aucun créneau pour cette classe.</p>}
      </div>
    </div>
  );
}
