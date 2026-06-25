import {
  AlertTriangle,
  CalendarDays,
  CheckCircle2,
  Download,
  FileSpreadsheet,
  Play,
  RefreshCw,
  Rocket,
  ShieldCheck,
  Users,
} from "lucide-react";
import { useMemo, useState } from "react";
import {
  DEFAULT_SCENARIO_CONFIG,
  MAX_EMPLOYEE_COUNT,
  MIN_EMPLOYEE_COUNT,
  PERIOD_DAY_OPTIONS,
  addDaysIso,
  buildScenarioEmployees,
  buildScenarioSummary,
  normalizeScenarioConfig,
  periodEndFor,
  type ScenarioConfig,
  type ScenarioEmployee,
} from "./scenario";

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

type DemoState = {
  organizationId: string;
  runId: string;
  employees: Employee[];
};

export function App() {
  const [scenario, setScenario] = useState<ScenarioConfig>(DEFAULT_SCENARIO_CONFIG);
  const [demo, setDemo] = useState<DemoState | null>(null);
  const [result, setResult] = useState<ScheduleResult | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [downloadState, setDownloadState] = useState("대기");

  const normalizedScenario = useMemo(() => normalizeScenarioConfig(scenario), [scenario]);
  const scenarioEmployees = useMemo(
    () => buildScenarioEmployees(normalizedScenario.employeeCount),
    [normalizedScenario.employeeCount],
  );
  const scenarioSummary = useMemo(
    () => buildScenarioSummary(normalizedScenario),
    [normalizedScenario],
  );
  const steps = useMemo(
    () => [
      { label: "조직 생성", icon: Rocket },
      { label: `직원 ${normalizedScenario.employeeCount}명 bulk paste`, icon: Users },
      { label: `휴가 ${normalizedScenario.vacationEmployeeCode}`, icon: CalendarDays },
      {
        label: `상극 ${normalizedScenario.pairEmployeeACode}/${normalizedScenario.pairEmployeeBCode}`,
        icon: ShieldCheck,
      },
      { label: `${normalizedScenario.periodDays}일 근무표 생성`, icon: FileSpreadsheet },
    ],
    [normalizedScenario],
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

  function updateScenario(patch: Partial<ScenarioConfig>) {
    setScenario((current) => normalizeScenarioConfig({ ...current, ...patch }));
    setDemo(null);
    setResult(null);
    setDownloadState("대기");
    setError(null);
  }

  async function runDemo() {
    setBusy("demo");
    setError(null);
    setDownloadState("대기");
    try {
      const activeScenario = normalizeScenarioConfig(scenario);
      const activeEmployees = buildScenarioEmployees(activeScenario.employeeCount);
      const organization = await api<{ id: string; default_roles: { id: string; name: string }[] }>(
        "/organizations",
        {
          method: "POST",
          body: {
            name: `Operator Scenario ${Date.now()}`,
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
            rows: activeEmployees.map(employeeRow),
          },
        },
      );
      const seniorRole = organization.default_roles.find((role) => role.name === "사수");
      const juniorRole = organization.default_roles.find((role) => role.name === "부사수");
      if (!seniorRole || !juniorRole) throw new Error("Default roles are missing.");
      await api(`/organizations/${organization.id}/shift-types`, {
        method: "POST",
        body: {
          name: "주간 근무",
          local_start_time: "09:00",
          local_end_time: "18:00",
          timezone: "Asia/Seoul",
          requirements: [
            { role_id: seniorRole.id, required_count: 1 },
            { role_id: juniorRole.id, required_count: 1 },
          ],
        },
      });
      const employeesByCode = new Map(
        employeePayload.employees.map((employee) => [employee.employee_code, employee]),
      );
      const vacationEmployee = employeesByCode.get(activeScenario.vacationEmployeeCode);
      const pairEmployeeA = employeesByCode.get(activeScenario.pairEmployeeACode);
      const pairEmployeeB = employeesByCode.get(activeScenario.pairEmployeeBCode);
      if (!vacationEmployee || !pairEmployeeA || !pairEmployeeB) {
        throw new Error("선택한 직원 조건을 생성된 직원 목록에서 찾을 수 없습니다.");
      }
      await api(`/organizations/${organization.id}/unavailabilities`, {
        method: "POST",
        body: {
          employee_id: vacationEmployee.id,
          type: "vacation",
          starts_at: `${activeScenario.vacationDate}T00:00:00+09:00`,
          ends_at: `${addDaysIso(activeScenario.vacationDate, 1)}T00:00:00+09:00`,
          override_allowed: true,
          note: "Operator scenario vacation",
        },
      });
      await api(`/organizations/${organization.id}/pair-constraints`, {
        method: "POST",
        body: {
          employee_a_id: pairEmployeeA.id,
          employee_b_id: pairEmployeeB.id,
          type: "blocked",
          severity: "high",
          override_allowed: true,
          active: true,
        },
      });
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
            <span>1차 릴리즈 콘솔</span>
          </div>
        </div>
        <nav className="nav-list">
          {steps.map((step, index) => {
            const Icon = step.icon;
            return (
              <div className="nav-row" key={step.label}>
                <Icon size={18} />
                <span>{index + 1}. {step.label}</span>
              </div>
            );
          })}
        </nav>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <h1>근무표 생성/검토</h1>
            <p>{scenarioSummary}</p>
          </div>
          <button className="primary-action" disabled={busy === "demo"} onClick={runDemo}>
            <Play size={17} />
            {busy === "demo" ? "생성 중" : "시나리오 생성"}
          </button>
        </header>

        {error ? <div className="error-banner">{error}</div> : null}

        <div className="content-grid">
          <section className="setup-panel">
            <ScenarioControls
              config={normalizedScenario}
              disabled={busy === "demo"}
              employees={scenarioEmployees}
              onChange={updateScenario}
            />
            <SectionTitle title="입력 상태" />
            <Metric label="조직" value={demo?.organizationId ?? "대기"} />
            <Metric
              label="직원"
              value={demo ? `${demo.employees.length}명` : `${normalizedScenario.employeeCount}명 선택`}
            />
            <Metric
              label="기간"
              value={`${normalizedScenario.startDate} ~ ${periodEndFor(
                normalizedScenario.startDate,
                normalizedScenario.periodDays,
              )}`}
            />
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
            <div className="action-stack">
              <button disabled={!result?.proposals.length || busy === "approve"} onClick={approveProposal}>
                <CheckCircle2 size={16} />
                완화안 승인
              </button>
              <button disabled={!demo || busy === "recalculate"} onClick={recalculate}>
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
                <strong>{slot.local_date}</strong>
                <span>{slot.label}</span>
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
  employees,
  onChange,
}: {
  config: ScenarioConfig;
  disabled: boolean;
  employees: ScenarioEmployee[];
  onChange: (patch: Partial<ScenarioConfig>) => void;
}) {
  return (
    <div className="scenario-controls">
      <SectionTitle title="시나리오 설정" />
      <div className="field-grid">
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
        <label className="field-row">
          <span>휴가자</span>
          <EmployeeSelect
            disabled={disabled}
            employees={employees}
            onChange={(value) => onChange({ vacationEmployeeCode: value })}
            value={config.vacationEmployeeCode}
          />
        </label>
        <label className="field-row">
          <span>휴가일</span>
          <input
            disabled={disabled}
            onChange={(event) => onChange({ vacationDate: event.target.value })}
            type="date"
            value={config.vacationDate}
          />
        </label>
        <label className="field-row">
          <span>상극 A</span>
          <EmployeeSelect
            disabled={disabled}
            employees={employees}
            onChange={(value) => onChange({ pairEmployeeACode: value })}
            value={config.pairEmployeeACode}
          />
        </label>
        <label className="field-row">
          <span>상극 B</span>
          <EmployeeSelect
            disabled={disabled}
            employees={employees}
            excludedCode={config.pairEmployeeACode}
            onChange={(value) => onChange({ pairEmployeeBCode: value })}
            value={config.pairEmployeeBCode}
          />
        </label>
      </div>
    </div>
  );
}

function EmployeeSelect({
  disabled,
  employees,
  excludedCode,
  onChange,
  value,
}: {
  disabled: boolean;
  employees: ScenarioEmployee[];
  excludedCode?: string;
  onChange: (value: string) => void;
  value: string;
}) {
  return (
    <select disabled={disabled} onChange={(event) => onChange(event.target.value)} value={value}>
      {employees.map((employee) => (
        <option
          disabled={employee.employeeCode === excludedCode}
          key={employee.employeeCode}
          value={employee.employeeCode}
        >
          {employee.employeeCode} {employee.name}
        </option>
      ))}
    </select>
  );
}

function employeeRow(employee: ScenarioEmployee) {
  return {
    row_no: employee.rowNo,
    employee_code: employee.employeeCode,
    name: employee.name,
    role_names: employee.roleNames,
    max_shifts_per_week: employee.maxShiftsPerWeek,
  };
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

function messageFromError(error: unknown) {
  return error instanceof Error ? error.message : "알 수 없는 오류가 발생했습니다.";
}
