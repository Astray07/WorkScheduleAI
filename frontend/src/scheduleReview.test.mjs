import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, "..");
const outDir = join(tmpdir(), `workscheduleai-schedule-review-test-${process.pid}`);
const tscBin = join(projectRoot, "node_modules", "typescript", "bin", "tsc");

if (!existsSync(tscBin)) {
  throw new Error("Run npm install in frontend before schedule review tests.");
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
      join(projectRoot, "src", "scheduleReview.ts"),
      join(projectRoot, "src", "scenario.ts"),
    ],
    { stdio: "inherit" },
  );

  const review = await import(pathToFileURL(join(outDir, "scheduleReview.js")).href);
  const slots = [{ id: "slot_1", label: "평일 오전 근무", local_date: "2026-07-02" }];
  const requirements = [{ slot_id: "slot_1", role_id: "role_junior", role_name: "부사수" }];
  const issue = { id: "issue_1", slot_id: "slot_1", role_id: "role_junior" };

  assert.equal(
    review.issueContextLabel(issue, slots, requirements),
    "2026-07-02 (목) · 평일 오전 근무 · 평일 · 부사수",
  );
  assert.equal(
    review.proposalContextLabel(
      {
        affected_slot_id: null,
        impact_preview: { resolved_issue_ids: ["issue_1"] },
      },
      [issue],
      slots,
      requirements,
    ),
    "2026-07-02 (목) · 평일 오전 근무 · 평일 · 부사수",
  );
} finally {
  rmSync(outDir, { recursive: true, force: true });
}
