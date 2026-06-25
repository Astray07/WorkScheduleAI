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
  MAX_PERIOD_DAYS,
  MAX_EMPLOYEE_COUNT,
  MIN_EMPLOYEE_COUNT,
  addDaysIso,
  dateDisplayLabel,
  slotDisplayLabel,
  normalizeScenarioConfig,
  periodDaysForRange,
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
import {
  assignmentLockLabel,
  assignmentSourceLabel,
  manualEditRequest,
  openManualEditDraft,
  type ManualEditDraft,
} from "./manualEdits";
import { parseDelimitedText, validateImportRows, type ImportType } from "./importPreview";
import {
  DEFAULT_POLICY,
  normalizePolicy,
  unfilledPolicyLabel,
  type SchedulePolicy,
} from "./policies";
import { REFERENCE_TABS, referenceSummary, type ReferenceTabId } from "./referenceData";
import { canRecalculate } from "./scheduleActions";
import {
  DEFAULT_SHIFT_COVERAGE,
  SHIFT_DAY_GROUP_OPTIONS,
  SHIFT_PRESETS,
  normalizeShiftCoverage,
  planScenarioShiftTypeSync,
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

type Role = {
  id: string;
  name: string;
};

type ManagedEmployee = Employee & {
  active: boolean;
  role_ids: string[];
  role_names: string[];
  max_shifts_per_week: number | null;
};

type ManagedUnavailability = {
  id: string;
  employee_id: string;
  type: string;
  starts_at: string;
  ends_at: string;
  override_allowed: boolean;
  note: string | null;
};

type ManagedPairConstraint = {
  id: string;
  employee_a_id: string;
  employee_b_id: string;
  type: string;
  severity: string;
  override_allowed: boolean;
  active: boolean;
};

type ManagedShiftType = {
  id: string;
  name: string;
  local_start_time: string;
  local_end_time: string;
  timezone: string;
  crosses_midnight: boolean;
  active_weekdays: number[];
  active: boolean;
  requirements: {
    id: string;
    role_id: string;
    role_name: string;
    required_count: number;
    unfilled_weight_override: number | null;
  }[];
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
  locked_by_user: boolean;
  warning_state: string;
  warning_message: string | null;
  attempt_no: number;
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

type FieldError = {
  field: string;
  code: string;
  message: string;
};

type ManualEditValidation = {
  valid: boolean;
  blocking_errors: FieldError[];
  warnings: FieldError[];
};

type OrganizationWorkspace = {
  id: string;
  default_roles: Role[];
};

type ReferenceDataSnapshot = {
  employees: ManagedEmployee[];
  unavailabilities: ManagedUnavailability[];
  pairConstraints: ManagedPairConstraint[];
  shiftTypes: ManagedShiftType[];
  policy: SchedulePolicy;
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
  const [activeSetupTab, setActiveSetupTab] = useState<ReferenceTabId>("scenario");
  const [workspaceOrganization, setWorkspaceOrganization] = useState<OrganizationWorkspace | null>(null);
  const [managedEmployees, setManagedEmployees] = useState<ManagedEmployee[]>([]);
  const [managedUnavailabilities, setManagedUnavailabilities] = useState<ManagedUnavailability[]>([]);
  const [managedPairConstraints, setManagedPairConstraints] = useState<ManagedPairConstraint[]>([]);
  const [managedShiftTypes, setManagedShiftTypes] = useState<ManagedShiftType[]>([]);
  const [policy, setPolicy] = useState<SchedulePolicy>(DEFAULT_POLICY);
  const [importType, setImportType] = useState<ImportType>("employees");
  const [importContent, setImportContent] = useState(
    "employee_code,name,roles,max_shifts_per_week\nE013,신규직원,사수|부사수,5",
  );
  const [importPreview, setImportPreview] = useState<{
    valid: boolean;
    rows: Record<string, string>[];
    errors: { field: string | null; row_no: number | null; message: string }[];
  } | null>(null);
  const [manualEditDraft, setManualEditDraft] = useState<ManualEditDraft | null>(null);
  const [manualEditValidation, setManualEditValidation] = useState<ManualEditValidation | null>(null);
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
      {
        label: "생성기간",
        value: `${normalizedScenario.startDate} ~ ${periodEndFor(
          normalizedScenario.startDate,
          normalizedScenario.periodDays,
        )}`,
        icon: FileSpreadsheet,
      },
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
      const { employees, organization } = await prepareGenerationWorkspace({
        activeEmployees,
        activePairs,
        activeScenario,
        activeShiftCoverage,
        activeVacations,
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
      setDemo({ organizationId: organization.id, runId: run.id, employees });
      const nextResult = await waitForCompletedResult(organization.id, run.id);
      setResult(nextResult);
      await refreshVisibility(organization.id, run.id);
      await refreshReferenceData(organization.id);
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

  async function ensureWorkspaceOrganization() {
    if (workspaceOrganization) return workspaceOrganization;
    const activeScenario = normalizeScenarioConfig(scenario);
    const organization = await api<OrganizationWorkspace>("/organizations", {
      method: "POST",
      body: {
        name: activeScenario.organizationName,
        timezone: "Asia/Seoul",
      },
    });
    setWorkspaceOrganization(organization);
    await refreshReferenceData(organization.id);
    return organization;
  }

  async function prepareGenerationWorkspace({
    activeEmployees,
    activePairs,
    activeScenario,
    activeShiftCoverage,
    activeVacations,
  }: {
    activeEmployees: ReturnType<typeof employeeRowsToBulkRows>;
    activePairs: ReturnType<typeof pairRowsToDrafts>;
    activeScenario: ScenarioConfig;
    activeShiftCoverage: ShiftCoverage;
    activeVacations: ReturnType<typeof vacationRowsToDrafts>;
  }): Promise<{ organization: OrganizationWorkspace; employees: Employee[] }> {
    const organization = workspaceOrganization
      ?? await api<OrganizationWorkspace>("/organizations", {
        method: "POST",
        body: {
          name: activeScenario.organizationName,
          timezone: "Asia/Seoul",
        },
      });
    setWorkspaceOrganization(organization);

    let referenceData = await fetchReferenceData(organization.id);
    if (referenceData.employees.filter((employee) => employee.active).length < MIN_EMPLOYEE_COUNT) {
      await api(`/organizations/${organization.id}/employees/bulk-paste`, {
        method: "POST",
        body: {
          mode: "upsert",
          rows: activeEmployees,
        },
      });
      referenceData = await fetchReferenceData(organization.id);
    }

    const seniorRole = organization.default_roles.find((role) => role.name === "사수");
    const juniorRole = organization.default_roles.find((role) => role.name === "부사수");
    if (!seniorRole || !juniorRole) throw new Error("Default roles are missing.");
    const shiftTypeSync = planScenarioShiftTypeSync(
      activeShiftCoverage,
      {
        seniorRoleId: seniorRole.id,
        juniorRoleId: juniorRole.id,
      },
      referenceData.shiftTypes,
    );
    if (shiftTypeSync.creates.length || shiftTypeSync.updates.length) {
      await Promise.all([
        ...shiftTypeSync.updates.map((update) =>
          api(`/organizations/${organization.id}/shift-types/${update.id}`, {
            method: "PATCH",
            body: update.request,
          }),
        ),
        ...shiftTypeSync.creates.map((request) =>
          api(`/organizations/${organization.id}/shift-types`, {
            method: "POST",
            body: request,
          }),
        ),
      ]);
      referenceData = await fetchReferenceData(organization.id);
    }

    const activeManagedEmployees = referenceData.employees.filter((employee) => employee.active);
    const employeesByCode = new Map(
      activeManagedEmployees.map((employee) => [employee.employee_code, employee]),
    );
    if (!referenceData.unavailabilities.length) {
      for (const vacation of activeVacations) {
        const vacationEmployee = employeesByCode.get(vacation.employeeCode);
        if (!vacationEmployee) continue;
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
    }
    if (!referenceData.pairConstraints.length) {
      for (const pair of activePairs) {
        const pairEmployeeA = employeesByCode.get(pair.employeeACode);
        const pairEmployeeB = employeesByCode.get(pair.employeeBCode);
        if (!pairEmployeeA || !pairEmployeeB) continue;
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
    }

    referenceData = await refreshReferenceData(organization.id);
    const employees = referenceData.employees
      .filter((employee) => employee.active)
      .map((employee) => ({
        id: employee.id,
        employee_code: employee.employee_code,
        name: employee.name,
      }));
    if (employees.length < MIN_EMPLOYEE_COUNT) {
      throw new Error(`직원은 최소 ${MIN_EMPLOYEE_COUNT}명 이상 준비되어야 합니다.`);
    }
    return { organization, employees };
  }

  async function prepareWorkspace() {
    setBusy("prepare");
    setError(null);
    try {
      await ensureWorkspaceOrganization();
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setBusy(null);
    }
  }

  async function refreshReferenceData(organizationId = workspaceOrganization?.id) {
    if (!organizationId) {
      return {
        employees: managedEmployees,
        pairConstraints: managedPairConstraints,
        policy,
        shiftTypes: managedShiftTypes,
        unavailabilities: managedUnavailabilities,
      };
    }
    const referenceData = await fetchReferenceData(organizationId);
    setManagedEmployees(referenceData.employees);
    setManagedUnavailabilities(referenceData.unavailabilities);
    setManagedPairConstraints(referenceData.pairConstraints);
    setManagedShiftTypes(referenceData.shiftTypes);
    setPolicy(referenceData.policy);
    return referenceData;
  }

  async function fetchReferenceData(organizationId: string): Promise<ReferenceDataSnapshot> {
    const [employees, unavailabilities, pairConstraints, shiftTypes, policyResponse] =
      await Promise.all([
        api<ManagedEmployee[]>(`/organizations/${organizationId}/employees`),
        api<ManagedUnavailability[]>(`/organizations/${organizationId}/unavailabilities`),
        api<ManagedPairConstraint[]>(`/organizations/${organizationId}/pair-constraints`),
        api<ManagedShiftType[]>(`/organizations/${organizationId}/shift-types`),
        api<SchedulePolicy>(`/organizations/${organizationId}/schedule-policy`),
      ]);
    return {
      employees,
      pairConstraints,
      policy: normalizePolicy(policyResponse),
      shiftTypes,
      unavailabilities,
    };
  }

  async function loadReferenceData() {
    setBusy("reference");
    setError(null);
    try {
      const organization = await ensureWorkspaceOrganization();
      await refreshReferenceData(organization.id);
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setBusy(null);
    }
  }

  function selectManualCell(slotId: string, roleId: string) {
    if (!demo || !result || result.read_only) return;
    const assignment = result.assignments.find(
      (item) => item.slot_id === slotId && item.role_id === roleId,
    );
    setManualEditDraft(
      openManualEditDraft({
        assignment,
        employees: demo.employees,
        roleId,
        slotId,
      }),
    );
    setManualEditValidation(null);
  }

  async function validateManualEdit() {
    if (!demo || !manualEditDraft) return null;
    setBusy("manual-validate");
    setError(null);
    try {
      const validation = await api<ManualEditValidation>(
        `/organizations/${demo.organizationId}/schedule-runs/${demo.runId}/manual-edits/validate`,
        {
          method: "POST",
          body: manualEditRequest(manualEditDraft),
        },
      );
      setManualEditValidation(validation);
      return validation;
    } catch (caught) {
      setError(messageFromError(caught));
      return null;
    } finally {
      setBusy(null);
    }
  }

  async function saveManualEdit() {
    if (!demo || !manualEditDraft) return;
    const validation = await validateManualEdit();
    if (!validation?.valid) return;
    setBusy("manual-save");
    setError(null);
    try {
      await api<Assignment>(
        `/organizations/${demo.organizationId}/schedule-runs/${demo.runId}/manual-edits`,
        {
          method: "POST",
          body: manualEditRequest(manualEditDraft),
        },
      );
      setResult(await fetchResult(demo.organizationId, demo.runId));
      await refreshVisibility(demo.organizationId, demo.runId);
      await refreshReferenceData(demo.organizationId);
      setManualEditDraft(null);
      setManualEditValidation(null);
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setBusy(null);
    }
  }

  async function savePolicy() {
    setBusy("policy");
    setError(null);
    try {
      const organization = await ensureWorkspaceOrganization();
      const savedPolicy = await api<SchedulePolicy>(
        `/organizations/${organization.id}/schedule-policy`,
        {
          method: "PUT",
          body: normalizePolicy(policy),
        },
      );
      setPolicy(normalizePolicy(savedPolicy));
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setBusy(null);
    }
  }

  async function addManagedEmployee() {
    setBusy("reference");
    setError(null);
    try {
      const organization = await ensureWorkspaceOrganization();
      const nextNumber = managedEmployees.length + 1;
      await api(`/organizations/${organization.id}/employees/bulk-paste`, {
        method: "POST",
        body: {
          mode: "upsert",
          rows: [
            {
              row_no: 1,
              employee_code: `M${nextNumber.toString().padStart(3, "0")}`,
              name: "신규 직원",
              role_names: [organization.default_roles[0]?.name ?? "사수"],
              max_shifts_per_week: 5,
            },
          ],
        },
      });
      await refreshReferenceData(organization.id);
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setBusy(null);
    }
  }

  async function saveManagedEmployee(employee: ManagedEmployee) {
    if (!workspaceOrganization) return;
    setBusy("reference");
    setError(null);
    try {
      await api(`/organizations/${workspaceOrganization.id}/employees/${employee.id}`, {
        method: "PATCH",
        body: {
          employee_code: employee.employee_code,
          name: employee.name,
          active: employee.active,
          role_names: employee.role_names.length ? employee.role_names : ["사수"],
          max_shifts_per_week: employee.max_shifts_per_week ?? 5,
        },
      });
      await refreshReferenceData(workspaceOrganization.id);
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setBusy(null);
    }
  }

  async function deleteManagedEmployee(employeeId: string) {
    if (!workspaceOrganization) return;
    setBusy("reference");
    setError(null);
    try {
      await api(`/organizations/${workspaceOrganization.id}/employees/${employeeId}`, {
        method: "DELETE",
      });
      await refreshReferenceData(workspaceOrganization.id);
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setBusy(null);
    }
  }

  async function addManagedUnavailability() {
    const employee = managedEmployees.find((item) => item.active) ?? managedEmployees[0];
    if (!workspaceOrganization || !employee) return;
    setBusy("reference");
    setError(null);
    try {
      await api(`/organizations/${workspaceOrganization.id}/unavailabilities`, {
        method: "POST",
        body: {
          employee_id: employee.id,
          type: "vacation",
          starts_at: `${normalizedScenario.startDate}T00:00:00+09:00`,
          ends_at: `${addDaysIso(normalizedScenario.startDate, 1)}T00:00:00+09:00`,
          override_allowed: true,
          note: "Manual reference entry",
        },
      });
      await refreshReferenceData(workspaceOrganization.id);
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setBusy(null);
    }
  }

  async function saveManagedUnavailability(unavailability: ManagedUnavailability) {
    if (!workspaceOrganization) return;
    setBusy("reference");
    setError(null);
    try {
      await api(`/organizations/${workspaceOrganization.id}/unavailabilities/${unavailability.id}`, {
        method: "PATCH",
        body: unavailability,
      });
      await refreshReferenceData(workspaceOrganization.id);
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setBusy(null);
    }
  }

  async function deleteManagedUnavailability(unavailabilityId: string) {
    if (!workspaceOrganization) return;
    setBusy("reference");
    setError(null);
    try {
      await api(`/organizations/${workspaceOrganization.id}/unavailabilities/${unavailabilityId}`, {
        method: "DELETE",
      });
      await refreshReferenceData(workspaceOrganization.id);
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setBusy(null);
    }
  }

  async function addManagedPairConstraint() {
    if (!workspaceOrganization || managedEmployees.length < 2) return;
    setBusy("reference");
    setError(null);
    try {
      await api(`/organizations/${workspaceOrganization.id}/pair-constraints`, {
        method: "POST",
        body: {
          employee_a_id: managedEmployees[0].id,
          employee_b_id: managedEmployees[1].id,
          type: "blocked",
          severity: "high",
          override_allowed: true,
          active: true,
        },
      });
      await refreshReferenceData(workspaceOrganization.id);
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setBusy(null);
    }
  }

  async function saveManagedPairConstraint(pairConstraint: ManagedPairConstraint) {
    if (!workspaceOrganization) return;
    setBusy("reference");
    setError(null);
    try {
      await api(`/organizations/${workspaceOrganization.id}/pair-constraints/${pairConstraint.id}`, {
        method: "PATCH",
        body: pairConstraint,
      });
      await refreshReferenceData(workspaceOrganization.id);
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setBusy(null);
    }
  }

  async function deleteManagedPairConstraint(pairConstraintId: string) {
    if (!workspaceOrganization) return;
    setBusy("reference");
    setError(null);
    try {
      await api(`/organizations/${workspaceOrganization.id}/pair-constraints/${pairConstraintId}`, {
        method: "DELETE",
      });
      await refreshReferenceData(workspaceOrganization.id);
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setBusy(null);
    }
  }

  async function addManagedShiftType() {
    if (!workspaceOrganization || workspaceOrganization.default_roles.length < 2) return;
    setBusy("reference");
    setError(null);
    try {
      await api(`/organizations/${workspaceOrganization.id}/shift-types`, {
        method: "POST",
        body: {
          name: `추가 근무 ${managedShiftTypes.length + 1}`,
          local_start_time: "09:00",
          local_end_time: "18:00",
          timezone: "Asia/Seoul",
          crosses_midnight: false,
          active_weekdays: [0, 1, 2, 3, 4],
          active: true,
          requirements: workspaceOrganization.default_roles.slice(0, 2).map((role) => ({
            role_id: role.id,
            required_count: 1,
          })),
        },
      });
      await refreshReferenceData(workspaceOrganization.id);
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setBusy(null);
    }
  }

  async function saveManagedShiftType(shiftType: ManagedShiftType) {
    if (!workspaceOrganization) return;
    setBusy("reference");
    setError(null);
    try {
      await api(`/organizations/${workspaceOrganization.id}/shift-types/${shiftType.id}`, {
        method: "PATCH",
        body: {
          name: shiftType.name,
          local_start_time: shiftType.local_start_time,
          local_end_time: shiftType.local_end_time,
          timezone: shiftType.timezone,
          crosses_midnight: shiftType.crosses_midnight,
          active_weekdays: shiftType.active_weekdays,
          active: shiftType.active,
          requirements: shiftType.requirements.map((requirement) => ({
            role_id: requirement.role_id,
            required_count: requirement.required_count,
            unfilled_weight_override: requirement.unfilled_weight_override,
          })),
        },
      });
      await refreshReferenceData(workspaceOrganization.id);
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setBusy(null);
    }
  }

  async function deleteManagedShiftType(shiftTypeId: string) {
    if (!workspaceOrganization) return;
    setBusy("reference");
    setError(null);
    try {
      await api(`/organizations/${workspaceOrganization.id}/shift-types/${shiftTypeId}`, {
        method: "DELETE",
      });
      await refreshReferenceData(workspaceOrganization.id);
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setBusy(null);
    }
  }

  async function previewImport() {
    setBusy("import-preview");
    setError(null);
    try {
      const organization = await ensureWorkspaceOrganization();
      const localPreview = validateImportRows(importType, parseDelimitedText(importContent));
      if (!localPreview.valid) {
        setImportPreview(localPreview);
        return;
      }
      const serverPreview = await api<typeof importPreview>(
        `/organizations/${organization.id}/imports/preview`,
        {
          method: "POST",
          body: { type: importType, content: importContent },
        },
      );
      setImportPreview(serverPreview);
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setBusy(null);
    }
  }

  async function applyImport() {
    setBusy("import-apply");
    setError(null);
    try {
      const organization = await ensureWorkspaceOrganization();
      const response = await api<typeof importPreview>(
        `/organizations/${organization.id}/imports/apply`,
        {
          method: "POST",
          body: { type: importType, mode: "upsert", content: importContent },
        },
      );
      setImportPreview(response);
      await refreshReferenceData(organization.id);
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
            <OperationsSetupTabs
              activeTab={activeSetupTab}
              busy={busy}
              employees={managedEmployees}
              importContent={importContent}
              importPreview={importPreview}
              importType={importType}
              onApplyImport={applyImport}
              onAddEmployee={addManagedEmployee}
              onAddPairConstraint={addManagedPairConstraint}
              onAddShiftType={addManagedShiftType}
              onAddUnavailability={addManagedUnavailability}
              onDeleteEmployee={deleteManagedEmployee}
              onDeletePairConstraint={deleteManagedPairConstraint}
              onDeleteShiftType={deleteManagedShiftType}
              onDeleteUnavailability={deleteManagedUnavailability}
              onEmployeesChange={setManagedEmployees}
              onImportContentChange={setImportContent}
              onImportTypeChange={setImportType}
              onLoadReferenceData={loadReferenceData}
              onPairConstraintsChange={setManagedPairConstraints}
              onPolicyChange={setPolicy}
              onPrepareWorkspace={prepareWorkspace}
              onPreviewImport={previewImport}
              onSavePolicy={savePolicy}
              onSaveEmployee={saveManagedEmployee}
              onSavePairConstraint={saveManagedPairConstraint}
              onSaveShiftType={saveManagedShiftType}
              onSaveUnavailability={saveManagedUnavailability}
              onShiftTypesChange={setManagedShiftTypes}
              onTabChange={setActiveSetupTab}
              onUnavailabilitiesChange={setManagedUnavailabilities}
              pairConstraints={managedPairConstraints}
              policy={policy}
              shiftTypes={managedShiftTypes}
              unavailabilities={managedUnavailabilities}
              workspace={workspaceOrganization}
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
            <ScheduleGrid
              onCellSelect={selectManualCell}
              result={result}
              roles={roles}
            />
            <ManualEditPanel
              busy={busy}
              demo={demo}
              draft={manualEditDraft}
              onChange={setManualEditDraft}
              onClose={() => {
                setManualEditDraft(null);
                setManualEditValidation(null);
              }}
              onSave={saveManualEdit}
              onValidate={validateManualEdit}
              result={result}
              validation={manualEditValidation}
            />
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
  onCellSelect,
  result,
  roles,
}: {
  onCellSelect: (slotId: string, roleId: string) => void;
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
                  <AssignmentCell
                    onSelect={() => onCellSelect(slot.id, role.roleId)}
                    readOnly={result.read_only}
                    result={result}
                    slotId={slot.id}
                    roleId={role.roleId}
                  />
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
  onSelect,
  readOnly,
  result,
  slotId,
  roleId,
}: {
  onSelect: () => void;
  readOnly: boolean;
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
      <button
        className="assignment-cell cell-action"
        disabled={readOnly}
        onClick={onSelect}
        type="button"
      >
        <strong>{assignment.employee_name}</strong>
        <span>{assignmentSourceLabel(assignment)} · {assignmentLockLabel(assignment)}</span>
      </button>
    );
  }
  if (issue) {
    return (
      <button
        className="unfilled-cell cell-action"
        disabled={readOnly}
        onClick={onSelect}
        type="button"
      >
        <AlertTriangle size={15} />
        미배정
      </button>
    );
  }
  return <span className="muted">-</span>;
}

function ManualEditPanel({
  busy,
  demo,
  draft,
  onChange,
  onClose,
  onSave,
  onValidate,
  result,
  validation,
}: {
  busy: string | null;
  demo: DemoState | null;
  draft: ManualEditDraft | null;
  onChange: (draft: ManualEditDraft) => void;
  onClose: () => void;
  onSave: () => void;
  onValidate: () => void;
  result: ScheduleResult | null;
  validation: ManualEditValidation | null;
}) {
  if (!draft || !demo || !result) return null;
  const slot = result.slots.find((item) => item.id === draft.slotId);
  const role = result.requirements.find((item) => item.role_id === draft.roleId);
  return (
    <div className="manual-edit-panel">
      <div className="panel-heading compact-heading">
        <SectionTitle title="수동 편집" />
        <button onClick={onClose} type="button">닫기</button>
      </div>
      <div className="manual-edit-grid">
        <Metric label="슬롯" value={slot ? `${slot.local_date} ${slot.label}` : draft.slotId} />
        <Metric label="역할" value={role?.role_name ?? draft.roleId} />
        <label className="field-row field-row-wide">
          <span>직원 변경</span>
          <select
            disabled={result.read_only}
            onChange={(event) => onChange({ ...draft, employeeId: event.target.value })}
            value={draft.employeeId}
          >
            {demo.employees.map((employee) => (
              <option key={employee.id} value={employee.id}>
                {employee.employee_code} · {employee.name}
              </option>
            ))}
          </select>
        </label>
        <label className="inline-check">
          <input
            checked={draft.lockedByUser}
            disabled={result.read_only}
            onChange={(event) => onChange({ ...draft, lockedByUser: event.target.checked })}
            type="checkbox"
          />
          <span>재계산 시 수동 배정 잠금</span>
        </label>
      </div>
      <ValidationSummary validation={validation} />
      <div className="button-row">
        <button disabled={busy === "manual-validate" || result.read_only} onClick={onValidate} type="button">
          저장 전 검증
        </button>
        <button className="primary-action" disabled={busy === "manual-save" || result.read_only} onClick={onSave} type="button">
          저장
        </button>
      </div>
    </div>
  );
}

function ValidationSummary({ validation }: { validation: ManualEditValidation | null }) {
  if (!validation) return <div className="subtle-box">저장 전 서버 검증을 실행하세요.</div>;
  if (!validation.blocking_errors.length && !validation.warnings.length) {
    return <div className="success-box">검증을 통과했습니다.</div>;
  }
  return (
    <div className="validation-list">
      {validation.blocking_errors.map((error) => (
        <div className="validation-row blocking" key={`${error.field}-${error.code}`}>
          <strong>{error.code}</strong>
          <span>{error.message}</span>
        </div>
      ))}
      {validation.warnings.map((warning) => (
        <div className="validation-row warning" key={`${warning.field}-${warning.code}`}>
          <strong>{warning.code}</strong>
          <span>{warning.message}</span>
        </div>
      ))}
    </div>
  );
}

function OperationsSetupTabs({
  activeTab,
  busy,
  employees,
  importContent,
  importPreview,
  importType,
  onAddEmployee,
  onAddPairConstraint,
  onAddShiftType,
  onAddUnavailability,
  onApplyImport,
  onDeleteEmployee,
  onDeletePairConstraint,
  onDeleteShiftType,
  onDeleteUnavailability,
  onEmployeesChange,
  onImportContentChange,
  onImportTypeChange,
  onLoadReferenceData,
  onPairConstraintsChange,
  onPolicyChange,
  onPrepareWorkspace,
  onPreviewImport,
  onSaveEmployee,
  onSavePairConstraint,
  onSavePolicy,
  onSaveShiftType,
  onSaveUnavailability,
  onShiftTypesChange,
  onTabChange,
  onUnavailabilitiesChange,
  pairConstraints,
  policy,
  shiftTypes,
  unavailabilities,
  workspace,
}: {
  activeTab: ReferenceTabId;
  busy: string | null;
  employees: ManagedEmployee[];
  importContent: string;
  importPreview: {
    valid: boolean;
    rows: Record<string, string>[];
    errors: { field: string | null; row_no: number | null; message: string }[];
  } | null;
  importType: ImportType;
  onAddEmployee: () => void;
  onAddPairConstraint: () => void;
  onAddShiftType: () => void;
  onAddUnavailability: () => void;
  onApplyImport: () => void;
  onDeleteEmployee: (employeeId: string) => void;
  onDeletePairConstraint: (pairConstraintId: string) => void;
  onDeleteShiftType: (shiftTypeId: string) => void;
  onDeleteUnavailability: (unavailabilityId: string) => void;
  onEmployeesChange: (employees: ManagedEmployee[]) => void;
  onImportContentChange: (content: string) => void;
  onImportTypeChange: (type: ImportType) => void;
  onLoadReferenceData: () => void;
  onPairConstraintsChange: (pairs: ManagedPairConstraint[]) => void;
  onPolicyChange: (policy: SchedulePolicy) => void;
  onPrepareWorkspace: () => void;
  onPreviewImport: () => void;
  onSaveEmployee: (employee: ManagedEmployee) => void;
  onSavePairConstraint: (pairConstraint: ManagedPairConstraint) => void;
  onSavePolicy: () => void;
  onSaveShiftType: (shiftType: ManagedShiftType) => void;
  onSaveUnavailability: (unavailability: ManagedUnavailability) => void;
  onShiftTypesChange: (shiftTypes: ManagedShiftType[]) => void;
  onTabChange: (tab: ReferenceTabId) => void;
  onUnavailabilitiesChange: (unavailabilities: ManagedUnavailability[]) => void;
  pairConstraints: ManagedPairConstraint[];
  policy: SchedulePolicy;
  shiftTypes: ManagedShiftType[];
  unavailabilities: ManagedUnavailability[];
  workspace: OrganizationWorkspace | null;
}) {
  return (
    <div className="operations-tabs">
      <div className="segmented-tabs">
        {REFERENCE_TABS.map((tab) => (
          <button
            className={activeTab === tab.id ? "active" : ""}
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            type="button"
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="workspace-strip">
        <span>{workspace ? `조직 ${workspace.id}` : "저장된 조직 없음"}</span>
        <button disabled={busy === "prepare"} onClick={onPrepareWorkspace} type="button">
          조직 준비
        </button>
        <button disabled={!workspace || busy === "reference"} onClick={onLoadReferenceData} type="button">
          새로고침
        </button>
      </div>
      {activeTab === "scenario" ? (
        <div className="subtle-box">생성 탭은 위 운영 설정과 시나리오 기준정보를 사용합니다.</div>
      ) : null}
      {activeTab === "reference" ? (
        <ReferenceManager
          employees={employees}
          onAddEmployee={onAddEmployee}
          onAddPairConstraint={onAddPairConstraint}
          onAddShiftType={onAddShiftType}
          onAddUnavailability={onAddUnavailability}
          onDeleteEmployee={onDeleteEmployee}
          onDeletePairConstraint={onDeletePairConstraint}
          onDeleteShiftType={onDeleteShiftType}
          onDeleteUnavailability={onDeleteUnavailability}
          onEmployeesChange={onEmployeesChange}
          onPairConstraintsChange={onPairConstraintsChange}
          onSaveEmployee={onSaveEmployee}
          onSavePairConstraint={onSavePairConstraint}
          onSaveShiftType={onSaveShiftType}
          onSaveUnavailability={onSaveUnavailability}
          onShiftTypesChange={onShiftTypesChange}
          onUnavailabilitiesChange={onUnavailabilitiesChange}
          pairConstraints={pairConstraints}
          roles={workspace?.default_roles ?? []}
          shiftTypes={shiftTypes}
          unavailabilities={unavailabilities}
        />
      ) : null}
      {activeTab === "policy" ? (
        <PolicyManager onChange={onPolicyChange} onSave={onSavePolicy} policy={policy} />
      ) : null}
      {activeTab === "import" ? (
        <ImportManager
          content={importContent}
          importType={importType}
          onApply={onApplyImport}
          onContentChange={onImportContentChange}
          onPreview={onPreviewImport}
          onTypeChange={onImportTypeChange}
          preview={importPreview}
        />
      ) : null}
    </div>
  );
}

function ReferenceManager({
  employees,
  onAddEmployee,
  onAddPairConstraint,
  onAddShiftType,
  onAddUnavailability,
  onDeleteEmployee,
  onDeletePairConstraint,
  onDeleteShiftType,
  onDeleteUnavailability,
  onEmployeesChange,
  onPairConstraintsChange,
  onSaveEmployee,
  onSavePairConstraint,
  onSaveShiftType,
  onSaveUnavailability,
  onShiftTypesChange,
  onUnavailabilitiesChange,
  pairConstraints,
  roles,
  shiftTypes,
  unavailabilities,
}: {
  employees: ManagedEmployee[];
  onAddEmployee: () => void;
  onAddPairConstraint: () => void;
  onAddShiftType: () => void;
  onAddUnavailability: () => void;
  onDeleteEmployee: (employeeId: string) => void;
  onDeletePairConstraint: (pairConstraintId: string) => void;
  onDeleteShiftType: (shiftTypeId: string) => void;
  onDeleteUnavailability: (unavailabilityId: string) => void;
  onEmployeesChange: (employees: ManagedEmployee[]) => void;
  onPairConstraintsChange: (pairs: ManagedPairConstraint[]) => void;
  onSaveEmployee: (employee: ManagedEmployee) => void;
  onSavePairConstraint: (pairConstraint: ManagedPairConstraint) => void;
  onSaveShiftType: (shiftType: ManagedShiftType) => void;
  onSaveUnavailability: (unavailability: ManagedUnavailability) => void;
  onShiftTypesChange: (shiftTypes: ManagedShiftType[]) => void;
  onUnavailabilitiesChange: (unavailabilities: ManagedUnavailability[]) => void;
  pairConstraints: ManagedPairConstraint[];
  roles: Role[];
  shiftTypes: ManagedShiftType[];
  unavailabilities: ManagedUnavailability[];
}) {
  const summary = referenceSummary({ employees, unavailabilities, pairConstraints, shiftTypes });
  return (
    <div className="reference-manager">
      <div className="subtle-box">{summary}</div>
      <ReferenceEmployeeTable
        employees={employees}
        onAdd={onAddEmployee}
        onChange={onEmployeesChange}
        onDelete={onDeleteEmployee}
        onSave={onSaveEmployee}
        roles={roles}
      />
      <ReferenceUnavailabilityTable
        employees={employees}
        onAdd={onAddUnavailability}
        onChange={onUnavailabilitiesChange}
        onDelete={onDeleteUnavailability}
        onSave={onSaveUnavailability}
        rows={unavailabilities}
      />
      <ReferencePairTable
        employees={employees}
        onAdd={onAddPairConstraint}
        onChange={onPairConstraintsChange}
        onDelete={onDeletePairConstraint}
        onSave={onSavePairConstraint}
        rows={pairConstraints}
      />
      <ReferenceShiftTypeTable
        onAdd={onAddShiftType}
        onChange={onShiftTypesChange}
        onDelete={onDeleteShiftType}
        onSave={onSaveShiftType}
        rows={shiftTypes}
      />
    </div>
  );
}

function ReferenceEmployeeTable({
  employees,
  onAdd,
  onChange,
  onDelete,
  onSave,
  roles,
}: {
  employees: ManagedEmployee[];
  onAdd: () => void;
  onChange: (employees: ManagedEmployee[]) => void;
  onDelete: (employeeId: string) => void;
  onSave: (employee: ManagedEmployee) => void;
  roles: Role[];
}) {
  return (
    <div className="table-editor">
      <div className="table-editor-heading">
        <SectionTitle title="직원 CRUD" />
        <button onClick={onAdd} type="button"><Plus size={15} />추가</button>
      </div>
      <div className="table-scroll">
        <table className="editor-table">
          <thead>
            <tr>
              <th>코드</th>
              <th>이름</th>
              <th>역할</th>
              <th>주 최대</th>
              <th>활성</th>
              <th>저장</th>
              <th>삭제</th>
            </tr>
          </thead>
          <tbody>
            {employees.map((employee) => (
              <tr key={employee.id}>
                <td>
                  <input
                    onChange={(event) =>
                      onChange(employees.map((item) => item.id === employee.id ? { ...item, employee_code: event.target.value } : item))
                    }
                    value={employee.employee_code}
                  />
                </td>
                <td>
                  <input
                    onChange={(event) =>
                      onChange(employees.map((item) => item.id === employee.id ? { ...item, name: event.target.value } : item))
                    }
                    value={employee.name}
                  />
                </td>
                <td>
                  <div className="role-toggle-list">
                    {roles.map((role) => (
                      <label className="inline-checkbox" key={role.id}>
                        <input
                          checked={employee.role_names.includes(role.name)}
                          onChange={(event) =>
                            onChange(employees.map((item) => item.id === employee.id
                              ? {
                                  ...item,
                                  role_names: withEmployeeRole(item.role_names, role.name, event.target.checked),
                                }
                              : item))
                          }
                          type="checkbox"
                        />
                        <span>{role.name}</span>
                      </label>
                    ))}
                  </div>
                </td>
                <td>
                  <input
                    min={1}
                    onChange={(event) =>
                      onChange(employees.map((item) => item.id === employee.id ? { ...item, max_shifts_per_week: Number(event.target.value) } : item))
                    }
                    type="number"
                    value={employee.max_shifts_per_week ?? 5}
                  />
                </td>
                <td>
                  <label className="inline-checkbox">
                    <input
                      checked={employee.active}
                      onChange={(event) =>
                        onChange(employees.map((item) => item.id === employee.id ? { ...item, active: event.target.checked } : item))
                      }
                      type="checkbox"
                    />
                    <span>사용</span>
                  </label>
                </td>
                <td><button onClick={() => onSave(employee)} type="button">저장</button></td>
                <td><button className="icon-button danger-button" onClick={() => onDelete(employee.id)} type="button"><Trash2 size={15} /></button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ReferenceUnavailabilityTable({
  employees,
  onAdd,
  onChange,
  onDelete,
  onSave,
  rows,
}: {
  employees: ManagedEmployee[];
  onAdd: () => void;
  onChange: (rows: ManagedUnavailability[]) => void;
  onDelete: (unavailabilityId: string) => void;
  onSave: (row: ManagedUnavailability) => void;
  rows: ManagedUnavailability[];
}) {
  return (
    <div className="table-editor">
      <div className="table-editor-heading">
        <SectionTitle title="휴가/출장 CRUD" />
        <button disabled={!employees.length} onClick={onAdd} type="button"><Plus size={15} />추가</button>
      </div>
      <div className="table-scroll">
        <table className="editor-table">
          <thead>
            <tr>
              <th>직원</th>
              <th>시작일</th>
              <th>종료일</th>
              <th>유형</th>
              <th>예외</th>
              <th>메모</th>
              <th>저장</th>
              <th>삭제</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>
                  <select
                    onChange={(event) => onChange(rows.map((item) => item.id === row.id ? { ...item, employee_id: event.target.value } : item))}
                    value={row.employee_id}
                  >
                    {employees.map((employee) => (
                      <option key={employee.id} value={employee.id}>{employee.employee_code} · {employee.name}</option>
                    ))}
                  </select>
                </td>
                <td><input onChange={(event) => onChange(rows.map((item) => item.id === row.id ? { ...item, starts_at: `${event.target.value}T00:00:00+09:00` } : item))} type="date" value={dateInputValue(row.starts_at)} /></td>
                <td><input onChange={(event) => onChange(rows.map((item) => item.id === row.id ? { ...item, ends_at: `${event.target.value}T00:00:00+09:00` } : item))} type="date" value={dateInputValue(row.ends_at)} /></td>
                <td>
                  <select onChange={(event) => onChange(rows.map((item) => item.id === row.id ? { ...item, type: event.target.value } : item))} value={row.type}>
                    {VACATION_TYPE_OPTIONS.map((type) => <option key={type} value={type}>{vacationTypeLabel(type)}</option>)}
                  </select>
                </td>
                <td>
                  <label className="inline-checkbox">
                    <input
                      checked={row.override_allowed}
                      onChange={(event) => onChange(rows.map((item) => item.id === row.id ? { ...item, override_allowed: event.target.checked } : item))}
                      type="checkbox"
                    />
                    <span>허용</span>
                  </label>
                </td>
                <td>
                  <input
                    onChange={(event) => onChange(rows.map((item) => item.id === row.id ? { ...item, note: event.target.value || null } : item))}
                    value={row.note ?? ""}
                  />
                </td>
                <td><button onClick={() => onSave(row)} type="button">저장</button></td>
                <td><button className="icon-button danger-button" onClick={() => onDelete(row.id)} type="button"><Trash2 size={15} /></button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ReferencePairTable({
  employees,
  onAdd,
  onChange,
  onDelete,
  onSave,
  rows,
}: {
  employees: ManagedEmployee[];
  onAdd: () => void;
  onChange: (rows: ManagedPairConstraint[]) => void;
  onDelete: (pairConstraintId: string) => void;
  onSave: (row: ManagedPairConstraint) => void;
  rows: ManagedPairConstraint[];
}) {
  return (
    <div className="table-editor">
      <div className="table-editor-heading">
        <SectionTitle title="상극/선호 CRUD" />
        <button disabled={employees.length < 2} onClick={onAdd} type="button"><Plus size={15} />추가</button>
      </div>
      <div className="table-scroll">
        <table className="editor-table">
          <thead>
            <tr>
              <th>직원 A</th>
              <th>직원 B</th>
              <th>유형</th>
              <th>심각도</th>
              <th>예외</th>
              <th>활성</th>
              <th>저장</th>
              <th>삭제</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td><EmployeeIdSelect employees={employees} onChange={(employeeId) => onChange(rows.map((item) => item.id === row.id ? { ...item, employee_a_id: employeeId } : item))} value={row.employee_a_id} /></td>
                <td><EmployeeIdSelect employees={employees} onChange={(employeeId) => onChange(rows.map((item) => item.id === row.id ? { ...item, employee_b_id: employeeId } : item))} value={row.employee_b_id} /></td>
                <td>
                  <select onChange={(event) => onChange(rows.map((item) => item.id === row.id ? { ...item, type: event.target.value } : item))} value={row.type}>
                    <option value="blocked">상극</option>
                    <option value="avoid">회피</option>
                    <option value="prefer">선호</option>
                  </select>
                </td>
                <td>
                  <select onChange={(event) => onChange(rows.map((item) => item.id === row.id ? { ...item, severity: event.target.value } : item))} value={row.severity}>
                    <option value="low">낮음</option>
                    <option value="medium">보통</option>
                    <option value="high">높음</option>
                    <option value="critical">치명</option>
                  </select>
                </td>
                <td>
                  <label className="inline-checkbox">
                    <input
                      checked={row.override_allowed}
                      onChange={(event) => onChange(rows.map((item) => item.id === row.id ? { ...item, override_allowed: event.target.checked } : item))}
                      type="checkbox"
                    />
                    <span>허용</span>
                  </label>
                </td>
                <td>
                  <label className="inline-checkbox">
                    <input
                      checked={row.active}
                      onChange={(event) => onChange(rows.map((item) => item.id === row.id ? { ...item, active: event.target.checked } : item))}
                      type="checkbox"
                    />
                    <span>사용</span>
                  </label>
                </td>
                <td><button onClick={() => onSave(row)} type="button">저장</button></td>
                <td><button className="icon-button danger-button" onClick={() => onDelete(row.id)} type="button"><Trash2 size={15} /></button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ReferenceShiftTypeTable({
  onAdd,
  onChange,
  onDelete,
  onSave,
  rows,
}: {
  onAdd: () => void;
  onChange: (rows: ManagedShiftType[]) => void;
  onDelete: (shiftTypeId: string) => void;
  onSave: (row: ManagedShiftType) => void;
  rows: ManagedShiftType[];
}) {
  return (
    <div className="table-editor">
      <div className="table-editor-heading">
        <SectionTitle title="근무유형 CRUD" />
        <button onClick={onAdd} type="button"><Plus size={15} />추가</button>
      </div>
      <div className="table-scroll">
        <table className="editor-table">
          <thead>
            <tr>
              <th>이름</th>
              <th>시작</th>
              <th>종료</th>
              <th>요일</th>
              <th>자정</th>
              <th>활성</th>
              <th>필요 인원</th>
              <th>저장</th>
              <th>삭제</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td><input onChange={(event) => onChange(rows.map((item) => item.id === row.id ? { ...item, name: event.target.value } : item))} value={row.name} /></td>
                <td><input onChange={(event) => onChange(rows.map((item) => item.id === row.id ? { ...item, local_start_time: event.target.value } : item))} type="time" value={row.local_start_time} /></td>
                <td><input onChange={(event) => onChange(rows.map((item) => item.id === row.id ? { ...item, local_end_time: event.target.value } : item))} type="time" value={row.local_end_time} /></td>
                <td>
                  <div className="weekday-toggle-list">
                    {[0, 1, 2, 3, 4, 5, 6].map((weekday) => (
                      <label className="inline-checkbox" key={weekday}>
                        <input
                          checked={row.active_weekdays.includes(weekday)}
                          disabled={row.active_weekdays.length === 1 && row.active_weekdays.includes(weekday)}
                          onChange={(event) =>
                            onChange(rows.map((item) => item.id === row.id
                              ? { ...item, active_weekdays: toggleWeekday(item.active_weekdays, weekday, event.target.checked) }
                              : item))
                          }
                          type="checkbox"
                        />
                        <span>{weekdayLabel(weekday)}</span>
                      </label>
                    ))}
                  </div>
                </td>
                <td>
                  <label className="inline-checkbox">
                    <input
                      checked={row.crosses_midnight}
                      onChange={(event) => onChange(rows.map((item) => item.id === row.id ? { ...item, crosses_midnight: event.target.checked } : item))}
                      type="checkbox"
                    />
                    <span>넘김</span>
                  </label>
                </td>
                <td>
                  <label className="inline-checkbox">
                    <input
                      checked={row.active}
                      onChange={(event) => onChange(rows.map((item) => item.id === row.id ? { ...item, active: event.target.checked } : item))}
                      type="checkbox"
                    />
                    <span>사용</span>
                  </label>
                </td>
                <td>
                  <div className="requirement-list">
                    {row.requirements.map((requirement) => (
                      <div className="requirement-row" key={requirement.id}>
                        <span>{requirement.role_name}</span>
                        <input
                          min={1}
                          onChange={(event) =>
                            onChange(rows.map((item) => item.id === row.id
                              ? {
                                  ...item,
                                  requirements: item.requirements.map((entry) => entry.id === requirement.id
                                    ? { ...entry, required_count: Number(event.target.value) }
                                    : entry),
                                }
                              : item))
                          }
                          type="number"
                          value={requirement.required_count}
                        />
                        <input
                          min={0}
                          onChange={(event) =>
                            onChange(rows.map((item) => item.id === row.id
                              ? {
                                  ...item,
                                  requirements: item.requirements.map((entry) => entry.id === requirement.id
                                    ? { ...entry, unfilled_weight_override: parseOptionalNumber(event.target.value) }
                                    : entry),
                                }
                              : item))
                          }
                          placeholder="penalty"
                          type="number"
                          value={requirement.unfilled_weight_override ?? ""}
                        />
                      </div>
                    ))}
                  </div>
                </td>
                <td><button onClick={() => onSave(row)} type="button">저장</button></td>
                <td><button className="icon-button danger-button" onClick={() => onDelete(row.id)} type="button"><Trash2 size={15} /></button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function EmployeeIdSelect({
  employees,
  onChange,
  value,
}: {
  employees: ManagedEmployee[];
  onChange: (employeeId: string) => void;
  value: string;
}) {
  return (
    <select onChange={(event) => onChange(event.target.value)} value={value}>
      {employees.map((employee) => (
        <option key={employee.id} value={employee.id}>{employee.employee_code} · {employee.name}</option>
      ))}
    </select>
  );
}

function PolicyManager({
  onChange,
  onSave,
  policy,
}: {
  onChange: (policy: SchedulePolicy) => void;
  onSave: () => void;
  policy: SchedulePolicy;
}) {
  return (
    <div className="policy-manager">
      <SectionTitle title="정책 설정" />
      <label className="field-row field-row-wide">
        <span>정책명</span>
        <input onChange={(event) => onChange({ ...policy, name: event.target.value })} value={policy.name} />
      </label>
      <div className="field-grid">
        <NumberPolicyInput field="min_rest_hours" label="최소 휴식" onChange={onChange} policy={policy} />
        <NumberPolicyInput field="max_consecutive_shifts" label="최대 연속" onChange={onChange} policy={policy} />
        <NumberPolicyInput field="max_shifts_per_week" label="주 최대" onChange={onChange} policy={policy} />
        <NumberPolicyInput field="weekend_shift_limit_per_month" label="주말 제한" onChange={onChange} policy={policy} />
        <NumberPolicyInput field="night_shift_limit_per_month" label="야간 제한" onChange={onChange} policy={policy} />
        <NumberPolicyInput field="default_unfilled_requirement_weight" label="미배정 penalty" onChange={onChange} policy={policy} />
        <NumberPolicyInput field="weight_workload_imbalance" label="공정성 가중치" onChange={onChange} policy={policy} />
        <NumberPolicyInput field="weight_pair_avoid_violation" label="회피 조합 가중치" onChange={onChange} policy={policy} />
      </div>
      <div className="subtle-box">{unfilledPolicyLabel(policy.unfilled_policy)} · LLM은 설명 레이어로만 사용합니다.</div>
      <button className="primary-action" onClick={onSave} type="button">정책 저장</button>
    </div>
  );
}

function NumberPolicyInput({
  field,
  label,
  onChange,
  policy,
}: {
  field: keyof Pick<
    SchedulePolicy,
    | "min_rest_hours"
    | "max_consecutive_shifts"
    | "max_shifts_per_week"
    | "weekend_shift_limit_per_month"
    | "night_shift_limit_per_month"
    | "default_unfilled_requirement_weight"
    | "weight_workload_imbalance"
    | "weight_pair_avoid_violation"
  >;
  label: string;
  onChange: (policy: SchedulePolicy) => void;
  policy: SchedulePolicy;
}) {
  return (
    <label className="field-row">
      <span>{label}</span>
      <input
        min={0}
        onChange={(event) => onChange(normalizePolicy({ ...policy, [field]: Number(event.target.value) }))}
        type="number"
        value={policy[field]}
      />
    </label>
  );
}

function ImportManager({
  content,
  importType,
  onApply,
  onContentChange,
  onPreview,
  onTypeChange,
  preview,
}: {
  content: string;
  importType: ImportType;
  onApply: () => void;
  onContentChange: (content: string) => void;
  onPreview: () => void;
  onTypeChange: (type: ImportType) => void;
  preview: {
    valid: boolean;
    rows: Record<string, string>[];
    errors: { field: string | null; row_no: number | null; message: string }[];
  } | null;
}) {
  return (
    <div className="import-manager">
      <SectionTitle title="Excel CSV/TSV 가져오기" />
      <label className="field-row field-row-wide">
        <span>대상</span>
        <select onChange={(event) => onTypeChange(event.target.value as ImportType)} value={importType}>
          <option value="employees">직원</option>
          <option value="unavailabilities">휴가/출장</option>
          <option value="pair_constraints">상극 조합</option>
          <option value="policy">정책</option>
        </select>
      </label>
      <label className="field-row field-row-wide">
        <span>Excel CSV/TSV 파일</span>
        <input
          accept=".csv,.tsv,.txt,text/csv,text/tab-separated-values"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (!file) return;
            void file.text().then(onContentChange);
          }}
          type="file"
        />
      </label>
      <textarea
        onChange={(event) => onContentChange(event.target.value)}
        spellCheck={false}
        value={content}
      />
      <div className="button-row">
        <button onClick={onPreview} type="button">미리보기</button>
        <button className="primary-action" disabled={!preview?.valid} onClick={onApply} type="button">반영</button>
      </div>
      {preview ? (
        <div className={preview.valid ? "success-box" : "validation-list"}>
          {preview.valid ? (
            <>
              <div>{preview.rows.length}행을 반영할 수 있습니다.</div>
              <div className="table-scroll">
                <table className="editor-table import-preview-table">
                  <thead>
                    <tr>
                      {Object.keys(preview.rows[0] ?? {}).map((header) => (
                        <th key={header}>{header}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.rows.slice(0, 5).map((row, rowIndex) => (
                      <tr key={rowIndex}>
                        {Object.keys(preview.rows[0] ?? {}).map((header) => (
                          <td key={`${rowIndex}-${header}`}>{row[header]}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : null}
          {!preview.valid
            ? preview.errors.map((error) => (
                <div className="validation-row blocking" key={`${error.row_no}-${error.field}-${error.message}`}>
                  <strong>{error.row_no ?? "-"}행 {error.field ?? ""}</strong>
                  <span>{error.message}</span>
                </div>
              ))
            : null}
        </div>
      ) : null}
    </div>
  );
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
  const periodEndDate = periodEndFor(config.startDate, config.periodDays);
  const maxEndDate = addDaysIso(config.startDate, MAX_PERIOD_DAYS - 1);
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
          <span>시작일</span>
          <input
            disabled={disabled}
            onChange={(event) =>
              onChange({
                startDate: event.target.value,
                periodDays: periodDaysForRange(event.target.value, periodEndDate),
              })
            }
            type="date"
            value={config.startDate}
          />
        </label>
        <label className="field-row">
          <span>마감일</span>
          <input
            disabled={disabled}
            max={maxEndDate}
            min={config.startDate}
            onChange={(event) =>
              onChange({ periodDays: periodDaysForRange(config.startDate, event.target.value) })
            }
            type="date"
            value={periodEndDate}
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
  if (response.status === 204) {
    return null as T;
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

function dateInputValue(value: string) {
  return value.slice(0, 10);
}

function withEmployeeRole(roleNames: string[], roleName: string, enabled: boolean) {
  if (enabled) return roleNames.includes(roleName) ? roleNames : [...roleNames, roleName];
  return roleNames.filter((currentRoleName) => currentRoleName !== roleName);
}

function toggleWeekday(weekdays: number[], weekday: number, enabled: boolean) {
  if (enabled) return Array.from(new Set([...weekdays, weekday])).sort((left, right) => left - right);
  const nextWeekdays = weekdays.filter((currentWeekday) => currentWeekday !== weekday);
  return nextWeekdays.length ? nextWeekdays : weekdays;
}

function weekdayLabel(weekday: number) {
  return ["월", "화", "수", "목", "금", "토", "일"][weekday] ?? String(weekday);
}

function parseOptionalNumber(value: string) {
  return value === "" ? null : Number(value);
}
