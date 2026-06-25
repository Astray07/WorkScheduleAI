import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, "..");
const outDir = join(tmpdir(), `workscheduleai-shift-profile-test-${process.pid}`);
const tscBin = join(projectRoot, "node_modules", "typescript", "bin", "tsc");

if (!existsSync(tscBin)) {
  throw new Error("Run npm install in frontend before shift profile tests.");
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
      join(projectRoot, "src", "shiftProfile.ts"),
    ],
    { stdio: "inherit" },
  );

  const shiftProfile = await import(pathToFileURL(join(outDir, "shiftProfile.js")).href);
  const coverage = shiftProfile.DEFAULT_SHIFT_COVERAGE;

  assert.deepEqual(coverage, {
    weekday: ["morning", "afternoon"],
    weekend: ["day"],
  });
  assert.equal(shiftProfile.shiftCoverageSummary(coverage), "평일 오전/오후, 주말 주간");

  const requests = shiftProfile.buildShiftTypeRequests(coverage, {
    seniorRoleId: "role_senior",
    juniorRoleId: "role_junior",
  });
  assert.deepEqual(
    requests.map((request) => ({
      name: request.name,
      start: request.local_start_time,
      end: request.local_end_time,
      activeWeekdays: request.active_weekdays,
      crossesMidnight: request.crosses_midnight,
      requirementCount: request.requirements.length,
    })),
    [
      {
        name: "평일 오전 근무",
        start: "06:00",
        end: "14:00",
        activeWeekdays: [0, 1, 2, 3, 4],
        crossesMidnight: false,
        requirementCount: 2,
      },
      {
        name: "평일 오후 근무",
        start: "14:00",
        end: "22:00",
        activeWeekdays: [0, 1, 2, 3, 4],
        crossesMidnight: false,
        requirementCount: 2,
      },
      {
        name: "주말 주간 근무",
        start: "09:00",
        end: "18:00",
        activeWeekdays: [5, 6],
        crossesMidnight: false,
        requirementCount: 2,
      },
    ],
  );

  const nightCoverage = shiftProfile.setShiftCoverageEnabled(
    { weekday: [], weekend: [] },
    "weekend",
    "night",
    true,
  );
  assert.deepEqual(nightCoverage, { weekday: [], weekend: ["night"] });
  assert.equal(shiftProfile.shiftCoverageSummary(nightCoverage), "주말 야간");
  assert.equal(
    shiftProfile.buildShiftTypeRequests(nightCoverage, {
      seniorRoleId: "role_senior",
      juniorRoleId: "role_junior",
    })[0].crosses_midnight,
    true,
  );

  assert.deepEqual(
    shiftProfile.normalizeShiftCoverage({ weekday: [], weekend: [] }),
    shiftProfile.DEFAULT_SHIFT_COVERAGE,
  );

  const syncPlan = shiftProfile.planScenarioShiftTypeSync(
    { weekday: ["night"], weekend: [] },
    {
      seniorRoleId: "role_senior",
      juniorRoleId: "role_junior",
    },
    [
      {
        id: "shift_weekday_night",
        name: "평일 야간 근무",
        local_start_time: "22:00",
        local_end_time: "06:00",
        timezone: "Asia/Seoul",
        crosses_midnight: true,
        active_weekdays: [0, 1, 2, 3, 4],
        active: false,
        requirements: [
          {
            role_id: "role_senior",
            required_count: 1,
            unfilled_weight_override: null,
          },
          {
            role_id: "role_junior",
            required_count: 1,
            unfilled_weight_override: null,
          },
        ],
      },
      {
        id: "shift_weekend_day",
        name: "주말 주간 근무",
        local_start_time: "09:00",
        local_end_time: "18:00",
        timezone: "Asia/Seoul",
        crosses_midnight: false,
        active_weekdays: [5, 6],
        active: true,
        requirements: [
          {
            role_id: "role_senior",
            required_count: 1,
            unfilled_weight_override: null,
          },
          {
            role_id: "role_junior",
            required_count: 1,
            unfilled_weight_override: null,
          },
        ],
      },
    ],
  );
  assert.deepEqual(syncPlan.creates, []);
  assert.deepEqual(
    syncPlan.updates.map((update) => ({
      id: update.id,
      name: update.request.name,
      active: update.request.active,
      activeWeekdays: update.request.active_weekdays,
      start: update.request.local_start_time,
      end: update.request.local_end_time,
    })),
    [
      {
        id: "shift_weekday_night",
        name: "평일 야간 근무",
        active: true,
        activeWeekdays: [0, 1, 2, 3, 4],
        start: "22:00",
        end: "06:00",
      },
      {
        id: "shift_weekend_day",
        name: "주말 주간 근무",
        active: false,
        activeWeekdays: [5, 6],
        start: "09:00",
        end: "18:00",
      },
    ],
  );
} finally {
  rmSync(outDir, { recursive: true, force: true });
}
