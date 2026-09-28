// Formats d'image acceptés pour les logos, signatures et cachets : ceux qui
// s'impriment sur un PDF. Le SVG est refusé (le serveur le refuse aussi — la
// vérification ici évite seulement un aller-retour inutile).
export const IMAGE_ACCEPT = "image/png,image/jpeg,image/webp,image/gif";
const ALLOWED = new Set(["image/png", "image/jpeg", "image/webp", "image/gif"]);
export const MAX_IMAGE_BYTES = 1_000_000;

/** Renvoie un message d'erreur si le fichier ne convient pas, sinon null. */
export function checkImageFile(file: File): string | null {
  if (!ALLOWED.has(file.type)) return "Format non pris en charge : utilisez une image PNG, JPEG, WebP ou GIF (pas de SVG).";
  if (file.size > MAX_IMAGE_BYTES) return "Image trop volumineuse (1 Mo maximum).";
  return null;
}
