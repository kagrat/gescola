import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Search, ChevronLeft, ChevronRight, BellRing } from "lucide-react";
import { api, ApiError } from "../lib/api";
import FeePlans from "../components/FeePlans";
import RequireRole from "../components/RequireRole";
import StatusPill from "../components/StatusPill";
import { CAN_MANAGE_FINANCE } from "../lib/permissions";

interface ClassRow { class_name: string; due: number; paid: number; outstanding: number; students_with_balance: number }
interface Summary {
  academic_year: string; due: number; paid: number; outstanding: number; recovery_rate_percent: number | null;
  overdue_amount: number; overdue_invoices: number; unpaid_invoices: number;
  aging: Record<string, number>; previous_years_outstanding: number; by_class: ClassRow[];
}
interface InvoiceRow {
  id: string; student_id: string; student_name: string; class_name: string | null; label: string; academic_year: string;
  amount_due: number; amount_paid: number; balance: number; due_date: string; state: string; days_overdue: number;
}
interface SchoolClass { id: string; name: string; level: string }
interface BulkReport { dry_run: boolean; class_name: string; academic_year: string; students: number; created: number; already_billed: number; total_amount: number }

const STATE: Record<string, { label: string; tone: "ok" | "warn" | "bad" | "neutral" }> = {
  paid: { label: "Soldée", tone: "ok" },
  pending: { label: "À échoir", tone: "neutral" },
  partially_paid: { label: "Partielle", tone: "warn" },
  overdue: { label: "En retard", tone: "bad" },
  cancelled: { label: "Annulée", tone: "neutral" },
};
const PAGE_SIZE = 25;
const money = (n: number) => `${n.toLocaleString("fr-FR")} F`;

export default function FinancePage() {
  return (
    <RequireRole roles={CAN_MANAGE_FINANCE}>
      <FinanceContent />
    </RequireRole>
  );
}

function FinanceContent() {
  const [classes, setClasses] = useState<SchoolClass[]>([]);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => { api.get<SchoolClass[]>("/classes").then(setClasses).catch(() => setClasses([])); }, []);
  return (
    <div>
      <div className="px-10 py-8 border-b border-line">
        <h1 className="font-display text-[21px] font-bold text-ink">Finances</h1>
        <p className="text-[12.5px] text-ink/60 mt-0.5">Vue d'ensemble des frais de scolarité de l'établissement.</p>
      </div>
      <SummarySection refreshKey={refresh} />
      <FeePlans classes={classes} onBilled={() => setRefresh((k) => k + 1)} />
      <BulkSection classes={classes} onDone={() => setRefresh((k) => k + 1)} />
      <InvoicesSection classes={classes} refreshKey={refresh} onChanged={() => setRefresh((k) => k + 1)} />
    </div>
  );
}

function SummarySection({ refreshKey }: { refreshKey: number }) {
  const [s, setS] = useState<Summary | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    api.get<Summary>("/finance/summary").then((d) => { setS(d); setError(false); }).catch(() => setError(true));
  }, [refreshKey]);
  if (error) return <p className="px-10 pt-6 text-sm text-brick">Impossible de charger la synthèse.</p>;
  if (!s) return <p className="px-10 pt-6 text-sm text-ink/50">Chargement…</p>;
  return (
    <section className="px-10 pt-6">
      <h2 className="font-display text-[15px] font-bold text-ink mb-3">Synthèse {s.academic_year}</h2>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Stat label="Facturé" value={money(s.due)} />
        <Stat label="Encaissé" value={money(s.paid)} sub={s.recovery_rate_percent === null ? "Rien de facturé" : `${s.recovery_rate_percent.toLocaleString("fr-FR")} % recouvré`} tone="ok" />
        <Stat label="Reste à recouvrer" value={money(s.outstanding)} sub={`${s.unpaid_invoices} facture(s) non soldée(s)`} />
        <Stat label="En retard" value={money(s.overdue_amount)} sub={`${s.overdue_invoices} facture(s)`} tone={s.overdue_amount > 0 ? "bad" : undefined} />
      </div>
      {s.previous_years_outstanding > 0 && (
        <p className="mt-3 text-[13px] rounded-lg border border-amber-300 bg-amber-50 text-amber-900 px-4 py-2.5">
          Arriérés d'années précédentes : <strong>{money(s.previous_years_outstanding)}</strong> (non inclus ci-dessus).
        </p>
      )}
      <div className="grid lg:grid-cols-2 gap-4 mt-4">
        <div className="border border-line rounded-lg bg-white p-5">
          <h3 className="text-[13px] font-semibold text-ink mb-3">Retards par ancienneté</h3>
          <ul className="space-y-1.5 text-[13.5px]">
            {Object.entries(s.aging).map(([k, v]) => (
              <li key={k} className="flex justify-between"><span className="text-ink/60">{k}</span><span className={v > 0 ? "font-medium text-brick" : "text-ink/40"}>{money(v)}</span></li>
            ))}
          </ul>
        </div>
        <div className="border border-line rounded-lg bg-white overflow-hidden">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="text-left text-[11.5px] text-ink/40 uppercase tracking-wide">
                <th className="px-4 pt-4 pb-2">Classe</th><th className="px-4 pt-4 pb-2 text-right">Facturé</th><th className="px-4 pt-4 pb-2 text-right">Reste dû</th><th className="px-4 pt-4 pb-2 text-right">Élèves</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {s.by_class.length === 0 && <tr><td colSpan={4} className="px-4 py-4 text-ink/50">Aucune facture cette année.</td></tr>}
              {s.by_class.map((c) => (
                <tr key={c.class_name}>
                  <td className="px-4 py-2">{c.class_name}</td>
                  <td className="px-4 py-2 text-right text-ink/70">{money(c.due)}</td>
                  <td className={`px-4 py-2 text-right ${c.outstanding > 0 ? "text-brick font-medium" : "text-ink/50"}`}>{money(c.outstanding)}</td>
                  <td className="px-4 py-2 text-right text-ink/70">{c.students_with_balance}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function Stat({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: "ok" | "bad" }) {
  return (
    <div className="border border-line rounded-lg bg-white p-4">
      <p className="text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide">{label}</p>
      <p className={`font-display text-xl font-bold mt-1 ${tone === "ok" ? "text-pass" : tone === "bad" ? "text-brick" : "text-ink"}`}>{value}</p>
      {sub && <p className="text-[12px] text-ink/55 mt-0.5">{sub}</p>}
    </div>
  );
}

function BulkSection({ classes, onDone }: { classes: SchoolClass[]; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ class_id: "", label: "Scolarité", amount_due: "", due_date: "" });
  const [preview, setPreview] = useState<BulkReport | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const body = () => ({ class_id: form.class_id, label: form.label.trim(), amount_due: Number(form.amount_due), due_date: form.due_date });
  function edit(k: keyof typeof form, v: string) { setForm({ ...form, [k]: v }); setPreview(null); setMessage(null); }

  async function handlePreview(e: FormEvent) {
    e.preventDefault();
    setError(null); setMessage(null); setBusy(true);
    try { setPreview(await api.post<BulkReport>("/finance/bulk-invoices?dry_run=true", body())); }
    catch (err) { setPreview(null); setError(err instanceof ApiError ? err.message : "Aperçu impossible."); }
    finally { setBusy(false); }
  }
  async function handleConfirm() {
    setError(null); setBusy(true);
    try {
      const r = await api.post<BulkReport>("/finance/bulk-invoices?dry_run=false", body());
      setMessage(`${r.created} facture(s) créée(s) pour ${r.class_name}${r.already_billed ? ` · ${r.already_billed} déjà facturé(s), ignoré(s)` : ""}.`);
      setPreview(null); onDone();
    } catch (err) { setError(err instanceof ApiError ? err.message : "Facturation impossible."); }
    finally { setBusy(false); }
  }

  const input = "w-full rounded-lg border border-line bg-white px-3 py-2 text-[14px] focus:outline-none focus:ring-2 focus:ring-sky/30";
  return (
    <section className="px-10 pt-6">
      <button type="button" onClick={() => setOpen((v) => !v)} className="text-[13.5px] font-semibold text-navy hover:underline">
        {open ? "Masquer" : "Facturer une classe entière"}
      </button>
      {open && (
        <form onSubmit={handlePreview} className="mt-3 border border-line rounded-lg bg-white p-5 grid sm:grid-cols-4 gap-4 items-end">
          <label className="text-sm text-ink/80">Classe
            <select required value={form.class_id} onChange={(e) => edit("class_id", e.target.value)} className={input}>
              <option value="">— Choisir —</option>
              {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
          <label className="text-sm text-ink/80">Libellé
            <input required minLength={3} value={form.label} onChange={(e) => edit("label", e.target.value)} className={input} />
          </label>
          <label className="text-sm text-ink/80">Montant par élève (F)
            <input required type="number" min={1} step="any" value={form.amount_due} onChange={(e) => edit("amount_due", e.target.value)} className={input} />
          </label>
          <label className="text-sm text-ink/80">Échéance
            <input required type="date" value={form.due_date} onChange={(e) => edit("due_date", e.target.value)} className={input} />
          </label>
          <div className="sm:col-span-4 flex flex-wrap items-center gap-3">
            <button type="submit" disabled={busy} className="rounded-lg border border-line bg-white text-ink text-sm font-semibold px-4 py-2 hover:bg-paper disabled:opacity-60">Aperçu</button>
            {preview && (
              <>
                <span className="text-[13.5px] text-ink/80">
                  {preview.created} facture(s) à créer pour {preview.class_name} — {money(preview.total_amount)}
                  {preview.already_billed > 0 && ` · ${preview.already_billed} déjà facturé(s)`}
                </span>
                <button type="button" onClick={handleConfirm} disabled={busy || preview.created === 0}
                  className="rounded-lg bg-pass text-white text-sm font-semibold px-4 py-2 hover:opacity-90 disabled:opacity-50">Confirmer la facturation</button>
              </>
            )}
          </div>
          {error && <p className="sm:col-span-4 text-sm text-brick">{error}</p>}
        </form>
      )}
      {message && <p className="mt-3 text-sm text-pass">{message}</p>}
    </section>
  );
}

function InvoicesSection({ classes, refreshKey, onChanged }: { classes: SchoolClass[]; refreshKey: number; onChanged: () => void }) {
  const [rows, setRows] = useState<InvoiceRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [classId, setClassId] = useState("");
  const [state, setState] = useState("unpaid");
  const [sort, setSort] = useState("due");
  const [offset, setOffset] = useState(0);
  const requestId = useRef(0);

  useEffect(() => { const t = setTimeout(() => setDebounced(query.trim()), 300); return () => clearTimeout(t); }, [query]);
  useEffect(() => setOffset(0), [debounced, classId, state, sort]);

  const load = useCallback(() => {
    const id = ++requestId.current;
    const p = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset), sort });
    if (debounced) p.set("q", debounced);
    if (classId) p.set("class_id", classId);
    if (state) p.set("state", state);
    setLoading(true);
    api.page<InvoiceRow>(`/finance/invoices?${p}`)
      .then((pg) => { if (id !== requestId.current) return; setRows(pg.items); setTotal(pg.total); setError(null); })
      .catch(() => id === requestId.current && setError("Impossible de charger les factures."))
      .finally(() => id === requestId.current && setLoading(false));
  }, [debounced, classId, state, sort, offset]);
  useEffect(load, [load, refreshKey]);

  async function remind(inv: InvoiceRow) {
    setNote(null);
    try {
      const r = await api.post<{ notified: number }>(`/invoices/${inv.id}/remind`);
      setNote(r.notified > 0 ? `Relance envoyée pour ${inv.student_name}.` : `Aucun parent n'a de compte pour ${inv.student_name} : relance non envoyée.`);
      onChanged();
    } catch (err) { setNote(err instanceof ApiError ? err.message : "Relance impossible."); }
  }

  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + PAGE_SIZE, total);
  const sel = "rounded-lg border border-line bg-white px-3 py-2 focus:outline-none focus:ring-2 focus:ring-sky/30";
  return (
    <section className="px-10 py-6">
      <h2 className="font-display text-[15px] font-bold text-ink mb-3">Factures</h2>
      <div className="flex flex-wrap items-center gap-3 text-[13.5px] mb-4">
        <div className="flex items-center gap-2 bg-white border border-line rounded-lg px-3 py-2 min-w-[220px]">
          <Search className="w-4 h-4 text-ink/40" strokeWidth={1.8} />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Élève, matricule, libellé…" className="flex-1 outline-none bg-transparent" />
        </div>
        <select value={classId} onChange={(e) => setClassId(e.target.value)} aria-label="Classe" className={sel}>
          <option value="">Toutes les classes</option>
          {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <select value={state} onChange={(e) => setState(e.target.value)} aria-label="État" className={sel}>
          <option value="unpaid">Non soldées</option>
          <option value="overdue">En retard</option>
          <option value="partially_paid">Partielles</option>
          <option value="pending">À échoir</option>
          <option value="paid">Soldées</option>
          <option value="">Toutes</option>
          <option value="cancelled">Annulées</option>
        </select>
        <select value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Tri" className={sel}>
          <option value="due">Échéance la plus ancienne</option>
          <option value="balance">Plus gros solde</option>
        </select>
      </div>
      {note && <p className="mb-3 text-sm text-ink/70">{note}</p>}
      <div className="border border-line rounded-lg bg-white overflow-x-auto">
        <table className="w-full text-[13.5px]">
          <thead>
            <tr className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide">
              <th className="px-5 pt-4 pb-2.5">Élève</th><th className="px-5 pt-4 pb-2.5">Classe</th><th className="px-5 pt-4 pb-2.5">Libellé</th>
              <th className="px-5 pt-4 pb-2.5">Échéance</th><th className="px-5 pt-4 pb-2.5 text-right">Reste dû</th><th className="px-5 pt-4 pb-2.5">État</th><th className="px-5 pt-4 pb-2.5" />
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {loading && rows.length === 0 && <tr><td colSpan={7} className="px-5 py-6 text-ink/50">Chargement…</td></tr>}
            {error && <tr><td colSpan={7} className="px-5 py-6 text-brick">{error}</td></tr>}
            {!loading && !error && rows.length === 0 && <tr><td colSpan={7} className="px-5 py-8 text-ink/50">Aucune facture.</td></tr>}
            {rows.map((r) => {
              const pill = STATE[r.state] ?? { label: r.state, tone: "neutral" as const };
              return (
                <tr key={r.id} className="hover:bg-paper/60 transition">
                  <td className="px-5 py-3"><Link to={`/eleves/${r.student_id}`} className="font-semibold text-ink hover:text-navy hover:underline underline-offset-2">{r.student_name}</Link></td>
                  <td className="px-5 py-3 text-ink/70">{r.class_name ?? "—"}</td>
                  <td className="px-5 py-3 text-ink/70">{r.label}</td>
                  <td className="px-5 py-3 text-ink/70">
                    {new Date(r.due_date).toLocaleDateString("fr-FR")}
                    {r.days_overdue > 0 && <span className="block text-[12px] text-brick">{r.days_overdue} j de retard</span>}
                  </td>
                  <td className={`px-5 py-3 text-right font-medium ${r.balance > 0 ? "text-brick" : "text-pass"}`}>{money(r.balance)}</td>
                  <td className="px-5 py-3"><StatusPill label={pill.label} tone={pill.tone} /></td>
                  <td className="px-5 py-3 text-right">
                    {r.state === "overdue" && (
                      <button type="button" onClick={() => remind(r)} title="Relancer les parents" aria-label={`Relancer ${r.student_name}`}
                        className="inline-flex items-center gap-1 text-[12.5px] font-semibold text-navy hover:underline"><BellRing className="w-3.5 h-3.5" strokeWidth={1.8} />Relancer</button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between mt-4 text-[13px] text-ink/60">
        <span>{total === 0 ? "" : `${from.toLocaleString("fr-FR")}–${to.toLocaleString("fr-FR")} sur ${total.toLocaleString("fr-FR")}`}</span>
        <div className="flex items-center gap-2">
          <button type="button" disabled={offset === 0 || loading} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            className="flex items-center gap-1 rounded-lg border border-line bg-white px-3 py-1.5 hover:bg-paper disabled:opacity-40"><ChevronLeft className="w-4 h-4" strokeWidth={1.8} /> Précédent</button>
          <button type="button" disabled={offset + PAGE_SIZE >= total || loading} onClick={() => setOffset(offset + PAGE_SIZE)}
            className="flex items-center gap-1 rounded-lg border border-line bg-white px-3 py-1.5 hover:bg-paper disabled:opacity-40">Suivant <ChevronRight className="w-4 h-4" strokeWidth={1.8} /></button>
        </div>
      </div>
    </section>
  );
}
