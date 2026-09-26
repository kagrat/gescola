// Le Fondateur hérite systématiquement de tous les pouvoirs de la Direction
// (SCHOOL_ADMIN) — ajouté partout où celle-ci apparaît, en miroir exact de
// app/core/roles.py côté backend. Les pouvoirs qui lui sont EXCLUSIFS
// (créer/gérer la Direction, abonnement quand un Fondateur existe) sont
// gérés séparément (voir StaffPage.tsx, SchoolSubscriptionPage.tsx).
export const CAN_READ_GRADES = ["teacher", "school_admin", "staff", "censor", "founder"];
export const CAN_WRITE_GRADES = ["teacher", "school_admin", "founder"];
export const CAN_LOCK_GRADES = ["school_admin", "censor", "founder"];
export const CAN_OVERRIDE_LOCKED_GRADES = ["school_admin", "censor", "founder"];
export const CAN_MANAGE_ATTENDANCE = ["teacher", "school_admin", "staff", "censor", "supervisor", "founder"];
export const CAN_MANAGE_FINANCE = ["school_admin", "accountant", "founder"];
export const CAN_READ_REGISTRY = ["school_admin", "staff", "teacher", "censor", "supervisor", "accountant", "founder"];
export const CAN_MANAGE_REGISTRY = ["school_admin", "staff", "founder"];
export const CAN_MANAGE_USERS = ["school_admin", "founder"];
export const CAN_MANAGE_TEACHING = ["school_admin", "censor", "founder"];
export const CAN_MANAGE_GUARDIAN_LINKS = ["school_admin", "staff", "founder"];
export const CAN_VIEW_REPORTS = ["school_admin", "founder"];
export const CAN_VIEW_AUDIT_LOG = ["school_admin", "founder"];
export const CAN_MANAGE_ESTABLISHMENT_SETTINGS = ["school_admin", "founder"];
// L'abonnement est un cas particulier : la Direction n'y a accès QUE si
// aucun Fondateur n'existe pour l'établissement — règle dynamique vérifiée
// côté backend (check_billing_access), pas une simple liste de rôles. Cette
// constante ne sert qu'à afficher/masquer le lien de navigation ; le backend
// reste la seule source de vérité (403 si la Direction n'y a pas droit alors
// qu'un Fondateur existe — voir SchoolSubscriptionPage.tsx).
export const CAN_VIEW_SCHOOL_SUBSCRIPTION = ["school_admin", "founder"];
export const IS_SUPER_ADMIN = ["super_admin"];
// Seul le Fondateur peut créer un compte Direction (voir user_service.create_user).
export const CAN_CREATE_SCHOOL_ADMIN = ["founder"];

export function roleCan(role: string | undefined, allowed: string[]): boolean {
  return !!role && allowed.includes(role);
}
