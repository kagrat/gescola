import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import { api, ApiError } from "../lib/api";
import { checkImageFile, IMAGE_ACCEPT } from "../lib/images";
import { useAuth } from "../auth/AuthContext";
import { CAN_MANAGE_ESTABLISHMENT_SETTINGS, roleCan } from "../lib/permissions";

interface Settings {
  name: string;
  trade_name: string | null;
  rccm: string | null;
  ifu: string | null;
  address: string | null;
  logo_base64: string | null;
  academic_year: string | null;
  bulletin_motto: string | null;
  bulletin_authority_header: string | null;
  bulletin_place: string | null;
  bulletin_show_appreciations: boolean;
  bulletin_show_school_life: boolean;
  bulletin_show_head_teacher_signature: boolean;
  term_periods: Record<string, { start: string; end: string }> | null;
  bulletin_director_user_id: string | null;
  bulletin_censor_user_id: string | null;
}

interface Account {
  id: string;
  full_name: string;
  role: string;
  is_active: boolean;
}

const TERM_ROWS: [string, string][] = [["T1", "1er trimestre"], ["T2", "2e trimestre"], ["T3", "3e trimestre"]];

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
  const [accounts, setAccounts] = useState<Account[]>([]);

  function reload() {
    api.get<Settings>("/establishment/settings").then((s) => {
      setSettings(s);
      setLogoPreview(s.logo_base64);
    });
  }
  useEffect(reload, []);
  // Candidats aux signatures du bulletin : la liste des comptes n'est accessible qu'à qui peut modifier ces réglages.
  useEffect(() => {
    if (canEdit) api.get<Account[]>("/users").then(setAccounts).catch(() => setAccounts([]));
  }, [canEdit]);

  async function handleLogoChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const problem = checkImageFile(file);
    if (problem) {
      setError(problem);
      e.target.value = "";
      return;
    }
    setError(null);
    const dataUri = await fileToDataUri(file);
    setLogoPreview(dataUri);
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setSubmitting(true);
    const form = new FormData(e.currentTarget);
    // Périodes : on n'envoie que les trimestres dont début ET fin sont renseignés.
    const termPeriods: Record<string, { start: string; end: string }> = {};
    for (const [key, label] of TERM_ROWS) {
      const start = String(form.get(`${key}_start`) || "");
      const end = String(form.get(`${key}_end`) || "");
      if (start && end) termPeriods[key] = { start, end };
      else if (start || end) {
        setError(`${label} : renseignez la date de début ET la date de fin, ou laissez les deux vides.`);
        setSubmitting(false);
        return;
      }
    }
    try {
      await api.patch("/establishment/settings", {
        trade_name: form.get("trade_name") || null,
        rccm: form.get("rccm") || null,
        ifu: form.get("ifu") || null,
        address: form.get("address") || null,
        logo_base64: logoPreview,
        academic_year: form.get("academic_year") || null,
        bulletin_motto: form.get("bulletin_motto") || null,
        bulletin_authority_header: form.get("bulletin_authority_header") || null,
        bulletin_place: form.get("bulletin_place") || null,
        bulletin_director_user_id: form.get("bulletin_director_user_id") || null,
        bulletin_censor_user_id: form.get("bulletin_censor_user_id") || null,
        bulletin_show_appreciations: form.get("bulletin_show_appreciations") === "on",
        bulletin_show_school_life: form.get("bulletin_show_school_life") === "on",
        bulletin_show_head_teacher_signature: form.get("bulletin_show_head_teacher_signature") === "on",
        term_periods: Object.keys(termPeriods).length > 0 ? termPeriods : null,
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
              {canEdit && <input type="file" accept={IMAGE_ACCEPT} onChange={handleLogoChange} className="text-sm text-ink/60" />}
            </div>
          </div>

          <div className="pt-5 mt-2 border-t border-line">
            <h2 className="font-display text-lg text-ink">Bulletin de notes</h2>
            <p className="text-xs text-ink/45 mt-0.5 mb-4">Ces réglages s'appliquent à l'impression de tous les bulletins de l'établissement.</p>

            <div className="space-y-5">
              <div className="grid sm:grid-cols-2 gap-4">
                <Field name="academic_year" label="Année scolaire" defaultValue={settings.academic_year} placeholder="2026-2027" />
                <Field name="bulletin_place" label="Lieu (« Fait à … »)" defaultValue={settings.bulletin_place} placeholder="Cotonou" />
              </div>
              <Field name="bulletin_motto" label="Devise de l'établissement" defaultValue={settings.bulletin_motto} placeholder="Discipline - Travail - Réussite" />
              <div>
                <label htmlFor="bulletin_authority_header" className="block text-sm font-medium text-ink/80 mb-1.5">En-tête officiel (autorité de tutelle)</label>
                <textarea
                  id="bulletin_authority_header" name="bulletin_authority_header" rows={3} defaultValue={settings.bulletin_authority_header ?? ""}
                  placeholder={"République du Bénin\nMinistère des Enseignements Secondaire, Technique et de la Formation Professionnelle"}
                  className="w-full rounded border border-line bg-white px-3.5 py-2.5 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy transition resize-none"
                />
                <p className="text-xs text-ink/40 mt-1">Une ligne par ligne imprimée, en haut à droite du bulletin.</p>
              </div>

              <div>
                <p className="text-sm font-medium text-ink/80 mb-2">Signataires du bulletin</p>
                <div className="grid sm:grid-cols-2 gap-4">
                  <SignerSelect
                    name="bulletin_director_user_id" label="Directeur" current={settings.bulletin_director_user_id}
                    accounts={accounts.filter((a) => a.is_active && (a.role === "school_admin" || a.role === "founder"))}
                  />
                  <SignerSelect
                    name="bulletin_censor_user_id" label="Censeur" current={settings.bulletin_censor_user_id}
                    accounts={accounts.filter((a) => a.is_active && a.role === "censor")}
                  />
                </div>
                <p className="text-xs text-ink/40 mt-2">« Automatique » retient le compte actif le plus ancien du rôle. Chaque signataire pose sa propre signature et son propre cachet depuis son profil.</p>
              </div>

              <div>
                <p className="text-sm font-medium text-ink/80 mb-2">Affichage sur le bulletin</p>
                <div className="space-y-2">
                  <Toggle name="bulletin_show_appreciations" label="Appréciations (colonne « Appréciation du professeur » et appréciation générale)" defaultChecked={settings.bulletin_show_appreciations} />
                  <Toggle name="bulletin_show_school_life" label="Vie scolaire (absences, retards, incidents)" defaultChecked={settings.bulletin_show_school_life} />
                  <Toggle name="bulletin_show_head_teacher_signature" label="Signature du professeur principal (facultative)" defaultChecked={settings.bulletin_show_head_teacher_signature} />
                </div>
                <p className="text-xs text-ink/40 mt-2">Les signatures et cachets du Directeur et du Censeur figurent toujours sur le bulletin. La signature du professeur principal n'apparaît que si la classe en a un.</p>
              </div>

              <div>
                <p className="text-sm font-medium text-ink/80 mb-2">Périodes (facultatif)</p>
                <div className="space-y-2">
                  {TERM_ROWS.map(([key, label]) => (
                    <div key={key} className="grid grid-cols-[130px_1fr_1fr] gap-3 items-center">
                      <span className="text-sm text-ink/70">{label}</span>
                      <input type="date" name={`${key}_start`} defaultValue={settings.term_periods?.[key]?.start ?? ""} aria-label={`${label} — début`}
                        className="rounded border border-line bg-white px-3 py-2 text-[14px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy" />
                      <input type="date" name={`${key}_end`} defaultValue={settings.term_periods?.[key]?.end ?? ""} aria-label={`${label} — fin`}
                        className="rounded border border-line bg-white px-3 py-2 text-[14px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy" />
                    </div>
                  ))}
                </div>
                <p className="text-xs text-ink/40 mt-2">Sert à compter les absences, retards et incidents de chaque trimestre. Sans dates, ils sont comptés depuis le 1er septembre.</p>
              </div>
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

function Toggle({ name, label, defaultChecked }: { name: string; label: string; defaultChecked: boolean }) {
  return (
    <label className="flex items-start gap-2.5 text-sm text-ink/80 cursor-pointer">
      <input type="checkbox" name={name} defaultChecked={defaultChecked} className="mt-0.5 w-4 h-4 accent-navy" />
      <span>{label}</span>
    </label>
  );
}

function SignerSelect({ name, label, current, accounts }: { name: string; label: string; current: string | null; accounts: Account[] }) {
  return (
    <div>
      <label htmlFor={name} className="block text-xs font-medium text-ink/60 mb-1">{label}</label>
      <select
        id={name} name={name} defaultValue={current ?? ""}
        className="w-full rounded border border-line bg-white px-3.5 py-2.5 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy transition"
      >
        <option value="">Automatique</option>
        {accounts.map((a) => <option key={a.id} value={a.id}>{a.full_name}</option>)}
      </select>
    </div>
  );
}
