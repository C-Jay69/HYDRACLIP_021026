const tones = {
  accent: "border-accent/20 bg-accent/10 text-accent",
  purple: "border-accent2/20 bg-accent2/10 text-accent2",
  emerald: "border-emerald-400/20 bg-emerald-400/10 text-emerald-300",
  red: "border-red-400/20 bg-red-400/10 text-red-300",
  slate: "border-slate-400/20 bg-slate-400/10 text-slate-300",
};

export function StatCard({ icon: Icon, label, value, hint, tone = "accent" }) {
  return (
    <div className="card p-5">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted">
          {label}
        </span>
        <span className={`rounded-lg border p-1.5 ${tones[tone] || tones.accent}`}>
          <Icon className="h-4 w-4" />
        </span>
      </div>
      <p className="mt-3 text-3xl font-bold tracking-tight text-white">{value}</p>
      {hint ? <p className="mt-1 text-xs text-muted">{hint}</p> : null}
    </div>
  );
}
