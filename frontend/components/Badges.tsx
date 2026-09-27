import { DECISION_LABEL, STATUS_LABEL } from "@/lib/format";
import type { Decision, Status } from "@/lib/types";

export function StatusBadge({ status }: { status: Status }) {
  const pending = ["agendada", "entrando", "gravando", "processando"].includes(status);
  return (
    <span className={`badge status-${status}`}>
      {pending && <span className="dot" aria-hidden />}
      {STATUS_LABEL[status] || status}
    </span>
  );
}

export function DecisionBadge({ decision }: { decision: Decision | null | undefined }) {
  if (!decision) return <span className="muted">—</span>;
  return <span className={`badge decision-${decision}`}>{DECISION_LABEL[decision]}</span>;
}
