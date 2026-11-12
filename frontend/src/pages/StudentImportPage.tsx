import { useState, type ChangeEvent } from "react";
import { Link } from "react-router-dom";
import { Download, FileSpreadsheet, CheckCircle2, AlertTriangle } from "lucide-react";
import { api, ApiError } from "../lib/api";

interface Issue {
  row: number;
  message: string;
  field: string | null;
}
interface Report {
  dry_run: boolean;
  total_rows: number;
  valid_rows: number;
  imported: number;
  error_count: number;
  warning_count: number;
  errors: Issue[];
  warnings: Issue[];
  ignored_columns: string[];
  preview: { row: number; last_name: string; first_name: string; class: string | null; matricule: string | null }[];
}

const MAX_BYTES = 2 * 1024 * 1024;

export default function StudentImportPage() {
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<number | null>(null);

  function pick(e: ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0] ?? null;
    setReport(null);
    setDone(null);
    setError(null);
    if (f && f.size > MAX_BYTES) {
      setFile(null);
      setError("Fichier trop volumineux (2 Mo maximum).");
      return;
    }
    setFile(f);
  }

  async function send(dryRun: boolean) {
    if (!file) return;
    setBusy(true);
    setError(null);
    const form = new FormData();
    form.append("file", file);
    try {
      const result = await api.upload<Report>(`/students/import?dry_run=${dryRun}`, form);
      if (dryRun) setReport(result);
      else setDone(result.imported);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Envoi impossible. Vérifiez votre connexion et réessayez.");
    } finally {
      setBusy(false);
    }
  }

  async function downloadTemplate() {
    try {
      const blob = await api.blob("/students/import/template");
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "modele-import-eleves.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("Impossible de télécharger le modèle.");
    }
  }

  const ready = report !== null && report.error_count === 0 && report.valid_rows > 0;

  return (
    <div>
      <div className="px-10 py-8 border-b border-line">
        <Link to="/eleves" className="text-sm text-ink/50 hover:text-ink transition">← Élèves</Link>
        <h1 className="font-display text-[21px] font-bold text-ink mt-1">Importer des élèves</h1>
        <p className="text-[12.5px] text-ink/60 mt-0.5">Depuis un fichier Excel (.xlsx) ou CSV — jusqu'à 2 000 élèves à la fois.</p>
      </div>

      <div className="px-10 py-8 max-w-4xl space-y-6">
        <section className="border border-line rounded-lg bg-white p-5 text-[13.5px] text-ink/80 space-y-2">
          <p><b className="text-ink">1.</b> Téléchargez le modèle et remplissez-le (une ligne par élève). Colonnes obligatoires : <b>Nom</b> et <b>Prénom</b>.</p>
          <p><b className="text-ink">2.</b> La <b>classe</b> doit déjà exister (même nom que dans GESCOLA). Date de naissance : JJ/MM/AAAA.</p>
          <p><b className="text-ink">3.</b> Choisissez le fichier : une <b>vérification</b> est faite d'abord, rien n'est enregistré. L'import est « tout ou rien ».</p>
          <button type="button" onClick={downloadTemplate} className="mt-1 inline-flex items-center gap-1.5 text-navy underline underline-offset-2 hover:text-navy-light">
            <Download className="w-4 h-4" strokeWidth={1.8} /> Télécharger le modèle (CSV)
          </button>
        </section>

        <section className="border border-line rounded-lg bg-white p-5 flex flex-wrap items-center gap-4">
          <label className="inline-flex items-center gap-2 cursor-pointer text-[13.5px] font-semibold text-ink border border-line rounded-lg px-4 py-2.5 hover:bg-paper transition">
            <FileSpreadsheet className="w-4 h-4" strokeWidth={1.8} />
            {file ? "Changer de fichier" : "Choisir un fichier"}
            <input type="file" accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" onChange={pick} className="sr-only" />
          </label>
          <span className="text-[13px] text-ink/60 truncate max-w-[360px]">{file ? file.name : "Aucun fichier choisi"}</span>
          <button type="button" disabled={!file || busy || done !== null} onClick={() => send(true)}
            className="ml-auto rounded-lg bg-navy-deep text-sky-200 text-[13.5px] font-semibold px-4 py-2.5 hover:bg-navy transition disabled:opacity-50">
            {busy && !report ? "Vérification…" : "Vérifier le fichier"}
          </button>
        </section>

        {error && <p role="alert" className="text-sm text-brick">{error}</p>}

        {done !== null && (
          <div role="status" className="flex items-start gap-3 border border-pass/40 bg-pass/10 rounded-lg p-5 text-[14px] text-ink">
            <CheckCircle2 className="w-5 h-5 text-pass shrink-0 mt-0.5" strokeWidth={1.8} />
            <div>
              <p className="font-semibold">{done.toLocaleString("fr-FR")} élève{done > 1 ? "s" : ""} importé{done > 1 ? "s" : ""}.</p>
              <Link to="/eleves" className="text-navy underline underline-offset-2">Voir la liste des élèves</Link>
            </div>
          </div>
        )}

        {report && done === null && (
          <section className="space-y-4">
            <div className="grid sm:grid-cols-3 gap-3 text-[13px]">
              <Stat label="Lignes lues" value={report.total_rows} />
              <Stat label="Lignes valides" value={report.valid_rows} tone="ok" />
              <Stat label="Erreurs" value={report.error_count} tone={report.error_count ? "bad" : undefined} />
            </div>

            {report.ignored_columns.length > 0 && (
              <p className="text-[13px] text-ink/60">Colonnes ignorées : {report.ignored_columns.join(", ")}.</p>
            )}

            {report.errors.length > 0 && (
              <IssueTable title={`Erreurs à corriger (${report.error_count}${report.error_count > report.errors.length ? `, ${report.errors.length} affichées` : ""})`} issues={report.errors} tone="bad" />
            )}
            {report.warnings.length > 0 && (
              <IssueTable title={`Avertissements (${report.warning_count}) — n'empêchent pas l'import`} issues={report.warnings} tone="warn" />
            )}

            {report.preview.length > 0 && (
              <div className="border border-line rounded-lg bg-white overflow-hidden">
                <p className="px-5 pt-4 pb-2 text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide">Aperçu des premières lignes valides</p>
                <table className="w-full text-[13.5px]">
                  <tbody className="divide-y divide-line">
                    {report.preview.map((p) => (
                      <tr key={p.row}>
                        <td className="px-5 py-2 text-ink/40 w-16">L{p.row}</td>
                        <td className="px-5 py-2 font-semibold text-ink">{p.first_name} {p.last_name}</td>
                        <td className="px-5 py-2 text-ink/70">{p.class ?? "Sans classe"}</td>
                        <td className="px-5 py-2 text-ink/70">{p.matricule ?? ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {ready ? (
              <button type="button" disabled={busy} onClick={() => send(false)}
                className="rounded-lg bg-pass text-white text-[14px] font-semibold px-5 py-3 hover:opacity-90 transition disabled:opacity-60">
                {busy ? "Import en cours…" : `Importer ${report.valid_rows.toLocaleString("fr-FR")} élève${report.valid_rows > 1 ? "s" : ""}`}
              </button>
            ) : (
              <p className="flex items-center gap-2 text-[13.5px] text-brick">
                <AlertTriangle className="w-4 h-4" strokeWidth={1.8} />
                Corrigez le fichier puis relancez la vérification : tant qu'il reste une erreur, rien ne peut être importé.
              </p>
            )}
          </section>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone?: "ok" | "bad" }) {
  const color = tone === "ok" ? "text-pass" : tone === "bad" ? "text-brick" : "text-ink";
  return (
    <div className="border border-line rounded-lg bg-white px-5 py-3">
      <p className="text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide">{label}</p>
      <p className={`font-display text-2xl font-bold ${color}`}>{value.toLocaleString("fr-FR")}</p>
    </div>
  );
}

function IssueTable({ title, issues, tone }: { title: string; issues: Issue[]; tone: "bad" | "warn" }) {
  return (
    <div className="border border-line rounded-lg bg-white overflow-hidden">
      <p className={`px-5 pt-4 pb-2 text-[13px] font-semibold ${tone === "bad" ? "text-brick" : "text-ink/70"}`}>{title}</p>
      <table className="w-full text-[13.5px]">
        <tbody className="divide-y divide-line max-h-80">
          {issues.map((i, n) => (
            <tr key={`${i.row}-${n}`}>
              <td className="px-5 py-2 text-ink/50 w-20 whitespace-nowrap">Ligne {i.row}</td>
              <td className="px-5 py-2 text-ink">{i.message}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
