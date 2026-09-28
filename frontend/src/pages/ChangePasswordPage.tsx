import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import PasswordForm from "../components/PasswordForm";

/** Page plein écran affichée tant qu'un mot de passe provisoire n'a pas été remplacé. */
export default function ChangePasswordPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  // Une fois le mot de passe remplacé (ou pour quelqu'un qui n'a rien à changer), on va au tableau de bord :
  // le changement volontaire se fait depuis « Sécurité », pas depuis cette page.
  if (user && !user.must_change_password) return <Navigate to="/" replace />;

  return (
    <div className="min-h-screen bg-paper flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        <div className="flex items-center gap-2.5 mb-6">
          <span className="w-9 h-9 rounded-lg bg-gradient-to-br from-sky-200 to-sky flex items-center justify-center font-display font-bold text-navy-deep text-[15px]">G</span>
          <span className="font-display font-bold text-[16px] text-ink">GESCOLA</span>
        </div>
        <div className="border border-line rounded bg-white p-7">
          <h1 className="font-display text-2xl font-medium text-ink">Choisissez votre mot de passe</h1>
          <p className="mt-2 text-sm text-ink/60">
            Votre compte a été créé avec un mot de passe provisoire{user ? ` (${user.email})` : ""}. Pour la sécurité de vos données,
            choisissez dès maintenant un mot de passe que vous êtes seul(e) à connaître.
          </p>
          <div className="mt-6">
            <PasswordForm onDone={() => navigate("/", { replace: true })} />
          </div>
        </div>
        <button onClick={logout} className="mt-4 text-sm text-ink/50 hover:text-ink">Se déconnecter</button>
      </div>
    </div>
  );
}
