import { useEffect, useState } from "react";
import { api } from "../lib/api";

interface Subject { id: string; name: string; }
interface SchoolClass { id: string; name: string; }
interface Slot {
  id: string; class_id: string; subject_id: string; day_of_week: string;
  start_time: string; end_time: string; room: string | null;
}

const DAY_LABELS: Record<string, string> = {
  monday: "Lundi", tuesday: "Mardi", wednesday: "Mercredi", thursday: "Jeudi", friday: "Vendredi", saturday: "Samedi",
};
const DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"];

export default function MyTimetablePage() {
  const [slots, setSlots] = useState<Slot[] | null>(null);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [classes, setClasses] = useState<SchoolClass[]>([]);

  useEffect(() => {
    api.get<Slot[]>("/users/me/timetable").then(setSlots);
    api.get<Subject[]>("/subjects").then(setSubjects).catch(() => setSubjects([]));
    api.get<SchoolClass[]>("/classes").then(setClasses).catch(() => setClasses([]));
  }, []);

  const subjectName = (id: string) => subjects.find((s) => s.id === id)?.name ?? "—";
  const className = (id: string) => classes.find((c) => c.id === id)?.name ?? "—";

  return (
    <div className="px-10 py-10 max-w-3xl">
      <h1 className="font-display text-3xl font-medium text-ink">Mon emploi du temps</h1>
      <p className="text-sm text-ink/55 mt-1">Vos cours de la semaine.</p>

      {slots === null && <p className="mt-8 text-sm text-ink/40">Chargement…</p>}
      {slots && slots.length === 0 && <p className="mt-8 text-sm text-ink/40">Aucun cours planifié pour l'instant.</p>}

      <div className="mt-8 space-y-5">
        {DAYS.map((day) => {
          const daySlots = (slots ?? []).filter((s) => s.day_of_week === day).sort((a, b) => a.start_time.localeCompare(b.start_time));
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
                        <td className="px-4 py-2.5 text-ink/60">{className(s.class_id)}</td>
                        <td className="px-4 py-2.5 text-ink/40">{s.room ?? ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
