export type ReferenceTabId = "scenario" | "reference" | "policy" | "import";

export const REFERENCE_TABS: { id: ReferenceTabId; label: string }[] = [
  { id: "scenario", label: "생성" },
  { id: "reference", label: "기준정보" },
  { id: "policy", label: "정책" },
  { id: "import", label: "가져오기" },
];

export type ReferenceCollections = {
  employees: { id: string }[];
  unavailabilities: { id: string }[];
  pairConstraints: { id: string }[];
  shiftTypes: { id: string }[];
};

export function referenceSummary(collections: ReferenceCollections): string {
  return [
    `직원 ${collections.employees.length}명`,
    `일정 ${collections.unavailabilities.length}건`,
    `조합 ${collections.pairConstraints.length}건`,
    `근무유형 ${collections.shiftTypes.length}개`,
  ].join(" · ");
}
