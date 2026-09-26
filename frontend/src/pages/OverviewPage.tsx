import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../auth/AuthContext";
import SuperAdminPage from "./SuperAdminPage";

interface Student {
  id: string;
  first_name: string;
  last_name: string;
  status: string;
}

interface SchoolSnapshot {
  tenant_id: string;
  name: string;
  code: string;
  active_students: number;
  staff_count: number;
  revenue_due: number;
  revenue_collected: number;
  recovery_rate_percent: number | null;
}

interface NetworkOverviewData {
  network: { id: string; name: string; code: string };
  schools: SchoolSnapshot[];
  totals: {
    school_count: number;
    active_students: number;
    revenue_due: number;
    revenue_collected: number;
    recovery_rate_percent: number | null;
  };
}

export default function OverviewPage() {
  const { user } = useAuth();

  if (user?.role === "parent") return <ParentOverview />;
  if (user?.role === "network_admin") return <NetworkOverview />;
  if (user?.role === "super_admin") return <SuperAdminPage />;
  if (user?.role === "school_admin") return <DirectionOverview />;
  if (user?.role === "founder") return <DirectionOverview />;
  if (user?.role === "staff") return <RegistrarOverview />;
  if (user?.role === "teacher") return <TeacherOverview />;
  if (user?.role === "censor") return <CensorOverview />;
  if (user?.role === "supervisor") return <SupervisorOverview />;
  if (user?.role === "accountant") return <AccountantOverview />;
  return <DirectionOverview />;
}

function PageHeader({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="px-10 py-8 border-b border-line">
      <h1 className="font-display text-[21px] font-bold text-ink">{title}</h1>
      <p className="text-[12.5px] text-ink/60 mt-0.5">{subtitle} · Année scolaire 2026–2027</p>
    </div>
  );
}

function HeroCard({ label, value, caption }: { label: string; value: string | number; caption: string }) {
  return (
    <div className="bg-navy-deep text-paper rounded-lg p-6 relative overflow-hidden">
      <div
        className="absolute -right-10 -top-10 w-40 h-40 rounded-full"
        style={{ background: "radial-gradient(circle, rgba(62,143,217,.35), transparent 70%)" }}
      />
      <p className="relative text-[12.5px] text-sky-200 font-semibold">{label}</p>
      <p className="relative font-display font-bold text-[38px] mt-2.5 mb-1 tracking-tight">{value}</p>
      <p className="relative text-[12.5px] text-pass/90">{caption}</p>
    </div>
  );
}

function QuickLinks({ links }: { links: { to: string; label: string; description: string }[] }) {
  return (
    <section className="mt-10">
      <h2 className="font-display text-lg text-ink mb-3">Accès rapides</h2>
      <div className="grid sm:grid-cols-2 gap-4">
        {links.map((l) => (
          <Link key={l.to} to={l.to} className="block border border-line rounded bg-white p-5 hover:border-navy/40 transition group">
            <p className="text-[14.5px] font-semibold text-ink group-hover:text-navy">{l.label} →</p>
            <p className="text-[13px] text-ink/55 mt-1">{l.description}</p>
          </Link>
        ))}
      </div>
    </section>
  );
}

function useActiveStudentCount(enabled: boolean) {
  const [count, setCount] = useState<number | null>(null);
  useEffect(() => {
    if (!enabled) return;
    api
      .get<Student[]>("/students")
      .then((list) => setCount(list.filter((s) => s.status === "active").length))
      .catch(() => setCount(null));
  }, [enabled]);
  return count;
}

// ---------------- Direction ----------------

function DirectionOverview() {
  const { user } = useAuth();
  const isFounder = user?.role === "founder";
  const [students, setStudents] = useState<Student[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    api.get<Student[]>("/students").then(setStudents).catch(() => setLoadError("Impossible de charger les effectifs pour le moment."));
  }, []);

  const activeCount = students?.filter((s) => s.status === "active").length ?? 0;

  return (
    <div>
      <PageHeader
        title={`Bonjour, ${user?.email.split("@")[0]}`}
        subtitle={isFounder ? "Fondateur — vue d'ensemble de l'établissement" : "Direction — vue d'ensemble de l'établissement"}
      />
      <div className="px-10 py-8">
        <div className="grid sm:grid-cols-3 gap-4">
          <HeroCard label="Élèves actifs" value={students ? activeCount : "—"} caption="Établissement rattaché" />
          <StatCard label="Établissement" value={user?.tenant_id ? "Rattaché" : "—"} accent="navy" />
          <StatCard label="Rôle" value={isFounder ? "Fondateur" : "Direction"} accent="pass" />
        </div>

        {students && students.length > 0 && (
          <section className="mt-10 border border-line rounded bg-white">
            <div className="px-5 py-4 border-b border-line flex items-center justify-between">
              <h2 className="font-display text-lg text-ink">Derniers élèves inscrits</h2>
            </div>
            {loadError && <p className="px-5 py-6 text-sm text-brick">{loadError}</p>}
            <ul className="divide-y divide-line">
              {students.slice(0, 6).map((s) => (
                <li key={s.id} className="px-5 py-3 flex items-center justify-between text-[14.5px]">
                  <span className="text-ink">{s.first_name} {s.last_name}</span>
                  <span className="text-ink/40 text-xs uppercase tracking-wide">{s.status}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        <QuickLinks links={[
          { to: "/eleves", label: "Élèves", description: "Voir et inscrire des élèves" },
          { to: "/personnel", label: "Personnel", description: "Gérer les comptes de l'établissement" },
          { to: "/rapports", label: "Rapports", description: "Finances, notes, présences en un coup d'œil" },
          { to: "/parametres", label: "Paramètres établissement", description: "Identité légale, logo" },
        ]} />
      </div>
    </div>
  );
}

// ---------------- Secrétariat ----------------

function RegistrarOverview() {
  const { user } = useAuth();
  const [students, setStudents] = useState<Student[] | null>(null);

  useEffect(() => { api.get<Student[]>("/students").then(setStudents).catch(() => setStudents([])); }, []);
  const activeCount = students?.filter((s) => s.status === "active").length ?? 0;

  return (
    <div>
      <PageHeader title={`Bonjour, ${user?.email.split("@")[0]}`} subtitle="Secrétariat — inscriptions et référentiel" />
      <div className="px-10 py-8">
        <div className="grid sm:grid-cols-2 gap-4">
          <HeroCard label="Élèves actifs" value={students ? activeCount : "—"} caption="Établissement rattaché" />
          <StatCard label="Rôle" value="Secrétariat" accent="pass" />
        </div>

        {students && students.length > 0 && (
          <section className="mt-10 border border-line rounded bg-white">
            <div className="px-5 py-4 border-b border-line"><h2 className="font-display text-lg text-ink">Derniers élèves inscrits</h2></div>
            <ul className="divide-y divide-line">
              {students.slice(0, 6).map((s) => (
                <li key={s.id} className="px-5 py-3 flex items-center justify-between text-[14.5px]">
                  <span className="text-ink">{s.first_name} {s.last_name}</span>
                  <span className="text-ink/40 text-xs uppercase tracking-wide">{s.status}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        <QuickLinks links={[
          { to: "/eleves", label: "Élèves", description: "Inscrire un nouvel élève, consulter le registre" },
          { to: "/classes-matieres", label: "Classes & Matières", description: "Consulter le référentiel pédagogique" },
          { to: "/bibliotheque", label: "Bibliothèque", description: "Emprunts et catalogue" },
        ]} />
      </div>
    </div>
  );
}

// ---------------- Enseignant ----------------

interface Assignment { id: string; teacher_id: string; class_id: string; subject_id: string; }

function TeacherOverview() {
  const { user } = useAuth();
  const [assignments, setAssignments] = useState<Assignment[] | null>(null);

  useEffect(() => {
    api.get<Assignment[]>("/teacher-assignments").then((all) => setAssignments(all.filter((a) => a.teacher_id === user?.id))).catch(() => setAssignments([]));
  }, [user?.id]);

  return (
    <div>
      <PageHeader title={`Bonjour, ${user?.email.split("@")[0]}`} subtitle="Enseignant — vos classes et vos notes" />
      <div className="px-10 py-8">
        <div className="grid sm:grid-cols-2 gap-4">
          <HeroCard label="Classes affectées" value={assignments ? assignments.length : "—"} caption="Affectations pédagogiques" />
          <StatCard label="Rôle" value="Enseignant" accent="pass" />
        </div>

        {assignments && assignments.length === 0 && (
          <p className="mt-6 text-sm text-ink/55">
            Aucune classe ne vous est encore affectée. Contactez la Direction ou le Censeur.
          </p>
        )}

        <QuickLinks links={[
          { to: "/mes-classes", label: "Mes classes", description: "Saisir les notes de vos classes" },
          { to: "/mon-emploi-du-temps", label: "Mon emploi du temps", description: "Vos cours de la semaine" },
          { to: "/eleves", label: "Élèves", description: "Consulter le registre de l'établissement" },
        ]} />
      </div>
    </div>
  );
}

// ---------------- Censeur ----------------

function CensorOverview() {
  const { user } = useAuth();
  const activeCount = useActiveStudentCount(true);

  return (
    <div>
      <PageHeader title={`Bonjour, ${user?.email.split("@")[0]}`} subtitle="Censeur — coordination pédagogique et vie scolaire" />
      <div className="px-10 py-8">
        <div className="grid sm:grid-cols-2 gap-4">
          <HeroCard label="Élèves actifs" value={activeCount ?? "—"} caption="Établissement rattaché" />
          <StatCard label="Rôle" value="Censeur" accent="pass" />
        </div>

        <QuickLinks links={[
          { to: "/affectations", label: "Affectations", description: "Rattacher les enseignants à leurs classes" },
          { to: "/emploi-du-temps", label: "Emploi du temps", description: "Construire les emplois du temps" },
          { to: "/eleves", label: "Élèves", description: "Consulter et verrouiller les notes" },
          { to: "/classes-matieres", label: "Classes & Matières", description: "Consulter le référentiel" },
        ]} />
      </div>
    </div>
  );
}

// ---------------- Surveillant ----------------

function SupervisorOverview() {
  const { user } = useAuth();
  const activeCount = useActiveStudentCount(true);

  return (
    <div>
      <PageHeader title={`Bonjour, ${user?.email.split("@")[0]}`} subtitle="Surveillant — présences et discipline" />
      <div className="px-10 py-8">
        <div className="grid sm:grid-cols-2 gap-4">
          <HeroCard label="Élèves actifs" value={activeCount ?? "—"} caption="Établissement rattaché" />
          <StatCard label="Rôle" value="Surveillant" accent="pass" />
        </div>
        <p className="mt-6 text-sm text-ink/55 max-w-md">
          Votre accès est limité aux présences — vous n'avez pas accès aux notes ni aux finances.
        </p>

        <QuickLinks links={[
          { to: "/eleves", label: "Élèves", description: "Enregistrer les présences" },
        ]} />
      </div>
    </div>
  );
}

// ---------------- Comptable ----------------

function AccountantOverview() {
  const { user } = useAuth();
  const activeCount = useActiveStudentCount(true);

  return (
    <div>
      <PageHeader title={`Bonjour, ${user?.email.split("@")[0]}`} subtitle="Comptable — facturation et paiements" />
      <div className="px-10 py-8">
        <div className="grid sm:grid-cols-2 gap-4">
          <HeroCard label="Élèves actifs" value={activeCount ?? "—"} caption="Établissement rattaché" />
          <StatCard label="Rôle" value="Comptable" accent="pass" />
        </div>

        <QuickLinks links={[
          { to: "/eleves", label: "Élèves", description: "Retrouver un élève pour facturer ou encaisser" },
          { to: "/cantine", label: "Cantine", description: "Formules et abonnements" },
        ]} />
      </div>
    </div>
  );
}

function ParentOverview() {
  const { user } = useAuth();
  return (
    <div className="px-10 py-10 max-w-5xl">
      <p className="text-sm text-ink/50">Bonjour</p>
      <h1 className="font-display text-3xl font-medium text-ink mt-1">{user?.email.split("@")[0]}</h1>
      <p className="mt-4 text-sm text-ink/60 max-w-md">
        Retrouvez les notes, présences et frais de scolarité de vos enfants dans « Mes enfants ».
      </p>
    </div>
  );
}

function schoolInitials(name: string): string {
  const GENERIC_PREFIXES = ["école", "complexe", "groupe", "collège", "lycée", "institut"];
  const words = name
    .split(/\s+/)
    .map((w) => w.replace(/^[^\p{L}]+|[^\p{L}]+$/gu, "")) // retire ponctuation en bord de mot (tirets, em-dash…)
    .filter((w) => w.length > 0 && !GENERIC_PREFIXES.includes(w.toLowerCase()));
  const significant = words.length > 0 ? words : name.split(/\s+/);
  return significant.slice(0, 2).map((w) => w[0]).join("").toUpperCase();
}

function NetworkOverview() {
  const [data, setData] = useState<NetworkOverviewData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<NetworkOverviewData>("/network/overview")
      .then(setData)
      .catch(() => setError("Impossible de charger la vue du groupe."));
  }, []);

  return (
    <div>
      <div className="px-10 py-8 border-b border-line flex items-center justify-between">
        <div>
          <h1 className="font-display text-[21px] font-bold text-ink">
            {data ? data.network.name : "Vue du groupe"}
          </h1>
          <p className="text-[12.5px] text-ink/60 mt-0.5">
            {data ? `${data.totals.school_count} établissement${data.totals.school_count > 1 ? "s" : ""}` : ""} · Année scolaire 2026–2027
          </p>
        </div>
      </div>

      <div className="px-10 py-8">
        {error && <p className="text-sm text-brick">{error}</p>}
        {!data && !error && <p className="text-sm text-ink/50">Chargement…</p>}

        {data && (
          <>
            <div className="grid sm:grid-cols-3 gap-4">
              <div className="bg-navy-deep text-paper rounded-lg p-6 relative overflow-hidden">
                <div
                  className="absolute -right-10 -top-10 w-40 h-40 rounded-full"
                  style={{ background: "radial-gradient(circle, rgba(62,143,217,.35), transparent 70%)" }}
                />
                <p className="relative text-[12.5px] text-sky-200 font-semibold">Élèves inscrits — tout le groupe</p>
                <p className="relative font-display font-bold text-[38px] mt-2.5 mb-1 tracking-tight">
                  {data.totals.active_students.toLocaleString("fr-FR")}
                </p>
                <p className="relative text-[12.5px] text-pass/90">
                  {data.totals.school_count} établissement{data.totals.school_count > 1 ? "s" : ""}
                </p>
              </div>
              <StatCard
                label="Taux de recouvrement"
                value={data.totals.recovery_rate_percent !== null ? `${data.totals.recovery_rate_percent}%` : "—"}
                accent="pass"
              />
              <StatCard
                label="Restant dû (groupe)"
                value={`${(data.totals.revenue_due - data.totals.revenue_collected).toLocaleString("fr-FR")} F`}
                accent="brick"
              />
            </div>

            <div className="flex items-center justify-between mt-10 mb-4">
              <h2 className="font-display text-lg text-ink">Établissements</h2>
            </div>

            <div className="grid sm:grid-cols-2 gap-4">
              {data.schools.map((school) => {
                const outstanding = school.revenue_due - school.revenue_collected;
                const rate = school.recovery_rate_percent;
                const alert = rate !== null && rate < 70;
                return (
                  <div key={school.tenant_id} className="bg-white border border-line rounded-lg overflow-hidden">
                    <div className="h-16 bg-gradient-to-br from-navy to-navy-deep relative flex items-end px-4 pb-3">
                      <span
                        className={`absolute top-2.5 right-3 text-[10px] font-bold px-2 py-0.5 rounded ${
                          alert ? "bg-brick text-white" : "bg-white/15 text-white"
                        }`}
                      >
                        {alert ? "Attention" : "À jour"}
                      </span>
                      <span className="font-display font-bold text-sky-200 text-sm">
                        {schoolInitials(school.name)}
                      </span>
                    </div>
                    <div className="p-4">
                      <p className="text-[14.5px] font-bold text-ink">{school.name}</p>
                      <p className="text-[11.5px] text-ink/40 mt-0.5">{school.code}</p>
                      <div className="flex justify-between mt-3.5 pt-3.5 border-t border-line">
                        <MiniStat value={school.active_students} label="Élèves" />
                        <MiniStat value={school.staff_count} label="Personnel" />
                        <MiniStat
                          value={rate !== null ? `${rate}%` : "—"}
                          label="Recouvré"
                        />
                      </div>
                      {outstanding > 0 && (
                        <p className="text-[11px] text-brick mt-3">{outstanding.toLocaleString("fr-FR")} F restant dû</p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function MiniStat({ value, label }: { value: string | number; label: string }) {
  return (
    <div className="text-left">
      <p className="font-display font-bold text-base text-ink">{value}</p>
      <p className="text-[10.5px] text-ink/40">{label}</p>
    </div>
  );
}

function StatCard({ label, value, accent }: { label: string; value: string; accent: "ochre" | "navy" | "pass" | "brick" }) {
  const accentClass = { ochre: "text-ochre-dark", navy: "text-navy", pass: "text-pass", brick: "text-brick" }[accent];
  return (
    <div className="border border-line rounded bg-white px-5 py-4">
      <p className="text-xs text-ink/50 uppercase tracking-wide">{label}</p>
      <p className={`font-display text-2xl mt-1.5 ${accentClass}`}>{value}</p>
    </div>
  );
}
