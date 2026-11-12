import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { api } from "../lib/api";

export interface Quota {
  active_students: number;
  max_students: number | null;
  plan_name: string | null;
  remaining: number | null;
}

export function useQuota(refreshKey?: unknown): Quota | null {
  const [quota, setQuota] = useState<Quota | null>(null);
  useEffect(() => {
    api.get<Quota>("/students/quota").then(setQuota).catch(() => setQuota(null));
  }, [refreshKey]);
  return quota;
}

/** Bandeau discret : rien tant que la limite du plan est loin ; avertit à 90 % et à la limite. */
export default function QuotaNotice({ refreshKey, always = false }: { refreshKey?: unknown; always?: boolean }) {
  const quota = useQuota(refreshKey);
  if (!quota || quota.max_students === null || quota.remaining === null) return null;
  const full = quota.remaining === 0;
  const near = quota.active_students >= quota.max_students * 0.9;
  if (!full && !near && !always) return null;
  const tone = full ? "border-brick/40 bg-brick/5 text-brick" : near ? "border-ochre/40 bg-ochre/10 text-ochre-dark" : "border-line bg-white text-ink/70";
  return (
    <p role={full ? "alert" : "status"} className={`mx-10 mt-4 flex items-start gap-2 border rounded-lg px-4 py-2.5 text-[13px] ${tone}`}>
      {(full || near) && <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" strokeWidth={1.8} />}
      <span>
        {full
          ? `Limite du plan « ${quota.plan_name} » atteinte : ${quota.active_students} élève(s) actif(s) sur ${quota.max_students}. Plus aucune inscription n'est possible tant que le plan n'évolue pas ou que des places ne sont pas libérées.`
          : `Plan « ${quota.plan_name} » : ${quota.active_students} élève(s) actif(s) sur ${quota.max_students} — il reste ${quota.remaining} place${quota.remaining > 1 ? "s" : ""}.`}
      </span>
    </p>
  );
}
