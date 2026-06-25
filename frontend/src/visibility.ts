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

export type LongTermFairnessSource = "publications" | "runs";

export type LongTermFairnessSortableRow = {
  employee_code: string;
  employee_name: string;
  assignment_count: number;
  night_count: number;
  weekend_count: number;
  delta_from_average: number;
};

export function longTermFairnessSourceLabel(source: LongTermFairnessSource) {
  const labels: Record<LongTermFairnessSource, string> = {
    publications: "확정본",
    runs: "실행 기록",
  };
  return labels[source];
}

export function sortedLongTermFairnessRows<T extends LongTermFairnessSortableRow>(
  rows: T[],
): T[] {
  return [...rows].sort((left, right) => {
    const deltaRank = Math.abs(right.delta_from_average) - Math.abs(left.delta_from_average);
    if (deltaRank !== 0) return deltaRank;
    const assignmentRank = right.assignment_count - left.assignment_count;
    if (assignmentRank !== 0) return assignmentRank;
    const nightRank = right.night_count - left.night_count;
    if (nightRank !== 0) return nightRank;
    const weekendRank = right.weekend_count - left.weekend_count;
    if (weekendRank !== 0) return weekendRank;
    return left.employee_code.localeCompare(right.employee_code);
  });
}
