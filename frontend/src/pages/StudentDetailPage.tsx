import { useEffect, useState, type FormEvent } from "react";
import { useParams, Link } from "react-router-dom";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../auth/AuthContext";
import StatusPill from "../components/StatusPill";
import {
  CAN_LOCK_GRADES, CAN_MANAGE_ATTENDANCE, CAN_MANAGE_FINANCE, CAN_MANAGE_REGISTRY, CAN_OVERRIDE_LOCKED_GRADES,
  CAN_READ_GRADES, CAN_WRITE_GRADES, roleCan,
} from "../lib/permissions";

interface Student {
  id: string;
  first_name: string;
  last_name: string;
  class_id: string | null;
  status: string;
}
interface Subject {
  id: string;
  name: string;
}
interface Grade {
  id: string;
  subject_id: string;
  term: string;
  evaluation_label: string;
  value: number;
  coefficient: number;
  is_locked: boolean;
}
interface Average {
  general_average: number;
  subject_averages: Record<string, number>;
}
interface Attendance {
  id: string;
  date: string;
  status: string;
  justified: boolean;
}
interface Invoice {
  id: string;
  label: string;
  amount_due: number;
  due_date: string;
  status: string;
  amount_paid: number;
  balance: number;
}

const TERMS = ["T1", "T2", "T3"];

export default function StudentDetailPage() {
  const { studentId } = useParams<{ studentId: string }>();
  const { user } = useAuth();
  const [student, setStudent] = useState<Student | null>(null);
  const [notFound, setNotFound] = useState(false);

  function reloadStudent() {
    if (!studentId) return;
    api
      .get<Student>(`/students/${studentId}`)
      .then(setStudent)
      .catch(() => setNotFound(true));
  }
  useEffect(reloadStudent, [studentId]);

  if (notFound) {
    return (
      <div className="px-10 py-10">
        <p className="text-ink/60">Élève introuvable.</p>
        <Link to="/eleves" className="text-navy underline underline-offset-2 text-sm mt-2 inline-block">
          Retour à la liste
        </Link>
      </div>
    );
  }
  if (!student || !studentId) return <div className="px-10 py-10 text-ink/50">Chargement…</div>;

  return (
    <div className="px-10 py-10 max-w-4xl">
      <Link to="/eleves" className="text-sm text-ink/50 hover:text-ink transition">
        ← Élèves
      </Link>
      <h1 className="font-display text-3xl font-medium text-ink mt-2">
        {student.first_name} {student.last_name}
      </h1>
      <span className="inline-block mt-1"><StatusPill label={student.status === "active" ? "Actif" : student.status} tone={student.status === "active" ? "ok" : "neutral"} /></span>

      {roleCan(user?.role, CAN_MANAGE_REGISTRY) && (
        <ClassAssignment studentId={studentId} classId={student.class_id} onUpdated={reloadStudent} />
      )}

      {roleCan(user?.role, CAN_READ_GRADES) && <GradesSection studentId={studentId} role={user?.role} />}
      {roleCan(user?.role, CAN_MANAGE_ATTENDANCE) && <AttendanceSection studentId={studentId} />}
      {roleCan(user?.role, CAN_MANAGE_FINANCE) && <FinanceSection studentId={studentId} />}
      {roleCan(user?.role, CAN_MANAGE_REGISTRY) && <LibrarySection studentId={studentId} />}
      {roleCan(user?.role, CAN_MANAGE_FINANCE) && <CanteenSection studentId={studentId} />}
    </div>
  );
}

// ---------------- Classe (rattachement) ----------------

function ClassAssignment({
  studentId, classId, onUpdated,
}: { studentId: string; classId: string | null; onUpdated: () => void }) {
  const [classes, setClasses] = useState<{ id: string; name: string }[]>([]);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<{ id: string; name: string }[]>("/classes").then(setClasses).catch(() => setClasses([]));
  }, []);

  const currentName = classes.find((c) => c.id === classId)?.name ?? "Non affecté";

  async function handleChange(newClassId: string) {
    setError(null);
    try {
      await api.patch(`/students/${studentId}`, { class_id: newClassId || null });
      setEditing(false);
      onUpdated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible de changer la classe.");
    }
  }

  return (
    <div className="mt-3 flex items-center gap-2 text-sm">
      <span className="text-ink/50">Classe :</span>
      {editing ? (
        <select
          autoFocus defaultValue={classId ?? ""} onChange={(e) => handleChange(e.target.value)} onBlur={() => setEditing(false)}
          className="rounded border border-line bg-white px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy"
        >
          <option value="">— Non affecté —</option>
          {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      ) : (
        <button onClick={() => setEditing(true)} className="text-navy font-medium hover:underline">
          {currentName}
        </button>
      )}
      {error && <span className="text-brick text-xs">{error}</span>}
    </div>
  );
}

// ---------------- Notes ----------------

function GradesSection({ studentId, role }: { studentId: string; role: string | undefined }) {
  const [term, setTerm] = useState("T1");
  const [grades, setGrades] = useState<Grade[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [average, setAverage] = useState<Average | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lockMessage, setLockMessage] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [editError, setEditError] = useState<string | null>(null);

  function reload() {
    api.get<Grade[]>(`/students/${studentId}/grades?term=${term}`).then(setGrades);
    api.get<Average>(`/students/${studentId}/average?term=${term}`).then(setAverage).catch(() => setAverage(null));
  }

  useEffect(() => {
    api.get<Subject[]>("/subjects").then(setSubjects).catch(() => setSubjects([]));
  }, []);
  useEffect(reload, [studentId, term]);

  const subjectName = (id: string) => subjects.find((s) => s.id === id)?.name ?? "—";

  async function handleAdd(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    const form = new FormData(e.currentTarget);
    try {
      await api.post("/grades", {
        student_id: studentId,
        subject_id: form.get("subject_id"),
        term,
        evaluation_label: form.get("evaluation_label"),
        value: Number(form.get("value")),
        coefficient: Number(form.get("coefficient") || 1),
      });
      setShowForm(false);
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible d'enregistrer la note.");
    }
  }

  async function handleLock() {
    setLockMessage(null);
    try {
      const resp = await api.post<{ locked_count: number }>(`/students/${studentId}/grades/lock?term=${term}`);
      setLockMessage(`${resp.locked_count} note(s) verrouillée(s) pour ${term}.`);
      reload();
    } catch (err) {
      setLockMessage(err instanceof ApiError ? err.message : "Impossible de verrouiller.");
    }
  }

  function startEdit(g: Grade) {
    setEditingId(g.id);
    setEditValue(String(g.value));
    setEditError(null);
  }

  async function submitEdit(gradeId: string) {
    setEditError(null);
    try {
      await api.patch(`/grades/${gradeId}`, { value: Number(editValue) });
      setEditingId(null);
      reload();
    } catch (err) {
      setEditError(err instanceof ApiError ? err.message : "Impossible de modifier cette note.");
    }
  }

  return (
    <section className="mt-10">
      <SectionHeader
        title="Notes"
        right={
          <div className="flex items-center gap-2">
            <TermSelect term={term} onChange={setTerm} />
            {roleCan(role, CAN_WRITE_GRADES) && (
              <button onClick={() => setShowForm((v) => !v)} className="rounded bg-navy text-paper text-sm font-medium px-3.5 py-2 hover:bg-navy-light transition">
                {showForm ? "Annuler" : "+ Note"}
              </button>
            )}
          </div>
        }
      />

      {average && (
        <p className="text-sm text-ink/60 mt-2">
          Moyenne générale {term} : <span className="font-display text-lg text-navy">{average.general_average.toFixed(2)}</span> / 20
        </p>
      )}

      {showForm && (
        <form onSubmit={handleAdd} className="mt-4 border border-line rounded bg-white p-5 grid sm:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium text-ink/80 mb-1.5">Matière</label>
            <select name="subject_id" required className="w-full rounded border border-line bg-white px-3 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy">
              <option value="">—</option>
              {subjects.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>
          <TextField name="evaluation_label" label="Évaluation" placeholder="Devoir 1" required />
          <TextField name="value" label="Note /20" type="number" step="0.5" min="0" max="20" required />
          <TextField name="coefficient" label="Coefficient" type="number" step="0.5" min="0.5" defaultValue="1" />
          {error && <p className="sm:col-span-4 text-sm text-brick">{error}</p>}
          <div className="sm:col-span-4">
            <button type="submit" className="rounded bg-ochre text-navy-deep text-sm font-medium px-4 py-2 hover:bg-ochre-dark transition">
              Enregistrer
            </button>
          </div>
        </form>
      )}

      <div className="mt-4 border border-line rounded bg-white overflow-hidden">
        <table className="w-full text-[14.5px]">
          <thead>
            <tr>
              <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-4 border-b border-line">Matière</th>
              <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-4 border-b border-line">Évaluation</th>
              <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-4 border-b border-line">Note</th>
              <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-4 border-b border-line">Coef.</th>
              <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-4 border-b border-line">Statut</th>
              <th className="border-b border-line"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {grades.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-6 text-ink/50">Aucune note pour {term}.</td></tr>
            )}
            {grades.map((g) => {
              const canEdit = roleCan(role, CAN_WRITE_GRADES) || roleCan(role, CAN_OVERRIDE_LOCKED_GRADES);
              const isEditing = editingId === g.id;
              return (
                <tr key={g.id}>
                  <td className="px-4 py-2.5 text-ink">{subjectName(g.subject_id)}</td>
                  <td className="px-4 py-2.5 text-ink/70">{g.evaluation_label}</td>
                  <td className="px-4 py-2.5 text-ink font-medium">
                    {isEditing ? (
                      <input
                        type="number" step="0.5" min="0" max="20" value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        className="w-20 rounded border border-line px-2 py-1 text-[13.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy"
                      />
                    ) : g.value}
                  </td>
                  <td className="px-4 py-2.5 text-ink/70">{g.coefficient}</td>
                  <td className="px-4 py-2.5">
                    {g.is_locked ? (
                      <StatusPill label="Verrouillée" tone="bad" />
                    ) : (
                      <StatusPill label="Modifiable" tone="neutral" />
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    {canEdit && (g.is_locked ? roleCan(role, CAN_OVERRIDE_LOCKED_GRADES) : true) && (
                      isEditing ? (
                        <div className="flex items-center justify-end gap-2">
                          <button onClick={() => submitEdit(g.id)} className="text-pass text-sm hover:underline">OK</button>
                          <button onClick={() => setEditingId(null)} className="text-ink/40 text-sm hover:underline">Annuler</button>
                        </div>
                      ) : (
                        <button onClick={() => startEdit(g)} className="text-navy text-sm hover:underline">Modifier</button>
                      )
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {editError && <p className="mt-2 text-sm text-brick">{editError}</p>}

      {roleCan(role, CAN_LOCK_GRADES) && grades.length > 0 && (
        <div className="mt-3 flex items-center gap-3">
          <button onClick={handleLock} className="rounded border border-navy text-navy text-sm font-medium px-3.5 py-1.5 hover:bg-navy/5 transition">
            Verrouiller les notes de {term}
          </button>
          {lockMessage && <p className="text-sm text-ink/60">{lockMessage}</p>}
        </div>
      )}
    </section>
  );
}

// ---------------- Présences ----------------

function AttendanceSection({ studentId }: { studentId: string }) {
  const [records, setRecords] = useState<Attendance[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function reload() {
    api.get<Attendance[]>(`/students/${studentId}/attendance`).then(setRecords);
  }
  useEffect(reload, [studentId]);

  async function handleAdd(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    const form = new FormData(e.currentTarget);
    try {
      await api.post("/attendance", {
        student_id: studentId,
        date: form.get("date"),
        status: form.get("status"),
        justified: form.get("justified") === "on",
      });
      setShowForm(false);
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible d'enregistrer.");
    }
  }

  return (
    <section className="mt-10">
      <SectionHeader
        title="Présences"
        right={
          <button onClick={() => setShowForm((v) => !v)} className="rounded bg-navy text-paper text-sm font-medium px-3.5 py-2 hover:bg-navy-light transition">
            {showForm ? "Annuler" : "+ Enregistrer"}
          </button>
        }
      />

      {showForm && (
        <form onSubmit={handleAdd} className="mt-4 border border-line rounded bg-white p-5 grid sm:grid-cols-4 gap-4 items-end">
          <TextField name="date" label="Date" type="date" required />
          <div>
            <label className="block text-sm font-medium text-ink/80 mb-1.5">Statut</label>
            <select name="status" required className="w-full rounded border border-line bg-white px-3 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy">
              <option value="present">Présent</option>
              <option value="absent">Absent</option>
              <option value="late">Retard</option>
            </select>
          </div>
          <label className="flex items-center gap-2 text-sm text-ink/70 pb-2">
            <input type="checkbox" name="justified" className="rounded border-line" /> Justifié
          </label>
          {error && <p className="sm:col-span-4 text-sm text-brick">{error}</p>}
          <div className="sm:col-span-4">
            <button type="submit" className="rounded bg-ochre text-navy-deep text-sm font-medium px-4 py-2 hover:bg-ochre-dark transition">
              Enregistrer
            </button>
          </div>
        </form>
      )}

      <div className="mt-4 border border-line rounded bg-white overflow-hidden">
        <table className="w-full text-[14.5px]">
          <thead>
            <tr>
              <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-4 border-b border-line">Date</th>
              <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-4 border-b border-line">Statut</th>
              <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-4 border-b border-line">Justifié</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {records.length === 0 && (
              <tr><td colSpan={3} className="px-4 py-6 text-ink/50">Aucune présence enregistrée.</td></tr>
            )}
            {records.map((r) => (
              <tr key={r.id}>
                <td className="px-4 py-2.5 text-ink">{r.date}</td>
                <td className="px-4 py-2.5">
                  <StatusPill
                    label={r.status === "present" ? "Présent" : r.status === "absent" ? "Absent" : "Retard"}
                    tone={r.status === "absent" ? "bad" : r.status === "late" ? "warn" : "ok"}
                  />
                </td>
                <td className="px-4 py-2.5 text-ink/70">{r.justified ? "Oui" : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

// ---------------- Finances ----------------

function FinanceSection({ studentId }: { studentId: string }) {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [showInvoiceForm, setShowInvoiceForm] = useState(false);
  const [payingInvoice, setPayingInvoice] = useState<Invoice | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [remindMessage, setRemindMessage] = useState<string | null>(null);

  function reload() {
    api.get<Invoice[]>(`/students/${studentId}/invoices`).then(setInvoices);
  }
  useEffect(reload, [studentId]);

  async function handleCreateInvoice(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    const form = new FormData(e.currentTarget);
    try {
      await api.post("/invoices", {
        student_id: studentId,
        label: form.get("label"),
        amount_due: Number(form.get("amount_due")),
        due_date: form.get("due_date"),
      });
      setShowInvoiceForm(false);
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible de créer la facture.");
    }
  }

  async function handlePay(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!payingInvoice) return;
    setError(null);
    const form = new FormData(e.currentTarget);
    try {
      await api.post("/payments", {
        invoice_id: payingInvoice.id,
        amount: Number(form.get("amount")),
        method: form.get("method"),
        reference: form.get("reference") || null,
      });
      setPayingInvoice(null);
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible d'enregistrer le paiement.");
    }
  }

  async function handleRemind(invoiceId: string) {
    setRemindMessage(null);
    try {
      const resp = await api.post<{ notified: number }>(`/invoices/${invoiceId}/remind`);
      setRemindMessage(
        resp.notified > 0
          ? `${resp.notified} parent(s) notifié(s).`
          : "Aucun parent rattaché à cet élève — relance non envoyée."
      );
    } catch (err) {
      setRemindMessage(err instanceof ApiError ? err.message : "Impossible d'envoyer la relance.");
    }
  }

  const statusLabel: Record<string, string> = {
    pending: "En attente", partially_paid: "Partiellement payée", paid: "Payée", overdue: "En retard", cancelled: "Annulée",
  };
  const statusTone: Record<string, "ok" | "warn" | "bad" | "neutral"> = {
    pending: "warn", partially_paid: "warn", paid: "ok", overdue: "bad", cancelled: "neutral",
  };

  return (
    <section className="mt-10 mb-16">
      <SectionHeader
        title="Finances"
        right={
          <button onClick={() => setShowInvoiceForm((v) => !v)} className="rounded bg-navy text-paper text-sm font-medium px-3.5 py-2 hover:bg-navy-light transition">
            {showInvoiceForm ? "Annuler" : "+ Facture"}
          </button>
        }
      />

      {showInvoiceForm && (
        <form onSubmit={handleCreateInvoice} className="mt-4 border border-line rounded bg-white p-5 grid sm:grid-cols-3 gap-4">
          <TextField name="label" label="Libellé" placeholder="Scolarité T1" required />
          <TextField name="amount_due" label="Montant dû (FCFA)" type="number" min="1" required />
          <TextField name="due_date" label="Échéance" type="date" required />
          {error && !payingInvoice && <p className="sm:col-span-3 text-sm text-brick">{error}</p>}
          <div className="sm:col-span-3">
            <button type="submit" className="rounded bg-ochre text-navy-deep text-sm font-medium px-4 py-2 hover:bg-ochre-dark transition">
              Créer la facture
            </button>
          </div>
        </form>
      )}

      <div className="mt-4 border border-line rounded bg-white overflow-hidden">
        <table className="w-full text-[14.5px]">
          <thead>
            <tr>
              <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-4 border-b border-line">Libellé</th>
              <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-4 border-b border-line">Dû</th>
              <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-4 border-b border-line">Payé</th>
              <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-4 border-b border-line">Solde</th>
              <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-4 border-b border-line">Statut</th>
              <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-4 border-b border-line"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {invoices.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-6 text-ink/50">Aucune facture.</td></tr>
            )}
            {invoices.map((inv) => (
              <tr key={inv.id}>
                <td className="px-4 py-2.5 text-ink">{inv.label}</td>
                <td className="px-4 py-2.5 text-ink/70">{inv.amount_due.toLocaleString("fr-FR")} F</td>
                <td className="px-4 py-2.5 text-ink/70">{inv.amount_paid.toLocaleString("fr-FR")} F</td>
                <td className={`px-4 py-2.5 font-medium ${inv.balance > 0 ? "text-brick" : "text-pass"}`}>{inv.balance.toLocaleString("fr-FR")} F</td>
                <td className="px-4 py-2.5"><StatusPill label={statusLabel[inv.status]} tone={statusTone[inv.status]} /></td>
                <td className="px-4 py-2.5">
                  {inv.status !== "paid" && inv.status !== "cancelled" && (
                    <div className="flex items-center gap-3 justify-end">
                      <button onClick={() => handleRemind(inv.id)} className="text-ochre-dark text-sm underline underline-offset-2 hover:text-ochre">
                        Relancer
                      </button>
                      <button onClick={() => setPayingInvoice(inv)} className="text-navy text-sm underline underline-offset-2 hover:text-navy-light">
                        Encaisser
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {remindMessage && <p className="mt-2 text-sm text-ink/60">{remindMessage}</p>}

      {payingInvoice && (
        <div className="fixed inset-0 bg-ink/40 flex items-center justify-center z-50 px-4">
          <div className="bg-white rounded max-w-sm w-full p-6">
            <h3 className="font-display text-lg text-ink">Encaisser — {payingInvoice.label}</h3>
            <p className="text-sm text-ink/55 mt-1">Solde restant : {payingInvoice.balance.toLocaleString("fr-FR")} F</p>
            <form onSubmit={handlePay} className="mt-4 space-y-3">
              <TextField name="amount" label="Montant reçu (FCFA)" type="number" min="1" max={payingInvoice.balance} required />
              <div>
                <label className="block text-sm font-medium text-ink/80 mb-1.5">Moyen de paiement</label>
                <select name="method" required className="w-full rounded border border-line bg-white px-3 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy">
                  <option value="cash">Espèces</option>
                  <option value="mobile_money">Mobile money</option>
                  <option value="bank_transfer">Virement bancaire</option>
                </select>
              </div>
              <TextField name="reference" label="Référence (optionnel)" />
              {error && <p className="text-sm text-brick">{error}</p>}
              <div className="flex gap-2 pt-1">
                <button type="submit" className="rounded bg-ochre text-navy-deep text-sm font-medium px-4 py-2 hover:bg-ochre-dark transition">
                  Confirmer
                </button>
                <button type="button" onClick={() => setPayingInvoice(null)} className="text-sm text-ink/60 px-2">
                  Annuler
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </section>
  );
}

// ---------------- Bibliothèque ----------------

interface Loan {
  id: string;
  book_id: string;
  loaned_at: string;
  due_at: string;
  returned_at: string | null;
}
interface Book {
  id: string;
  title: string;
  author: string;
}

function LibrarySection({ studentId }: { studentId: string }) {
  const [loans, setLoans] = useState<Loan[]>([]);
  const [books, setBooks] = useState<Book[]>([]);
  const [error, setError] = useState<string | null>(null);

  function reload() {
    api.get<Loan[]>(`/library/students/${studentId}/loans`).then(setLoans).catch(() => setLoans([]));
    api.get<Book[]>("/library/books").then(setBooks).catch(() => setBooks([]));
  }
  useEffect(reload, [studentId]);

  const bookTitle = (id: string) => books.find((b) => b.id === id)?.title ?? "—";

  async function handleReturn(loanId: string) {
    setError(null);
    try {
      await api.post(`/library/loans/${loanId}/return`);
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible d'enregistrer le retour.");
    }
  }

  if (books.length === 0 && loans.length === 0) return null; // bibliothèque pas encore utilisée dans l'établissement

  return (
    <section className="mt-10">
      <SectionHeader title="Bibliothèque" />
      {error && <p className="mt-2 text-sm text-brick">{error}</p>}
      <div className="mt-4 border border-line rounded bg-white overflow-hidden">
        <table className="w-full text-[14.5px]">
          <thead>
            <tr>
              <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-4 border-b border-line">Ouvrage</th>
              <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-4 border-b border-line">Emprunté le</th>
              <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-4 border-b border-line">À rendre le</th>
              <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-4 border-b border-line">Statut</th>
              <th className="border-b border-line"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {loans.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-6 text-ink/50">Aucun emprunt pour cet élève.</td></tr>
            )}
            {loans.map((l) => (
              <tr key={l.id}>
                <td className="px-4 py-2.5 text-ink">{bookTitle(l.book_id)}</td>
                <td className="px-4 py-2.5 text-ink/70">{l.loaned_at}</td>
                <td className="px-4 py-2.5 text-ink/70">{l.due_at}</td>
                <td className="px-4 py-2.5">
                  {l.returned_at ? <StatusPill label="Rendu" tone="ok" /> : <StatusPill label="En cours" tone="warn" />}
                </td>
                <td className="px-4 py-2.5 text-right">
                  {!l.returned_at && (
                    <button onClick={() => handleReturn(l.id)} className="text-navy text-sm underline underline-offset-2 hover:text-navy-light">
                      Retourner
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

// ---------------- Cantine ----------------

interface CanteenSubscription {
  id: string;
  plan_id: string;
  month: string;
  status: string;
}
interface CanteenPlan {
  id: string;
  name: string;
}

function CanteenSection({ studentId }: { studentId: string }) {
  const [subscriptions, setSubscriptions] = useState<CanteenSubscription[]>([]);
  const [plans, setPlans] = useState<CanteenPlan[]>([]);

  useEffect(() => {
    api.get<CanteenSubscription[]>(`/canteen/students/${studentId}/subscriptions`).then(setSubscriptions).catch(() => setSubscriptions([]));
    api.get<CanteenPlan[]>("/canteen/plans").then(setPlans).catch(() => setPlans([]));
  }, [studentId]);

  const planName = (id: string) => plans.find((p) => p.id === id)?.name ?? "—";

  if (plans.length === 0 && subscriptions.length === 0) return null; // cantine pas encore utilisée dans l'établissement

  return (
    <section className="mt-10">
      <SectionHeader title="Cantine" />
      <div className="mt-4 border border-line rounded bg-white overflow-hidden">
        <table className="w-full text-[14.5px]">
          <thead>
            <tr>
              <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-4 border-b border-line">Mois</th>
              <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-4 border-b border-line">Formule</th>
              <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-4 border-b border-line">Statut</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {subscriptions.length === 0 && (
              <tr><td colSpan={3} className="px-4 py-6 text-ink/50">Aucun abonnement pour cet élève.</td></tr>
            )}
            {subscriptions.map((s) => (
              <tr key={s.id}>
                <td className="px-4 py-2.5 text-ink">{s.month}</td>
                <td className="px-4 py-2.5 text-ink/70">{planName(s.plan_id)}</td>
                <td className="px-4 py-2.5">
                  <StatusPill label={s.status === "active" ? "Actif" : "Annulé"} tone={s.status === "active" ? "ok" : "neutral"} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

// ---------------- Utilitaires UI ----------------

function SectionHeader({ title, right }: { title: string; right?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between">
      <h2 className="font-display text-xl font-medium text-ink">{title}</h2>
      {right}
    </div>
  );
}

function TermSelect({ term, onChange }: { term: string; onChange: (t: string) => void }) {
  return (
    <select
      value={term}
      onChange={(e) => onChange(e.target.value)}
      className="rounded border border-line bg-white px-2.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy"
    >
      {TERMS.map((t) => (
        <option key={t} value={t}>{t}</option>
      ))}
    </select>
  );
}

function TextField({
  name, label, type = "text", required, placeholder, min, max, step, defaultValue,
}: {
  name: string; label: string; type?: string; required?: boolean; placeholder?: string;
  min?: string; max?: number | string; step?: string; defaultValue?: string;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-ink/80 mb-1.5">{label}</label>
      <input
        name={name} type={type} required={required} placeholder={placeholder}
        min={min} max={max} step={step} defaultValue={defaultValue}
        className="w-full rounded border border-line bg-white px-3 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy transition"
      />
    </div>
  );
}
