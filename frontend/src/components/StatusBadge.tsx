import { STATUS_LABEL, Status } from "../api";

export function StatusBadge({ status }: { status: Status }) {
  return <span className={`badge ${status}`}>{STATUS_LABEL[status]}</span>;
}

export function StatusBar({ counts, total }: { counts: Partial<Record<Status, number>>; total: number }) {
  const order: Status[] = ["met", "partially_met", "not_met", "insufficient_evidence"];
  return (
    <div className="statusbar" role="img" aria-label={order.map((s) => `${STATUS_LABEL[s]}: ${counts[s] ?? 0}`).join(", ")}>
      {order.map((s) => (counts[s] ? <span key={s} className={s} style={{ width: `${((counts[s] ?? 0) / total) * 100}%` }} /> : null))}
    </div>
  );
}
