import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { CheckCircle2, XCircle } from "lucide-react";

interface Verification {
  kind: "receipt" | "certificate"; valid: boolean; number: number; school_name: string; issued_on: string;
  student_name: string; details: Record<string, string>; voided_on: string | null;
}
const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

/** Page PUBLIQUE (sans connexion) ouverte par le QR code d'un reçu ou d'une attestation. */
export default function VerifyDocumentPage() {
  const { code = "" } = useParams();
  const [state, setState] = useState<"loading" | "notfound" | "limited" | "error" | Verification>("loading");

  useEffect(() => {
    fetch(`${API_BASE}/public/verify/${encodeURIComponent(code)}`)
      .then(async (r) => {
        if (r.status === 404) return setState("notfound");
        if (r.status === 429) return setState("limited");
        if (!r.ok) return setState("error");
        setState(await r.json());
      })
      .catch(() => setState("error"));
  }, [code]);

  const label = typeof state === "object" ? (state.kind === "receipt" ? "Reçu de paiement" : "Attestation de scolarité") : "";
  return (
    <main className="min-h-screen bg-paper flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-md bg-white border border-line rounded-xl p-7">
        <p className="font-display text-[13px] font-bold text-navy tracking-wide">GESCOLA · VÉRIFICATION DE DOCUMENT</p>
        {state === "loading" && <p className="mt-6 text-ink/60">Vérification en cours…</p>}
        {state === "notfound" && (
          <Result ok={false} title="Document introuvable">
            Ce code ne correspond à aucun document émis. Vérifiez qu'il est bien recopié ; en cas de doute, considérez le document comme non authentique.
          </Result>
        )}
        {state === "limited" && <p className="mt-6 text-ink/70">Trop de vérifications en peu de temps. Réessayez dans une minute.</p>}
        {state === "error" && <p className="mt-6 text-brick">Vérification impossible pour le moment. Réessayez plus tard.</p>}
        {typeof state === "object" && (
          <>
            <Result ok={state.valid} title={state.valid ? "Document authentique" : "Document ANNULÉ"}>
              {state.valid
                ? `Ce document a bien été émis par ${state.school_name}.`
                : `Ce document a été annulé par ${state.school_name}${state.voided_on ? ` le ${new Date(state.voided_on).toLocaleDateString("fr-FR")}` : ""} : il n'a plus de valeur.`}
            </Result>
            <dl className="mt-5 text-[14px] divide-y divide-line border-y border-line">
              <Row k="Document" v={`${label} n° ${String(state.number).padStart(6, "0")}`} />
              <Row k="Établissement" v={state.school_name} />
              <Row k="Émis le" v={new Date(state.issued_on).toLocaleDateString("fr-FR")} />
              <Row k="Élève" v={state.student_name} />
              {Object.entries(state.details).map(([k, v]) => <Row key={k} k={k} v={v} />)}
            </dl>
            <p className="mt-4 text-[12px] text-ink/50">Comparez ces informations avec celles du document papier ou PDF que vous avez reçu.</p>
          </>
        )}
      </div>
    </main>
  );
}

function Result({ ok, title, children }: { ok: boolean; title: string; children: React.ReactNode }) {
  const Icon = ok ? CheckCircle2 : XCircle;
  return (
    <div className={`mt-6 rounded-lg p-4 flex gap-3 ${ok ? "bg-green-50 text-green-900" : "bg-red-50 text-red-900"}`} role="status">
      <Icon className="w-6 h-6 shrink-0" strokeWidth={1.8} />
      <div><p className="font-semibold">{title}</p><p className="text-[13.5px] mt-1">{children}</p></div>
    </div>
  );
}
function Row({ k, v }: { k: string; v: string }) {
  return <div className="flex justify-between gap-4 py-2.5"><dt className="text-ink/55">{k}</dt><dd className="font-medium text-ink text-right">{v}</dd></div>;
}
