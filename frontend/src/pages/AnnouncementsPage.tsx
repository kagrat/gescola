import { useEffect, useState, type FormEvent } from "react";
import { Megaphone, Trash2 } from "lucide-react";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../auth/AuthContext";
import RequireRole from "../components/RequireRole";
import { CAN_PUBLISH_ANNOUNCEMENTS, CAN_READ_ANNOUNCEMENTS, roleCan } from "../lib/permissions";

interface SchoolClass { id: string; name: string; }
interface Announcement {
  id: string; author_id: string; author_name: string; class_id: string | null; class_name: string | null;
  title: string; body: string; created_at: string;
}

const inputCls = "w-full rounded border border-line bg-white px-3.5 py-2.5 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy transition";

export default function AnnouncementsPage() {
  return (
    <RequireRole roles={CAN_READ_ANNOUNCEMENTS}>
      <AnnouncementsPageContent />
    </RequireRole>
  );
}

function AnnouncementsPageContent() {
  const { user } = useAuth();
  const canPublish = roleCan(user?.role, CAN_PUBLISH_ANNOUNCEMENTS);
  const [items, setItems] = useState<Announcement[]>([]);
  const [classes, setClasses] = useState<SchoolClass[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  function reload() {
    api.get<Announcement[]>("/announcements").then(setItems).catch(() => setItems([]));
  }
  useEffect(reload, []);
  useEffect(() => {
    if (canPublish) api.get<SchoolClass[]>("/classes").then(setClasses).catch(() => setClasses([]));
  }, [canPublish]);

  async function handleCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    const form = new FormData(e.currentTarget);
    try {
      await api.post("/announcements", {
        title: form.get("title"),
        body: form.get("body"),
        class_id: form.get("class_id") || null,
      });
      setShowForm(false);
      setNotice("Annonce publiée.");
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible de publier cette annonce.");
    }
  }

  async function handleDelete(id: string) {
    if (!window.confirm("Retirer cette annonce ? Elle ne sera plus visible.")) return;
    setError(null);
    try {
      await api.del(`/announcements/${id}`);
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible de retirer cette annonce.");
    }
  }

  return (
    <div className="px-10 py-10 max-w-3xl">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-medium text-ink">Annonces</h1>
          <p className="text-sm text-ink/55 mt-1">
            {user?.role === "parent"
              ? "Informations de l'établissement et de la classe de vos enfants."
              : canPublish
                ? "Publiez une information pour toutes les familles, ou pour une seule classe."
                : "Informations publiées par l'établissement."}
          </p>
        </div>
        {canPublish && (
          <button onClick={() => setShowForm((v) => !v)} className="rounded bg-navy text-paper text-sm font-medium px-4 py-2.5 hover:bg-navy-light transition shrink-0">
            {showForm ? "Annuler" : "Nouvelle annonce"}
          </button>
        )}
      </div>

      {notice && <p className="mt-4 text-sm text-pass">{notice}</p>}

      {showForm && (
        <form onSubmit={handleCreate} className="mt-6 border border-line rounded bg-white p-5 space-y-4">
          <div>
            <label htmlFor="title" className="block text-sm font-medium text-ink/80 mb-1.5">Titre</label>
            <input id="title" name="title" required maxLength={200} className={inputCls} placeholder="Rentrée des classes" />
          </div>
          <div>
            <label htmlFor="body" className="block text-sm font-medium text-ink/80 mb-1.5">Texte</label>
            <textarea id="body" name="body" required rows={4} maxLength={5000} className={`${inputCls} resize-none`} placeholder="La rentrée aura lieu le lundi 6 octobre à 8h." />
          </div>
          <div>
            <label htmlFor="class_id" className="block text-sm font-medium text-ink/80 mb-1.5">Destinataires</label>
            <select id="class_id" name="class_id" className={inputCls}>
              <option value="">Tout l'établissement</option>
              {classes.map((c) => <option key={c.id} value={c.id}>Uniquement {c.name}</option>)}
            </select>
          </div>
          {error && <p className="text-sm text-brick">{error}</p>}
          <div className="flex justify-end">
            <button type="submit" className="rounded bg-ochre text-navy-deep text-sm font-medium px-5 py-2.5 hover:bg-ochre-dark transition">Publier</button>
          </div>
        </form>
      )}

      {!showForm && error && <p className="mt-4 text-sm text-brick">{error}</p>}

      <div className="mt-8 space-y-3 mb-16">
        {items.length === 0 && <p className="text-sm text-ink/40">Aucune annonce pour l'instant.</p>}
        {items.map((a) => (
          <div key={a.id} className="border border-line rounded bg-white p-5">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <Megaphone className="w-4 h-4 mt-1 text-navy shrink-0" />
                <div>
                  <p className="font-medium text-ink">{a.title}</p>
                  <p className="text-xs text-ink/45 mt-0.5">
                    {a.class_name ?? "Tout l'établissement"} · {a.author_name} · {new Date(a.created_at).toLocaleDateString("fr-FR", { day: "2-digit", month: "long", year: "numeric" })}
                  </p>
                </div>
              </div>
              {canPublish && (user?.id === a.author_id || ["school_admin", "founder"].includes(user?.role ?? "")) && (
                <button onClick={() => handleDelete(a.id)} title="Retirer" className="text-ink/40 hover:text-brick shrink-0">
                  <Trash2 className="w-4 h-4" />
                </button>
              )}
            </div>
            <p className="text-[14.5px] text-ink/80 mt-3 whitespace-pre-wrap">{a.body}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
