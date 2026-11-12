import { api } from "./api";

/** Ouvre un PDF authentifié dans un nouvel onglet (un simple lien n'enverrait pas le jeton). */
export async function openPdf(path: string): Promise<void> {
  const blob = await api.blob(path);
  const url = URL.createObjectURL(blob);
  const w = window.open(url, "_blank");
  if (!w) {
    // Fenêtre bloquée : on déclenche un téléchargement à la place.
    const a = document.createElement("a");
    a.href = url;
    a.download = "document.pdf";
    a.click();
  }
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

/** Télécharge un fichier authentifié (ex. export Excel) sous le nom donné. */
export async function downloadFile(path: string, filename: string): Promise<void> {
  const blob = await api.blob(path);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
