import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../auth/AuthContext";
import RequireRole from "../components/RequireRole";
import StatusPill from "../components/StatusPill";
import TemporaryPasswordDialog from "../components/TemporaryPasswordDialog";
import { CAN_MANAGE_USERS } from "../lib/permissions";

interface StaffUser {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  must_change_password: boolean;
  mfa_enabled: boolean;
}

interface Student {
  id: string;
  first_name: string;
  last_name: string;
}

const ROLE_OPTIONS = [
  { value: "school_admin", label: "Direction" },
  { value: "censor", label: "Censeur" },
  { value: "supervisor", label: "Surveillant" },
  { value: "accountant", label: "Comptable" },
  { value: "staff", label: "Secrétariat" },
  { value: "teacher", label: "Enseignant" },
  { value: "parent", label: "Parent" },
];

const ROLE_LABELS: Record<string, string> = {
  ...Object.fromEntries(ROLE_OPTIONS.map((r) => [r.value, r.label])),
  founder: "Fondateur", // affiché dans la liste du personnel, jamais proposé à la création (voir plus bas)
};

export default function StaffPage() {
  return (
    <RequireRole roles={CAN_MANAGE_USERS}>
      <StaffPageContent />
    </RequireRole>
  );
}

function StaffPageContent() {
  const { user } = useAuth();
  const isFounder = user?.role === "founder";
  // Seul le Fondateur peut créer un compte Direction — vérifié aussi côté
  // backend (user_service.create_user) ; ce filtrage n'est qu'un confort
  // d'interface, pas la protection réelle.
  const availableRoleOptions = isFounder ? ROLE_OPTIONS : ROLE_OPTIONS.filter((r) => r.value !== "school_admin");

  const [users, setUsers] = useState<StaffUser[]>([]);
  const [students, setStudents] = useState<Student[]>([]);
  const [showUserForm, setShowUserForm] = useState(false);
  const [showLinkForm, setShowLinkForm] = useState(false);
  const [userError, setUserError] = useState<string | null>(null);
  const [linkError, setLinkError] = useState<string | null>(null);
  const [linkSuccess, setLinkSuccess] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ tone: "ok" | "error"; text: string } | null>(null);
  const [editing, setEditing] = useState<StaffUser | null>(null);
  const [temporary, setTemporary] = useState<{ name: string; password: string } | null>(null);

  // Habilitations (miroir de account_service côté serveur, qui reste seul juge) : on ne se gère pas soi-même
  // ici, le Fondateur n'est pas géré depuis l'établissement, et seul le Fondateur gère la Direction.
  function canManage(u: StaffUser): boolean {
    if (u.id === user?.id || u.role === "founder") return false;
    if (u.role === "school_admin") return isFounder;
    return true;
  }

  function fail(err: unknown, fallback: string) {
    setNotice({ tone: "error", text: err instanceof ApiError ? err.message : fallback });
  }

  async function toggleActive(u: StaffUser) {
    const verb = u.is_active ? "désactiver" : "réactiver";
    const consequence = u.is_active ? " Elle perdra immédiatement l'accès, y compris ses sessions en cours." : "";
    if (!window.confirm(`Voulez-vous ${verb} le compte de ${u.full_name} ?${consequence}`)) return;
    setNotice(null);
    try {
      await api.post(`/users/${u.id}/${u.is_active ? "deactivate" : "reactivate"}`);
      setNotice({ tone: "ok", text: `Compte ${u.is_active ? "désactivé" : "réactivé"} : ${u.full_name}.` });
      reload();
    } catch (err) { fail(err, "Action impossible."); }
  }

  async function resetPassword(u: StaffUser) {
    if (!window.confirm(`Générer un nouveau mot de passe provisoire pour ${u.full_name} ? Ses sessions en cours seront fermées.`)) return;
    setNotice(null);
    try {
      const r = await api.post<{ temporary_password: string }>(`/users/${u.id}/reset-password`);
      setTemporary({ name: u.full_name, password: r.temporary_password });
      reload();
    } catch (err) { fail(err, "Impossible de réinitialiser le mot de passe."); }
  }

  async function resetMfa(u: StaffUser) {
    if (!window.confirm(`Désactiver la double authentification de ${u.full_name} (téléphone perdu) ? Elle pourra la réactiver depuis sa page Sécurité.`)) return;
    setNotice(null);
    try {
      await api.post(`/users/${u.id}/reset-mfa`);
      setNotice({ tone: "ok", text: `Double authentification désactivée : ${u.full_name}.` });
      reload();
    } catch (err) { fail(err, "Impossible de réinitialiser la double authentification."); }
  }

  function reload() {
    api.get<StaffUser[]>("/users").then(setUsers);
    api.get<Student[]>("/students").then(setStudents);
  }

  useEffect(reload, []);

  async function handleCreateUser(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setUserError(null);
    const form = new FormData(e.currentTarget);
    try {
      await api.post("/users", {
        email: form.get("email"),
        password: form.get("password"),
        full_name: form.get("full_name"),
        role: form.get("role"),
      });
      setShowUserForm(false);
      setNotice({ tone: "ok", text: "Compte créé. Communiquez le mot de passe provisoire en personne : la personne devra le remplacer dès sa première connexion." });
      reload();
    } catch (err) {
      setUserError(err instanceof ApiError ? err.message : "Impossible de créer ce compte.");
    }
  }

  async function handleCreateLink(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLinkError(null);
    setLinkSuccess(null);
    const form = new FormData(e.currentTarget);
    try {
      await api.post("/guardian-links", {
        parent_user_id: form.get("parent_user_id"),
        student_id: form.get("student_id"),
        relationship_label: form.get("relationship_label"),
      });
      setLinkSuccess("Rattachement créé — le parent peut désormais consulter cet élève.");
      (e.target as HTMLFormElement).reset();
    } catch (err) {
      setLinkError(err instanceof ApiError ? err.message : "Impossible de créer ce rattachement.");
    }
  }

  const parents = users.filter((u) => u.role === "parent");

  return (
    <div className="px-10 py-10 max-w-6xl">
      {editing && (
        <EditUserDialog
          target={editing} isSelf={editing.id === user?.id} isFounder={isFounder}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); setNotice({ tone: "ok", text: "Compte modifié." }); reload(); }}
        />
      )}
      {temporary && <TemporaryPasswordDialog name={temporary.name} password={temporary.password} onClose={() => setTemporary(null)} />}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-display text-3xl font-medium text-ink">Personnel</h1>
          <p className="text-sm text-ink/55 mt-1">Comptes de l'établissement, tous rôles confondus.</p>
        </div>
        <button
          onClick={() => setShowUserForm((v) => !v)}
          className="rounded bg-navy text-paper text-sm font-medium px-4 py-2 hover:bg-navy-light transition"
        >
          {showUserForm ? "Annuler" : "Ajouter un compte"}
        </button>
      </div>

      {showUserForm && (
        <form onSubmit={handleCreateUser} className="mt-6 border border-line rounded bg-white p-5 grid sm:grid-cols-2 gap-4">
          <Field name="full_name" label="Nom complet" required />
          <Field name="email" label="E-mail" type="email" required />
          <Field name="password" label="Mot de passe provisoire" type="password" required />
          <div>
            <label htmlFor="role" className="block text-sm font-medium text-ink/80 mb-1.5">
              Rôle
            </label>
            <select
              id="role"
              name="role"
              required
              className="w-full rounded border border-line bg-white px-3.5 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy transition"
            >
              {availableRoleOptions.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </div>
          {userError && <p className="sm:col-span-2 text-sm text-brick">{userError}</p>}
          <div className="sm:col-span-2">
            <button type="submit" className="rounded bg-ochre text-navy-deep text-sm font-medium px-4 py-2 hover:bg-ochre-dark transition">
              Créer le compte
            </button>
          </div>
        </form>
      )}

      {notice && (
        <p className={`mt-6 text-sm rounded px-3 py-2 border ${notice.tone === "ok" ? "text-[#1F7A52] bg-pass/10 border-pass/20" : "text-brick bg-brick/10 border-brick/20"}`}>{notice.text}</p>
      )}

      <div className="mt-8 border border-line rounded bg-white overflow-hidden">
        <table className="w-full text-[14.5px]">
          <thead>
            <tr>
              <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-5 pb-2.5 pt-4 border-b border-line">Nom</th>
              <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-5 pb-2.5 pt-4 border-b border-line">E-mail</th>
              <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-5 pb-2.5 pt-4 border-b border-line">Rôle</th>
              <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-5 pb-2.5 pt-4 border-b border-line">Statut</th>
              <th className="border-b border-line"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {users.length === 0 && (
              <tr>
                <td colSpan={5} className="px-5 py-8 text-ink/50">
                  Aucun compte pour l'instant.
                </td>
              </tr>
            )}
            {users.map((u) => (
              <tr key={u.id}>
                <td className="px-5 py-3 text-ink font-medium">{u.full_name}</td>
                <td className="px-5 py-3 text-ink/70">{u.email}</td>
                <td className="px-5 py-3 text-ink/70">{ROLE_LABELS[u.role] ?? u.role}</td>
                <td className="px-5 py-3">
                  <div className="flex flex-wrap gap-1.5">
                    <StatusPill label={u.is_active ? "Actif" : "Désactivé"} tone={u.is_active ? "ok" : "bad"} />
                    {u.must_change_password && <StatusPill label="Mot de passe provisoire" tone="warn" />}
                    {u.mfa_enabled && <StatusPill label="2FA" tone="neutral" />}
                  </div>
                </td>
                <td className="px-5 py-3">
                  <div className="flex flex-wrap items-center justify-end gap-x-3 gap-y-1 text-[13px]">
                    {u.id === user?.id && <span className="text-ink/40">Vous</span>}
                    {(canManage(u) || u.id === user?.id) && (
                      <button onClick={() => setEditing(u)} className="text-navy underline underline-offset-2 hover:text-navy-light">Modifier</button>
                    )}
                    {canManage(u) && (
                      <>
                        <button onClick={() => resetPassword(u)} className="text-navy underline underline-offset-2 hover:text-navy-light">Mot de passe</button>
                        {u.mfa_enabled && <button onClick={() => resetMfa(u)} className="text-navy underline underline-offset-2 hover:text-navy-light">Réinit. 2FA</button>}
                        <button onClick={() => toggleActive(u)} className={u.is_active ? "text-brick underline underline-offset-2" : "text-pass underline underline-offset-2"}>
                          {u.is_active ? "Désactiver" : "Réactiver"}
                        </button>
                      </>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <section className="mt-10">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="font-display text-xl font-medium text-ink">Rattacher un parent à un élève</h2>
            <p className="text-sm text-ink/55 mt-1">
              Un compte Parent n'a accès qu'aux élèves explicitement rattachés ici.
            </p>
          </div>
          <button
            onClick={() => setShowLinkForm((v) => !v)}
            className="rounded border border-navy text-navy text-sm font-medium px-4 py-2 hover:bg-navy/5 transition"
          >
            {showLinkForm ? "Annuler" : "Nouveau rattachement"}
          </button>
        </div>

        {showLinkForm && (
          <form onSubmit={handleCreateLink} className="mt-4 border border-line rounded bg-white p-5 grid sm:grid-cols-3 gap-4">
            <div>
              <label htmlFor="parent_user_id" className="block text-sm font-medium text-ink/80 mb-1.5">
                Compte parent
              </label>
              <select
                id="parent_user_id"
                name="parent_user_id"
                required
                className="w-full rounded border border-line bg-white px-3.5 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy transition"
              >
                <option value="">— Choisir —</option>
                {parents.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.full_name} ({p.email})
                  </option>
                ))}
              </select>
              {parents.length === 0 && (
                <p className="text-xs text-ink/50 mt-1">Créez d'abord un compte de rôle « Parent » ci-dessus.</p>
              )}
            </div>
            <div>
              <label htmlFor="student_id" className="block text-sm font-medium text-ink/80 mb-1.5">
                Élève
              </label>
              <select
                id="student_id"
                name="student_id"
                required
                className="w-full rounded border border-line bg-white px-3.5 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy transition"
              >
                <option value="">— Choisir —</option>
                {students.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.first_name} {s.last_name}
                  </option>
                ))}
              </select>
            </div>
            <Field name="relationship_label" label="Lien de parenté" placeholder="Mère, Père, Tuteur…" required />
            {linkError && <p className="sm:col-span-3 text-sm text-brick">{linkError}</p>}
            {linkSuccess && <p className="sm:col-span-3 text-sm text-pass">{linkSuccess}</p>}
            <div className="sm:col-span-3">
              <button type="submit" className="rounded bg-ochre text-navy-deep text-sm font-medium px-4 py-2 hover:bg-ochre-dark transition">
                Créer le rattachement
              </button>
            </div>
          </form>
        )}
      </section>
    </div>
  );
}

function Field({
  name, label, required, type = "text", placeholder,
}: { name: string; label: string; required?: boolean; type?: string; placeholder?: string }) {
  return (
    <div>
      <label htmlFor={name} className="block text-sm font-medium text-ink/80 mb-1.5">
        {label}
      </label>
      <input
        id={name}
        name={name}
        type={type}
        required={required}
        placeholder={placeholder}
        className="w-full rounded border border-line bg-white px-3.5 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy transition"
      />
    </div>
  );
}

function EditUserDialog({
  target, isSelf, isFounder, onClose, onSaved,
}: { target: StaffUser; isSelf: boolean; isFounder: boolean; onClose: () => void; onSaved: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  // Un compte parent reste parent, et un compte du personnel ne devient pas parent (le serveur l'impose aussi).
  const roleLocked = isSelf || target.role === "parent" || target.role === "founder";
  const roleChoices = ROLE_OPTIONS.filter((r) => r.value !== "parent" && (r.value !== "school_admin" || isFounder || target.role === "school_admin"));

  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    const form = new FormData(e.currentTarget);
    const body: Record<string, string> = {};
    const name = String(form.get("full_name") || "").trim();
    const email = String(form.get("email") || "").trim();
    const role = String(form.get("role") || target.role);
    if (name !== target.full_name) body.full_name = name;
    if (email.toLowerCase() !== target.email.toLowerCase()) body.email = email;
    if (!roleLocked && role !== target.role) body.role = role;
    if (Object.keys(body).length === 0) { onClose(); return; }
    setSaving(true);
    try {
      await api.patch(`/users/${target.id}`, body);
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible de modifier le compte.");
    } finally { setSaving(false); }
  }

  const cls = "w-full rounded border border-line bg-white px-3.5 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy transition disabled:bg-paper disabled:text-ink/50";
  return (
    <div className="fixed inset-0 bg-ink/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <form onSubmit={save} onClick={(e) => e.stopPropagation()} className="bg-white rounded-lg w-full max-w-md p-6 space-y-4" aria-label="Modifier le compte">
        <h3 className="font-display text-lg text-ink">Modifier le compte</h3>
        <div><label className="block text-sm font-medium text-ink/80 mb-1.5">Nom complet</label><input name="full_name" defaultValue={target.full_name} required className={cls} /></div>
        <div><label className="block text-sm font-medium text-ink/80 mb-1.5">E-mail</label><input name="email" type="email" defaultValue={target.email} required className={cls} /></div>
        <div>
          <label className="block text-sm font-medium text-ink/80 mb-1.5">Rôle</label>
          <select name="role" defaultValue={target.role} disabled={roleLocked} className={cls}>
            {roleLocked && <option value={target.role}>{ROLE_LABELS[target.role] ?? target.role}</option>}
            {!roleLocked && roleChoices.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
          {!roleLocked && <p className="text-xs text-ink/45 mt-1">Un changement de rôle prend effet immédiatement : la personne devra se reconnecter.</p>}
          {isSelf && <p className="text-xs text-ink/45 mt-1">Vous ne pouvez pas changer votre propre rôle.</p>}
        </div>
        {error && <p className="text-sm text-brick">{error}</p>}
        <div className="flex justify-end gap-3 pt-1">
          <button type="button" onClick={onClose} className="text-sm text-ink/60 px-3 py-2">Annuler</button>
          <button type="submit" disabled={saving} className="rounded bg-ochre text-navy-deep text-sm font-medium px-5 py-2 hover:bg-ochre-dark transition disabled:opacity-60">{saving ? "Enregistrement…" : "Enregistrer"}</button>
        </div>
      </form>
    </div>
  );
}
