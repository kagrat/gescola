import { useState } from "react";
import { Download } from "lucide-react";
import { ApiError } from "../lib/api";
import { downloadFile } from "../lib/files";

/** Bouton « Exporter (Excel) » : télécharge le fichier et affiche l'erreur du serveur le cas échéant. */
export default function ExportButton({ path, filename, label = "Exporter (Excel)" }: { path: string; filename: string; label?: string }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function run() {
    setBusy(true); setError(null);
    try { await downloadFile(path, filename); }
    catch (e) { setError(e instanceof ApiError ? e.message : "Export impossible."); }
    finally { setBusy(false); }
  }
  return (
    <span className="inline-flex flex-col items-start">
      <button type="button" onClick={run} disabled={busy}
        className="flex items-center gap-1.5 rounded-lg border border-line bg-white text-ink text-[13.5px] font-semibold px-4 py-2.5 hover:bg-paper transition disabled:opacity-60">
        <Download className="w-4 h-4" strokeWidth={2} />{busy ? "Préparation…" : label}
      </button>
      {error && <span className="mt-1 text-[12px] text-brick">{error}</span>}
    </span>
  );
}
