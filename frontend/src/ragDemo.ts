export type RagDocumentPayload = {
  source_type: "organization_policy";
  document_title: string;
  checked_at: string;
  chunks: string[];
};

export function demoRagDocumentPayload(checkedAt: string): RagDocumentPayload {
  return {
    source_type: "organization_policy",
    document_title: "샘플 근무표 운영 규정",
    checked_at: checkedAt,
    chunks: [
      "근무표 작성 시 주 52시간을 초과할 가능성이 있는 배정은 발행 전에 검토하고 예외 사유를 기록합니다.",
      "야간 근무 다음 날에는 충분한 휴식 시간을 우선 배정하며, 연속 야간 근무는 운영 책임자가 확인합니다.",
      "휴가, 출장, 교육 일정은 근무표 생성 전에 반영하고 충돌이 있으면 완화안 또는 수동 검토 대상으로 표시합니다.",
    ],
  };
}
