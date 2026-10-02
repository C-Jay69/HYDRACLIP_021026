/**
 * Figures here are deliberately drawn from what the repository actually
 * implements. The previous version advertised "10m+ Creators Trusted", which
 * is not something this codebase can support.
 */
const STATS = [
  { figure: "4", label: "Publishing destinations" },
  { figure: "3", label: "Subscription tiers" },
  { figure: "100%", label: "Open-source model stack" },
  { figure: "0", label: "Paid model API keys needed" },
] as const;

export function Stats() {
  return (
    <section aria-label="Platform at a glance" className="border-t border-border px-6 py-16">
      <dl className="mx-auto grid max-w-7xl grid-cols-2 gap-8 md:grid-cols-4">
        {STATS.map((stat) => (
          <div key={stat.label} className="text-center">
            <dt className="sr-only">{stat.label}</dt>
            <dd>
              <span className="vf-gradient-text block text-4xl font-extrabold tracking-tight sm:text-5xl">
                {stat.figure}
              </span>
              <span aria-hidden="true" className="mt-2 block text-sm text-muted-foreground">
                {stat.label}
              </span>
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
