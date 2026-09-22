export const CAN_READ_GRADES = ["teacher", "school_admin", "staff", "censor"];
export const CAN_WRITE_GRADES = ["teacher", "school_admin"];
export const CAN_LOCK_GRADES = ["school_admin", "censor"];
export const CAN_OVERRIDE_LOCKED_GRADES = ["school_admin", "censor"];
export const CAN_MANAGE_ATTENDANCE = ["teacher", "school_admin", "staff", "censor", "supervisor"];
export const CAN_MANAGE_FINANCE = ["school_admin", "accountant"];
export const CAN_READ_REGISTRY = ["school_admin", "staff", "teacher", "censor", "supervisor", "accountant"];
export const CAN_MANAGE_REGISTRY = ["school_admin", "staff"];
export const CAN_MANAGE_USERS = ["school_admin"];
export const CAN_MANAGE_TEACHING = ["school_admin", "censor"];
export const CAN_MANAGE_GUARDIAN_LINKS = ["school_admin", "staff"];
// Ces trois listes n'ont, à ce jour, qu'un seul rôle habilité côté backend —
// exprimées comme des tableaux (pas une simple chaîne) pour rester du même
// type que les autres constantes de ce fichier et s'utiliser de façon
// identique partout (roleCan, RequireRole), sans cas particulier à retenir.
export const CAN_VIEW_REPORTS = ["school_admin"];
export const CAN_VIEW_AUDIT_LOG = ["school_admin"];
export const CAN_VIEW_SCHOOL_SUBSCRIPTION = ["school_admin"];
export const CAN_MANAGE_ESTABLISHMENT_SETTINGS = ["school_admin"];
export const IS_SUPER_ADMIN = ["super_admin"];

export function roleCan(role: string | undefined, allowed: string[]): boolean {
  return !!role && allowed.includes(role);
}
