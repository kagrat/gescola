import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../lib/api";

interface StaffUser {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
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

const ROLE_LABELS: Record<string, string> = Object.fromEntries(ROLE_OPTIONS.map((r) => [r.value, r.label]));

export default function StaffPage() {
  const [users, setUsers] = useState<StaffUser[]>([]);
  const [students, setStudents] = useState<Student[]>([]);
  const [showUserForm, setShowUserForm] = useState(false);
  const [showLinkForm, setShowLinkForm] = useState(false);
  const [userError, setUserError] = useState<string | null>(null);
  const [linkError, setLinkError] = useState<string | null>(null);
  const [linkSuccess, setLinkSuccess] = useState<string | null>(null);

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
    <div className="px-10 py-10 max-w-4xl">
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
              {ROLE_OPTIONS.map((r) => (
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

      <div className="mt-8 border border-line rounded bg-white overflow-hidden">
        <table className="w-full text-[14.5px]">
          <thead>
            <tr>
              <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-5 pb-2.5 pt-4 border-b border-line">Nom</th>
              <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-5 pb-2.5 pt-4 border-b border-line">E-mail</th>
              <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-5 pb-2.5 pt-4 border-b border-line">Rôle</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {users.length === 0 && (
              <tr>
                <td colSpan={3} className="px-5 py-8 text-ink/50">
                  Aucun compte pour l'instant.
                </td>
              </tr>
            )}
            {users.map((u) => (
              <tr key={u.id}>
                <td className="px-5 py-3 text-ink font-medium">{u.full_name}</td>
                <td className="px-5 py-3 text-ink/70">{u.email}</td>
                <td className="px-5 py-3 text-ink/70">{ROLE_LABELS[u.role] ?? u.role}</td>
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
