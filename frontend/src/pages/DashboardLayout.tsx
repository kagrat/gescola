import { NavLink, Outlet } from "react-router-dom";
import {
  LayoutGrid, Users, GraduationCap, Wallet, ShieldCheck, Bell, ScrollText, UtensilsCrossed, Library as LibraryIcon,
  Settings, UserCircle, BookOpen, CalendarDays, CalendarClock,
} from "lucide-react";
import { useAuth } from "../auth/AuthContext";

const ROLE_LABELS: Record<string, string> = {
  super_admin: "Super administrateur",
  network_admin: "Promoteur de réseau",
  school_admin: "Direction",
  censor: "Censeur",
  supervisor: "Surveillant",
  accountant: "Comptable",
  staff: "Secrétariat",
  teacher: "Enseignant",
  parent: "Parent",
};

// Navigation visible par rôle — chaque intervenant ne voit que ce qui relève
// de sa fonction (cohérent avec la matrice de permissions du backend,
// app/core/roles.py).
function navItemsFor(role: string) {
  const items: { to: string; label: string; end?: boolean; icon: typeof LayoutGrid }[] = [
    { to: "/", label: role === "network_admin" ? "Vue du groupe" : "Vue d'ensemble", end: true, icon: LayoutGrid },
  ];

  if (role === "network_admin") {
    items.push({ to: "/profil", label: "Profil", icon: UserCircle });
    items.push({ to: "/securite", label: "Sécurité", icon: ShieldCheck });
    return items;
  }

  if (role === "parent") {
    items.push({ to: "/mes-enfants", label: "Mes enfants", icon: Users });
    items.push({ to: "/notifications", label: "Notifications", icon: Bell });
    items.push({ to: "/profil", label: "Profil", icon: UserCircle });
    return items;
  }

  if (["school_admin", "staff", "teacher", "censor", "supervisor", "accountant"].includes(role)) {
    items.push({ to: "/eleves", label: "Élèves", icon: Users });
  }
  if (["school_admin", "staff", "teacher", "censor", "supervisor"].includes(role)) {
    items.push({ to: "/classes-matieres", label: "Classes & Matières", icon: BookOpen });
  }
  if (["school_admin", "censor"].includes(role)) {
    items.push({ to: "/affectations", label: "Affectations", icon: CalendarClock });
    items.push({ to: "/emploi-du-temps", label: "Emploi du temps", icon: CalendarDays });
  }
  if (role === "teacher") {
    items.push({ to: "/mes-classes", label: "Mes classes", icon: BookOpen });
    items.push({ to: "/mon-emploi-du-temps", label: "Mon emploi du temps", icon: CalendarDays });
  }
  if (["school_admin", "staff"].includes(role)) {
    items.push({ to: "/bibliotheque", label: "Bibliothèque", icon: LibraryIcon });
  }
  if (["school_admin", "accountant"].includes(role)) {
    items.push({ to: "/cantine", label: "Cantine", icon: UtensilsCrossed });
  }
  if (role === "school_admin") {
    items.push({ to: "/rapports", label: "Rapports", icon: GraduationCap });
    items.push({ to: "/personnel", label: "Personnel", icon: Wallet });
    items.push({ to: "/parametres", label: "Paramètres établissement", icon: Settings });
    items.push({ to: "/abonnement", label: "Mon abonnement", icon: Wallet });
    items.push({ to: "/audit", label: "Journal d'audit", icon: ScrollText });
  }
  items.push({ to: "/profil", label: "Profil", icon: UserCircle });
  items.push({ to: "/securite", label: "Sécurité", icon: ShieldCheck });
  return items;
}

function initialsOf(email: string): string {
  const local = email.split("@")[0];
  const parts = local.split(/[._-]/).filter(Boolean);
  const chars = parts.length >= 2 ? parts[0][0] + parts[1][0] : local.slice(0, 2);
  return chars.toUpperCase();
}

export default function DashboardLayout() {
  const { user, logout } = useAuth();
  const navItems = navItemsFor(user?.role ?? "");

  return (
    <div className="min-h-screen flex bg-paper">
      <aside className="w-64 shrink-0 bg-navy-deep text-paper flex flex-col p-4">
        <div className="flex items-center gap-2.5 px-1.5 pb-4">
          <span className="w-9 h-9 rounded-lg bg-gradient-to-br from-sky-200 to-sky flex items-center justify-center font-display font-bold text-navy-deep text-[15px] shrink-0">
            G
          </span>
          <div>
            <div className="font-display font-bold text-[15px] leading-tight">GESCOLA</div>
            <div className="text-[10px] text-sky-200 mt-0.5 tracking-wide">GESTION SCOLAIRE</div>
          </div>
        </div>

        <nav className="flex-1 flex flex-col gap-0.5 mt-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-[10px] text-[13.5px] font-medium transition ${
                  isActive ? "bg-navy text-paper" : "text-[#AEB6CB] hover:bg-navy hover:text-paper"
                }`
              }
            >
              <item.icon className="w-[17px] h-[17px] shrink-0 opacity-90" strokeWidth={1.8} />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-white/10 pt-3.5 mt-2.5 flex items-center gap-2.5">
          <span className="w-[33px] h-[33px] rounded-lg bg-navy-light flex items-center justify-center font-display font-bold text-sky-200 text-xs shrink-0">
            {user ? initialsOf(user.email) : ""}
          </span>
          <div className="min-w-0">
            <p className="text-[12.5px] font-semibold text-paper truncate">{user?.email}</p>
            <p className="text-[11px] text-[#8C93A3]">{user ? ROLE_LABELS[user.role] : ""}</p>
          </div>
        </div>
        <button
          onClick={logout}
          className="mt-2.5 text-[12px] text-[#8C93A3] hover:text-paper transition text-left"
        >
          Se déconnecter
        </button>
      </aside>

      <main className="flex-1 min-w-0 bg-paper min-h-screen">
        <Outlet />
      </main>
    </div>
  );
}
