import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../lib/api";
import { openPdf } from "../lib/files";

export interface PaymentRow {
  id: string; invoice_label: string; amount: number; method: string; reference: string | null; receipt_number: number; paid_on: string;
}
interface Certificate { id: string; academic_year: string; number: number; voided_at: string | null }
const METHODS: Record<string, string> = { cash: "Espèces", mobile_money: "Mobile money", bank_transfer: "Virement" };
const pad = (n: number) => String(n).padStart(6, "0");

/** Historique des paiements d'un élève avec le reçu PDF de chacun. `base` = "/students/{id}" (personnel) ou "/children/{id}" (parent). */
export function PaymentsHistory({ base, refreshKey }: { base: string; refreshKey?: unknown }) {
  const [rows, setRows] = useState<PaymentRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api.get<PaymentRow[]>(`${base}/payments`).then(setRows).catch(() => setRows([])); }, [base, refreshKey]);
  if (rows.length === 0) return null;
  return (
    <div className="mt-4 border border-line rounded bg-white overflow-hidden">
      <p className="px-4 pt-3 text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide">Paiements et reçus</p>
      <table className="w-full text-[14px] mt-1">
        <tbody className="divide-y divide-line">
          {rows.map((p) => (
            <tr key={p.id}>
              <td className="px-4 py-2 text-ink/70">{new Date(p.paid_on).toLocaleDateString("fr-FR")}</td>
              <td className="px-4 py-2 text-ink">{p.invoice_label}</td>
              <td className="px-4 py-2 text-ink/70">{METHODS[p.method] ?? p.method}{p.reference ? ` · ${p.reference}` : ""}</td>
              <td className="px-4 py-2 font-medium text-ink">{p.amount.toLocaleString("fr-FR")} F</td>
              <td className="px-4 py-2 text-right">
                <button type="button" onClick={() => openPdf(base.startsWith("/children/") ? `${base}/payments/${p.id}/receipt` : `/payments/${p.id}/receipt`).catch(() => setError("Reçu indisponible."))}
                  className="text-navy text-sm underline underline-offset-2 hover:text-navy-light">Reçu n° {pad(p.receipt_number)}</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {error && <p className="px-4 pb-3 text-sm text-brick">{error}</p>}
    </div>
  );
}

/** Attestations de scolarité d'un élève. Le personnel peut en délivrer (et la Direction annuler) ; un parent ne fait que consulter. */
export function Certificates({ studentId, mode, canVoid }: { studentId: string; mode: "staff" | "parent"; canVoid?: boolean }) {
  const [list, setList] = useState<Certificate[] | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const listPath = mode === "staff" ? `/students/${studentId}/certificates` : `/children/${studentId}/certificates`;
  const pdfPath = (id: string) => (mode === "staff" ? `/certificates/${id}/pdf` : `/children/${studentId}/certificates/${id}/pdf`);
  const load = useCallback(() => { api.get<Certificate[]>(listPath).then(setList).catch(() => setList([])); }, [listPath]);
  useEffect(load, [load]);

  async function issue() {
    setBusy(true); setMessage(null);
    try {
      const c = await api.post<Certificate>(`/students/${studentId}/certificate`);
      load();
      await openPdf(pdfPath(c.id));
    } catch (err) { setMessage(err instanceof ApiError ? err.message : "Impossible de délivrer l'attestation."); }
    finally { setBusy(false); }
  }
  async function voidIt(c: Certificate) {
    const reason = window.prompt("Motif de l'annulation (obligatoire) :");
    if (!reason || reason.trim().length < 5) return;
    try { await api.post(`/certificates/${c.id}/void`, { reason: reason.trim() }); load(); }
    catch (err) { setMessage(err instanceof ApiError ? err.message : "Annulation impossible."); }
  }

  if (mode === "parent" && (list === null || list.length === 0)) return null;
  return (
    <div className="mt-4 border border-line rounded bg-white p-4">
      <div className="flex items-center justify-between">
        <p className="text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide">Attestation de scolarité</p>
        {mode === "staff" && (
          <button type="button" disabled={busy} onClick={issue} className="rounded bg-navy text-paper text-sm font-medium px-3.5 py-2 hover:bg-navy-light transition disabled:opacity-60">
            {list && list.some((c) => !c.voided_at) ? "Réimprimer l'attestation" : "Délivrer l'attestation"}
          </button>
        )}
      </div>
      {message && <p className="mt-2 text-sm text-brick">{message}</p>}
      {list && list.length > 0 && (
        <ul className="mt-3 divide-y divide-line text-[14px]">
          {list.map((c) => (
            <li key={c.id} className="py-2 flex items-center justify-between">
              <span className={c.voided_at ? "text-ink/40 line-through" : "text-ink"}>Année {c.academic_year} · n° {pad(c.number)}{c.voided_at ? " (annulée)" : ""}</span>
              <span className="flex gap-4">
                <button type="button" onClick={() => openPdf(pdfPath(c.id)).catch(() => setMessage("Document indisponible."))} className="text-navy underline underline-offset-2">Ouvrir</button>
                {mode === "staff" && canVoid && !c.voided_at && <button type="button" onClick={() => voidIt(c)} className="text-brick underline underline-offset-2">Annuler</button>}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
