export function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="card flex flex-col items-center justify-center gap-3 border-dashed px-6 py-16 text-center">
      <span className="rounded-2xl border border-line bg-panel2/70 p-3 text-muted">
        <Icon className="h-6 w-6" />
      </span>
      <h3 className="text-base font-semibold text-white">{title}</h3>
      <p className="max-w-md text-sm leading-relaxed text-muted">{description}</p>
      {action}
    </div>
  );
}
