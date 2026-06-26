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
  assert.equal(roadmap.budgetStatusLabel("within_budget"), "예산 내");
  assert.equal(roadmap.budgetStatusLabel("over_budget"), "예산 초과");
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
} finally {
  rmSync(outDir, { recursive: true, force: true });
}
