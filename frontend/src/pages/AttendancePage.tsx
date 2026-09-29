import { useEffect, useState } from "react";
import { api, ApiError } from "../lib/api";
import RequireRole from "../components/RequireRole";
import { CAN_MANAGE_ATTENDANCE } from "../lib/permissions";

interface SchoolClass { id: string; name: string; }
interface RosterRow {
  student_id: string; first_name: string; last_name: string; attendance_id: string | null;
  status: "present" | "absent" | "late" | null; justified: boolean;
}

type Status = "present" | "absent" | "late";
const STATUS_OPTIONS: { value: Status; label: string; activeCls: string }[] = [
  { value: "present", label: "Présent", activeCls: "bg-pass text-white border-pass" },
  { value: "absent", label: "Absent", activeCls: "bg-brick text-white border-brick" },
  { value: "late", label: "Retard", activeCls: "bg-ochre text-navy-deep border-ochre" },
];

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function AttendancePage() {
  return (
    <RequireRole roles={CAN_MANAGE_ATTENDANCE}>
      <AttendancePageContent />
    </RequireRole>
  );
}

function AttendancePageContent() {
  const [classes, setClasses] = useState<SchoolClass[]>([]);
  const [classId, setClassId] = useState("");
  const [date, setDate] = useState(todayIso());
  const [roster, setRoster] = useState<RosterRow[]>([]);
  const [draft, setDraft] = useState<Record<string, { status: Status; justified: boolean }>>({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ tone: "ok" | "error"; text: string } | null>(null);

  useEffect(() => {
    api.get<SchoolClass[]>("/classes").then((list) => {
      setClasses(list);
      if (list.length > 0) setClassId((current) => current || list[0].id);
    }).catch(() => setClasses([]));
  }, []);

  function reload() {
    if (!classId) return;
    setLoading(true);
    setMessage(null);
    api.get<RosterRow[]>(`/classes/${classId}/attendance?date=${date}`)
      .then((list) => {
        setRoster(list);
        setDraft(Object.fromEntries(list.map((r) => [r.student_id, { status: r.status ?? "present", justified: r.justified }])));
      })
      .catch(() => { setRoster([]); setDraft({}); })
      .finally(() => setLoading(false));
  }
  useEffect(reload, [classId, date]);

  function setStatus(studentId: string, status: Status) {
    setDraft((prev) => ({ ...prev, [studentId]: { status, justified: status === "absent" ? (prev[studentId]?.justified ?? false) : false } }));
  }
  function setJustified(studentId: string, justified: boolean) {
    setDraft((prev) => ({ ...prev, [studentId]: { ...prev[studentId], justified } }));
  }
  function markAllPresent() {
    setDraft(Object.fromEntries(roster.map((r) => [r.student_id, { status: "present" as Status, justified: false }])));
  }

  async function save() {
    setSaving(true);
    setMessage(null);
    try {
      await api.post("/attendance/bulk", {
        class_id: classId,
        date,
        entries: roster.map((r) => ({ student_id: r.student_id, ...draft[r.student_id] })),
      });
      setMessage({ tone: "ok", text: "Appel enregistré." });
      reload();
    } catch (err) {
      setMessage({ tone: "error", text: err instanceof ApiError ? err.message : "Impossible d'enregistrer l'appel." });
    } finally {
      setSaving(false);
    }
  }

  const alreadyTaken = roster.some((r) => r.status !== null);
  const counts = roster.reduce(
    (acc, r) => { const st = draft[r.student_id]?.status; if (st) acc[st] += 1; return acc; },
    { present: 0, absent: 0, late: 0 } as Record<Status, number>,
  );

  return (
    <div className="px-10 py-10 max-w-4xl">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-medium text-ink">Présences</h1>
          <p className="text-sm text-ink/55 mt-1">Faites l'appel d'une classe entière en une seule fois, ou corrigez un appel déjà fait.</p>
        </div>
      </div>

      <div className="mt-6 grid sm:grid-cols-[1fr_200px] gap-4 border border-line rounded bg-white p-4">
        <div>
          <label className="block text-xs font-semibold text-ink/50 mb-1.5">Classe</label>
          <select value={classId} onChange={(e) => setClassId(e.target.value)}
            className="w-full rounded border border-line bg-white px-3 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy">
            {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs font-semibold text-ink/50 mb-1.5">Date</label>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} max={todayIso()}
            className="w-full rounded border border-line bg-white px-3 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy" />
        </div>
      </div>

      {alreadyTaken && !loading && (
        <p className="mt-4 text-sm text-ochre-dark bg-ochre/10 border border-ochre/20 rounded px-3 py-2">
          L'appel de cette classe a déjà été fait pour cette date — vous consultez et pouvez corriger un appel existant.
        </p>
      )}
      {message && (
        <p className={`mt-4 text-sm rounded px-3 py-2 border ${message.tone === "ok" ? "text-[#1F7A52] bg-pass/10 border-pass/20" : "text-brick bg-brick/10 border-brick/20"}`}>{message.text}</p>
      )}

      <div className="mt-6 flex items-center justify-between">
        <div className="flex items-center gap-4 text-sm text-ink/60">
          <span><b className="text-pass">{counts.present}</b> présent{counts.present > 1 ? "s" : ""}</span>
          <span><b className="text-brick">{counts.absent}</b> absent{counts.absent > 1 ? "s" : ""}</span>
          <span><b className="text-ochre-dark">{counts.late}</b> retard{counts.late > 1 ? "s" : ""}</span>
        </div>
        <button onClick={markAllPresent} disabled={roster.length === 0} className="text-sm text-navy underline underline-offset-2 hover:text-navy-light disabled:opacity-40">
          Tout marquer présent
        </button>
      </div>

      <div className="mt-3 border border-line rounded bg-white overflow-hidden">
        <table className="w-full text-[14.5px]">
          <tbody className="divide-y divide-line">
            {loading && <tr><td className="px-4 py-6 text-ink/50">Chargement…</td></tr>}
            {!loading && roster.length === 0 && <tr><td className="px-4 py-6 text-ink/50">Aucun élève actif dans cette classe.</td></tr>}
            {!loading && roster.map((r) => {
              const current = draft[r.student_id];
              return (
                <tr key={r.student_id}>
                  <td className="px-4 py-3 text-ink font-medium w-56">{r.last_name.toUpperCase()} {r.first_name}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      {STATUS_OPTIONS.map((opt) => (
                        <button
                          key={opt.value} onClick={() => setStatus(r.student_id, opt.value)}
                          className={`rounded-full px-3.5 py-1.5 text-xs font-semibold border transition ${current?.status === opt.value ? opt.activeCls : "bg-white text-ink/60 border-line hover:border-navy/40"}`}
                        >
                          {opt.label}
                        </button>
                      ))}
                      {current?.status === "absent" && (
                        <label className="flex items-center gap-1.5 text-xs text-ink/60 ml-2">
                          <input type="checkbox" checked={current.justified} onChange={(e) => setJustified(r.student_id, e.target.checked)} className="w-3.5 h-3.5 accent-navy" />
                          Justifiée
                        </label>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {roster.length > 0 && (
        <button onClick={save} disabled={saving} className="mt-5 rounded bg-navy text-paper text-sm font-medium px-5 py-2.5 hover:bg-navy-light transition disabled:opacity-60">
          {saving ? "Enregistrement…" : alreadyTaken ? "Enregistrer les corrections" : "Enregistrer l'appel"}
        </button>
      )}
    </div>
  );
}
