import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../lib/api";

interface Installment { label: string; amount: number; month: number; day: number }
interface Plan { id: string; level: string; name: string; installments: Installment[]; total: number }
interface SchoolClass { id: string; name: string; level: string }
interface Report {
  dry_run: boolean; class_name: string; academic_year: string; students: number; discounted_students: number; exempted_students: number;
  installments: { label: string; due_date: string; created: number; already_billed: number; total_amount: number }[]; total_amount: number;
}
const MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"];
const SCHOOL_ORDER = [9, 10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8];
const money = (n: number) => `${n.toLocaleString("fr-FR")} F`;
const input = "w-full rounded-lg border border-line bg-white px-3 py-2 text-[14px] focus:outline-none focus:ring-2 focus:ring-sky/30";

/** Barèmes de frais par niveau (tranches datées) et application à une classe : aperçu puis confirmation. */
export default function FeePlans({ classes, onBilled }: { classes: SchoolClass[]; onBilled: () => void }) {
  const [open, setOpen] = useState(false);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [editing, setEditing] = useState<Plan | "new" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => { api.get<Plan[]>("/finance/fee-plans").then(setPlans).catch(() => setPlans([])); }, []);
  useEffect(load, [load]);

  async function remove(p: Plan) {
    if (!window.confirm(`Supprimer le barème « ${p.name} » (${p.level}) ? Les factures déjà créées ne changent pas.`)) return;
    try { await api.del(`/finance/fee-plans/${p.id}`); load(); } catch (e) { setError(e instanceof ApiError ? e.message : "Suppression impossible."); }
  }

  return (
    <section className="px-10 pt-6">
      <button type="button" onClick={() => setOpen((v) => !v)} className="text-[13.5px] font-semibold text-navy hover:underline">
        {open ? "Masquer les barèmes de frais" : `Barèmes de frais et tranches (${plans.length})`}
      </button>
      {open && (
        <div className="mt-3 space-y-3">
          {plans.length === 0 && editing === null && (
            <p className="text-[13.5px] text-ink/60">Aucun barème. Un barème décrit la scolarité d'un niveau en tranches datées : vous le facturez ensuite à toute une classe en un clic, remises incluses.</p>
          )}
          {plans.map((p) => (
            <div key={p.id} className="border border-line rounded-lg bg-white p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-semibold text-ink">{p.name} <span className="text-ink/50 font-normal">· {p.level} · total {money(p.total)}</span></p>
                <div className="flex gap-4 text-[13px]">
                  <button type="button" onClick={() => setEditing(p)} className="text-navy underline underline-offset-2">Modifier</button>
                  <button type="button" onClick={() => remove(p)} className="text-brick underline underline-offset-2">Supprimer</button>
                </div>
              </div>
              <ul className="mt-2 text-[13.5px] text-ink/70 space-y-0.5">
                {p.installments.map((i) => <li key={i.label}>{i.label} — {money(i.amount)} avant le {i.day} {MONTHS[i.month - 1]}</li>)}
              </ul>
              <Apply plan={p} classes={classes.filter((c) => c.level.trim().toLowerCase() === p.level.trim().toLowerCase())} onBilled={onBilled} />
            </div>
          ))}
          {error && <p className="text-sm text-brick">{error}</p>}
          {editing ? (
            <PlanForm plan={editing === "new" ? null : editing} levels={Array.from(new Set(classes.map((c) => c.level)))}
              onDone={() => { setEditing(null); load(); }} onCancel={() => setEditing(null)} />
          ) : (
            <button type="button" onClick={() => setEditing("new")} className="rounded-lg border border-line bg-white text-ink text-[13.5px] font-semibold px-4 py-2 hover:bg-paper">+ Nouveau barème</button>
          )}
        </div>
      )}
    </section>
  );
}

function Apply({ plan, classes, onBilled }: { plan: Plan; classes: SchoolClass[]; onBilled: () => void }) {
  const [classId, setClassId] = useState("");
  const [preview, setPreview] = useState<Report | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(dry: boolean) {
    setBusy(true); setError(null); setMessage(null);
    try {
      const r = await api.post<Report>(`/finance/fee-plans/${plan.id}/apply?dry_run=${dry}`, { class_id: classId });
      if (dry) setPreview(r);
      else {
        const created = r.installments.reduce((n, i) => n + i.created, 0);
        setMessage(`${created} facture(s) créée(s) pour ${r.class_name}.`); setPreview(null); onBilled();
      }
    } catch (e) { setPreview(null); setError(e instanceof ApiError ? e.message : "Opération impossible."); }
    finally { setBusy(false); }
  }

  if (classes.length === 0) return <p className="mt-3 text-[12.5px] text-ink/50">Aucune classe de niveau « {plan.level} » : créez-la pour pouvoir facturer ce barème.</p>;
  const created = preview?.installments.reduce((n, i) => n + i.created, 0) ?? 0;
  return (
    <div className="mt-3 pt-3 border-t border-line">
      <div className="flex flex-wrap items-center gap-3">
        <select value={classId} onChange={(e) => { setClassId(e.target.value); setPreview(null); setMessage(null); }} aria-label={`Classe à facturer (${plan.name})`} className={`${input} !w-auto`}>
          <option value="">— Classe à facturer —</option>
          {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <button type="button" disabled={!classId || busy} onClick={() => run(true)} className="rounded-lg border border-line bg-white text-ink text-sm font-semibold px-4 py-2 hover:bg-paper disabled:opacity-50">Aperçu</button>
        {preview && <button type="button" disabled={busy || created === 0} onClick={() => run(false)} className="rounded-lg bg-pass text-white text-sm font-semibold px-4 py-2 hover:opacity-90 disabled:opacity-50">Confirmer : {created} facture(s) · {money(preview.total_amount)}</button>}
      </div>
      {preview && (
        <div className="mt-2 text-[13px] text-ink/70">
          {preview.students} élève(s) actif(s) en {preview.academic_year}
          {preview.discounted_students > 0 && ` · ${preview.discounted_students} avec remise`}
          {preview.exempted_students > 0 && ` (dont ${preview.exempted_students} exempté(s))`}
          <ul className="mt-1 space-y-0.5">
            {preview.installments.map((i) => (
              <li key={i.label}>{i.label} — échéance {new Date(i.due_date).toLocaleDateString("fr-FR")} : {i.created} à créer{i.already_billed > 0 ? `, ${i.already_billed} déjà facturé(s)` : ""} ({money(i.total_amount)})</li>
            ))}
          </ul>
        </div>
      )}
      {message && <p className="mt-2 text-sm text-pass">{message}</p>}
      {error && <p className="mt-2 text-sm text-brick">{error}</p>}
    </div>
  );
}

function PlanForm({ plan, levels, onDone, onCancel }: { plan: Plan | null; levels: string[]; onDone: () => void; onCancel: () => void }) {
  const [level, setLevel] = useState(plan?.level ?? levels[0] ?? "");
  const [name, setName] = useState(plan?.name ?? "Scolarité");
  const [rows, setRows] = useState<Installment[]>(plan?.installments ?? [{ label: "Tranche 1", amount: 0, month: 10, day: 15 }]);
  const [error, setError] = useState<string | null>(null);
  const total = rows.reduce((n, r) => n + (Number(r.amount) || 0), 0);
  const set = (i: number, patch: Partial<Installment>) => setRows(rows.map((r, k) => (k === i ? { ...r, ...patch } : r)));

  function split(n: number) {
    const each = Math.floor(total / n);
    const months = SCHOOL_ORDER.filter((m) => [10, 1, 4, 11, 2, 5].includes(m)).slice(0, n);
    setRows(Array.from({ length: n }, (_, k) => ({ label: `Tranche ${k + 1}`, amount: k === n - 1 ? total - each * (n - 1) : each, month: months[k] ?? 10, day: 15 })));
  }

  async function submit(e: FormEvent) {
    e.preventDefault(); setError(null);
    const body = { level: level.trim(), name: name.trim(), installments: rows.map((r) => ({ ...r, amount: Number(r.amount), month: Number(r.month), day: Number(r.day) })) };
    try { if (plan) await api.put(`/finance/fee-plans/${plan.id}`, body); else await api.post("/finance/fee-plans", body); onDone(); }
    catch (err) { setError(err instanceof ApiError ? err.message : "Enregistrement impossible."); }
  }

  return (
    <form onSubmit={submit} className="border border-line rounded-lg bg-white p-5 space-y-4">
      <div className="grid sm:grid-cols-2 gap-4">
        <label className="text-sm text-ink/80">Niveau
          <input required list="fee-levels" value={level} onChange={(e) => setLevel(e.target.value)} className={input} />
          <datalist id="fee-levels">{levels.map((l) => <option key={l} value={l} />)}</datalist>
        </label>
        <label className="text-sm text-ink/80">Nom du barème
          <input required minLength={3} value={name} onChange={(e) => setName(e.target.value)} className={input} />
        </label>
      </div>
      <div className="space-y-2">
        {rows.map((r, i) => (
          <div key={i} className="grid grid-cols-12 gap-2 items-end">
            <label className="col-span-4 text-[12px] text-ink/60">Tranche<input required minLength={2} value={r.label} onChange={(e) => set(i, { label: e.target.value })} className={input} /></label>
            <label className="col-span-3 text-[12px] text-ink/60">Montant (F)<input required type="number" min={1} value={r.amount || ""} onChange={(e) => set(i, { amount: Number(e.target.value) })} className={input} /></label>
            <label className="col-span-2 text-[12px] text-ink/60">Jour<input required type="number" min={1} max={28} value={r.day} onChange={(e) => set(i, { day: Number(e.target.value) })} className={input} /></label>
            <label className="col-span-2 text-[12px] text-ink/60">Mois
              <select value={r.month} onChange={(e) => set(i, { month: Number(e.target.value) })} className={input}>{SCHOOL_ORDER.map((m) => <option key={m} value={m}>{MONTHS[m - 1]}</option>)}</select>
            </label>
            <button type="button" aria-label="Retirer la tranche" disabled={rows.length === 1} onClick={() => setRows(rows.filter((_, k) => k !== i))} className="col-span-1 pb-2 text-brick disabled:opacity-30">✕</button>
          </div>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-4 text-[13.5px]">
        <button type="button" disabled={rows.length >= 12} onClick={() => setRows([...rows, { label: `Tranche ${rows.length + 1}`, amount: 0, month: 1, day: 15 }])} className="text-navy underline underline-offset-2">+ Ajouter une tranche</button>
        <span className="text-ink/50">Répartir le total en :</span>
        {[2, 3, 4].map((n) => <button key={n} type="button" disabled={total <= 0} onClick={() => split(n)} className="text-navy underline underline-offset-2 disabled:opacity-40">{n} tranches égales</button>)}
        <span className="ml-auto font-semibold text-ink">Total : {money(total)}</span>
      </div>
      {error && <p className="text-sm text-brick">{error}</p>}
      <div className="flex gap-3">
        <button type="submit" className="rounded-lg bg-navy-deep text-sky-200 text-sm font-semibold px-4 py-2.5 hover:bg-navy">Enregistrer le barème</button>
        <button type="button" onClick={onCancel} className="text-sm text-ink/60 px-2">Annuler</button>
      </div>
    </form>
  );
}

/** Remise de l'élève (fratrie, bourse…) : appliquée automatiquement aux prochaines factures issues d'un barème. */
export function StudentDiscount({ studentId }: { studentId: string }) {
  const [current, setCurrent] = useState<{ percent: number; reason: string | null } | null>(null);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.get<{ fee_discount_percent: number; fee_discount_reason: string | null }>(`/students/${studentId}`)
      .then((s) => setCurrent({ percent: Number(s.fee_discount_percent), reason: s.fee_discount_reason })).catch(() => setCurrent(null));
  }, [studentId]);
  if (!current) return null;

  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); setError(null);
    const f = new FormData(e.currentTarget);
    try {
      const s = await api.put<{ fee_discount_percent: number; fee_discount_reason: string | null }>(`/students/${studentId}/fee-discount`, { percent: Number(f.get("percent")), reason: String(f.get("reason") || "") || null });
      setCurrent({ percent: Number(s.fee_discount_percent), reason: s.fee_discount_reason }); setEditing(false);
    } catch (err) { setError(err instanceof ApiError ? err.message : "Enregistrement impossible."); }
  }

  return (
    <div className="mt-3 text-[13.5px] text-ink/70">
      {!editing ? (
        <p>
          {current.percent > 0 ? <>Remise sur les frais : <strong className="text-ink">{current.percent.toLocaleString("fr-FR")} %</strong>{current.reason ? ` (${current.reason})` : ""} — </> : "Aucune remise sur les frais — "}
          <button type="button" onClick={() => setEditing(true)} className="text-navy underline underline-offset-2">{current.percent > 0 ? "modifier" : "définir"}</button>
        </p>
      ) : (
        <form onSubmit={save} className="flex flex-wrap items-end gap-3">
          <label className="text-[12px]">Remise (%)<input name="percent" type="number" min={0} max={100} step="any" defaultValue={current.percent} className={`${input} !w-24`} /></label>
          <label className="text-[12px]">Motif<input name="reason" maxLength={200} defaultValue={current.reason ?? ""} placeholder="Fratrie, bourse…" className={`${input} !w-56`} /></label>
          <button type="submit" className="rounded-lg bg-navy-deep text-sky-200 text-sm font-semibold px-4 py-2">Enregistrer</button>
          <button type="button" onClick={() => setEditing(false)} className="text-sm text-ink/60">Annuler</button>
          {error && <span className="text-brick">{error}</span>}
        </form>
      )}
    </div>
  );
}
