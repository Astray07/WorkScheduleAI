import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, "..");
const outDir = join(tmpdir(), `workscheduleai-import-preview-test-${process.pid}`);
const tscBin = join(projectRoot, "node_modules", "typescript", "bin", "tsc");

if (!existsSync(tscBin)) {
  throw new Error("Run npm install in frontend before import preview tests.");
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
      join(projectRoot, "src", "importPreview.ts"),
    ],
    { stdio: "inherit" },
  );

  const importPreview = await import(pathToFileURL(join(outDir, "importPreview.js")).href);

  assert.equal(importPreview.detectDelimiter("a\tb\n1\t2"), "\t");
  assert.deepEqual(importPreview.parseDelimitedText("a,b\n1,2"), [{ a: "1", b: "2" }]);
  const preview = importPreview.validateImportRows("employees", [
    { employee_code: "E001", name: "", roles: "사수", max_shifts_per_week: "5" },
  ]);
  assert.equal(preview.valid, false);
  assert.equal(preview.errors[0].field, "name");
  const shiftTypePreview = importPreview.validateImportRows("shift_types", [
    {
      shift_type: "야간 근무",
      local_start_time: "22:00",
      local_end_time: "06:00",
      timezone: "Asia/Seoul",
      crosses_midnight: "true",
      active_weekdays: "0|1|2|3|4",
      active: "true",
      role_name: "",
      required_count: "",
      unfilled_weight_override: "",
    },
  ]);
  assert.equal(shiftTypePreview.valid, false);
  assert.deepEqual(
    shiftTypePreview.errors.map((error) => error.field),
    ["role_name", "required_count"],
  );
  assert.equal(importPreview.parseImportBoolean("true"), true);
  assert.equal(importPreview.parseImportBoolean("불가"), false);
  assert.equal(importPreview.isXlsxFileName("template.xlsx"), true);
  assert.equal(importPreview.isXlsxFileName("template.csv"), false);
  assert.equal(importPreview.bytesToBase64(new Uint8Array([65, 66])), "QUI=");
} finally {
  rmSync(outDir, { recursive: true, force: true });
}
