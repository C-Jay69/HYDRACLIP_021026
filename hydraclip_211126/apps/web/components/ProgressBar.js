export function ProgressBar({ value = 0, active = false, className = "" }) {
  const percent = Math.min(100, Math.max(0, Number(value) || 0));
  return (
    <div
      className={`h-2 w-full overflow-hidden rounded-full bg-line/70 ${className}`}
      role="progressbar"
      aria-valuenow={Math.round(percent)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className={`h-full rounded-full bg-gradient-to-r from-accent2 to-accent transition-[width] duration-700 ${
          active ? "animate-pulse" : ""
        }`}
        style={{ width: `${percent}%` }}
      />
    </div>
  );
}
