import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../auth/AuthContext";

interface MySignature {
  signature_base64: string | null;
  stamp_base64: string | null;
}

function fileToDataUri(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

export default function ProfilePage() {
  const { user } = useAuth();
  const [data, setData] = useState<MySignature | null>(null);
  const [signaturePreview, setSignaturePreview] = useState<string | null>(null);
  const [stampPreview, setStampPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function reload() {
    api.get<MySignature>("/users/me/signature").then((d) => {
      setData(d);
      setSignaturePreview(d.signature_base64);
      setStampPreview(d.stamp_base64);
    });
  }
  useEffect(reload, []);

  async function handleFileChange(e: ChangeEvent<HTMLInputElement>, setPreview: (v: string) => void) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 1_000_000) {
      setError("Image trop volumineuse (1 Mo maximum).");
      return;
    }
    setPreview(await fileToDataUri(file));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setSubmitting(true);
    try {
      await api.patch("/users/me/signature", { signature_base64: signaturePreview, stamp_base64: stampPreview });
      setSuccess("Enregistré.");
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible d'enregistrer.");
    } finally {
      setSubmitting(false);
    }
  }

  if (!data) return <div className="px-10 py-10 text-ink/40">Chargement…</div>;

  return (
    <div className="px-10 py-10 max-w-xl">
      <h1 className="font-display text-3xl font-medium text-ink">Mon profil</h1>
      <p className="text-sm text-ink/55 mt-1">{user?.email}</p>

      <form onSubmit={handleSubmit} className="mt-8 border border-line rounded bg-white p-6 space-y-6">
        <p className="text-sm text-ink/60">
          Votre signature et votre tampon personnels servent à authentifier les documents que vous validez
          (bulletins, attestations). Vous seul(e) pouvez les renseigner ou les modifier.
        </p>

        <ImageField label="Signature" preview={signaturePreview} onChange={(e) => handleFileChange(e, setSignaturePreview)} />
        <ImageField label="Tampon" preview={stampPreview} onChange={(e) => handleFileChange(e, setStampPreview)} />

        {error && <p className="text-sm text-brick">{error}</p>}
        {success && <p className="text-sm text-pass">{success}</p>}

        <button type="submit" disabled={submitting} className="rounded bg-navy text-paper text-sm font-medium px-5 py-2.5 hover:bg-navy-light transition disabled:opacity-60">
          {submitting ? "Enregistrement…" : "Enregistrer"}
        </button>
      </form>
    </div>
  );
}

function ImageField({ label, preview, onChange }: { label: string; preview: string | null; onChange: (e: ChangeEvent<HTMLInputElement>) => void }) {
  return (
    <div>
      <label className="block text-sm font-medium text-ink/80 mb-1.5">{label}</label>
      <div className="flex items-center gap-4">
        {preview ? (
          <img src={preview} alt={label} className="w-20 h-20 object-contain border border-line rounded bg-paper" />
        ) : (
          <div className="w-20 h-20 border border-dashed border-line rounded flex items-center justify-center text-xs text-ink/30 text-center px-1">
            Aucun{label === "Signature" ? "e" : ""}
          </div>
        )}
        <input type="file" accept="image/*" onChange={onChange} className="text-sm text-ink/60" />
      </div>
    </div>
  );
}
