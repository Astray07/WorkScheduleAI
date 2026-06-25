export type ScheduleRunHistoryItem = {
  id: string;
  organization_id: string;
  period_start: string;
  period_end: string;
  status: string;
  solver_status: string | null;
  solution_quality: string;
  current_attempt_no: number;
  recalculation_count: number;
  created_at: string;
  updated_at: string;
  finished_at: string | null;
  assignment_count: number;
  issue_count: number;
  manual_locked_count: number;
};

export type ScheduleRunHistory = {
  organization_id: string;
  runs: ScheduleRunHistoryItem[];
};

export type RunComparisonSummary = {
  assignment_added_count: number;
  assignment_removed_count: number;
  assignment_unchanged_count: number;
  manual_lock_maintained_count: number;
  issue_added_count: number;
  issue_resolved_count: number;
  fairness_changed_employee_count: number;
};

export type AssignmentComparisonRow = {
  change_type: "added" | "removed" | "unchanged";
  slot_id: string;
  role_id: string;
  role_name: string;
  employee_id: string;
  employee_name: string;
  before_source: string | null;
  after_source: string | null;
  before_locked_by_user: boolean | null;
  after_locked_by_user: boolean | null;
  manual_lock_maintained: boolean;
};

export type IssueComparisonRow = {
  change_type: "added" | "resolved" | "changed";
  slot_id: string | null;
  role_id: string | null;
  role_name: string | null;
  type: string;
  reason_code: string;
  before_missing_count: number;
  after_missing_count: number;
  missing_delta: number;
  before_severity: string | null;
  after_severity: string | null;
  before_display_message: string | null;
  after_display_message: string | null;
};

export type FairnessComparisonRow = {
  employee_id: string;
  employee_code: string;
  employee_name: string;
  before_assignment_count: number;
  after_assignment_count: number;
  assignment_delta: number;
};

export type ScheduleRunComparison = {
  organization_id: string;
  base_run_id: string;
  candidate_run_id: string;
  base_run: ScheduleRunHistoryItem;
  candidate_run: ScheduleRunHistoryItem;
  summary: RunComparisonSummary;
  assignment_changes: AssignmentComparisonRow[];
  issue_changes: IssueComparisonRow[];
  fairness_changes: FairnessComparisonRow[];
};

export function comparisonSummaryMetrics(comparison: Pick<ScheduleRunComparison, "summary">) {
  return [
    { label: "추가 배정", value: `${comparison.summary.assignment_added_count}건` },
    { label: "삭제 배정", value: `${comparison.summary.assignment_removed_count}건` },
    { label: "수동 잠금 유지", value: `${comparison.summary.manual_lock_maintained_count}건` },
    {
      label: "이슈 변화",
      value: `+${comparison.summary.issue_added_count} / -${comparison.summary.issue_resolved_count}`,
    },
  ];
}

export function changedFairnessRows(
  comparison: Pick<ScheduleRunComparison, "fairness_changes">,
) {
  return comparison.fairness_changes
    .filter((row) => row.assignment_delta !== 0)
    .sort((left, right) => {
      const deltaRank = Math.abs(right.assignment_delta) - Math.abs(left.assignment_delta);
      if (deltaRank !== 0) return deltaRank;
      return left.employee_name.localeCompare(right.employee_name);
    });
}

export function changeTypeLabel(changeType: AssignmentComparisonRow["change_type"]) {
  const labels: Record<AssignmentComparisonRow["change_type"], string> = {
    added: "추가",
    removed: "삭제",
    unchanged: "유지",
  };
  return labels[changeType];
}

export function issueChangeTypeLabel(changeType: IssueComparisonRow["change_type"]) {
  const labels: Record<IssueComparisonRow["change_type"], string> = {
    added: "추가",
    resolved: "해결",
    changed: "변경",
  };
  return labels[changeType];
}

export function deltaLabel(delta: number) {
  if (delta > 0) return `+${delta}`;
  return `${delta}`;
}
