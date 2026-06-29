import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, "..");
const outDir = join(tmpdir(), `workscheduleai-rag-demo-test-${process.pid}`);
const tscBin = join(projectRoot, "node_modules", "typescript", "bin", "tsc");

if (!existsSync(tscBin)) {
  throw new Error("Run npm install in frontend before RAG demo tests.");
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
      join(projectRoot, "src", "ragDemo.ts"),
    ],
    { stdio: "inherit" },
  );

  const { demoRagDocumentPayload } = await import(
    pathToFileURL(join(outDir, "ragDemo.js")).href
  );
  const payload = demoRagDocumentPayload("2026-06-29");

  assert.equal(payload.source_type, "organization_policy");
  assert.equal(payload.document_title, "샘플 근무표 운영 규정");
  assert.equal(payload.checked_at, "2026-06-29");
  assert.ok(payload.chunks.length >= 2);
  assert.ok(payload.chunks.some((chunk) => chunk.includes("주 52시간")));
  assert.ok(payload.chunks.some((chunk) => chunk.includes("야간")));
  assert.ok(payload.chunks.some((chunk) => chunk.includes("휴식")));
} finally {
  rmSync(outDir, { recursive: true, force: true });
}
