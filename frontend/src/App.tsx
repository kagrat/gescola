import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import LoginPage from "./pages/LoginPage";
import SignupPage from "./pages/SignupPage";
import DashboardLayout from "./pages/DashboardLayout";
import OverviewPage from "./pages/OverviewPage";
import StudentsPage from "./pages/StudentsPage";
import StudentDetailPage from "./pages/StudentDetailPage";
import StaffPage from "./pages/StaffPage";
import MyChildrenPage from "./pages/MyChildrenPage";
import ReportsPage from "./pages/ReportsPage";
import SecurityPage from "./pages/SecurityPage";
import NotificationsPage from "./pages/NotificationsPage";
import AuditLogPage from "./pages/AuditLogPage";
import CanteenPage from "./pages/CanteenPage";
import LibraryPage from "./pages/LibraryPage";
import TenantBillingPage from "./pages/TenantBillingPage";
import EstablishmentSettingsPage from "./pages/EstablishmentSettingsPage";
import SchoolSubscriptionPage from "./pages/SchoolSubscriptionPage";
import ProfilePage from "./pages/ProfilePage";
import CourseworkPage from "./pages/CourseworkPage";
import DisciplinePage from "./pages/DisciplinePage";
import BulletinsPage from "./pages/BulletinsPage";
import AcademicPage from "./pages/AcademicPage";
import TeachingPage from "./pages/TeachingPage";
import MyClassesPage from "./pages/MyClassesPage";
import TimetablePage from "./pages/TimetablePage";
import MyTimetablePage from "./pages/MyTimetablePage";
import ChangePasswordPage from "./pages/ChangePasswordPage";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-screen flex items-center justify-center text-ink/40">Chargement…</div>;
  const location = useLocation();
  if (!user) return <Navigate to="/connexion" replace />;
  // Mot de passe provisoire : rien d'autre n'est accessible tant qu'il n'a pas été remplacé
  // (le serveur applique la même règle — cette redirection n'est qu'un confort).
  if (user.must_change_password && location.pathname !== "/mot-de-passe") return <Navigate to="/mot-de-passe" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/connexion" element={<LoginPage />} />
          <Route path="/inscription" element={<SignupPage />} />
          <Route path="/mot-de-passe" element={<RequireAuth><ChangePasswordPage /></RequireAuth>} />
          <Route
            path="/"
            element={
              <RequireAuth>
                <DashboardLayout />
              </RequireAuth>
            }
          >
            <Route index element={<OverviewPage />} />
            <Route path="eleves" element={<StudentsPage />} />
            <Route path="eleves/:studentId" element={<StudentDetailPage />} />
            <Route path="personnel" element={<StaffPage />} />
            <Route path="mes-enfants" element={<MyChildrenPage />} />
            <Route path="rapports" element={<ReportsPage />} />
            <Route path="securite" element={<SecurityPage />} />
            <Route path="notifications" element={<NotificationsPage />} />
            <Route path="audit" element={<AuditLogPage />} />
            <Route path="cantine" element={<CanteenPage />} />
            <Route path="bibliotheque" element={<LibraryPage />} />
            <Route path="etablissements/:tenantId" element={<TenantBillingPage />} />
            <Route path="parametres" element={<EstablishmentSettingsPage />} />
            <Route path="abonnement" element={<SchoolSubscriptionPage />} />
            <Route path="profil" element={<ProfilePage />} />
            <Route path="cahier-de-texte" element={<CourseworkPage />} />
            <Route path="discipline" element={<DisciplinePage />} />
            <Route path="bulletins" element={<BulletinsPage />} />
            <Route path="classes-matieres" element={<AcademicPage />} />
            <Route path="affectations" element={<TeachingPage />} />
            <Route path="mes-classes" element={<MyClassesPage />} />
            <Route path="emploi-du-temps" element={<TimetablePage />} />
            <Route path="mon-emploi-du-temps" element={<MyTimetablePage />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
