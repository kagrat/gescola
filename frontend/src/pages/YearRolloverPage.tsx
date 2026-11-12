import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, CheckCircle2, ChevronDown, ChevronRight } from "lucide-react";
import { api, ApiError } from "../lib/api";

interface AtRisk { id: string; name: string; annual_average: number }
interface PlanClass {
  id: string; name: string; level: string; active_count: number;
  suggested_to_class_id: string | null; suggested_graduate: boolean; without_average: number; at_risk: AtRisk[];
}
interface Proposal {
  current_year: string; next_year: string; pass_mark: number; classes: PlanClass[];
  targets: { id: string; name: string; level: string }[];
}
interface ReportRow { from_class_id: string; from_class: string; to_class: string | null; promoted: number; repeated: number; graduated: number }
interface Report {
  executed: boolean; from_year: string; to_year: string; promoted: number; repeated: number; graduated: number;
  without_class: number; classes: ReportRow[]; errors: string[]; warnings: string[];
}
interface StudentLite { id: string; first_name: string; last_name: string }

const GRADUATE = "__graduate__";

export default function YearRolloverPage() {
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [dest, setDest] = useState<Record<string, string>>({});
  const [repeaters, setRepeaters] = useState<Set<string>>(new Set());
  const [report, setReport] = useState<Report | null>(null);
  const [confirmText, setConfirmText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<Report | null>(null);

  useEffect(() => {
    api.get<Proposal>("/academic-year/proposal")
      .then((p) => {
        setProposal(p);
        setDest(Object.fromEntries(p.classes.map((c) => [c.id, c.suggested_graduate ? GRADUATE : c.suggested_to_class_id ?? ""])));
      })
      .catch((e) => setLoadError(e instanceof ApiError ? e.message : "Chargement impossible."));
  }, []);

  function invalidate() { setReport(null); setConfirmText(""); setError(null); }

  const missing = useMemo(
    () => (proposal?.classes ?? []).filter((c) => !dest[c.id]).map((c) => c.name),
    [proposal, dest],
  );

  function payload() {
    return {
      from_year: proposal!.current_year,
      to_year: proposal!.next_year,
      class_moves: proposal!.classes.map((c) => ({ from_class_id: c.id, to_class_id: dest[c.id] === GRADUATE ? null : dest[c.id] })),
      repeater_student_ids: [...repeaters],
    };
  }

  async function send(dryRun: boolean) {
    setBusy(true);
    setError(null);
    try {
      const r = await api.post<Report>(`/academic-year/rollover?dry_run=${dryRun}`, payload());
      if (dryRun) setReport(r); else setDone(r);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Envoi impossible. Vérifiez votre connexion.");
    } finally {
      setBusy(false);
    }
  }

  if (loadError) return <div className="px-10 py-10 text-brick">{loadError}</div>;
  if (!proposal) return <div className="px-10 py-10 text-ink/50">Chargement…</div>;

  if (done) {
    return (
      <div className="px-10 py-10 max-w-3xl">
        <div role="status" className="flex items-start gap-3 border border-pass/40 bg-pass/10 rounded-lg p-6">
          <CheckCircle2 className="w-6 h-6 text-pass shrink-0" strokeWidth={1.8} />
          <div className="text-[14px] text-ink space-y-1">
            <p className="font-display text-xl font-bold">Année {done.to_year} ouverte.</p>
            <p>{done.promoted} élève(s) promu(s), {done.repeated} redoublant(s), {done.graduated} sortant(s). L'année {done.from_year} est clôturée ; ses notes restent consultables.</p>
            <p className="pt-2">À faire maintenant : saisir les dates des trimestres dans <Link className="underline text-navy" to="/parametres">Paramètres</Link>, vérifier les affectations des enseignants et l'emploi du temps.</p>
            <p><Link className="underline text-navy" to="/eleves">Voir la liste des élèves</Link></p>
          </div>
        </div>
      </div>
    );
  }

  const ready = report !== null && report.errors.length === 0;

  return (
    <div>
      <div className="px-10 py-8 border-b border-line">
        <h1 className="font-display text-[21px] font-bold text-ink">Passage d'année scolaire</h1>
        <p className="text-[12.5px] text-ink/60 mt-0.5">
          Clôturer <b>{proposal.current_year}</b> et ouvrir <b>{proposal.next_year}</b> : chaque classe est promue, redouble ou termine son cursus.
        </p>
      </div>

      <div className="px-10 py-8 max-w-5xl space-y-6">
        <section className="border border-line rounded-lg bg-white p-5 text-[13.5px] text-ink/80 space-y-1.5">
          <p><b className="text-ink">1.</b> Pour chaque classe, choisissez la classe d'accueil (une suggestion est pré-remplie, à vérifier) ou « Terminale ».</p>
          <p><b className="text-ink">2.</b> Cochez les <b>redoublants</b> : ils restent dans leur classe. Les élèves sous {proposal.pass_mark}/20 de moyenne annuelle sont signalés.</p>
          <p><b className="text-ink">3.</b> Vérifiez le plan (rien n'est modifié), puis confirmez. L'opération est <b>unique et non annulable</b> : les notes de l'année close sont conservées à part.</p>
        </section>

        {proposal.classes.length === 0 && (
          <p className="text-ink/60 text-sm">Aucune classe n'a d'élève actif : il n'y a rien à faire passer.</p>
        )}

        <div className="space-y-3">
          {proposal.classes.map((c) => (
            <ClassCard
              key={c.id} c={c} targets={proposal.targets} value={dest[c.id] ?? ""}
              onDest={(v) => { setDest({ ...dest, [c.id]: v }); invalidate(); }}
              repeaters={repeaters}
              onRepeaters={(next) => { setRepeaters(next); invalidate(); }}
            />
          ))}
        </div>

        {missing.length > 0 && (
          <p className="text-[13px] text-brick flex items-center gap-2"><AlertTriangle className="w-4 h-4" strokeWidth={1.8} />
            Choisissez une destination pour : {missing.join(", ")}.</p>
        )}
        {error && <p role="alert" className="text-sm text-brick">{error}</p>}

        <button type="button" disabled={busy || missing.length > 0 || proposal.classes.length === 0} onClick={() => send(true)}
          className="rounded-lg bg-navy-deep text-sky-200 text-[13.5px] font-semibold px-5 py-2.5 hover:bg-navy transition disabled:opacity-50">
          {busy && !report ? "Vérification…" : "Vérifier le plan"}
        </button>

        {report && (
          <section className="space-y-4" aria-label="Résultat de la vérification">
            <div className="grid sm:grid-cols-3 gap-3">
              <Stat label="Promus" value={report.promoted} tone="ok" />
              <Stat label="Redoublants" value={report.repeated} />
              <Stat label="Sortants (diplômés)" value={report.graduated} />
            </div>
            <div className="border border-line rounded-lg bg-white overflow-hidden">
              <table className="w-full text-[13.5px]">
                <thead className="text-[11.5px] uppercase tracking-wide text-ink/40 text-left">
                  <tr><th className="px-5 py-2">Classe</th><th className="px-5 py-2">Destination</th><th className="px-5 py-2">Promus</th><th className="px-5 py-2">Redoublants</th><th className="px-5 py-2">Sortants</th></tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {report.classes.map((r) => (
                    <tr key={r.from_class_id}>
                      <td className="px-5 py-2 font-semibold text-ink">{r.from_class}</td>
                      <td className="px-5 py-2">{r.to_class ?? "Terminale — sortie"}</td>
                      <td className="px-5 py-2">{r.promoted}</td><td className="px-5 py-2">{r.repeated}</td><td className="px-5 py-2">{r.graduated}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {report.errors.map((e, i) => <p key={i} role="alert" className="text-sm text-brick flex gap-2"><AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" strokeWidth={1.8} />{e}</p>)}
            {report.warnings.length > 0 && (
              <ul className="text-[13px] text-ink/70 list-disc pl-5 space-y-1">
                {report.warnings.map((w, i) => <li key={i}>{w}</li>)}
              </ul>
            )}
            {ready && (
              <div className="border border-brick/30 bg-brick/5 rounded-lg p-5 space-y-3">
                <p className="text-[13.5px] text-ink">
                  Pour confirmer, tapez <b>{proposal.next_year}</b> ci-dessous. Cette opération ne peut pas être annulée.
                </p>
                <div className="flex flex-wrap items-center gap-3">
                  <input aria-label="Confirmer la nouvelle année" value={confirmText} onChange={(e) => setConfirmText(e.target.value.trim())}
                    placeholder={proposal.next_year} className="border border-line rounded-lg px-3 py-2 text-[14px] w-40 bg-white" />
                  <button type="button" disabled={busy || confirmText !== proposal.next_year} onClick={() => send(false)}
                    className="rounded-lg bg-brick text-white text-[14px] font-semibold px-5 py-2.5 hover:opacity-90 transition disabled:opacity-40">
                    {busy ? "Passage en cours…" : `Clôturer ${proposal.current_year} et ouvrir ${proposal.next_year}`}
                  </button>
                </div>
              </div>
            )}
          </section>
        )}
      </div>
    </div>
  );
}

function ClassCard({ c, targets, value, onDest, repeaters, onRepeaters }: {
  c: PlanClass; targets: Proposal["targets"]; value: string; onDest: (v: string) => void;
  repeaters: Set<string>; onRepeaters: (s: Set<string>) => void;
}) {
  const [open, setOpen] = useState(false);
  const [students, setStudents] = useState<StudentLite[] | null>(null);
  const risk = new Map(c.at_risk.map((r) => [r.id, r.annual_average]));
  const chosen = [...repeaters].filter((id) => risk.has(id) || students?.some((s) => s.id === id)).length;

  useEffect(() => {
    if (open && students === null) {
      api.all<StudentLite>(`/students?class_id=${c.id}&status=active`).then(setStudents).catch(() => setStudents([]));
    }
  }, [open, students, c.id]);

  function toggle(id: string) {
    const next = new Set(repeaters);
    if (next.has(id)) next.delete(id); else next.add(id);
    onRepeaters(next);
  }
  function checkAllAtRisk() {
    const next = new Set(repeaters);
    c.at_risk.forEach((r) => next.add(r.id));
    onRepeaters(next);
  }

  return (
    <div className="border border-line rounded-lg bg-white">
      <div className="p-4 flex flex-wrap items-center gap-4">
        <div className="min-w-[160px]">
          <p className="font-semibold text-ink">{c.name}</p>
          <p className="text-[12px] text-ink/50">{c.active_count} élève{c.active_count > 1 ? "s" : ""} actif{c.active_count > 1 ? "s" : ""}</p>
        </div>
        <label className="text-[13px] text-ink/70 flex items-center gap-2">Passe en
          <select value={value} onChange={(e) => onDest(e.target.value)} aria-label={`Destination de ${c.name}`}
            className={`border rounded-lg px-3 py-2 text-[14px] bg-white ${value ? "border-line" : "border-brick"}`}>
            <option value="">— choisir —</option>
            <option value={GRADUATE}>Terminale — sortie de l'établissement</option>
            {targets.filter((t) => t.id !== c.id).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </label>
        <span className="text-[12.5px] text-ink/60 ml-auto">{chosen} redoublant{chosen > 1 ? "s" : ""}</span>
        <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
          className="inline-flex items-center gap-1 text-[13px] text-navy underline underline-offset-2">
          {open ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />} Élèves
        </button>
      </div>
      {open && (
        <div className="border-t border-line px-4 py-3 space-y-2">
          {c.at_risk.length > 0 && (
            <button type="button" onClick={checkAllAtRisk} className="text-[12.5px] text-navy underline underline-offset-2">
              Cocher les {c.at_risk.length} élève(s) sous la moyenne de passage
            </button>
          )}
          {c.without_average > 0 && <p className="text-[12px] text-ink/50">{c.without_average} élève(s) sans note : aucune suggestion pour eux.</p>}
          {students === null ? <p className="text-sm text-ink/50">Chargement…</p> : (
            <ul className="grid sm:grid-cols-2 gap-x-6 gap-y-1">
              {students.map((s) => {
                const avg = risk.get(s.id);
                return (
                  <li key={s.id}>
                    <label className="flex items-center gap-2 text-[13.5px] cursor-pointer py-0.5">
                      <input type="checkbox" checked={repeaters.has(s.id)} onChange={() => toggle(s.id)} />
                      <span className="text-ink">{s.last_name} {s.first_name}</span>
                      {avg !== undefined && <span className="text-[12px] text-brick">{avg.toFixed(2)}/20</span>}
                    </label>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone?: "ok" }) {
  return (
    <div className="border border-line rounded-lg bg-white px-5 py-3">
      <p className="text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide">{label}</p>
      <p className={`font-display text-2xl font-bold ${tone === "ok" ? "text-pass" : "text-ink"}`}>{value.toLocaleString("fr-FR")}</p>
    </div>
  );
}
