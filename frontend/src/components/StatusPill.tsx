type PillTone = "ok" | "warn" | "bad" | "neutral";

const TONE_STYLES: Record<PillTone, string> = {
  ok: "bg-pass/10 text-[#1F7A52]",
  warn: "bg-sky/10 text-[#2568A3]",
  bad: "bg-brick/10 text-[#B03A32]",
  neutral: "bg-ink/5 text-ink/50",
};

const TONE_DOT: Record<PillTone, string> = {
  ok: "bg-pass",
  warn: "bg-sky",
  bad: "bg-brick",
  neutral: "bg-ink/30",
};

export default function StatusPill({ label, tone }: { label: string; tone: PillTone }) {
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${TONE_STYLES[tone]}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${TONE_DOT[tone]}`} />
      {label}
    </span>
  );
}
