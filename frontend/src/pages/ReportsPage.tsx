import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { api } from "../lib/api";
import RequireRole from "../components/RequireRole";
import { CAN_VIEW_REPORTS } from "../lib/permissions";

interface OverviewReport {
  total_active_students: number;
  finance: { amount_due_total: number; amount_paid_total: number; outstanding_total: number };
  attendance: { records_count: number; unjustified_absences: number; attendance_rate_percent: number | null };
  average_by_class: Record<string, number>;
}

const TERMS = ["T1", "T2", "T3"];

export default function ReportsPage() {
  return (
    <RequireRole roles={CAN_VIEW_REPORTS}>
      <ReportsPageContent />
    </RequireRole>
  );
}

function ReportsPageContent() {
  const [term, setTerm] = useState("T1");
  const [report, setReport] = useState<OverviewReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<OverviewReport>(`/reports/overview?term=${term}`)
      .then(setReport)
      .catch(() => setError("Impossible de charger le rapport."));
  }, [term]);

  const classData = report
    ? Object.entries(report.average_by_class).map(([name, average]) => ({ name, average }))
    : [];

  const financeData = report
    ? [
        { name: "Encaissé", value: report.finance.amount_paid_total },
        { name: "Restant dû", value: report.finance.outstanding_total },
      ]
    : [];

  return (
    <div className="px-10 py-10 max-w-5xl">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-display text-3xl font-medium text-ink">Rapports</h1>
          <p className="text-sm text-ink/55 mt-1">Vue consolidée de l'établissement.</p>
        </div>
        <select
          value={term} onChange={(e) => setTerm(e.target.value)}
          className="rounded border border-line bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy"
        >
          {TERMS.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>

      {error && <p className="mt-6 text-sm text-brick">{error}</p>}
      {!report && !error && <p className="mt-6 text-sm text-ink/50">Chargement…</p>}

      {report && (
        <>
          <div className="grid sm:grid-cols-4 gap-4 mt-8">
            <Stat label="Élèves actifs" value={String(report.total_active_students)} accent="navy" />
            <Stat label="Encaissé" value={`${report.finance.amount_paid_total.toLocaleString("fr-FR")} F`} accent="pass" />
            <Stat label="Restant dû" value={`${report.finance.outstanding_total.toLocaleString("fr-FR")} F`} accent="brick" />
            <Stat
              label="Taux de présence"
              value={report.attendance.attendance_rate_percent !== null ? `${report.attendance.attendance_rate_percent}%` : "—"}
              accent="ochre"
            />
          </div>

          <div className="grid lg:grid-cols-2 gap-6 mt-8">
            <div className="border border-line rounded bg-white p-5">
              <h2 className="font-display text-lg text-ink mb-4">Moyenne générale par classe — {term}</h2>
              {classData.length === 0 ? (
                <p className="text-sm text-ink/50">Aucune note enregistrée pour {term}.</p>
              ) : (
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={classData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E4DDCB" />
                    <XAxis dataKey="name" tick={{ fontSize: 12, fill: "#211F1C" }} />
                    <YAxis domain={[0, 20]} tick={{ fontSize: 12, fill: "#211F1C" }} />
                    <Tooltip formatter={(v) => [`${Number(v)}/20`, "Moyenne"]} />
                    <Bar dataKey="average" radius={[4, 4, 0, 0]}>
                      {classData.map((_, i) => <Cell key={i} fill="#1F3A5F" />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>

            <div className="border border-line rounded bg-white p-5">
              <h2 className="font-display text-lg text-ink mb-4">Situation financière</h2>
              {report.finance.amount_due_total === 0 ? (
                <p className="text-sm text-ink/50">Aucune facture émise.</p>
              ) : (
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={financeData} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" stroke="#E4DDCB" />
                    <XAxis type="number" tick={{ fontSize: 12, fill: "#211F1C" }} />
                    <YAxis type="category" dataKey="name" tick={{ fontSize: 12, fill: "#211F1C" }} width={90} />
                    <Tooltip formatter={(v) => `${Number(v).toLocaleString("fr-FR")} F`} />
                    <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                      <Cell fill="#2F6B4F" />
                      <Cell fill="#AE3B32" />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          <p className="text-xs text-ink/40 mt-6">
            {report.attendance.records_count} présence(s) enregistrée(s), dont {report.attendance.unjustified_absences} absence(s) non justifiée(s).
          </p>
        </>
      )}
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent: "navy" | "pass" | "brick" | "ochre" }) {
  const accentClass = { navy: "text-navy", pass: "text-pass", brick: "text-brick", ochre: "text-ochre-dark" }[accent];
  return (
    <div className="border border-line rounded bg-white px-5 py-4">
      <p className="text-xs text-ink/50 uppercase tracking-wide">{label}</p>
      <p className={`font-display text-2xl mt-1.5 ${accentClass}`}>{value}</p>
    </div>
  );
}
