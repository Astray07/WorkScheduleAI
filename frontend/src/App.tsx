import {
  AlertTriangle,
  Building2,
  CheckCircle2,
  ClipboardList,
  Clock3,
  Download,
  FileSpreadsheet,
  Plus,
  Play,
  RefreshCw,
  ShieldCheck,
  Trash2,
  Users,
} from "lucide-react";
import { useMemo, useState } from "react";
import {
  DEFAULT_SCENARIO_CONFIG,
  MAX_EMPLOYEE_COUNT,
  MIN_EMPLOYEE_COUNT,
  PERIOD_DAY_OPTIONS,
  addDaysIso,
  dateDisplayLabel,
  slotDisplayLabel,
  normalizeScenarioConfig,
  periodEndFor,
  type ScenarioConfig,
} from "./scenario";
import {
  PAIR_SEVERITY_OPTIONS,
  ROLE_OPTIONS,
  VACATION_TYPE_OPTIONS,
  appendEmployeeRow,
  appendPairRow,
  appendVacationRow,
  buildEmployeeTableRows,
  buildPairTableRows,
  buildVacationTableRows,
  employeeRowsToBulkRows,
  normalizePairRowsForEmployees,
  normalizeVacationRowsForEmployees,
  pairRowsToDrafts,
  removeEmployeeRow,
  removePairRow,
  removeVacationRow,
  setEmployeeRole,
  updateEmployeeRow,
  updatePairRow,
  updateVacationRow,
  vacationRowsToDrafts,
  type EmployeeTableRow,
  type PairTableRow,
  type VacationTableRow,
} from "./scenarioTables";
import { canRecalculate } from "./scheduleActions";
import {
  DEFAULT_SHIFT_COVERAGE,
  SHIFT_DAY_GROUP_OPTIONS,
  SHIFT_PRESETS,
  buildShiftTypeRequests,
  normalizeShiftCoverage,
  setShiftCoverageEnabled,
  shiftCoverageSummary,
  type ShiftCoverage,
} from "./shiftProfile";
import { auditActionLabel, fairnessDeltaLabel, fairnessSpreadLabel } from "./visibility";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const TERMINAL_RUN_STATUSES = new Set(["succeeded", "infeasible"]);
const FAILED_RUN_STATUSES = new Set(["failed", "canceled"]);
const RESULT_POLL_INTERVAL_MS = 1000;
const RESULT_POLL_ATTEMPTS = 60;

type Employee = {
  id: string;
  employee_code: string;
  name: string;
};

type Slot = {
  id: string;
  local_date: string;
  label: string;
};

type Requirement = {
  id: string;
  slot_id: string;
  role_id: string;
  role_name: string;
  required_count: number;
};

type Assignment = {
  id: string;
  slot_id: string;
  role_id: string;
  employee_id: string;
  employee_name: string;
  source: string;
  warning_state: string;
};

type Issue = {
  id: string;
  slot_id: string | null;
  role_id: string | null;
  type: string;
  severity: string;
  display_message: string;
  missing_count: number;
};

type Proposal = {
  id: string;
  type: string;
  severity: string;
  display_summary: string;
  status: string;
};

type Publication = {
  id: string;
  status: string;
  published_at: string;
};

type ScheduleResult = {
  schedule_run_id: string;
  status: string;
  solution_quality: string;
  recalculation_count: number;
  read_only: boolean;
  publication: Publication | null;
  assignment_snapshot_hash: string;
  issue_snapshot_hash: string;
  slots: Slot[];
  requirements: Requirement[];
  assignments: Assignment[];
  issues: Issue[];
  proposals: Proposal[];
};

type AuditLogEntry = {
  id: string;
  actor_user_id: string | null;
  action: string;
  target_type: string;
  target_id: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

type AuditLogList = {
  organization_id: string;
  entries: AuditLogEntry[];
};

type FairnessEmployeeRow = {
  employee_id: string;
  employee_code: string;
  employee_name: string;
  assignment_count: number;
  delta_from_average: number;
};

type FairnessSummary = {
  organization_id: string;
  schedule_run_id: string | null;
  employee_count: number;
  total_assignments: number;
  average_assignments: number;
  min_assignments: number;
  max_assignments: number;
  spread: number;
  rows: FairnessEmployeeRow[];
};

type DemoState = {
  organizationId: string;
  runId: string;
  employees: Employee[];
};

export function App() {
  const [scenario, setScenario] = useState<ScenarioConfig>(DEFAULT_SCENARIO_CONFIG);
  const [shiftCoverage, setShiftCoverage] = useState<ShiftCoverage>(DEFAULT_SHIFT_COVERAGE);
  const [employeeRows, setEmployeeRows] = useState(() =>
    buildEmployeeTableRows(DEFAULT_SCENARIO_CONFIG.employeeCount),
  );
  const [vacationRows, setVacationRows] = useState(() =>
    buildVacationTableRows(DEFAULT_SCENARIO_CONFIG),
  );
  const [pairRows, setPairRows] = useState(() => buildPairTableRows(DEFAULT_SCENARIO_CONFIG));
  const [demo, setDemo] = useState<DemoState | null>(null);
  const [result, setResult] = useState<ScheduleResult | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([]);
  const [fairness, setFairness] = useState<FairnessSummary | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [downloadState, setDownloadState] = useState("대기");

  const normalizedScenario = useMemo(() => normalizeScenarioConfig(scenario), [scenario]);
  const normalizedShiftCoverage = useMemo(
    () => normalizeShiftCoverage(shiftCoverage),
    [shiftCoverage],
  );
  const scenarioSummary = useMemo(
    () =>
      `직원 ${employeeRows.length}명, 휴가 ${vacationRows.length}건, 상극 ${pairRows.length}건, ${normalizedScenario.periodDays}일 생성 · ${shiftCoverageSummary(normalizedShiftCoverage)}`,
    [employeeRows.length, normalizedScenario.periodDays, normalizedShiftCoverage, pairRows.length, vacationRows.length],
  );
  const operationSections = useMemo(
    () => [
      { label: "조직", value: normalizedScenario.organizationName, icon: Building2 },
      { label: "직원", value: `${employeeRows.length}명`, icon: Users },
      { label: "휴가/상극", value: `${vacationRows.length}건 / ${pairRows.length}건`, icon: ClipboardList },
      {
        label: "근무유형",
        value: shiftCoverageSummary(normalizedShiftCoverage),
        icon: Clock3,
      },
      { label: "생성기간", value: `${normalizedScenario.periodDays}일`, icon: FileSpreadsheet },
    ],
    [employeeRows.length, normalizedScenario, normalizedShiftCoverage, pairRows.length, vacationRows.length],
  );
  const roles = useMemo(() => {
    const seen = new Map<string, string>();
    result?.requirements.forEach((requirement) => {
      seen.set(requirement.role_id, requirement.role_name);
    });
    return Array.from(seen, ([roleId, roleName]) => ({ roleId, roleName }));
  }, [result]);
  const assignmentCounts = useMemo(() => {
    if (!demo || !result) return [];
    const counts = new Map(demo.employees.map((employee) => [employee.id, 0]));
    result.assignments.forEach((assignment) => {
      counts.set(assignment.employee_id, (counts.get(assignment.employee_id) ?? 0) + 1);
    });
    return demo.employees.map((employee) => ({
      id: employee.id,
      name: employee.name,
      count: counts.get(employee.id) ?? 0,
    }));
  }, [demo, result]);

  function clearRunState() {
    setDemo(null);
    setResult(null);
    setAuditLogs([]);
    setFairness(null);
    setDownloadState("대기");
    setError(null);
  }

  function updateScenario(patch: Partial<ScenarioConfig>) {
    const nextScenario = normalizeScenarioConfig({ ...scenario, ...patch });
    setScenario(nextScenario);
    if (patch.employeeCount !== undefined) {
      const nextEmployeeRows = buildEmployeeTableRows(nextScenario.employeeCount);
      setEmployeeRows(nextEmployeeRows);
      setVacationRows(buildVacationTableRows(nextScenario));
      setPairRows(buildPairTableRows(nextScenario));
    } else if (
      patch.startDate !== undefined ||
      patch.periodDays !== undefined
    ) {
      setVacationRows(buildVacationTableRows(nextScenario));
    }
    clearRunState();
  }

  function updateShiftCoverage(nextCoverage: ShiftCoverage) {
    setShiftCoverage(normalizeShiftCoverage(nextCoverage));
    clearRunState();
  }

  function replaceEmployeeRows(nextRows: EmployeeTableRow[]) {
    setEmployeeRows(nextRows);
    setScenario(normalizeScenarioConfig({ ...scenario, employeeCount: nextRows.length }));
    setVacationRows((currentRows) => normalizeVacationRowsForEmployees(currentRows, nextRows));
    setPairRows((currentRows) => normalizePairRowsForEmployees(currentRows, nextRows));
    clearRunState();
  }

  function replaceVacationRows(nextRows: VacationTableRow[]) {
    setVacationRows(nextRows);
    clearRunState();
  }

  function replacePairRows(nextRows: PairTableRow[]) {
    setPairRows(nextRows);
    clearRunState();
  }

  async function runDemo() {
    setBusy("demo");
    setError(null);
    setDownloadState("대기");
    try {
      const activeScenario = normalizeScenarioConfig(scenario);
      const activeShiftCoverage = normalizeShiftCoverage(shiftCoverage);
      const activeEmployees = employeeRowsToBulkRows(employeeRows);
      const activeVacations = vacationRowsToDrafts(
        normalizeVacationRowsForEmployees(vacationRows, employeeRows),
      );
      const activePairs = pairRowsToDrafts(normalizePairRowsForEmployees(pairRows, employeeRows));
      if (activeEmployees.length < MIN_EMPLOYEE_COUNT) {
        throw new Error(`직원은 최소 ${MIN_EMPLOYEE_COUNT}명 이상 입력해야 합니다.`);
      }
      const organization = await api<{ id: string; default_roles: { id: string; name: string }[] }>(
        "/organizations",
        {
          method: "POST",
          body: {
            name: activeScenario.organizationName,
            timezone: "Asia/Seoul",
          },
        },
      );
      const employeePayload = await api<{ employees: Employee[] }>(
        `/organizations/${organization.id}/employees/bulk-paste`,
        {
          method: "POST",
          body: {
            mode: "upsert",
            rows: activeEmployees,
          },
        },
      );
      const seniorRole = organization.default_roles.find((role) => role.name === "사수");
      const juniorRole = organization.default_roles.find((role) => role.name === "부사수");
      if (!seniorRole || !juniorRole) throw new Error("Default roles are missing.");
      await Promise.all(
        buildShiftTypeRequests(activeShiftCoverage, {
          seniorRoleId: seniorRole.id,
          juniorRoleId: juniorRole.id,
        }).map((request) =>
          api(`/organizations/${organization.id}/shift-types`, {
            method: "POST",
            body: request,
          }),
        ),
      );
      const employeesByCode = new Map(
        employeePayload.employees.map((employee) => [employee.employee_code, employee]),
      );
      for (const vacation of activeVacations) {
        const vacationEmployee = employeesByCode.get(vacation.employeeCode);
        if (!vacationEmployee) {
          throw new Error(`휴가 직원 ${vacation.employeeCode}를 직원 목록에서 찾을 수 없습니다.`);
        }
        await api(`/organizations/${organization.id}/unavailabilities`, {
          method: "POST",
          body: {
            employee_id: vacationEmployee.id,
            type: vacation.type,
            starts_at: `${vacation.startDate}T00:00:00+09:00`,
            ends_at: `${addDaysIso(vacation.endDate, 1)}T00:00:00+09:00`,
            override_allowed: vacation.overrideAllowed,
            note: "Operator scenario vacation",
          },
        });
      }
      for (const pair of activePairs) {
        const pairEmployeeA = employeesByCode.get(pair.employeeACode);
        const pairEmployeeB = employeesByCode.get(pair.employeeBCode);
        if (!pairEmployeeA || !pairEmployeeB) {
          throw new Error(`상극 직원 ${pair.employeeACode}/${pair.employeeBCode}를 직원 목록에서 찾을 수 없습니다.`);
        }
        await api(`/organizations/${organization.id}/pair-constraints`, {
          method: "POST",
          body: {
            employee_a_id: pairEmployeeA.id,
            employee_b_id: pairEmployeeB.id,
            type: "blocked",
            severity: pair.severity,
            override_allowed: pair.overrideAllowed,
            active: true,
          },
        });
      }
      const run = await api<{ id: string }>(`/organizations/${organization.id}/schedule-runs`, {
        method: "POST",
        body: {
          period_start: activeScenario.startDate,
          period_end: periodEndFor(activeScenario.startDate, activeScenario.periodDays),
          template: "one_shift_per_day",
          deterministic_mode: true,
          timeout_seconds: 30,
        },
      });
      setDemo({ organizationId: organization.id, runId: run.id, employees: employeePayload.employees });
      const nextResult = await waitForCompletedResult(organization.id, run.id);
      setResult(nextResult);
      await refreshVisibility(organization.id, run.id);
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setBusy(null);
    }
  }

  async function approveProposal() {
    if (!demo || !result?.proposals[0]) return;
    setBusy("approve");
    setError(null);
    try {
      await api(
        `/organizations/${demo.organizationId}/schedule-runs/${demo.runId}/relaxation-proposals/${result.proposals[0].id}/approve`,
        {
          method: "POST",
          body: { reason: "운영 관리자 승인", notification_required: true },
        },
      );
      setResult(await fetchResult(demo.organizationId, demo.runId));
      await refreshVisibility(demo.organizationId, demo.runId);
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setBusy(null);
    }
  }

  async function recalculate() {
    if (!demo) return;
    setBusy("recalculate");
    setError(null);
    try {
      await api(`/organizations/${demo.organizationId}/schedule-runs/${demo.runId}/recalculate`, {
        method: "POST",
        body: { reason: "승인된 완화안을 반영합니다." },
      });
      setResult(await waitForCompletedResult(demo.organizationId, demo.runId));
      await refreshVisibility(demo.organizationId, demo.runId);
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setBusy(null);
    }
  }

  async function publish() {
    if (!demo || !result) return;
    setBusy("publish");
    setError(null);
    try {
      await api(`/organizations/${demo.organizationId}/schedule-runs/${demo.runId}/publications`, {
        method: "POST",
        body: {
          expected_assignment_snapshot_hash: result.assignment_snapshot_hash,
          expected_issue_snapshot_hash: result.issue_snapshot_hash,
        },
      });
      setResult(await fetchResult(demo.organizationId, demo.runId));
      await refreshVisibility(demo.organizationId, demo.runId);
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setBusy(null);
    }
  }

  async function downloadExcel() {
    if (!demo || !result?.publication) return;
    setBusy("download");
    setError(null);
    try {
      const response = await fetch(
        `${API_BASE}/organizations/${demo.organizationId}/schedule-publications/${result.publication.id}/excel`,
      );
      if (!response.ok) throw new Error(`Excel download failed: ${response.status}`);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "work_schedule_p0.xlsx";
      anchor.click();
      URL.revokeObjectURL(url);
      setDownloadState("완료");
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setBusy(null);
    }
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">W</div>
          <div>
            <strong>WorkScheduleAI</strong>
            <span>스케줄 운영 플랫폼</span>
          </div>
        </div>
        <div className="tenant-card">
          <span>현재 조직</span>
          <strong>{normalizedScenario.organizationName}</strong>
        </div>
        <nav className="nav-list">
          {operationSections.map((section) => {
            const Icon = section.icon;
            return (
              <div className="nav-row" key={section.label}>
                <Icon size={18} />
                <span>{section.label}</span>
                <strong>{section.value}</strong>
              </div>
            );
          })}
        </nav>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <h1>근무표 운영 콘솔</h1>
            <p>{scenarioSummary}</p>
          </div>
          <button className="primary-action" disabled={busy === "demo"} onClick={runDemo}>
            <Play size={17} />
            {busy === "demo" ? "생성 중" : "근무표 생성"}
          </button>
        </header>

        {error ? <div className="error-banner">{error}</div> : null}

        <div className="content-grid">
          <section className="setup-panel">
            <ScenarioControls
              config={normalizedScenario}
              disabled={busy === "demo"}
              employeeRows={employeeRows}
              onChange={updateScenario}
              onEmployeeRowsChange={replaceEmployeeRows}
              onPairRowsChange={replacePairRows}
              onShiftCoverageChange={updateShiftCoverage}
              onVacationRowsChange={replaceVacationRows}
              pairRows={pairRows}
              shiftCoverage={normalizedShiftCoverage}
              vacationRows={vacationRows}
            />
            <SectionTitle title="입력 상태" />
            <Metric label="조직명" value={normalizedScenario.organizationName} />
            <Metric label="조직 ID" value={demo?.organizationId ?? "대기"} />
            <Metric
              label="직원"
              value={demo ? `${demo.employees.length}명` : `${employeeRows.length}명 입력`}
            />
            <Metric
              label="기간"
              value={`${normalizedScenario.startDate} ~ ${periodEndFor(
                normalizedScenario.startDate,
                normalizedScenario.periodDays,
              )}`}
            />
            <Metric label="근무유형" value={shiftCoverageSummary(normalizedShiftCoverage)} />
            <Metric label="생성 상태" value={result?.status ?? "대기"} />
            <Metric label="재계산" value={`${result?.recalculation_count ?? 0}회`} />
            <Metric label="다운로드" value={downloadState} />
            <AssignmentSummary counts={assignmentCounts} />
          </section>

          <section className="schedule-panel">
            <div className="panel-heading">
              <SectionTitle title="결과 그리드" />
              <div className="status-line">
                <span className="quality-badge">{qualityLabel(result?.solution_quality)}</span>
                {result?.read_only ? <span className="published-badge">읽기 전용</span> : null}
              </div>
            </div>
            <ScheduleGrid result={result} roles={roles} />
          </section>

          <section className="review-panel">
            <SectionTitle title="이슈/완화안" />
            <IssueList issues={result?.issues ?? []} />
            <ProposalList proposals={result?.proposals ?? []} />
            <FairnessPanel summary={fairness} />
            <AuditLogPanel entries={auditLogs} />
            <div className="action-stack">
              <button disabled={!result?.proposals.length || busy === "approve"} onClick={approveProposal}>
                <CheckCircle2 size={16} />
                완화안 승인
              </button>
              <button
                disabled={!demo || !canRecalculate(result) || busy === "recalculate"}
                onClick={recalculate}
                title={
                  canRecalculate(result)
                    ? undefined
                    : "승인된 완화안이 있을 때만 재계산할 수 있습니다."
                }
              >
                <RefreshCw size={16} />
                재계산
              </button>
              <button disabled={!result || result.issues.length > 0 || result.read_only || busy === "publish"} onClick={publish}>
                <ShieldCheck size={16} />
                확정
              </button>
              <button disabled={!result?.publication || busy === "download"} onClick={downloadExcel}>
                <Download size={16} />
                엑셀 다운로드
              </button>
            </div>
          </section>
        </div>
      </section>
    </main>
  );

  async function refreshVisibility(organizationId: string, runId: string) {
    const [fairnessResponse, auditResponse] = await Promise.all([
      api<FairnessSummary>(
        `/operations/organizations/${organizationId}/fairness/summary?schedule_run_id=${runId}`,
      ),
      api<AuditLogList>(`/operations/organizations/${organizationId}/audit-logs`),
    ]);
    setFairness(fairnessResponse);
    setAuditLogs(auditResponse.entries);
  }
}

function ScheduleGrid({
  result,
  roles,
}: {
  result: ScheduleResult | null;
  roles: { roleId: string; roleName: string }[];
}) {
  if (!result) {
    return <div className="empty-state">시나리오를 생성하면 결과 그리드가 표시됩니다.</div>;
  }
  return (
    <div className="schedule-table-wrap">
      <table className="schedule-table">
        <thead>
          <tr>
            <th>날짜/슬롯</th>
            {roles.map((role) => <th key={role.roleId}>{role.roleName}</th>)}
          </tr>
        </thead>
        <tbody>
          {result.slots.map((slot) => (
            <tr key={slot.id}>
              <th>
                <strong>{dateDisplayLabel(slot.local_date)}</strong>
                <span>{slotDisplayLabel(slot.label, slot.local_date)}</span>
              </th>
              {roles.map((role) => (
                <td key={role.roleId}>
                  <AssignmentCell result={result} slotId={slot.id} roleId={role.roleId} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AssignmentCell({
  result,
  slotId,
  roleId,
}: {
  result: ScheduleResult;
  slotId: string;
  roleId: string;
}) {
  const assignment = result.assignments.find(
    (item) => item.slot_id === slotId && item.role_id === roleId,
  );
  const issue = result.issues.find((item) => item.slot_id === slotId && item.role_id === roleId);
  if (assignment) {
    return (
      <div className="assignment-cell">
        <strong>{assignment.employee_name}</strong>
        <span>{assignment.source}</span>
      </div>
    );
  }
  if (issue) {
    return (
      <div className="unfilled-cell">
        <AlertTriangle size={15} />
        미배정
      </div>
    );
  }
  return <span className="muted">-</span>;
}

function IssueList({ issues }: { issues: Issue[] }) {
  if (!issues.length) {
    return <div className="success-box">열린 ScheduleIssue가 없습니다.</div>;
  }
  return (
    <div className="item-list">
      {issues.map((issue) => (
        <div className="issue-item" key={issue.id}>
          <span className="severity">{severityLabel(issue.severity)}</span>
          <strong>{issue.display_message}</strong>
          <small>{issue.type} · missing {issue.missing_count}</small>
        </div>
      ))}
    </div>
  );
}

function ProposalList({ proposals }: { proposals: Proposal[] }) {
  if (!proposals.length) {
    return <div className="subtle-box">추천 완화안이 없습니다.</div>;
  }
  return (
    <div className="item-list">
      {proposals.map((proposal) => (
        <div className="proposal-item" key={proposal.id}>
          <span>{proposal.status === "approved" ? "승인됨" : "추천"}</span>
          <strong>{proposal.display_summary}</strong>
          <small>{proposal.type}</small>
        </div>
      ))}
    </div>
  );
}

function FairnessPanel({ summary }: { summary: FairnessSummary | null }) {
  return (
    <div className="visibility-panel">
      <SectionTitle title="공정성" />
      {!summary ? (
        <div className="subtle-box">공정성 요약이 없습니다.</div>
      ) : (
        <>
          <div className="summary-metrics">
            <Metric label="총 배정" value={`${summary.total_assignments}회`} />
            <Metric label="평균" value={`${summary.average_assignments}회`} />
            <Metric label="편차" value={fairnessSpreadLabel(summary)} />
          </div>
          <div className="fairness-list">
            {summary.rows.slice(0, 8).map((row) => (
              <div className="fairness-row" key={row.employee_id}>
                <div>
                  <strong>{row.employee_name}</strong>
                  <span>{row.employee_code}</span>
                </div>
                <b>{row.assignment_count}회</b>
                <em>{fairnessDeltaLabel(row.delta_from_average)}</em>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function AuditLogPanel({ entries }: { entries: AuditLogEntry[] }) {
  return (
    <div className="visibility-panel">
      <SectionTitle title="감사 로그" />
      {!entries.length ? (
        <div className="subtle-box">최근 감사 로그가 없습니다.</div>
      ) : (
        <div className="audit-list">
          {entries.slice(0, 5).map((entry) => (
            <div className="audit-row" key={entry.id}>
              <strong>{auditActionLabel(entry.action)}</strong>
              <span>{entry.target_type} · {formatDateTime(entry.created_at)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function SectionTitle({ title }: { title: string }) {
  return <h2 className="section-title">{title}</h2>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function AssignmentSummary({
  counts,
}: {
  counts: { id: string; name: string; count: number }[];
}) {
  if (!counts.length) return null;
  return (
    <div className="assignment-summary">
      <span>직원별 배정</span>
      {counts.map((employee) => (
        <div className="assignment-summary-row" key={employee.id}>
          <strong>{employee.name}</strong>
          <b>{employee.count}회</b>
        </div>
      ))}
    </div>
  );
}

function ScenarioControls({
  config,
  disabled,
  employeeRows,
  onChange,
  onEmployeeRowsChange,
  onPairRowsChange,
  onShiftCoverageChange,
  onVacationRowsChange,
  pairRows,
  shiftCoverage,
  vacationRows,
}: {
  config: ScenarioConfig;
  disabled: boolean;
  employeeRows: EmployeeTableRow[];
  onChange: (patch: Partial<ScenarioConfig>) => void;
  onEmployeeRowsChange: (rows: EmployeeTableRow[]) => void;
  onPairRowsChange: (rows: PairTableRow[]) => void;
  onShiftCoverageChange: (coverage: ShiftCoverage) => void;
  onVacationRowsChange: (rows: VacationTableRow[]) => void;
  pairRows: PairTableRow[];
  shiftCoverage: ShiftCoverage;
  vacationRows: VacationTableRow[];
}) {
  return (
    <div className="scenario-controls">
      <SectionTitle title="운영 설정" />
      <div className="field-grid">
        <label className="field-row field-row-wide">
          <span>회사/조직명</span>
          <input
            disabled={disabled}
            onChange={(event) => onChange({ organizationName: event.target.value })}
            type="text"
            value={config.organizationName}
          />
        </label>
        <label className="field-row">
          <span>직원 수</span>
          <input
            disabled={disabled}
            max={MAX_EMPLOYEE_COUNT}
            min={MIN_EMPLOYEE_COUNT}
            onChange={(event) => onChange({ employeeCount: Number(event.target.value) })}
            type="number"
            value={config.employeeCount}
          />
        </label>
        <label className="field-row">
          <span>기간</span>
          <select
            disabled={disabled}
            onChange={(event) => onChange({ periodDays: Number(event.target.value) })}
            value={config.periodDays}
          >
            {PERIOD_DAY_OPTIONS.map((days) => (
              <option key={days} value={days}>
                {days}일
              </option>
            ))}
          </select>
        </label>
        <label className="field-row">
          <span>시작일</span>
          <input
            disabled={disabled}
            onChange={(event) => onChange({ startDate: event.target.value })}
            type="date"
            value={config.startDate}
          />
        </label>
      </div>
      <ShiftCoverageMatrix
        coverage={shiftCoverage}
        disabled={disabled}
        onChange={onShiftCoverageChange}
      />
      <ReferenceDataTables
        config={config}
        disabled={disabled}
        employeeRows={employeeRows}
        onEmployeeRowsChange={onEmployeeRowsChange}
        onPairRowsChange={onPairRowsChange}
        onVacationRowsChange={onVacationRowsChange}
        pairRows={pairRows}
        vacationRows={vacationRows}
      />
    </div>
  );
}

function ReferenceDataTables({
  config,
  disabled,
  employeeRows,
  onEmployeeRowsChange,
  onPairRowsChange,
  onVacationRowsChange,
  pairRows,
  vacationRows,
}: {
  config: ScenarioConfig;
  disabled: boolean;
  employeeRows: EmployeeTableRow[];
  onEmployeeRowsChange: (rows: EmployeeTableRow[]) => void;
  onPairRowsChange: (rows: PairTableRow[]) => void;
  onVacationRowsChange: (rows: VacationTableRow[]) => void;
  pairRows: PairTableRow[];
  vacationRows: VacationTableRow[];
}) {
  return (
    <div className="reference-data">
      <EmployeeTable
        disabled={disabled}
        rows={employeeRows}
        onChange={onEmployeeRowsChange}
      />
      <VacationTable
        config={config}
        disabled={disabled}
        employeeRows={employeeRows}
        rows={vacationRows}
        onChange={onVacationRowsChange}
      />
      <PairConstraintTable
        disabled={disabled}
        employeeRows={employeeRows}
        rows={pairRows}
        onChange={onPairRowsChange}
      />
    </div>
  );
}

function EmployeeTable({
  disabled,
  onChange,
  rows,
}: {
  disabled: boolean;
  onChange: (rows: EmployeeTableRow[]) => void;
  rows: EmployeeTableRow[];
}) {
  return (
    <div className="table-editor">
      <div className="table-editor-heading">
        <SectionTitle title="직원 기준정보" />
        <button
          disabled={disabled || rows.length >= MAX_EMPLOYEE_COUNT}
          onClick={() => onChange(appendEmployeeRow(rows))}
          type="button"
        >
          <Plus size={15} />
          직원 추가
        </button>
      </div>
      <div className="table-scroll">
        <table className="editor-table employee-editor-table">
          <thead>
            <tr>
              <th>직원코드</th>
              <th>이름</th>
              <th>역할</th>
              <th>주 최대</th>
              <th>삭제</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>
                  <input
                    disabled={disabled}
                    onChange={(event) =>
                      onChange(updateEmployeeRow(rows, row.id, { employeeCode: event.target.value }))
                    }
                    type="text"
                    value={row.employeeCode}
                  />
                </td>
                <td>
                  <input
                    disabled={disabled}
                    onChange={(event) =>
                      onChange(updateEmployeeRow(rows, row.id, { name: event.target.value }))
                    }
                    type="text"
                    value={row.name}
                  />
                </td>
                <td>
                  <div className="role-toggle-group">
                    {ROLE_OPTIONS.map((roleName) => (
                      <label className="inline-check" key={roleName}>
                        <input
                          checked={row.roleNames.includes(roleName)}
                          disabled={disabled}
                          onChange={(event) =>
                            onChange(setEmployeeRole(rows, row.id, roleName, event.target.checked))
                          }
                          type="checkbox"
                        />
                        <span>{roleName}</span>
                      </label>
                    ))}
                  </div>
                </td>
                <td>
                  <input
                    disabled={disabled}
                    min={1}
                    onChange={(event) =>
                      onChange(
                        updateEmployeeRow(rows, row.id, {
                          maxShiftsPerWeek: Number(event.target.value),
                        }),
                      )
                    }
                    type="number"
                    value={row.maxShiftsPerWeek}
                  />
                </td>
                <td>
                  <button
                    className="icon-button danger-button"
                    disabled={disabled || rows.length <= MIN_EMPLOYEE_COUNT}
                    onClick={() => onChange(removeEmployeeRow(rows, row.id))}
                    title="직원 삭제"
                    type="button"
                  >
                    <Trash2 size={15} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function VacationTable({
  config,
  disabled,
  employeeRows,
  onChange,
  rows,
}: {
  config: ScenarioConfig;
  disabled: boolean;
  employeeRows: EmployeeTableRow[];
  onChange: (rows: VacationTableRow[]) => void;
  rows: VacationTableRow[];
}) {
  return (
    <div className="table-editor">
      <div className="table-editor-heading">
        <SectionTitle title="휴가/출장 일정" />
        <button
          disabled={disabled}
          onClick={() => onChange(appendVacationRow(rows, employeeRows, config.startDate))}
          type="button"
        >
          <Plus size={15} />
          일정 추가
        </button>
      </div>
      <div className="table-scroll">
        <table className="editor-table vacation-editor-table">
          <thead>
            <tr>
              <th>직원</th>
              <th>시작일</th>
              <th>종료일</th>
              <th>유형</th>
              <th>예외</th>
              <th>삭제</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>
                  <EmployeeSelect
                    disabled={disabled}
                    employeeRows={employeeRows}
                    onChange={(employeeCode) =>
                      onChange(updateVacationRow(rows, row.id, { employeeCode }))
                    }
                    value={row.employeeCode}
                  />
                </td>
                <td>
                  <input
                    disabled={disabled}
                    onChange={(event) =>
                      onChange(updateVacationRow(rows, row.id, { startDate: event.target.value }))
                    }
                    type="date"
                    value={row.startDate}
                  />
                </td>
                <td>
                  <input
                    disabled={disabled}
                    onChange={(event) =>
                      onChange(updateVacationRow(rows, row.id, { endDate: event.target.value }))
                    }
                    type="date"
                    value={row.endDate}
                  />
                </td>
                <td>
                  <select
                    disabled={disabled}
                    onChange={(event) =>
                      onChange(updateVacationRow(rows, row.id, { type: event.target.value }))
                    }
                    value={row.type}
                  >
                    {VACATION_TYPE_OPTIONS.map((type) => (
                      <option key={type} value={type}>
                        {vacationTypeLabel(type)}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <label className="inline-check">
                    <input
                      checked={row.overrideAllowed}
                      disabled={disabled}
                      onChange={(event) =>
                        onChange(
                          updateVacationRow(rows, row.id, {
                            overrideAllowed: event.target.checked,
                          }),
                        )
                      }
                      type="checkbox"
                    />
                    <span>허용</span>
                  </label>
                </td>
                <td>
                  <button
                    className="icon-button danger-button"
                    disabled={disabled || rows.length <= 1}
                    onClick={() => onChange(removeVacationRow(rows, row.id))}
                    title="일정 삭제"
                    type="button"
                  >
                    <Trash2 size={15} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function PairConstraintTable({
  disabled,
  employeeRows,
  onChange,
  rows,
}: {
  disabled: boolean;
  employeeRows: EmployeeTableRow[];
  onChange: (rows: PairTableRow[]) => void;
  rows: PairTableRow[];
}) {
  return (
    <div className="table-editor">
      <div className="table-editor-heading">
        <SectionTitle title="상극 조합" />
        <button
          disabled={disabled}
          onClick={() => onChange(appendPairRow(rows, employeeRows))}
          type="button"
        >
          <Plus size={15} />
          조합 추가
        </button>
      </div>
      <div className="table-scroll">
        <table className="editor-table pair-editor-table">
          <thead>
            <tr>
              <th>직원 A</th>
              <th>직원 B</th>
              <th>심각도</th>
              <th>예외</th>
              <th>삭제</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>
                  <EmployeeSelect
                    disabled={disabled}
                    employeeRows={employeeRows}
                    onChange={(employeeACode) =>
                      onChange(updatePairRow(rows, row.id, { employeeACode }, employeeRows))
                    }
                    value={row.employeeACode}
                  />
                </td>
                <td>
                  <EmployeeSelect
                    disabled={disabled}
                    employeeRows={employeeRows}
                    onChange={(employeeBCode) =>
                      onChange(updatePairRow(rows, row.id, { employeeBCode }, employeeRows))
                    }
                    value={row.employeeBCode}
                  />
                </td>
                <td>
                  <select
                    disabled={disabled}
                    onChange={(event) =>
                      onChange(updatePairRow(rows, row.id, { severity: event.target.value }, employeeRows))
                    }
                    value={row.severity}
                  >
                    {PAIR_SEVERITY_OPTIONS.map((severity) => (
                      <option key={severity} value={severity}>
                        {severityLabel(severity)}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <label className="inline-check">
                    <input
                      checked={row.overrideAllowed}
                      disabled={disabled}
                      onChange={(event) =>
                        onChange(
                          updatePairRow(
                            rows,
                            row.id,
                            { overrideAllowed: event.target.checked },
                            employeeRows,
                          ),
                        )
                      }
                      type="checkbox"
                    />
                    <span>허용</span>
                  </label>
                </td>
                <td>
                  <button
                    className="icon-button danger-button"
                    disabled={disabled || rows.length <= 1}
                    onClick={() => onChange(removePairRow(rows, row.id))}
                    title="조합 삭제"
                    type="button"
                  >
                    <Trash2 size={15} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function EmployeeSelect({
  disabled,
  employeeRows,
  onChange,
  value,
}: {
  disabled: boolean;
  employeeRows: EmployeeTableRow[];
  onChange: (employeeCode: string) => void;
  value: string;
}) {
  return (
    <select
      disabled={disabled}
      onChange={(event) => onChange(event.target.value)}
      value={value}
    >
      {employeeRows.map((employee) => (
        <option key={employee.id} value={employee.employeeCode}>
          {employee.employeeCode} · {employee.name}
        </option>
      ))}
    </select>
  );
}

function ShiftCoverageMatrix({
  coverage,
  disabled,
  onChange,
}: {
  coverage: ShiftCoverage;
  disabled: boolean;
  onChange: (coverage: ShiftCoverage) => void;
}) {
  return (
    <div className="shift-coverage">
      <div className="coverage-heading">
        <SectionTitle title="근무유형" />
        <span>{shiftCoverageSummary(coverage)}</span>
      </div>
      <div className="shift-matrix">
        <div className="shift-matrix-head">시간대</div>
        {SHIFT_DAY_GROUP_OPTIONS.map((dayGroup) => (
          <div className="shift-matrix-head" key={dayGroup.id}>
            {dayGroup.label}
          </div>
        ))}
        {SHIFT_PRESETS.map((preset) => (
          <div className="shift-matrix-row" key={preset.id}>
            <span>{preset.label}</span>
            {SHIFT_DAY_GROUP_OPTIONS.map((dayGroup) => {
              const checked = coverage[dayGroup.id].includes(preset.id);
              return (
                <label className="check-cell" key={`${dayGroup.id}-${preset.id}`}>
                  <input
                    checked={checked}
                    disabled={disabled}
                    onChange={(event) =>
                      onChange(
                        setShiftCoverageEnabled(
                          coverage,
                          dayGroup.id,
                          preset.id,
                          event.target.checked,
                        ),
                      )
                    }
                    type="checkbox"
                  />
                  <span>{checked ? "사용" : "미사용"}</span>
                </label>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

async function fetchResult(organizationId: string, runId: string) {
  return api<ScheduleResult>(`/organizations/${organizationId}/schedule-runs/${runId}/result`);
}

async function waitForCompletedResult(organizationId: string, runId: string) {
  for (let attempt = 0; attempt < RESULT_POLL_ATTEMPTS; attempt += 1) {
    const result = await fetchResult(organizationId, runId);
    if (TERMINAL_RUN_STATUSES.has(result.status)) {
      return result;
    }
    if (FAILED_RUN_STATUSES.has(result.status)) {
      throw new Error(`근무표 생성이 ${result.status} 상태로 종료되었습니다.`);
    }
    await delay(RESULT_POLL_INTERVAL_MS);
  }
  throw new Error("근무표 생성이 제한 시간 안에 완료되지 않았습니다. worker 서비스를 확인해주세요.");
}

function delay(milliseconds: number) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

async function api<T>(path: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: options.method ?? "GET",
    headers: options.body ? { "Content-Type": "application/json" } : undefined,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`${response.status} ${detail}`);
  }
  return response.json() as Promise<T>;
}

function qualityLabel(value?: string) {
  if (!value) return "대기";
  if (value === "feasible_not_proven_optimal") return "최적 보장 없음";
  if (value === "optimal") return "최적";
  return value;
}

function severityLabel(value: string) {
  const labels: Record<string, string> = {
    low: "낮음",
    medium: "주의",
    high: "높음",
    critical: "매우 높음",
  };
  return labels[value] ?? value;
}

function vacationTypeLabel(value: string) {
  const labels: Record<string, string> = {
    vacation: "휴가",
    business_trip: "출장",
    training: "교육",
    personal: "개인",
  };
  return labels[value] ?? value;
}

function messageFromError(error: unknown) {
  return error instanceof Error ? error.message : "알 수 없는 오류가 발생했습니다.";
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString("ko-KR", {
    dateStyle: "short",
    timeStyle: "short",
  });
}
