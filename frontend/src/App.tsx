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

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

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

const steps = [
  { label: "조직 생성", icon: Rocket },
  { label: "직원 4명 bulk paste", icon: Users },
  { label: "휴가 1건", icon: CalendarDays },
  { label: "상극 조합 1건", icon: ShieldCheck },
  { label: "근무표 생성", icon: FileSpreadsheet },
];

export function App() {
  const [demo, setDemo] = useState<DemoState | null>(null);
  const [result, setResult] = useState<ScheduleResult | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [downloadState, setDownloadState] = useState("대기");

  const roles = useMemo(() => {
    const seen = new Map<string, string>();
    result?.requirements.forEach((requirement) => {
      seen.set(requirement.role_id, requirement.role_name);
    });
    return Array.from(seen, ([roleId, roleName]) => ({ roleId, roleName }));
  }, [result]);

  async function runDemo() {
    setBusy("demo");
    setError(null);
    setDownloadState("대기");
    try {
      const organization = await api<{ id: string; default_roles: { id: string; name: string }[] }>(
        "/organizations",
        {
          method: "POST",
          body: {
            name: `P0 Clinic ${Date.now()}`,
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
            rows: [
              employeeRow(1, "E001", "Kim"),
              employeeRow(2, "E002", "Lee"),
              employeeRow(3, "E003", "Park"),
              employeeRow(4, "E004", "Choi"),
            ],
          },
        },
      );
      const employeesByCode = new Map(
        employeePayload.employees.map((employee) => [employee.employee_code, employee]),
      );
      await api(`/organizations/${organization.id}/unavailabilities`, {
        method: "POST",
        body: {
          employee_id: employeesByCode.get("E002")?.id,
          type: "vacation",
          starts_at: "2026-07-01T00:00:00+09:00",
          ends_at: "2026-07-02T00:00:00+09:00",
          override_allowed: true,
          note: "P0 demo vacation",
        },
      });
      await api(`/organizations/${organization.id}/pair-constraints`, {
        method: "POST",
        body: {
          employee_a_id: employeesByCode.get("E001")?.id,
          employee_b_id: employeesByCode.get("E002")?.id,
          type: "blocked",
          severity: "high",
          override_allowed: true,
          active: true,
        },
      });
      const run = await api<{ id: string }>(`/organizations/${organization.id}/schedule-runs`, {
        method: "POST",
        body: {
          period_start: "2026-07-01",
          period_end: "2026-07-07",
          template: "one_shift_per_day",
          deterministic_mode: true,
          timeout_seconds: 30,
        },
      });
      const nextResult = await fetchResult(organization.id, run.id);
      setDemo({ organizationId: organization.id, runId: run.id, employees: employeePayload.employees });
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
      setResult(await fetchResult(demo.organizationId, demo.runId));
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
            <p>직원 4명, 휴가 1건, 상극 조합 1건, 1주 P0 흐름</p>
          </div>
          <button className="primary-action" disabled={busy === "demo"} onClick={runDemo}>
            <Play size={17} />
            {busy === "demo" ? "생성 중" : "P0 데모 생성"}
          </button>
        </header>

        {error ? <div className="error-banner">{error}</div> : null}

        <div className="content-grid">
          <section className="setup-panel">
            <SectionTitle title="입력 상태" />
            <Metric label="조직" value={demo?.organizationId ?? "대기"} />
            <Metric label="직원" value={demo ? `${demo.employees.length}명` : "0명"} />
            <Metric label="생성 상태" value={result?.status ?? "대기"} />
            <Metric label="재계산" value={`${result?.recalculation_count ?? 0}회`} />
            <Metric label="다운로드" value={downloadState} />
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
    return <div className="empty-state">P0 데모를 생성하면 결과 그리드가 표시됩니다.</div>;
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

function employeeRow(row_no: number, employee_code: string, name: string) {
  return {
    row_no,
    employee_code,
    name,
    role_names: ["사수", "부사수"],
    max_shifts_per_week: 5,
  };
}

async function fetchResult(organizationId: string, runId: string) {
  return api<ScheduleResult>(`/organizations/${organizationId}/schedule-runs/${runId}/result`);
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
