import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { CalendarClock, Plus } from "lucide-react";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../auth/AuthContext";
import RequireRole from "../components/RequireRole";
import { CAN_USE_MESSAGING } from "../lib/permissions";

interface ThreadSummary {
  id: string; student_name: string; subject: string; kind: "conversation" | "convocation"; meeting_at: string | null;
  last_message_at: string; last_message_preview: string; last_message_sender_id: string; unread: boolean; participant_names: string[];
}
interface Participant { user_id: string; full_name: string; role: string; last_read_at: string | null; }
interface Message { id: string; sender_id: string; sender_name: string; sender_role: string; body: string; created_at: string; }
interface ThreadDetail {
  id: string; student_name: string; subject: string; kind: "conversation" | "convocation"; meeting_at: string | null;
  meeting_place: string | null; created_by: string; participants: Participant[]; messages: Message[];
}
interface Contact { id: string; full_name: string; role: string; detail: string | null; }
interface Student { id: string; first_name: string; last_name: string; class_id: string | null; }
interface SchoolClass { id: string; head_teacher_id: string | null; }
interface Assignment { teacher_id: string; class_id: string; }

const ROLE_LABELS: Record<string, string> = {
  founder: "Fondateur", school_admin: "Direction", censor: "Censeur", supervisor: "Surveillant", accountant: "Comptable",
  staff: "Secrétariat", teacher: "Enseignant", parent: "Parent",
};
const inputCls = "w-full rounded border border-line bg-white px-3.5 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy transition";

function whenLabel(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  return d.toDateString() === now.toDateString()
    ? d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })
    : d.toLocaleDateString("fr-FR", { day: "2-digit", month: "short" });
}
const fullWhen = (iso: string) => new Date(iso).toLocaleString("fr-FR", { dateStyle: "medium", timeStyle: "short" });
const notifyChanged = () => window.dispatchEvent(new Event("gescola:messages-changed"));

export default function MessagesPage() {
  return (
    <RequireRole roles={CAN_USE_MESSAGING}>
      <MessagesPageContent />
    </RequireRole>
  );
}

function MessagesPageContent() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [onlyUnread, setOnlyUnread] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ThreadDetail | null>(null);
  const [composing, setComposing] = useState(false);
  const [prefill, setPrefill] = useState<{ studentId?: string; subject?: string } | null>(null);

  const reloadThreads = useCallback(() => {
    api.get<ThreadSummary[]>(`/messages/threads${onlyUnread ? "?unread=true" : ""}`)
      .then(setThreads).catch(() => setThreads([])).finally(() => setLoading(false));
  }, [onlyUnread]);
  useEffect(reloadThreads, [reloadThreads]);

  // Arrivée depuis une autre page (ex. « Informer les parents » de la Discipline) : ouvre la rédaction pré-remplie.
  useEffect(() => {
    if (params.get("nouveau") === "1") {
      setPrefill({ studentId: params.get("eleve") ?? undefined, subject: params.get("sujet") ?? undefined });
      setComposing(true);
      setParams({}, { replace: true });
    }
  }, [params, setParams]);

  const openThread = useCallback(async (id: string) => {
    setSelectedId(id);
    try {
      const d = await api.get<ThreadDetail>(`/messages/threads/${id}`);
      setDetail(d);
      await api.post(`/messages/threads/${id}/read`);
      reloadThreads();
      notifyChanged();
    } catch { setDetail(null); }
  }, [reloadThreads]);

  return (
    <div className="px-8 py-8 max-w-7xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-3xl font-medium text-ink">Messages</h1>
          <p className="text-sm text-ink/55 mt-1">
            {user?.role === "parent" ? "Vos échanges avec l'établissement au sujet de vos enfants." : "Vos échanges avec les familles."}
          </p>
        </div>
        <button onClick={() => { setPrefill(null); setComposing(true); }} className="flex items-center gap-1.5 rounded bg-navy text-paper text-sm font-medium px-4 py-2.5 hover:bg-navy-light transition">
          <Plus className="w-4 h-4" /> Nouveau message
        </button>
      </div>

      <div className="mt-6 grid lg:grid-cols-[340px_1fr] gap-5 items-start">
        <aside className="border border-line rounded bg-white overflow-hidden">
          <div className="flex gap-2 p-3 border-b border-line">
            {([[false, "Toutes"], [true, "Non lues"]] as const).map(([value, label]) => (
              <button key={label} onClick={() => setOnlyUnread(value)}
                className={`rounded-full px-3.5 py-1.5 text-xs font-semibold border transition ${onlyUnread === value ? "bg-navy text-paper border-navy" : "bg-white text-ink/60 border-line hover:border-navy/40"}`}>
                {label}
              </button>
            ))}
          </div>
          <ul className="divide-y divide-line max-h-[68vh] overflow-y-auto">
            {loading && <li className="px-4 py-6 text-sm text-ink/45">Chargement…</li>}
            {!loading && threads.length === 0 && (
              <li className="px-4 py-8 text-sm text-ink/45">{onlyUnread ? "Aucun message non lu." : "Aucune conversation pour l'instant."}</li>
            )}
            {threads.map((t) => (
              <li key={t.id}>
                <button onClick={() => openThread(t.id)} className={`w-full text-left px-4 py-3 hover:bg-paper transition ${selectedId === t.id ? "bg-paper" : ""}`}>
                  <div className="flex items-center gap-2">
                    {t.unread && <span aria-label="Non lu" className="w-2 h-2 rounded-full bg-brick shrink-0" />}
                    <span className={`flex-1 truncate text-[14.5px] ${t.unread ? "font-semibold text-ink" : "text-ink/80"}`}>{t.subject}</span>
                    <span className="text-[11px] text-ink/40 shrink-0">{whenLabel(t.last_message_at)}</span>
                  </div>
                  <p className="text-xs text-ink/50 mt-0.5 truncate">
                    {t.kind === "convocation" && <span className="text-ochre-dark font-semibold">Convocation · </span>}
                    {t.student_name} · {t.participant_names.join(", ")}
                  </p>
                  <p className="text-[13px] text-ink/55 mt-1 line-clamp-2">{t.last_message_preview}</p>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <section className="border border-line rounded bg-white min-h-[320px]">
          {detail && selectedId ? (
            <Conversation
              key={detail.id} detail={detail} meId={user?.id ?? ""}
              onSent={async () => { await openThread(detail.id); }}
            />
          ) : (
            <p className="px-6 py-16 text-center text-sm text-ink/40">Sélectionnez une conversation, ou écrivez un nouveau message.</p>
          )}
        </section>
      </div>

      {composing && (
        <ComposeDialog
          prefill={prefill} onClose={() => setComposing(false)}
          onCreated={async (id) => { setComposing(false); reloadThreads(); notifyChanged(); await openThread(id); }}
        />
      )}
    </div>
  );
}

function Conversation({ detail, meId, onSent }: { detail: ThreadDetail; meId: string; onSent: () => Promise<void> }) {
  const [body, setBody] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => { endRef.current?.scrollIntoView({ block: "end" }); }, [detail.messages.length]);

  const others = detail.participants.filter((p) => p.user_id !== meId);
  const lastMine = [...detail.messages].reverse().find((m) => m.sender_id === meId);
  // « Vu » : tous les autres participants ont lu jusqu'à ce message (ou après).
  const seen = lastMine && others.length > 0 && others.every((p) => p.last_read_at && new Date(p.last_read_at) >= new Date(lastMine.created_at));

  async function send(e: FormEvent) {
    e.preventDefault();
    if (!body.trim()) return;
    setError(null);
    setSending(true);
    try {
      await api.post(`/messages/threads/${detail.id}/messages`, { body });
      setBody("");
      await onSent();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible d'envoyer le message.");
    } finally { setSending(false); }
  }

  return (
    <div className="flex flex-col h-full">
      <header className="px-6 py-4 border-b border-line">
        <h2 className="font-display text-xl text-ink">{detail.subject}</h2>
        <p className="text-xs text-ink/50 mt-1">
          À propos de <b className="text-ink/70">{detail.student_name}</b> · avec {others.map((p) => `${p.full_name} (${ROLE_LABELS[p.role] ?? p.role})`).join(", ")}
        </p>
        {others.length > 1 && <p className="text-xs text-ink/40 mt-0.5">Tous les participants voient l'ensemble des messages.</p>}
        {detail.kind === "convocation" && detail.meeting_at && (
          <div className="mt-3 flex items-start gap-2.5 rounded border border-ochre/30 bg-ochre/10 px-3.5 py-2.5 text-sm text-ochre-dark">
            <CalendarClock className="w-4 h-4 mt-0.5 shrink-0" />
            <div><b>Convocation</b> — {fullWhen(detail.meeting_at)}{detail.meeting_place ? ` · ${detail.meeting_place}` : ""}</div>
          </div>
        )}
      </header>

      <div className="px-6 py-5 space-y-3 max-h-[52vh] overflow-y-auto" aria-live="polite">
        {detail.messages.map((m) => {
          const mine = m.sender_id === meId;
          return (
            <div key={m.id} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[80%] rounded-lg px-4 py-2.5 ${mine ? "bg-navy text-paper" : "bg-paper text-ink"}`}>
                {!mine && <p className="text-[11.5px] font-semibold opacity-70 mb-0.5">{m.sender_name} · {ROLE_LABELS[m.sender_role] ?? m.sender_role}</p>}
                <p className="text-[14.5px] whitespace-pre-wrap break-words">{m.body}</p>
                <p className={`text-[11px] mt-1 ${mine ? "text-paper/60" : "text-ink/40"}`}>
                  {fullWhen(m.created_at)}{mine && lastMine?.id === m.id && (seen ? " · Vu" : " · Envoyé")}
                </p>
              </div>
            </div>
          );
        })}
        <div ref={endRef} />
      </div>

      <form onSubmit={send} className="px-6 py-4 border-t border-line">
        <label htmlFor="reply" className="sr-only">Votre réponse</label>
        <textarea id="reply" value={body} onChange={(e) => setBody(e.target.value)} rows={3} maxLength={5000} placeholder="Votre réponse…" className={`${inputCls} resize-none`} />
        {error && <p className="mt-2 text-sm text-brick">{error}</p>}
        <div className="mt-2 flex items-center justify-between">
          <span className="text-xs text-ink/40">{body.length}/5000</span>
          <button type="submit" disabled={sending || !body.trim()} className="rounded bg-ochre text-navy-deep text-sm font-medium px-5 py-2 hover:bg-ochre-dark transition disabled:opacity-50">
            {sending ? "Envoi…" : "Envoyer"}
          </button>
        </div>
      </form>
    </div>
  );
}

function ComposeDialog({ prefill, onClose, onCreated }: { prefill: { studentId?: string; subject?: string } | null; onClose: () => void; onCreated: (id: string) => void | Promise<void> }) {
  const { user } = useAuth();
  const isParent = user?.role === "parent";
  const [students, setStudents] = useState<{ id: string; label: string }[]>([]);
  const [studentId, setStudentId] = useState(prefill?.studentId ?? "");
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [contactsLoading, setContactsLoading] = useState(false);
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [kind, setKind] = useState<"conversation" | "convocation">("conversation");
  const [subject, setSubject] = useState(prefill?.subject ?? "");
  const [body, setBody] = useState("");
  const [meetingAt, setMeetingAt] = useState("");
  const [meetingPlace, setMeetingPlace] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  // Élèves proposés : les enfants du parent ; pour le personnel, les élèves qu'il a le droit de contacter
  // (un enseignant : ceux de ses classes — le serveur reste seul juge).
  useEffect(() => {
    const label = (s: Student) => `${s.last_name.toUpperCase()} ${s.first_name}`;
    if (isParent) {
      api.get<Student[]>("/me/children").then((list) => {
        setStudents(list.map((s) => ({ id: s.id, label: label(s) })));
        if (!studentId && list.length === 1) setStudentId(list[0].id);
      }).catch(() => setStudents([]));
      return;
    }
    (async () => {
      const all = await api.get<Student[]>("/students").catch(() => [] as Student[]);
      let allowed = all;
      if (user?.role === "teacher") {
        const [assignments, classes] = await Promise.all([
          api.get<Assignment[]>("/teacher-assignments").catch(() => [] as Assignment[]),
          api.get<SchoolClass[]>("/classes").catch(() => [] as SchoolClass[]),
        ]);
        const mine = new Set([
          ...assignments.filter((a) => a.teacher_id === user.id).map((a) => a.class_id),
          ...classes.filter((c) => c.head_teacher_id === user.id).map((c) => c.id),
        ]);
        allowed = all.filter((s) => s.class_id && mine.has(s.class_id));
      }
      setStudents(allowed.map((s) => ({ id: s.id, label: label(s) })));
    })();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isParent]);

  useEffect(() => {
    setChosen(new Set());
    setContacts([]);
    if (!studentId) return;
    setContactsLoading(true);
    const url = isParent ? `/children/${studentId}/contacts` : `/messages/guardians?student_id=${studentId}`;
    api.get<Contact[]>(url).then((list) => {
      setContacts(list);
      if (!isParent) setChosen(new Set(list.map((c) => c.id)));   // personnel → parents : tous cochés par défaut
    }).catch((err) => setError(err instanceof ApiError ? err.message : "Impossible de charger les destinataires."))
      .finally(() => setContactsLoading(false));
  }, [studentId, isParent]);

  const grouped = useMemo(() => {
    if (!isParent) return [{ title: "Parents de l'élève", items: contacts }];
    return [
      { title: "Enseignants de la classe", items: contacts.filter((c) => c.role === "teacher") },
      { title: "Administration", items: contacts.filter((c) => c.role !== "teacher") },
    ].filter((g) => g.items.length > 0);
  }, [contacts, isParent]);

  function toggle(id: string) {
    setChosen((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else if (!isParent || next.size < 3) next.add(id);
      return next;
    });
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (chosen.size === 0) { setError(isParent ? "Choisissez à qui vous écrivez." : "Choisissez au moins un parent."); return; }
    if (kind === "convocation" && !meetingAt) { setError("Indiquez la date et l'heure de la convocation."); return; }
    setSending(true);
    try {
      const created = await api.post<ThreadDetail>("/messages/threads", {
        student_id: studentId, subject, body, kind, recipient_user_ids: [...chosen],
        meeting_at: kind === "convocation" ? new Date(meetingAt).toISOString() : null,
        meeting_place: kind === "convocation" ? meetingPlace || null : null,
      });
      await onCreated(created.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible d'envoyer le message.");
    } finally { setSending(false); }
  }

  return (
    <div className="fixed inset-0 bg-ink/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <form onSubmit={submit} onClick={(e) => e.stopPropagation()} aria-label="Nouveau message" className="bg-white rounded-lg w-full max-w-xl max-h-[92vh] overflow-y-auto p-6 space-y-4">
        <h3 className="font-display text-xl text-ink">Nouveau message</h3>

        <div>
          <label htmlFor="c_student" className="block text-sm font-medium text-ink/80 mb-1.5">{isParent ? "Votre enfant" : "Élève concerné"}</label>
          <select id="c_student" value={studentId} onChange={(e) => setStudentId(e.target.value)} required className={inputCls}>
            <option value="">—</option>
            {students.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
          </select>
          {!isParent && user?.role === "teacher" && <p className="text-xs text-ink/45 mt-1">Vous ne pouvez écrire qu'aux parents d'élèves de vos classes.</p>}
        </div>

        {studentId && (
          <fieldset>
            <legend className="block text-sm font-medium text-ink/80 mb-1.5">{isParent ? "À qui écrivez-vous ? (3 au plus)" : "Destinataires"}</legend>
            {contactsLoading && <p className="text-sm text-ink/45">Chargement…</p>}
            {!contactsLoading && contacts.length === 0 && (
              <p className="text-sm text-ink/45">
                {isParent ? "Aucun contact disponible pour le moment." : "Aucun parent (actif) n'est rattaché à cet élève."}
              </p>
            )}
            {grouped.map((g) => (
              <div key={g.title} className="mb-2">
                <p className="text-xs font-semibold text-ink/40 uppercase tracking-wide mb-1">{g.title}</p>
                <div className="space-y-1.5">
                  {g.items.map((c) => (
                    <label key={c.id} className="flex items-center gap-2.5 text-sm text-ink/80 cursor-pointer">
                      <input type="checkbox" checked={chosen.has(c.id)} onChange={() => toggle(c.id)} className="w-4 h-4 accent-navy" />
                      <span>{c.full_name}</span>
                      <span className="text-ink/40 text-xs">{isParent ? c.detail ?? ROLE_LABELS[c.role] : c.detail}</span>
                    </label>
                  ))}
                </div>
              </div>
            ))}
            {!isParent && chosen.size > 1 && <p className="text-xs text-ink/45">Tous les parents cochés verront l'ensemble des échanges.</p>}
          </fieldset>
        )}

        {!isParent && (
          <div className="flex gap-2" role="radiogroup" aria-label="Type de message">
            {([["conversation", "Message"], ["convocation", "Convocation"]] as const).map(([value, label]) => (
              <button key={value} type="button" role="radio" aria-checked={kind === value} onClick={() => setKind(value)}
                className={`rounded-full px-4 py-1.5 text-sm font-medium border transition ${kind === value ? "bg-navy text-paper border-navy" : "bg-white text-ink/60 border-line hover:border-navy/40"}`}>
                {label}
              </button>
            ))}
          </div>
        )}

        {kind === "convocation" && (
          <div className="grid sm:grid-cols-2 gap-3">
            <div><label className="block text-sm font-medium text-ink/80 mb-1.5">Date et heure</label><input type="datetime-local" value={meetingAt} onChange={(e) => setMeetingAt(e.target.value)} required className={inputCls} /></div>
            <div><label className="block text-sm font-medium text-ink/80 mb-1.5">Lieu</label><input value={meetingPlace} onChange={(e) => setMeetingPlace(e.target.value)} maxLength={200} placeholder="Bureau du Censeur" className={inputCls} /></div>
          </div>
        )}

        <div><label htmlFor="c_subject" className="block text-sm font-medium text-ink/80 mb-1.5">Objet</label><input id="c_subject" value={subject} onChange={(e) => setSubject(e.target.value)} required maxLength={200} className={inputCls} /></div>
        <div><label htmlFor="c_body" className="block text-sm font-medium text-ink/80 mb-1.5">Message</label><textarea id="c_body" value={body} onChange={(e) => setBody(e.target.value)} required rows={5} maxLength={5000} className={`${inputCls} resize-none`} /></div>

        {error && <p className="text-sm text-brick">{error}</p>}
        <div className="flex justify-end gap-3 pt-1">
          <button type="button" onClick={onClose} className="text-sm text-ink/60 px-3 py-2">Annuler</button>
          <button type="submit" disabled={sending} className="rounded bg-ochre text-navy-deep text-sm font-medium px-5 py-2 hover:bg-ochre-dark transition disabled:opacity-60">
            {sending ? "Envoi…" : kind === "convocation" ? "Envoyer la convocation" : "Envoyer"}
          </button>
        </div>
      </form>
    </div>
  );
}
