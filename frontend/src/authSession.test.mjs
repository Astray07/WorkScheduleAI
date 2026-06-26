import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, "..");
const outDir = join(tmpdir(), `workscheduleai-auth-session-test-${process.pid}`);
const tscBin = join(projectRoot, "node_modules", "typescript", "bin", "tsc");

if (!existsSync(tscBin)) {
  throw new Error("Run npm install in frontend before auth session tests.");
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
      join(projectRoot, "src", "authSession.ts"),
    ],
    { stdio: "inherit" },
  );

  const authSession = await import(pathToFileURL(join(outDir, "authSession.js")).href);

  assert.deepEqual(authSession.authHeaders(null), {});
  assert.deepEqual(authSession.authHeaders({ access_token: "abc" }), {
    Authorization: "Bearer abc",
  });
  assert.equal(
    authSession.sessionLabel({
      organization_id: "org_1",
      role: "scheduler",
      user_id: "user_1",
    }),
    "org_1 · scheduler",
  );
  assert.equal(
    authSession.sessionVerificationPath({
      access_token: "abc",
      organization_id: "org 1",
      role: "scheduler",
      user_id: "user_1",
    }),
    "/auth/session?organization_id=org%201",
  );
} finally {
  rmSync(outDir, { recursive: true, force: true });
}
