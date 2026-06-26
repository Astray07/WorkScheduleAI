export function employeeRequestStatusLabel(status: string) {
  const labels: Record<string, string> = {
    pending: "승인 대기",
    approved: "승인됨",
    rejected: "거절됨",
    canceled: "취소됨",
  };
  return labels[status] ?? status;
}

export function acknowledgementStatusLabel(status: string) {
  const labels: Record<string, string> = {
    pending: "확인 대기",
    acknowledged: "확인 완료",
  };
  return labels[status] ?? status;
}

export function complianceSeverityLabel(severity: string) {
  const labels: Record<string, string> = {
    blocking: "발행 차단",
    warning: "검토 필요",
    info: "참고",
  };
  return labels[severity] ?? severity;
}

export function ragConfidenceLabel(confidence: string) {
  const labels: Record<string, string> = {
    high: "높음",
    medium: "보통",
    low: "낮음",
    insufficient: "근거 부족",
  };
  return labels[confidence] ?? confidence;
}

export function budgetStatusLabel(status: string) {
  const labels: Record<string, string> = {
    within_budget: "예산 내",
    over_budget: "예산 초과",
    no_budget: "예산 없음",
  };
  return labels[status] ?? status;
}

export type RagDocumentQueueItem = {
  id: string;
  checked_at: string;
};

export function ragDocumentRows<T extends RagDocumentQueueItem>(
  documents: T[],
  limit = 5,
): T[] {
  return [...documents]
    .sort((left, right) => {
      const checkedRank = right.checked_at.localeCompare(left.checked_at);
      if (checkedRank !== 0) return checkedRank;
      return left.id.localeCompare(right.id);
    })
    .slice(0, limit);
}

export type EmployeeRequestQueueItem = {
  id: string;
  status: string;
};

export function pendingEmployeeRequestQueue<T extends EmployeeRequestQueueItem>(
  requests: T[],
  limit = 5,
): T[] {
  return requests.filter((request) => request.status === "pending").slice(0, limit);
}

export type EmployeeScheduleSlot = {
  id: string;
  local_date: string;
  label: string;
  starts_at: string;
  ends_at: string;
};

export type EmployeeScheduleAssignment = {
  id: string;
  slot_id: string;
  role_id: string;
  employee_id: string;
  employee_name: string;
};

export type EmployeeScheduleRequirement = {
  role_id: string;
  role_name: string;
};

export type EmployeeScheduleCard = {
  assignmentId: string;
  localDate: string;
  label: string;
  roleName: string;
  startsAt: string;
  endsAt: string;
};

export function employeeScheduleCards(
  employeeId: string,
  slots: EmployeeScheduleSlot[],
  assignments: EmployeeScheduleAssignment[],
  requirements: EmployeeScheduleRequirement[],
): EmployeeScheduleCard[] {
  const slotsById = new Map(slots.map((slot) => [slot.id, slot]));
  const roleNamesById = new Map(
    requirements.map((requirement) => [requirement.role_id, requirement.role_name]),
  );
  return assignments
    .filter((assignment) => assignment.employee_id === employeeId)
    .map((assignment) => {
      const slot = slotsById.get(assignment.slot_id);
      if (!slot) return null;
      return {
        assignmentId: assignment.id,
        localDate: slot.local_date,
        label: slot.label,
        roleName: roleNamesById.get(assignment.role_id) ?? assignment.role_id,
        startsAt: slot.starts_at,
        endsAt: slot.ends_at,
      };
    })
    .filter((card): card is EmployeeScheduleCard => card !== null)
    .sort((left, right) => {
      const dateRank = left.localDate.localeCompare(right.localDate);
      if (dateRank !== 0) return dateRank;
      return left.startsAt.localeCompare(right.startsAt);
    });
}
