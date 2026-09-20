function initialsOf(firstName: string, lastName: string): string {
  return `${firstName[0] ?? ""}${lastName[0] ?? ""}`.toUpperCase();
}

export default function Avatar({ firstName, lastName, size = "sm" }: { firstName: string; lastName: string; size?: "sm" | "md" }) {
  const dims = size === "sm" ? "w-8 h-8 text-[11.5px]" : "w-9 h-9 text-xs";
  return (
    <span
      className={`inline-flex items-center justify-center ${dims} rounded-lg bg-navy-light text-sky-200 font-display font-bold shrink-0`}
    >
      {initialsOf(firstName, lastName)}
    </span>
  );
}
