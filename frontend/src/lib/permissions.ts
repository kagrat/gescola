export const CAN_READ_GRADES = ["teacher", "school_admin", "staff", "censor"];
export const CAN_WRITE_GRADES = ["teacher", "school_admin"];
export const CAN_LOCK_GRADES = ["school_admin", "censor"];
export const CAN_MANAGE_ATTENDANCE = ["teacher", "school_admin", "staff", "censor", "supervisor"];
export const CAN_MANAGE_FINANCE = ["school_admin", "accountant"];
export const CAN_READ_REGISTRY = ["school_admin", "staff", "teacher", "censor", "supervisor"];

export function roleCan(role: string | undefined, allowed: string[]): boolean {
  return !!role && allowed.includes(role);
}
