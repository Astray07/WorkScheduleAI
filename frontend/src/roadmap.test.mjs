import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, "..");
const outDir = join(tmpdir(), `workscheduleai-roadmap-test-${process.pid}`);
const tscBin = join(projectRoot, "node_modules", "typescript", "bin", "tsc");

if (!existsSync(tscBin)) {
  throw new Error("Run npm install in frontend before roadmap tests.");
}

rmSync(outDir, { recursive: true, force: true });
mkdirSync(outDir, { recursive: true });

try {
  execFileSync(
    process.execPath,
    [
      tscBin,
      "--target",
      "ES2022",
      "--module",
      "NodeNext",
      "--moduleResolution",
      "NodeNext",
      "--rootDir",
      join(projectRoot, "src"),
      "--outDir",
      outDir,
      join(projectRoot, "src", "roadmap.ts"),
    ],
    { stdio: "inherit" },
  );

  const roadmap = await import(pathToFileURL(join(outDir, "roadmap.js")).href);

  assert.equal(roadmap.employeeRequestStatusLabel("pending"), "승인 대기");
  assert.equal(roadmap.employeeRequestStatusLabel("approved"), "승인됨");
  assert.equal(roadmap.employeeRequestStatusLabel("unknown"), "unknown");
  assert.equal(roadmap.acknowledgementStatusLabel("acknowledged"), "확인 완료");
  assert.equal(roadmap.complianceSeverityLabel("blocking"), "발행 차단");
  assert.equal(roadmap.ragConfidenceLabel("insufficient"), "근거 부족");
  assert.equal(roadmap.ragGroundingStatusLabel("grounded"), "근거 확인됨");
  assert.equal(roadmap.ragGroundingStatusLabel("insufficient_evidence"), "근거 부족");
  assert.equal(roadmap.ragSourceTypeLabel("organization_policy"), "사내 운영 규정");
  assert.equal(roadmap.ragSourceTypeLabel("compliance_guide"), "법규/컴플라이언스 가이드");
  assert.equal(roadmap.ragEvidenceConfidenceLabel(0.75), "관련도 높음");
  assert.equal(roadmap.ragEvidenceConfidenceLabel(0.58), "관련도 보통");
  assert.equal(roadmap.ragEvidenceConfidenceLabel(0.4), "관련도 낮음");
  assert.equal(roadmap.budgetStatusLabel("within_budget"), "예산 내");
  assert.equal(roadmap.budgetStatusLabel("over_budget"), "예산 초과");
  assert.equal(roadmap.employeeLinkTokenFromFragment("#token=abc%20123"), "abc 123");
  assert.equal(roadmap.employeeLinkTokenFromFragment("#other=value"), null);
  assert.equal(roadmap.isSignedEmployeePublicationUrl("?publicationId=publication_1&runId=run_1"), true);
  assert.equal(roadmap.isSignedEmployeePublicationUrl("?runId=run_1"), false);
  assert.equal(
    roadmap.employeePublicationContextPath({
      employeeId: "emp 1",
      organizationId: "org_1",
      publicationId: "publication/1",
    }),
    "/employee/schedule-publications/publication%2F1?organization_id=org_1&employee_id=emp+1",
  );
  assert.deepEqual(
    roadmap.ragDocumentRows(
      [
        { id: "doc_old", checked_at: "2026-06-20" },
        { id: "doc_latest", checked_at: "2026-06-26" },
        { id: "doc_same_a", checked_at: "2026-06-25" },
        { id: "doc_same_b", checked_at: "2026-06-25" },
      ],
      3,
    ).map((document) => document.id),
    ["doc_latest", "doc_same_a", "doc_same_b"],
  );
  assert.deepEqual(
    roadmap.pendingEmployeeRequestQueue(
      [
        { id: "approved_1", status: "approved" },
        { id: "pending_1", status: "pending" },
        { id: "rejected_1", status: "rejected" },
        { id: "pending_2", status: "pending" },
        { id: "pending_3", status: "pending" },
        { id: "pending_4", status: "pending" },
        { id: "pending_5", status: "pending" },
        { id: "pending_6", status: "pending" },
      ],
    ).map((request) => request.id),
    ["pending_1", "pending_2", "pending_3", "pending_4", "pending_5"],
  );
  assert.deepEqual(
    roadmap.employeeScheduleCards(
      "emp_1",
      [
        {
          id: "slot_2",
          local_date: "2026-07-02",
          label: "야간",
          starts_at: "2026-07-02T22:00:00+09:00",
          ends_at: "2026-07-03T06:00:00+09:00",
        },
        {
          id: "slot_1",
          local_date: "2026-07-01",
          label: "주간",
          starts_at: "2026-07-01T09:00:00+09:00",
          ends_at: "2026-07-01T18:00:00+09:00",
        },
      ],
      [
        {
          id: "assign_2",
          slot_id: "slot_2",
          role_id: "role_junior",
          employee_id: "emp_1",
          employee_name: "Kim",
        },
        {
          id: "assign_other",
          slot_id: "slot_1",
          role_id: "role_senior",
          employee_id: "emp_2",
          employee_name: "Lee",
        },
        {
          id: "assign_1",
          slot_id: "slot_1",
          role_id: "role_senior",
          employee_id: "emp_1",
          employee_name: "Kim",
        },
      ],
      [
        { id: "role_senior", role_id: "role_senior", role_name: "사수" },
        { id: "role_junior", role_id: "role_junior", role_name: "부사수" },
      ],
    ).map((card) => `${card.localDate}:${card.roleName}:${card.label}`),
    ["2026-07-01:사수:주간", "2026-07-02:부사수:야간"],
  );
  assert.deepEqual(
    roadmap.employeeScheduleCardsFromPublicContext([
      {
        assignment_id: "assign_2",
        local_date: "2026-07-02",
        label: "야간",
        role_name: "부사수",
        starts_at: "2026-07-02T22:00:00+09:00",
        ends_at: "2026-07-03T06:00:00+09:00",
      },
      {
        assignment_id: "assign_1",
        local_date: "2026-07-01",
        label: "주간",
        role_name: "사수",
        starts_at: "2026-07-01T09:00:00+09:00",
        ends_at: "2026-07-01T18:00:00+09:00",
      },
    ]).map((card) => `${card.assignmentId}:${card.localDate}:${card.roleName}`),
    ["assign_1:2026-07-01:사수", "assign_2:2026-07-02:부사수"],
  );
  assert.deepEqual(
    roadmap.employeeNotificationRows([
      {
        id: "notification_old",
        created_at: "2026-07-01T09:00:00+09:00",
        notification_type: "published",
        channel: "in_app",
        status: "pending_recorded",
      },
      {
        id: "notification_new",
        created_at: "2026-07-02T09:00:00+09:00",
        notification_type: "changed",
        channel: "in_app",
        status: "sent",
      },
    ]).map((notification) => notification.id),
    ["notification_new", "notification_old"],
  );
} finally {
  rmSync(outDir, { recursive: true, force: true });
}
