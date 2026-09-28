import { useEffect, useMemo, useState } from "react";
import { Download, Eye, Pencil } from "lucide-react";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../auth/AuthContext";
import RequireRole from "../components/RequireRole";
import StatusPill from "../components/StatusPill";
import { CAN_MANAGE_BULLETINS, CAN_READ_BULLETINS, roleCan } from "../lib/permissions";

interface SchoolClass { id: string; name: string; }
interface Summary {
  id: string; student_id: string; student_name: string; class_id: string; class_name: string; term: string;
  academic_year: string; status: "draft" | "published"; general_average: number | null; rank: number | null;
  class_size: number; published_at: string | null;
}
interface Detail extends Summary { principal_comment: string | null; council_decision: string | null; }

const TERMS: Record<string, string> = { T1: "1er trimestre", T2: "2e trimestre", T3: "3e trimestre" };
const DECISION_SUGGESTIONS = [
  "Tableau d'honneur", "Félicitations", "Encouragements", "Avertissement travail", "Avertissement conduite", "Blâme",
  "Admis(e) en classe supérieure", "Redouble",
];
const inputCls = "w-full rounded border border-line bg-white px-3.5 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy transition";

const fmt = (v: number | null) => (v === null ? "—" : v.toFixed(2).replace(".", ","));

export default function BulletinsPage() {
  return (
    <RequireRole roles={CAN_READ_BULLETINS}>
      <BulletinsPageContent />
    </RequireRole>
  );
}

function BulletinsPageContent() {
  const { user } = useAuth();
  const canManage = roleCan(user?.role, CAN_MANAGE_BULLETINS);
  const [classes, setClasses] = useState<SchoolClass[]>([]);
  const [classId, setClassId] = useState("");
  const [term, setTerm] = useState("T1");
  const [query, setQuery] = useState("");
  const [cards, setCards] = useState<Summary[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ tone: "ok" | "error"; text: string } | null>(null);
  const [preview, setPreview] = useState<{ url: string; title: string } | null>(null);
  const [editing, setEditing] = useState<Detail | null>(null);

  useEffect(() => {
    api.get<SchoolClass[]>("/classes").then((list) => {
      setClasses(list);
      if (list.length > 0) setClassId((current) => current || list[0].id);
    }).catch(() => setClasses([]));
  }, []);

  function reload() {
    if (!classId) return;
    setLoading(true);
    api.get<Summary[]>(`/report-cards?class_id=${classId}&term=${term}`)
      .then(setCards)
      .catch(() => setCards([]))
      .finally(() => setLoading(false));
  }
  useEffect(reload, [classId, term]);

  const shown = useMemo(
    () => cards.filter((c) => c.student_name.toLowerCase().includes(query.trim().toLowerCase())),
    [cards, query],
  );

  function fail(err: unknown, fallback: string) {
    setMessage({ tone: "error", text: err instanceof ApiError ? err.message : fallback });
  }

  async function generate() {
    setMessage(null);
    try {
      const r = await api.post<{ created: number; updated: number; skipped_published: number }>("/report-cards/generate", { class_id: classId, term });
      const parts = [`${r.created} créé(s)`, `${r.updated} actualisé(s)`];
      if (r.skipped_published > 0) parts.push(`${r.skipped_published} publié(s) conservé(s) tels quels`);
      setMessage({ tone: "ok", text: `Bulletins générés : ${parts.join(", ")}.` });
      reload();
    } catch (err) { fail(err, "Impossible de générer les bulletins."); }
  }

  async function togglePublish(card: Summary) {
    setMessage(null);
    try {
      await api.post(`/report-cards/${card.id}/${card.status === "published" ? "unpublish" : "publish"}`);
      reload();
    } catch (err) { fail(err, "Action impossible."); }
  }

  async function openPreview(card: Summary) {
    setMessage(null);
    try {
      const blob = await api.blob(`/report-cards/${card.id}/pdf`);
      setPreview({ url: URL.createObjectURL(blob), title: card.student_name });
    } catch (err) { fail(err, "Impossible d'afficher le bulletin."); }
  }

  async function download(card: Summary) {
    setMessage(null);
    try {
      const blob = await api.blob(`/report-cards/${card.id}/pdf`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `bulletin-${card.student_name.replace(/\s+/g, "-")}-${card.term}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) { fail(err, "Impossible de télécharger le bulletin."); }
  }

  async function openEditor(card: Summary) {
    setMessage(null);
    try { setEditing(await api.get<Detail>(`/report-cards/${card.id}`)); }
    catch (err) { fail(err, "Impossible d'ouvrir le bulletin."); }
  }

  function closePreview() {
    if (preview) URL.revokeObjectURL(preview.url);
    setPreview(null);
  }

  return (
    <div className="px-10 py-10 max-w-6xl">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-medium text-ink">Bulletins</h1>
          <p className="text-sm text-ink/55 mt-1">
            {canManage ? "Générez, complétez et publiez les bulletins de notes de chaque classe."
              : user?.role === "staff" ? "Consultez et imprimez les bulletins publiés."
              : "Bulletins des classes dont vous êtes professeur principal — vous rédigez l'appréciation générale."}
          </p>
        </div>
        {canManage && (
          <button onClick={generate} disabled={!classId} className="rounded bg-navy text-paper text-sm font-medium px-4 py-2.5 hover:bg-navy-light transition disabled:opacity-50">
            Générer / actualiser les bulletins
          </button>
        )}
      </div>

      <div className="mt-6 grid sm:grid-cols-[200px_180px_1fr] gap-4 border border-line rounded bg-white p-4">
        <div>
          <label className="block text-xs font-semibold text-ink/50 mb-1.5">Classe</label>
          <select value={classId} onChange={(e) => setClassId(e.target.value)} className={inputCls}>
            {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs font-semibold text-ink/50 mb-1.5">Période</label>
          <select value={term} onChange={(e) => setTerm(e.target.value)} className={inputCls}>
            {Object.entries(TERMS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs font-semibold text-ink/50 mb-1.5">Élève</label>
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Rechercher un élève…" className={inputCls} />
        </div>
      </div>

      {message && (
        <p className={`mt-4 text-sm rounded px-3 py-2 border ${message.tone === "ok" ? "text-[#1F7A52] bg-pass/10 border-pass/20" : "text-brick bg-brick/10 border-brick/20"}`}>{message.text}</p>
      )}

      <h2 className="font-display text-lg text-ink mt-8 mb-3">Liste des bulletins</h2>
      <div className="border border-line rounded bg-white overflow-hidden">
        <table className="w-full text-[14.5px]">
          <thead>
            <tr>
              {["N°", "Élève", "Classe", "Période", "Moyenne générale", "Rang", "Statut", ""].map((h) => (
                <th key={h} className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-3.5 border-b border-line">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {loading && <tr><td colSpan={8} className="px-4 py-6 text-ink/50">Chargement…</td></tr>}
            {!loading && shown.length === 0 && (
              <tr><td colSpan={8} className="px-4 py-8 text-ink/50">
                {canManage ? "Aucun bulletin pour cette classe et cette période — cliquez sur « Générer / actualiser les bulletins »." : "Aucun bulletin à afficher."}
              </td></tr>
            )}
            {shown.map((c, i) => (
              <tr key={c.id}>
                <td className="px-4 py-2.5 text-ink/50">{i + 1}</td>
                <td className="px-4 py-2.5 font-medium text-ink">{c.student_name}</td>
                <td className="px-4 py-2.5 text-ink/70">{c.class_name}</td>
                <td className="px-4 py-2.5 text-ink/70">{TERMS[c.term]}</td>
                <td className="px-4 py-2.5 font-medium">{c.general_average === null ? "—" : `${fmt(c.general_average)} / 20`}</td>
                <td className="px-4 py-2.5 text-ink/70">{c.rank === null ? "—" : `${c.rank} / ${c.class_size}`}</td>
                <td className="px-4 py-2.5"><StatusPill label={c.status === "published" ? "Publié" : "Brouillon"} tone={c.status === "published" ? "ok" : "warn"} /></td>
                <td className="px-4 py-2.5">
                  <div className="flex items-center justify-end gap-3 text-sm">
                    <button title="Aperçu" onClick={() => openPreview(c)} className="text-ink/60 hover:text-navy"><Eye className="w-4 h-4" /></button>
                    <button title="Télécharger le PDF" onClick={() => download(c)} className="text-ink/60 hover:text-navy"><Download className="w-4 h-4" /></button>
                    {(canManage || user?.role === "teacher") && (
                      <button title="Appréciations" onClick={() => openEditor(c)} className="text-ink/60 hover:text-navy"><Pencil className="w-4 h-4" /></button>
                    )}
                    {canManage && (
                      <button onClick={() => togglePublish(c)} className={c.status === "published" ? "text-ink/50 underline underline-offset-2" : "text-navy underline underline-offset-2"}>
                        {c.status === "published" ? "Dépublier" : "Publier"}
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="px-4 py-3 border-t border-line text-xs text-ink/45">Total : {shown.length} élève{shown.length > 1 ? "s" : ""}</div>
      </div>

      {canManage && (
        <p className="mt-4 text-xs text-ink/45 max-w-3xl">
          Un bulletin ne peut être publié que lorsque toutes les notes de l'élève pour la période sont verrouillées. La publication fige les chiffres :
          un bulletin publié n'est plus modifié par une nouvelle génération — dépubliez-le d'abord pour le corriger.
        </p>
      )}

      {preview && (
        <div className="fixed inset-0 bg-ink/50 z-50 flex items-center justify-center p-4" onClick={closePreview}>
          <div className="bg-white rounded-lg w-full max-w-4xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-3 border-b border-line">
              <p className="font-medium text-ink">Bulletin — {preview.title}</p>
              <button onClick={closePreview} className="text-sm text-ink/50 hover:text-ink">Fermer</button>
            </div>
            <iframe src={preview.url} title="Aperçu du bulletin" className="w-full h-[78vh]" />
          </div>
        </div>
      )}

      {editing && (
        <RemarksEditor
          card={editing} canDecide={canManage}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); setMessage({ tone: "ok", text: "Appréciations enregistrées." }); reload(); }}
        />
      )}
    </div>
  );
}

function RemarksEditor({ card, canDecide, onClose, onSaved }: { card: Detail; canDecide: boolean; onClose: () => void; onSaved: () => void }) {
  const [comment, setComment] = useState(card.principal_comment ?? "");
  const [decision, setDecision] = useState(card.council_decision ?? "");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const locked = card.status === "published";

  async function save() {
    setError(null);
    setSaving(true);
    try {
      const body: Record<string, string | null> = { principal_comment: comment || null };
      if (canDecide) body.council_decision = decision || null;
      await api.patch(`/report-cards/${card.id}`, body);
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible d'enregistrer.");
    } finally { setSaving(false); }
  }

  return (
    <div className="fixed inset-0 bg-ink/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-lg w-full max-w-xl p-6" onClick={(e) => e.stopPropagation()}>
        <h3 className="font-display text-lg text-ink">Appréciations — {card.student_name}</h3>
        <p className="text-xs text-ink/45 mt-0.5">{TERMS[card.term]} · {card.class_name}</p>
        {locked && <p className="mt-3 text-sm text-ochre-dark bg-ochre/10 border border-ochre/20 rounded px-3 py-2">Ce bulletin est publié : dépubliez-le pour modifier ces champs.</p>}

        <label className="block text-sm font-medium text-ink/80 mt-5 mb-1.5">Appréciation générale du professeur principal</label>
        <textarea value={comment} onChange={(e) => setComment(e.target.value)} rows={4} maxLength={1000} disabled={locked} className={`${inputCls} resize-none`} />

        {canDecide ? (
          <>
            <label className="block text-sm font-medium text-ink/80 mt-4 mb-1.5">Décision du conseil de classe</label>
            <input value={decision} onChange={(e) => setDecision(e.target.value)} list="decisions" maxLength={200} disabled={locked} className={inputCls} placeholder="Ex : Félicitations" />
            <datalist id="decisions">{DECISION_SUGGESTIONS.map((d) => <option key={d} value={d} />)}</datalist>
          </>
        ) : (
          <p className="mt-4 text-xs text-ink/45">La décision du conseil de classe est saisie par la direction ou le censeur.</p>
        )}

        {error && <p className="mt-3 text-sm text-brick">{error}</p>}
        <div className="mt-5 flex justify-end gap-3">
          <button onClick={onClose} className="text-sm text-ink/60 px-3 py-2">Annuler</button>
          <button onClick={save} disabled={saving || locked} className="rounded bg-ochre text-navy-deep text-sm font-medium px-5 py-2 hover:bg-ochre-dark transition disabled:opacity-50">
            {saving ? "Enregistrement…" : "Enregistrer"}
          </button>
        </div>
      </div>
    </div>
  );
}
