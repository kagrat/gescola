import { useEffect, useState } from "react";
import { api } from "../lib/api";

interface Child {
  id: string;
  first_name: string;
  last_name: string;
}

interface Average {
  general_average: number;
}

interface Attendance {
  status: string;
  justified: boolean;
}

interface Invoice {
  balance: number;
  status: string;
}

const CURRENT_TERM = "T1";

export default function MyChildrenPage() {
  const [children, setChildren] = useState<Child[] | null>(null);

  useEffect(() => {
    api.get<Child[]>("/me/children").then(setChildren);
  }, []);

  return (
    <div className="px-10 py-10 max-w-4xl">
      <h1 className="font-display text-3xl font-medium text-ink">Mes enfants</h1>
      <p className="text-sm text-ink/55 mt-1">Notes, présences et frais de scolarité.</p>

      {children === null && <p className="mt-8 text-sm text-ink/50">Chargement…</p>}
      {children && children.length === 0 && (
        <p className="mt-8 text-sm text-ink/50">
          Aucun enfant n'est encore rattaché à votre compte. Contactez le secrétariat de l'établissement.
        </p>
      )}

      <div className="mt-8 space-y-4">
        {children?.map((child) => (
          <ChildCard key={child.id} child={child} />
        ))}
      </div>
    </div>
  );
}

function ChildCard({ child }: { child: Child }) {
  const [average, setAverage] = useState<Average | null>(null);
  const [attendance, setAttendance] = useState<Attendance[] | null>(null);
  const [invoices, setInvoices] = useState<Invoice[] | null>(null);

  useEffect(() => {
    api.get<Average>(`/children/${child.id}/average?term=${CURRENT_TERM}`).then(setAverage).catch(() => setAverage(null));
    api.get<Attendance[]>(`/children/${child.id}/attendance`).then(setAttendance).catch(() => setAttendance([]));
    api.get<Invoice[]>(`/children/${child.id}/invoices`).then(setInvoices).catch(() => setInvoices([]));
  }, [child.id]);

  const absences = attendance?.filter((a) => a.status === "absent" && !a.justified).length ?? 0;
  const outstanding = invoices?.reduce((sum, inv) => sum + (inv.status !== "paid" ? inv.balance : 0), 0) ?? 0;

  return (
    <div className="border border-line rounded bg-white p-5">
      <h2 className="font-display text-lg text-ink">
        {child.first_name} {child.last_name}
      </h2>
      <div className="grid sm:grid-cols-3 gap-4 mt-4">
        <Metric label={`Moyenne ${CURRENT_TERM}`} value={average ? average.general_average.toFixed(2) : "—"} accent="navy" />
        <Metric label="Absences non justifiées" value={attendance ? String(absences) : "—"} accent={absences > 0 ? "brick" : "pass"} />
        <Metric label="Solde dû" value={invoices ? `${outstanding.toLocaleString("fr-FR")} F` : "—"} accent={outstanding > 0 ? "ochre" : "pass"} />
      </div>
    </div>
  );
}

function Metric({ label, value, accent }: { label: string; value: string; accent: "navy" | "pass" | "ochre" | "brick" }) {
  const accentClass = { navy: "text-navy", pass: "text-pass", ochre: "text-ochre-dark", brick: "text-brick" }[accent];
  return (
    <div className="bg-paper border border-line rounded px-4 py-3">
      <p className="text-xs text-ink/50 uppercase tracking-wide">{label}</p>
      <p className={`font-display text-xl mt-1 ${accentClass}`}>{value}</p>
    </div>
  );
}
