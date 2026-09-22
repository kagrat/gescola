import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../auth/AuthContext";
import { CAN_MANAGE_ESTABLISHMENT_SETTINGS, roleCan } from "../lib/permissions";

interface Settings {
  name: string;
  trade_name: string | null;
  rccm: string | null;
  ifu: string | null;
  address: string | null;
  logo_base64: string | null;
}

function fileToDataUri(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

export default function EstablishmentSettingsPage() {
  const { user } = useAuth();
  const canEdit = roleCan(user?.role, CAN_MANAGE_ESTABLISHMENT_SETTINGS);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function reload() {
    api.get<Settings>("/establishment/settings").then((s) => {
      setSettings(s);
      setLogoPreview(s.logo_base64);
    });
  }
  useEffect(reload, []);

  async function handleLogoChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 1_000_000) {
      setError("Image trop volumineuse (1 Mo maximum).");
      return;
    }
    const dataUri = await fileToDataUri(file);
    setLogoPreview(dataUri);
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setSubmitting(true);
    const form = new FormData(e.currentTarget);
    try {
      await api.patch("/establishment/settings", {
        trade_name: form.get("trade_name") || null,
        rccm: form.get("rccm") || null,
        ifu: form.get("ifu") || null,
        address: form.get("address") || null,
        logo_base64: logoPreview,
      });
      setSuccess("Paramètres enregistrés.");
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible d'enregistrer les paramètres.");
    } finally {
      setSubmitting(false);
    }
  }

  if (!settings) return <div className="px-10 py-10 text-ink/40">Chargement…</div>;

  return (
    <div className="px-10 py-10 max-w-2xl">
      <h1 className="font-display text-3xl font-medium text-ink">Paramètres de l'établissement</h1>
      <p className="text-sm text-ink/55 mt-1">
        Identité légale utilisée sur les documents officiels (bulletins, attestations).
      </p>
      {!canEdit && (
        <p className="mt-3 text-sm text-ochre-dark bg-ochre/10 border border-ochre/20 rounded px-3 py-2">
          Lecture seule — seule la Direction peut modifier ces informations.
        </p>
      )}

      <form onSubmit={handleSubmit} className="mt-8 border border-line rounded bg-white p-6 space-y-5">
        <fieldset disabled={!canEdit} className="contents">
          <div>
            <label className="block text-sm font-medium text-ink/80 mb-1.5">Nom légal</label>
            <input value={settings.name} disabled className="w-full rounded border border-line bg-paper px-3.5 py-2.5 text-[14.5px] text-ink/50" />
            <p className="text-xs text-ink/40 mt-1">Modifiable uniquement par le Super Admin.</p>
          </div>

          <Field name="trade_name" label="Nom commercial (si différent)" defaultValue={settings.trade_name} placeholder="Groupe Scolaire La Colombe" />

          <div className="grid sm:grid-cols-2 gap-4">
            <Field name="rccm" label="RCCM" defaultValue={settings.rccm} placeholder="BJ-COT-2024-B-1234" />
            <Field name="ifu" label="IFU" defaultValue={settings.ifu} placeholder="3202400001234" />
          </div>

          <Field name="address" label="Localisation" defaultValue={settings.address} placeholder="Cotonou, Bénin" />

          <div>
            <label className="block text-sm font-medium text-ink/80 mb-1.5">Logo</label>
            <div className="flex items-center gap-4">
              {logoPreview ? (
                <img src={logoPreview} alt="Logo" className="w-16 h-16 object-contain border border-line rounded bg-paper" />
              ) : (
                <div className="w-16 h-16 border border-dashed border-line rounded flex items-center justify-center text-xs text-ink/30">
                  Aucun
                </div>
              )}
              {canEdit && <input type="file" accept="image/*" onChange={handleLogoChange} className="text-sm text-ink/60" />}
            </div>
          </div>
        </fieldset>

        {error && <p className="text-sm text-brick">{error}</p>}
        {success && <p className="text-sm text-pass">{success}</p>}

        {canEdit && (
          <button type="submit" disabled={submitting} className="rounded bg-navy text-paper text-sm font-medium px-5 py-2.5 hover:bg-navy-light transition disabled:opacity-60">
            {submitting ? "Enregistrement…" : "Enregistrer"}
          </button>
        )}
      </form>
    </div>
  );
}

function Field({ name, label, defaultValue, placeholder }: { name: string; label: string; defaultValue: string | null; placeholder?: string }) {
  return (
    <div>
      <label htmlFor={name} className="block text-sm font-medium text-ink/80 mb-1.5">{label}</label>
      <input
        id={name} name={name} defaultValue={defaultValue ?? ""} placeholder={placeholder}
        className="w-full rounded border border-line bg-white px-3.5 py-2.5 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy transition"
      />
    </div>
  );
}
