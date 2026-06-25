const auditActionLabels: Record<string, string> = {
  manual_assignment_saved: "수동 배정 저장",
  publication_created: "근무표 확정",
};

export function auditActionLabel(action: string) {
  return auditActionLabels[action] ?? action;
}

export function fairnessSpreadLabel(summary: { spread: number }) {
  return summary.spread === 0 ? "균등" : `편차 ${summary.spread}회`;
}

export function fairnessDeltaLabel(delta: number) {
  const rounded = delta.toFixed(2);
  return delta > 0 ? `+${rounded}` : rounded;
}
