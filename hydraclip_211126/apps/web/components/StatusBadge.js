import { Ban, CheckCircle2, Clock, Loader2, XCircle } from "lucide-react";
import { statusLabel } from "@/lib/format";

const styles = {
  queued: {
    className: "border-amber-400/30 bg-amber-400/10 text-amber-300",
    icon: Clock,
  },
  pending: {
    className: "border-amber-400/30 bg-amber-400/10 text-amber-300",
    icon: Clock,
  },
  generating: {
    className: "border-sky-400/30 bg-sky-400/10 text-sky-300",
    icon: Loader2,
    spin: true,
  },
  running: {
    className: "border-sky-400/30 bg-sky-400/10 text-sky-300",
    icon: Loader2,
    spin: true,
  },
  completed: {
    className: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300",
    icon: CheckCircle2,
  },
  published: {
    className: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300",
    icon: CheckCircle2,
  },
  failed: {
    className: "border-red-400/30 bg-red-400/10 text-red-300",
    icon: XCircle,
  },
  cancelled: {
    className: "border-slate-400/30 bg-slate-400/10 text-slate-300",
    icon: Ban,
  },
  manual_required: {
    className: "border-amber-400/30 bg-amber-400/10 text-amber-300",
    icon: Clock,
  },
};

export function StatusBadge({ status, className = "" }) {
  const item = styles[status] || styles.cancelled;
  const Icon = item.icon;
  return (
    <span className={`badge ${item.className} ${className}`}>
      <Icon className={`h-3.5 w-3.5 ${item.spin ? "animate-spin" : ""}`} />
      {statusLabel(status)}
    </span>
  );
}
