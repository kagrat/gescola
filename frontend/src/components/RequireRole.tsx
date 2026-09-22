import type { ReactNode } from "react";
import { useAuth } from "../auth/AuthContext";
import { roleCan } from "../lib/permissions";

/**
 * Bloque le rendu d'une page entière si le rôle courant n'y est pas habilité.
 *
 * Le menu de navigation (DashboardLayout) n'affiche déjà que les liens
 * pertinents pour chaque rôle, mais React Router ne vérifie rien par
 * lui-même : n'importe quel utilisateur connecté peut atteindre n'importe
 * quelle route en tapant son URL directement. Sans ce garde, une page
 * réservée (ex: la facturation plateforme, réservée au Super Admin) se
 * rendait quand même, avec des appels API qui échouaient un par un en 403 —
 * une expérience cassée plutôt qu'un refus net. Le backend reste la seule
 * source de vérité pour la sécurité réelle (RLS + require_roles) ; ce garde
 * est une question de présentation, pas de protection des données.
 */
export default function RequireRole({ roles, children }: { roles: string[]; children: ReactNode }) {
  const { user } = useAuth();

  if (!roleCan(user?.role, roles)) {
    return (
      <div className="px-10 py-10 max-w-lg">
        <h1 className="font-display text-2xl font-medium text-ink">Accès non autorisé</h1>
        <p className="mt-3 text-sm text-ink/60">
          Cette page ne fait pas partie de vos accès. Si vous pensez que c'est une erreur, contactez la direction de votre établissement.
        </p>
      </div>
    );
  }

  return <>{children}</>;
}
