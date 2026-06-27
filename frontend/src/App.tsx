import {
  AlertTriangle,
  Building2,
  CheckCircle2,
  ClipboardList,
  Clock3,
  Download,
  FileSpreadsheet,
  LogIn,
  LogOut,
  Plus,
  Play,
  RefreshCw,
  ShieldCheck,
  Trash2,
  Users,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
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
import {
  bytesToBase64,
  isXlsxFileName,
  parseDelimitedText,
  validateImportRows,
  type ImportFormat,
  type ImportPreview,
  type ImportType,
} from "./importPreview";
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
import {
  changedFairnessRows,
  changeTypeLabel,
  comparisonSummaryMetrics,
  deltaLabel,
  issueChangeTypeLabel,
  type ScheduleRunComparison,
  type ScheduleRunHistory,
} from "./runComparison";
import {
  auditActionLabel,
  fairnessDeltaLabel,
  fairnessSpreadLabel,
  longTermFairnessSourceLabel,
  sortedLongTermFairnessRows,
  type LongTermFairnessSource,
} from "./visibility";
import {
  acknowledgementStatusLabel,
  budgetStatusLabel,
  complianceSeverityLabel,
  employeeLinkTokenFromFragment,
  employeeNotificationRows,
  employeePublicationAcknowledgementPath,
  employeePublicationContextPath,
  employeeRequestStatusLabel,
  employeeScheduleCards,
  employeeScheduleCardsFromPublicContext,
  isSignedEmployeePublicationUrl,
  pendingEmployeeRequestQueue,
  ragConfidenceLabel,
  ragDocumentRows,
  type EmployeeScheduleCard,
  type PublicEmployeeScheduleCard,
} from "./roadmap";
import {
  authHeaders,
  sessionLabel,
  sessionVerificationPath,
  type AuthSession,
  type SessionIdentity,
} from "./authSession";
import { apiErrorMessage } from "./apiErrors";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const AUTH_SESSION_STORAGE_KEY = "workscheduleai.authSession";
const TERMINAL_RUN_STATUSES = new Set(["succeeded", "infeasible"]);
const FAILED_RUN_STATUSES = new Set(["failed", "canceled"]);
const RESULT_POLL_INTERVAL_MS = 1000;
const RESULT_POLL_ATTEMPTS = 60;
let activeAuthSession: AuthSession | null = loadStoredAuthSession();

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
  starts_at: string;
  ends_at: string;
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

type LongTermFairnessRow = {
  employee_id: string;
  employee_code: string;
  employee_name: string;
  assignment_count: number;
  night_count: number;
  weekend_count: number;
  role_counts: Record<string, number>;
  delta_from_average: number;
};

type LongTermFairnessSummary = {
  organization_id: string;
  source: LongTermFairnessSource;
  period_start: string | null;
  period_end: string | null;
  schedule_count: number;
  publication_count: number;
  run_count: number;
  employee_count: number;
  total_assignments: number;
  average_assignments: number;
  min_assignments: number;
  max_assignments: number;
  spread: number;
  rows: LongTermFairnessRow[];
};

type EmployeeRequestItem = {
  id: string;
  employee_id: string;
  type: string;
  status: string;
  starts_at: string;
  ends_at: string;
  note: string | null;
};

type PublicationAcknowledgementItem = {
  id: string;
  publication_id: string;
  employee_id: string;
  status: string;
  acknowledged_at: string | null;
};

type PublicationAcknowledgementList = {
  organization_id: string;
  publication_id: string;
  acknowledgements: PublicationAcknowledgementItem[];
};

type PublicationNotificationItem = {
  id: string;
  publication_id: string;
  employee_id: string;
  notification_type: string;
  channel: string;
  status: string;
  created_at: string;
};

type EmployeePublicationContext = {
  organization_id: string;
  publication_id: string;
  schedule_run_id: string;
  employee_id: string;
  employee_name: string;
  period_start: string;
  period_end: string;
  published_at: string;
  schedule_cards: PublicEmployeeScheduleCard[];
  acknowledgement: PublicationAcknowledgementItem;
  notifications: PublicationNotificationItem[];
};

type ComplianceWarningItem = {
  code: string;
  severity: string;
  publish_blocking: boolean;
  employee_id: string | null;
  employee_name: string | null;
  slot_id: string | null;
  week_key: string | null;
  snapshot_hash: string;
  instance_key: string;
  message: string;
  hours: number | null;
};

type ComplianceWarningResponse = {
  legal_disclaimer: string;
  warnings: ComplianceWarningItem[];
};

type RagEvidenceItem = {
  source_type: string;
  document_title: string;
  excerpt: string;
  checked_at: string;
  confidence: number;
};

type RagGrounding = {
  status: string;
  confidence: string;
  evidence: RagEvidenceItem[];
  safety_notes: string[];
};

type RagDocumentItem = {
  id: string;
  organization_id: string;
  source_type: string;
  document_title: string;
  checked_at: string;
  chunk_count: number;
};

type RagDocumentList = {
  organization_id: string;
  documents: RagDocumentItem[];
};

type DemandCostPreview = {
  required_staff_count: number;
  planned_staff_count: number;
  under_staffed_count: number;
  over_staffed_count: number;
  planned_cost_cents: number;
  budget_amount_cents: number | null;
  budget_status: string;
};

type DemandDriverDraft = {
  localDate: string;
  segment: string;
  demandCount: string;
  requiredStaffCount: string;
};

type LaborBudgetDraft = {
  periodStart: string;
  periodEnd: string;
  budgetAmountWon: string;
};

type LoginDraft = {
  email: string;
  password: string;
  organizationId: string;
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
  const [importFormat, setImportFormat] = useState<ImportFormat>("delimited");
  const [importContent, setImportContent] = useState(
    "employee_code,name,roles,max_shifts_per_week\nE013,신규직원,사수|부사수,5",
  );
  const [importContentBase64, setImportContentBase64] = useState("");
  const [importSheetName, setImportSheetName] = useState("");
  const [importPreview, setImportPreview] = useState<ImportPreview | null>(null);
  const [manualEditDraft, setManualEditDraft] = useState<ManualEditDraft | null>(null);
  const [manualEditValidation, setManualEditValidation] = useState<ManualEditValidation | null>(null);
  const [demo, setDemo] = useState<DemoState | null>(null);
  const [result, setResult] = useState<ScheduleResult | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([]);
  const [fairness, setFairness] = useState<FairnessSummary | null>(null);
  const [longTermFairness, setLongTermFairness] = useState<LongTermFairnessSummary | null>(null);
  const [longTermFairnessSource, setLongTermFairnessSource] =
    useState<LongTermFairnessSource>("publications");
  const [longTermPeriodStart, setLongTermPeriodStart] = useState(
    DEFAULT_SCENARIO_CONFIG.startDate,
  );
  const [longTermPeriodEnd, setLongTermPeriodEnd] = useState(
    periodEndFor(DEFAULT_SCENARIO_CONFIG.startDate, DEFAULT_SCENARIO_CONFIG.periodDays),
  );
  const [runHistory, setRunHistory] = useState<ScheduleRunHistory["runs"]>([]);
  const [comparisonBaseRunId, setComparisonBaseRunId] = useState("");
  const [comparisonCandidateRunId, setComparisonCandidateRunId] = useState("");
  const [runComparison, setRunComparison] = useState<ScheduleRunComparison | null>(null);
  const [employeeRequests, setEmployeeRequests] = useState<EmployeeRequestItem[]>([]);
  const [publicationAcknowledgements, setPublicationAcknowledgements] = useState<
    PublicationAcknowledgementItem[]
  >([]);
  const [complianceWarningSummary, setComplianceWarningSummary] =
    useState<ComplianceWarningResponse | null>(null);
  const [complianceOverrideReasons, setComplianceOverrideReasons] = useState<
    Record<string, string>
  >({});
  const [ragGrounding, setRagGrounding] = useState<RagGrounding | null>(null);
  const [ragDocuments, setRagDocuments] = useState<RagDocumentItem[]>([]);
  const [demandPreview, setDemandPreview] = useState<DemandCostPreview | null>(null);
  const [employeePublicationContext, setEmployeePublicationContext] =
    useState<EmployeePublicationContext | null>(null);
  const [employeeLinkToken, setEmployeeLinkToken] = useState<string | null>(null);
  const [authSession, setAuthSession] = useState<AuthSession | null>(() => activeAuthSession);
  const [loginDraft, setLoginDraft] = useState<LoginDraft>({
    email: "",
    password: "",
    organizationId: "",
  });
  const [demandDriverDraft, setDemandDriverDraft] = useState<DemandDriverDraft>({
    localDate: DEFAULT_SCENARIO_CONFIG.startDate,
    segment: "day",
    demandCount: "120",
    requiredStaffCount: "4",
  });
  const [laborBudgetDraft, setLaborBudgetDraft] = useState<LaborBudgetDraft>({
    periodStart: DEFAULT_SCENARIO_CONFIG.startDate,
    periodEnd: periodEndFor(DEFAULT_SCENARIO_CONFIG.startDate, DEFAULT_SCENARIO_CONFIG.periodDays),
    budgetAmountWon: "800000",
  });
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
  useEffect(() => {
    activeAuthSession = authSession;
    if (authSession) {
      window.sessionStorage.setItem(AUTH_SESSION_STORAGE_KEY, JSON.stringify(authSession));
    } else {
      window.sessionStorage.removeItem(AUTH_SESSION_STORAGE_KEY);
    }
  }, [authSession]);
  useEffect(() => {
    if (!authSession) return;
    let canceled = false;
    const sessionToVerify = authSession;
    async function verifySession() {
      try {
        await api<SessionIdentity>(sessionVerificationPath(sessionToVerify));
      } catch {
        if (!canceled) {
          setAuthSession(null);
          setError("저장된 세션이 만료되어 로그아웃되었습니다.");
        }
      }
    }
    void verifySession();
    return () => {
      canceled = true;
    };
  }, [authSession]);
  useEffect(() => {
    if (!workspaceOrganization || loginDraft.organizationId) return;
    setLoginDraft((current) => ({ ...current, organizationId: workspaceOrganization.id }));
  }, [loginDraft.organizationId, workspaceOrganization]);
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
  const mobileEmployee = employeePublicationContext
    ? {
        id: employeePublicationContext.employee_id,
        employee_code: employeePublicationContext.employee_id,
        name: employeePublicationContext.employee_name,
      }
    : demo?.employees[0] ?? null;
  const mobileEmployeeCards = useMemo(() => {
    if (employeePublicationContext) {
      return employeeScheduleCardsFromPublicContext(employeePublicationContext.schedule_cards);
    }
    if (!mobileEmployee || !result) return [];
    return employeeScheduleCards(
      mobileEmployee.id,
      result.slots,
      result.assignments,
      result.requirements,
    );
  }, [employeePublicationContext, mobileEmployee, result]);
  const mobilePublication = employeePublicationContext
    ? {
        id: employeePublicationContext.publication_id,
        status: "published",
        published_at: employeePublicationContext.published_at,
      }
    : result?.publication ?? null;
  const mobileNotifications = employeePublicationContext
    ? employeeNotificationRows(employeePublicationContext.notifications)
    : [];

  useEffect(() => {
    if (!window.location.pathname.startsWith("/employee") || demo || employeePublicationContext) {
      return;
    }
    const params = new URLSearchParams(window.location.search);
    const organizationId = params.get("organizationId") ?? "";
    const publicationId = params.get("publicationId") ?? "";
    const runId = params.get("runId") ?? "";
    const employeeId = params.get("employeeId") ?? "";
    const fragmentToken = employeeLinkTokenFromFragment(window.location.hash);
    const signedPublicationUrl = isSignedEmployeePublicationUrl(window.location.search);
    if (fragmentToken && organizationId && publicationId && employeeId) {
      window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
    }
    if (!organizationId || !employeeId) return;
    if (signedPublicationUrl && !fragmentToken) {
      setError("직원 링크 토큰이 없습니다. 발급받은 링크를 다시 열어주세요.");
      return;
    }
    let canceled = false;
    async function loadEmployeeContext() {
      setBusy("employee-load");
      setError(null);
      try {
        if (fragmentToken && publicationId) {
          const context = await api<EmployeePublicationContext>(
            employeePublicationContextPath({
              employeeId,
              organizationId,
              publicationId,
            }),
            {
              headers: { Authorization: `Bearer ${fragmentToken}` },
            },
          );
          if (canceled) return;
          setEmployeeLinkToken(fragmentToken);
          setEmployeePublicationContext(context);
          setPublicationAcknowledgements([context.acknowledgement]);
          setEmployeeRequests([]);
          setResult(null);
          return;
        }
        if (!runId) return;
        const [employees, nextResult] = await Promise.all([
          api<ManagedEmployee[]>(`/organizations/${organizationId}/employees`),
          fetchResult(organizationId, runId),
        ]);
        if (canceled) return;
        const employee = employees.find((item) => item.id === employeeId);
        if (!employee) throw new Error("직원 정보를 찾을 수 없습니다.");
        setDemo({
          organizationId,
          runId,
          employees: [{
            id: employee.id,
            employee_code: employee.employee_code,
            name: employee.name,
          }],
        });
        setResult(nextResult);
        await refreshRoadmapPanels(organizationId, runId, nextResult);
      } catch (caught) {
        if (!canceled) setError(messageFromError(caught));
      } finally {
        if (!canceled) setBusy(null);
      }
    }
    void loadEmployeeContext();
    return () => {
      canceled = true;
    };
  }, [demo, employeePublicationContext]);

  function clearRunState() {
    setDemo(null);
    setResult(null);
    setAuditLogs([]);
    setFairness(null);
    setLongTermFairness(null);
    setRunHistory([]);
    setComparisonBaseRunId("");
    setComparisonCandidateRunId("");
    setRunComparison(null);
    setEmployeeRequests([]);
    setPublicationAcknowledgements([]);
    setComplianceWarningSummary(null);
    setComplianceOverrideReasons({});
    setRagGrounding(null);
    setRagDocuments([]);
    setDemandPreview(null);
    setEmployeePublicationContext(null);
    setEmployeeLinkToken(null);
    setDownloadState("대기");
    setError(null);
  }

  function updateScenario(patch: Partial<ScenarioConfig>) {
    const nextScenario = normalizeScenarioConfig({ ...scenario, ...patch });
    setScenario(nextScenario);
    if (patch.startDate !== undefined || patch.periodDays !== undefined) {
      setLongTermPeriodStart(nextScenario.startDate);
      setLongTermPeriodEnd(periodEndFor(nextScenario.startDate, nextScenario.periodDays));
      setLongTermFairness(null);
    }
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

  async function loginSession() {
    setBusy("login");
    setError(null);
    try {
      const session = await api<AuthSession>("/auth/login", {
        method: "POST",
        body: {
          email: loginDraft.email,
          password: loginDraft.password,
          organization_id: loginDraft.organizationId,
        },
      });
      setAuthSession(session);
      setLoginDraft((current) => ({ ...current, password: "" }));
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setBusy(null);
    }
  }

  function logoutSession() {
    setAuthSession(null);
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
      await refreshRoadmapPanels(organization.id, run.id, nextResult);
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
      const nextResult = await fetchResult(demo.organizationId, demo.runId);
      setResult(nextResult);
      await refreshVisibility(demo.organizationId, demo.runId);
      await refreshRoadmapPanels(demo.organizationId, demo.runId, nextResult);
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
      const nextResult = await waitForCompletedResult(demo.organizationId, demo.runId);
      setResult(nextResult);
      await refreshVisibility(demo.organizationId, demo.runId);
      await refreshRoadmapPanels(demo.organizationId, demo.runId, nextResult);
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
      const nextResult = await fetchResult(demo.organizationId, demo.runId);
      setResult(nextResult);
      await refreshVisibility(demo.organizationId, demo.runId);
      await refreshRoadmapPanels(demo.organizationId, demo.runId, nextResult);
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
        { headers: authHeaders(activeAuthSession) },
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

  async function exportAuditLogs() {
    const organizationId = demo?.organizationId ?? workspaceOrganization?.id;
    if (!organizationId) return;
    setBusy("audit-export");
    setError(null);
    try {
      const response = await fetch(
        `${API_BASE}/operations/organizations/${organizationId}/audit-logs/export`,
        { headers: authHeaders(activeAuthSession) },
      );
      if (!response.ok) throw new Error(`Audit export failed: ${response.status}`);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `work_schedule_audit_${organizationId}.csv`;
      anchor.click();
      URL.revokeObjectURL(url);
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
      const nextResult = await fetchResult(demo.organizationId, demo.runId);
      setResult(nextResult);
      await refreshVisibility(demo.organizationId, demo.runId);
      await refreshRoadmapPanels(demo.organizationId, demo.runId, nextResult);
      await refreshReferenceData(demo.organizationId);
      setManualEditDraft(null);
      setManualEditValidation(null);
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setBusy(null);
    }
  }

  async function loadRunComparison(
    baseRunId = comparisonBaseRunId,
    candidateRunId = comparisonCandidateRunId,
  ) {
    if (!demo || !baseRunId || !candidateRunId || baseRunId === candidateRunId) return;
    setBusy("compare");
    setError(null);
    try {
      const params = new URLSearchParams({
        base_run_id: baseRunId,
        candidate_run_id: candidateRunId,
      });
      const comparison = await api<ScheduleRunComparison>(
        `/organizations/${demo.organizationId}/schedule-runs/compare?${params.toString()}`,
      );
      setRunComparison(comparison);
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setBusy(null);
    }
  }

  async function loadLongTermFairness({
    organizationId = demo?.organizationId ?? workspaceOrganization?.id,
    showBusy = true,
  }: {
    organizationId?: string;
    showBusy?: boolean;
  } = {}) {
    if (!organizationId) return;
    if (showBusy) setBusy("long-term-fairness");
    if (showBusy) setError(null);
    try {
      const params = new URLSearchParams({
        source: longTermFairnessSource,
        period_start: longTermPeriodStart,
        period_end: longTermPeriodEnd,
      });
      const summary = await api<LongTermFairnessSummary>(
        `/operations/organizations/${organizationId}/fairness/long-term?${params.toString()}`,
      );
      setLongTermFairness(summary);
    } catch (caught) {
      setLongTermFairness(null);
      if (showBusy) setError(messageFromError(caught));
    } finally {
      if (showBusy) setBusy(null);
    }
  }

  async function refreshRoadmapPanels(
    organizationId: string,
    runId: string,
    activeResult = result,
  ) {
    const [requestResponse, complianceResponse, acknowledgementResponse] =
      await Promise.allSettled([
        api<EmployeeRequestItem[]>(`/organizations/${organizationId}/employee-requests`),
        api<ComplianceWarningResponse>(
          `/organizations/${organizationId}/schedule-runs/${runId}/compliance-warnings`,
        ),
        activeResult?.publication
          ? api<PublicationAcknowledgementList>(
              `/organizations/${organizationId}/schedule-publications/${activeResult.publication.id}/acknowledgements`,
            )
          : Promise.resolve({
              acknowledgements: [],
              organization_id: organizationId,
              publication_id: "",
            }),
      ]);

    setEmployeeRequests(
      requestResponse.status === "fulfilled" ? requestResponse.value : [],
    );
    setComplianceWarningSummary(
      complianceResponse.status === "fulfilled" ? complianceResponse.value : null,
    );
    setPublicationAcknowledgements(
      acknowledgementResponse.status === "fulfilled"
        ? acknowledgementResponse.value.acknowledgements
        : [],
    );
    await Promise.allSettled([
      loadRagEvidence(organizationId),
      loadRagDocuments(organizationId),
      loadDemandPreview(organizationId, activeResult),
    ]);
  }

  async function loadRagEvidence(organizationId = demo?.organizationId ?? workspaceOrganization?.id) {
    if (!organizationId) return;
    const response = await api<RagGrounding>(`/organizations/${organizationId}/rag/query`, {
      method: "POST",
      body: {
        query: "근무표 휴식 야간 주 52시간 정책",
        purpose: "operator_explanation",
      },
    });
    setRagGrounding(response);
  }

  async function loadRagDocuments(organizationId = demo?.organizationId ?? workspaceOrganization?.id) {
    if (!organizationId) return;
    const response = await api<RagDocumentList>(`/organizations/${organizationId}/rag/documents`);
    setRagDocuments(response.documents);
  }

  async function deleteRagDocument(documentId: string) {
    const organizationId = demo?.organizationId ?? workspaceOrganization?.id;
    if (!organizationId) return;
    setBusy("rag-document");
    setError(null);
    try {
      await api<null>(`/organizations/${organizationId}/rag/documents/${documentId}`, {
        method: "DELETE",
      });
      await loadRagDocuments(organizationId);
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setBusy(null);
    }
  }

  async function loadDemandPreview(
    organizationId = demo?.organizationId ?? workspaceOrganization?.id,
    activeResult = result,
  ) {
    if (!organizationId || !activeResult?.slots.length) {
      setDemandPreview(null);
      return;
    }
    const sortedDates = activeResult.slots
      .map((slot) => slot.local_date)
      .sort((left, right) => left.localeCompare(right));
    const params = new URLSearchParams({
      period_start: sortedDates[0],
      period_end: sortedDates[sortedDates.length - 1],
      planned_staff_count: String(activeResult.assignments.length),
      hourly_rate_cents: "1500000",
      hours_per_shift: "8",
    });
    const response = await api<DemandCostPreview>(
      `/organizations/${organizationId}/demand-cost-preview?${params.toString()}`,
    );
    setDemandPreview(response);
  }

  async function createDemandDriverFromDraft() {
    const organizationId = demo?.organizationId ?? workspaceOrganization?.id;
    if (!organizationId) return;
    setBusy("demand-input");
    setError(null);
    try {
      await api(`/organizations/${organizationId}/demand-drivers`, {
        method: "POST",
        body: {
          local_date: demandDriverDraft.localDate,
          segment: demandDriverDraft.segment || "day",
          demand_count: Math.max(0, Number(demandDriverDraft.demandCount) || 0),
          required_staff_count: Math.max(0, Number(demandDriverDraft.requiredStaffCount) || 0),
          source: "manual",
        },
      });
      await loadDemandPreview(organizationId, result);
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setBusy(null);
    }
  }

  async function createLaborBudgetFromDraft() {
    const organizationId = demo?.organizationId ?? workspaceOrganization?.id;
    if (!organizationId) return;
    setBusy("demand-input");
    setError(null);
    try {
      await api(`/organizations/${organizationId}/labor-budgets`, {
        method: "POST",
        body: {
          period_start: laborBudgetDraft.periodStart,
          period_end: laborBudgetDraft.periodEnd,
          budget_amount_cents: Math.max(0, Number(laborBudgetDraft.budgetAmountWon) || 0) * 100,
          currency: "KRW",
        },
      });
      await loadDemandPreview(organizationId, result);
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setBusy(null);
    }
  }

  async function submitEmployeeRequest({
    employeeId,
    endsAt,
    note,
    startsAt,
  }: {
    employeeId: string;
    endsAt: string;
    note: string;
    startsAt: string;
  }) {
    if (!demo) return;
    setBusy("employee-request");
    setError(null);
    try {
      await api(`/organizations/${demo.organizationId}/employee-requests`, {
        method: "POST",
        body: {
          employee_id: employeeId,
          type: "unavailable",
          starts_at: startsAt,
          ends_at: endsAt,
          note: note || null,
        },
      });
      await refreshRoadmapPanels(demo.organizationId, demo.runId, result);
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setBusy(null);
    }
  }

  async function approveEmployeeRequest(requestId: string) {
    if (!demo) return;
    setBusy("employee-request");
    setError(null);
    try {
      await api(`/organizations/${demo.organizationId}/employee-requests/${requestId}/approve`, {
        method: "POST",
        body: { reason: "운영 관리자 승인" },
      });
      await refreshReferenceData(demo.organizationId);
      await refreshRoadmapPanels(demo.organizationId, demo.runId, result);
      await refreshVisibility(demo.organizationId, demo.runId);
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setBusy(null);
    }
  }

  async function rejectEmployeeRequest(requestId: string) {
    if (!demo) return;
    setBusy("employee-request");
    setError(null);
    try {
      await api(`/organizations/${demo.organizationId}/employee-requests/${requestId}/reject`, {
        method: "POST",
        body: { reason: "운영 관리자 거절" },
      });
      await refreshRoadmapPanels(demo.organizationId, demo.runId, result);
      await refreshVisibility(demo.organizationId, demo.runId);
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setBusy(null);
    }
  }

  async function overrideComplianceWarning(warning: ComplianceWarningItem) {
    if (!demo || !result) return;
    const reason = complianceOverrideReasons[warning.instance_key]?.trim();
    if (!reason) {
      setError("컴플라이언스 warning 예외 승인 사유를 입력해주세요.");
      return;
    }
    setBusy("compliance-override");
    setError(null);
    try {
      await api(`/organizations/${demo.organizationId}/schedule-runs/${demo.runId}/compliance-warning-overrides`, {
        method: "POST",
        body: {
          warning_code: warning.code,
          employee_id: warning.employee_id,
          slot_id: warning.slot_id,
          week_key: warning.week_key,
          snapshot_hash: warning.snapshot_hash,
          reason,
        },
      });
      setComplianceOverrideReasons((current) => {
        const next = { ...current };
        delete next[warning.instance_key];
        return next;
      });
      await refreshRoadmapPanels(demo.organizationId, demo.runId, result);
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setBusy(null);
    }
  }

  async function acknowledgePublication(employeeId: string) {
    setBusy("acknowledge");
    setError(null);
    try {
      if (employeePublicationContext && employeeLinkToken) {
        const params = new URLSearchParams({
          organization_id: employeePublicationContext.organization_id,
          employee_id: employeePublicationContext.employee_id,
        });
        const acknowledgement = await api<PublicationAcknowledgementItem>(
          `${employeePublicationAcknowledgementPath(employeePublicationContext.publication_id)}?${params.toString()}`,
          {
            method: "POST",
            headers: { Authorization: `Bearer ${employeeLinkToken}` },
            body: { status: "acknowledged" },
          },
        );
        setEmployeePublicationContext((current) =>
          current ? { ...current, acknowledgement } : current,
        );
        setPublicationAcknowledgements([acknowledgement]);
        return;
      }
      if (!demo || !result?.publication) return;
      await api(
        `/organizations/${demo.organizationId}/schedule-publications/${result.publication.id}/acknowledgements/${employeeId}`,
        {
          method: "POST",
          body: { status: "acknowledged" },
        },
      );
      await refreshRoadmapPanels(demo.organizationId, demo.runId, result);
      await refreshVisibility(demo.organizationId, demo.runId);
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
      if (importFormat === "delimited") {
        const localPreview = validateImportRows(importType, parseDelimitedText(importContent));
        if (!localPreview.valid) {
          setImportPreview(localPreview);
          return;
        }
      }
      const serverPreview = await api<ImportPreview>(
        `/organizations/${organization.id}/imports/preview`,
        {
          method: "POST",
          body: importRequestBody(),
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
      const response = await api<ImportPreview>(
        `/organizations/${organization.id}/imports/apply`,
        {
          method: "POST",
          body: { ...importRequestBody(), mode: "upsert" },
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

  function importRequestBody() {
    if (importFormat === "xlsx") {
      return {
        type: importType,
        format: importFormat,
        content_base64: importContentBase64,
        sheet_name: importSheetName || undefined,
      };
    }
    return {
      type: importType,
      format: importFormat,
      content: importContent,
    };
  }

  if (window.location.pathname.startsWith("/employee")) {
    return (
      <EmployeeMobileView
        acknowledgements={publicationAcknowledgements.filter(
          (acknowledgement) => acknowledgement.employee_id === mobileEmployee?.id,
        )}
        busy={busy}
        cards={mobileEmployeeCards}
        employee={mobileEmployee}
        error={error}
        notifications={mobileNotifications}
        onAcknowledge={acknowledgePublication}
        onSubmitRequest={submitEmployeeRequest}
        publication={mobilePublication}
        requestsEnabled={!employeePublicationContext}
        requests={employeeRequests.filter((request) => request.employee_id === mobileEmployee?.id)}
      />
    );
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
        <SessionPanel
          busy={busy}
          draft={loginDraft}
          onDraftChange={(patch) => setLoginDraft((current) => ({ ...current, ...patch }))}
          onLogin={loginSession}
          onLogout={logoutSession}
          session={authSession}
        />
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
              onImportContentBase64Change={setImportContentBase64}
              onImportFormatChange={setImportFormat}
              onImportSheetNameChange={setImportSheetName}
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
              importContentBase64={importContentBase64}
              importFormat={importFormat}
              importSheetName={importSheetName}
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
            <LongTermFairnessPanel
              busy={busy}
              periodEnd={longTermPeriodEnd}
              periodStart={longTermPeriodStart}
              source={longTermFairnessSource}
              summary={longTermFairness}
              onPeriodEndChange={(value) => {
                setLongTermPeriodEnd(value);
                setLongTermFairness(null);
              }}
              onPeriodStartChange={(value) => {
                setLongTermPeriodStart(value);
                setLongTermFairness(null);
              }}
              onRefresh={() => loadLongTermFairness()}
              onSourceChange={(value) => {
                setLongTermFairnessSource(value);
                setLongTermFairness(null);
              }}
            />
            <RunComparisonPanel
              baseRunId={comparisonBaseRunId}
              busy={busy}
              candidateRunId={comparisonCandidateRunId}
              comparison={runComparison}
              history={runHistory}
              onBaseChange={(runId) => {
                setComparisonBaseRunId(runId);
                setRunComparison(null);
              }}
              onCandidateChange={(runId) => {
                setComparisonCandidateRunId(runId);
                setRunComparison(null);
              }}
              onCompare={() => loadRunComparison()}
            />
            <RoadmapOpsPanel
              acknowledgements={publicationAcknowledgements}
              busy={busy}
              compliance={complianceWarningSummary}
              complianceOverrideReasons={complianceOverrideReasons}
              demandDriverDraft={demandDriverDraft}
              demandPreview={demandPreview}
              employees={demo?.employees ?? []}
              laborBudgetDraft={laborBudgetDraft}
              onApproveRequest={approveEmployeeRequest}
              onComplianceOverrideReasonChange={(instanceKey, reason) => {
                setComplianceOverrideReasons((current) => ({
                  ...current,
                  [instanceKey]: reason,
                }));
              }}
              onCreateDemandDriver={createDemandDriverFromDraft}
              onCreateLaborBudget={createLaborBudgetFromDraft}
              onDemandDriverDraftChange={(patch) => {
                setDemandDriverDraft((current) => ({ ...current, ...patch }));
              }}
              onDeleteRagDocument={deleteRagDocument}
              onLaborBudgetDraftChange={(patch) => {
                setLaborBudgetDraft((current) => ({ ...current, ...patch }));
              }}
              onOverrideComplianceWarning={overrideComplianceWarning}
              onRefreshDemand={() => loadDemandPreview()}
              onRefreshRag={() => {
                void Promise.allSettled([loadRagEvidence(), loadRagDocuments()]);
              }}
              onRejectRequest={rejectEmployeeRequest}
              ragDocuments={ragDocuments}
              ragGrounding={ragGrounding}
              requests={employeeRequests}
            />
            <AuditLogPanel
              busy={busy}
              entries={auditLogs}
              onExport={exportAuditLogs}
            />
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
    const [fairnessResponse, auditResponse, historyResponse] = await Promise.all([
      api<FairnessSummary>(
        `/operations/organizations/${organizationId}/fairness/summary?schedule_run_id=${runId}`,
      ),
      api<AuditLogList>(`/operations/organizations/${organizationId}/audit-logs`),
      api<ScheduleRunHistory>(`/organizations/${organizationId}/schedule-runs`),
    ]);
    setFairness(fairnessResponse);
    setAuditLogs(auditResponse.entries);
    setRunHistory(historyResponse.runs);
    setComparisonCandidateRunId(runId);
    setComparisonBaseRunId((currentRunId) => {
      if (currentRunId !== runId && historyResponse.runs.some((run) => run.id === currentRunId)) {
        return currentRunId;
      }
      return historyResponse.runs.find((run) => run.id !== runId)?.id ?? "";
    });
    void loadLongTermFairness({ organizationId, showBusy: false });
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

function RoadmapOpsPanel({
  acknowledgements,
  busy,
  compliance,
  complianceOverrideReasons,
  demandDriverDraft,
  demandPreview,
  employees,
  laborBudgetDraft,
  onApproveRequest,
  onComplianceOverrideReasonChange,
  onCreateDemandDriver,
  onCreateLaborBudget,
  onDemandDriverDraftChange,
  onDeleteRagDocument,
  onLaborBudgetDraftChange,
  onOverrideComplianceWarning,
  onRefreshDemand,
  onRefreshRag,
  onRejectRequest,
  ragDocuments,
  ragGrounding,
  requests,
}: {
  acknowledgements: PublicationAcknowledgementItem[];
  busy: string | null;
  compliance: ComplianceWarningResponse | null;
  complianceOverrideReasons: Record<string, string>;
  demandDriverDraft: DemandDriverDraft;
  demandPreview: DemandCostPreview | null;
  employees: Employee[];
  laborBudgetDraft: LaborBudgetDraft;
  onApproveRequest: (requestId: string) => void;
  onComplianceOverrideReasonChange: (instanceKey: string, reason: string) => void;
  onCreateDemandDriver: () => void;
  onCreateLaborBudget: () => void;
  onDemandDriverDraftChange: (patch: Partial<DemandDriverDraft>) => void;
  onDeleteRagDocument: (documentId: string) => void;
  onLaborBudgetDraftChange: (patch: Partial<LaborBudgetDraft>) => void;
  onOverrideComplianceWarning: (warning: ComplianceWarningItem) => void;
  onRefreshDemand: () => void;
  onRefreshRag: () => void;
  onRejectRequest: (requestId: string) => void;
  ragDocuments: RagDocumentItem[];
  ragGrounding: RagGrounding | null;
  requests: EmployeeRequestItem[];
}) {
  const employeeNames = new Map(employees.map((employee) => [employee.id, employee.name]));
  const pendingRequests = pendingEmployeeRequestQueue(requests);
  const visibleRagDocuments = ragDocumentRows(ragDocuments);
  const warnings = compliance?.warnings ?? [];
  return (
    <div className="roadmap-panel">
      <SectionTitle title="운영 확장 패널" />
      <div className="roadmap-section">
        <div className="roadmap-section-head">
          <strong>직원 요청 Queue</strong>
          <span>{pendingRequests.length}건 대기</span>
        </div>
        <div className="roadmap-list">
          {pendingRequests.length ? pendingRequests.map((request) => (
            <div className="roadmap-row" key={request.id}>
              <div>
                <strong>{employeeNames.get(request.employee_id) ?? request.employee_id}</strong>
                <span>
                  {employeeRequestStatusLabel(request.status)} · {dateInputValue(request.starts_at)}
                </span>
              </div>
              <div className="roadmap-actions">
                <button
                  disabled={busy === "employee-request"}
                  onClick={() => onApproveRequest(request.id)}
                  type="button"
                >
                  승인
                </button>
                <button
                  disabled={busy === "employee-request"}
                  onClick={() => onRejectRequest(request.id)}
                  type="button"
                >
                  거절
                </button>
              </div>
            </div>
          )) : <div className="empty-state compact-empty">요청 대기열이 비어 있습니다.</div>}
        </div>
      </div>

      <div className="roadmap-section">
        <div className="roadmap-section-head">
          <strong>발행 확인 상태</strong>
          <span>{acknowledgements.length}명</span>
        </div>
        <div className="roadmap-list">
          {acknowledgements.length ? acknowledgements.slice(0, 5).map((acknowledgement) => (
            <div className="roadmap-row" key={acknowledgement.id}>
              <div>
                <strong>{employeeNames.get(acknowledgement.employee_id) ?? acknowledgement.employee_id}</strong>
                <span>{acknowledgementStatusLabel(acknowledgement.status)}</span>
              </div>
              <em>{acknowledgement.acknowledged_at ? formatDateTime(acknowledgement.acknowledged_at) : "대기"}</em>
            </div>
          )) : <div className="empty-state compact-empty">확정 후 직원별 확인 상태가 생성됩니다.</div>}
        </div>
      </div>

      <div className="roadmap-section">
        <div className="roadmap-section-head">
          <strong>컴플라이언스 Warning</strong>
          <span>{warnings.length}건</span>
        </div>
        <div className="roadmap-list">
          {warnings.length ? warnings.slice(0, 5).map((warning) => (
            <div className={`roadmap-row warning-${warning.severity}`} key={warning.instance_key}>
              <div>
                <strong>{complianceSeverityLabel(warning.severity)} · {warning.code}</strong>
                <span>{warning.message}</span>
                {warning.publish_blocking ? (
                  <div className="warning-override-controls">
                    <input
                      onChange={(event) => onComplianceOverrideReasonChange(
                        warning.instance_key,
                        event.target.value,
                      )}
                      placeholder="예외 승인 사유"
                      value={complianceOverrideReasons[warning.instance_key] ?? ""}
                    />
                    <button
                      disabled={busy === "compliance-override"}
                      onClick={() => onOverrideComplianceWarning(warning)}
                      type="button"
                    >
                      예외 승인
                    </button>
                  </div>
                ) : null}
              </div>
              <em>{warning.publish_blocking ? "차단" : "발행 가능"}</em>
            </div>
          )) : <div className="success-box">현재 표시할 경고가 없습니다.</div>}
        </div>
        {compliance?.legal_disclaimer ? (
          <p className="roadmap-note">{compliance.legal_disclaimer}</p>
        ) : null}
      </div>

      <div className="roadmap-section">
        <div className="roadmap-section-head">
          <strong>RAG 근거</strong>
          <button onClick={onRefreshRag} type="button">근거 새로고침</button>
        </div>
        <div className="roadmap-list">
          <div className="roadmap-row">
            <div>
              <strong>{ragGrounding ? ragConfidenceLabel(ragGrounding.confidence) : "대기"}</strong>
              <span>{ragGrounding?.status ?? "검색 전"}</span>
            </div>
            <em>{ragGrounding?.evidence.length ?? 0}개 조각</em>
          </div>
          {ragGrounding?.evidence.slice(0, 3).map((evidence) => (
            <div className="roadmap-row evidence-row" key={`${evidence.document_title}-${evidence.checked_at}`}>
              <div>
                <strong>{evidence.document_title}</strong>
                <span>
                  {evidence.source_type} · confidence {Math.round(evidence.confidence * 100)}%
                  {" · "}
                  {evidence.excerpt}
                </span>
              </div>
              <em>{dateInputValue(evidence.checked_at)}</em>
            </div>
          ))}
          {ragGrounding?.safety_notes.length ? (
            <div className="roadmap-row warning-warning">
              <div>
                <strong>Safety notes</strong>
                <span>{ragGrounding.safety_notes.join(" · ")}</span>
              </div>
            </div>
          ) : null}
        </div>
        <div className="roadmap-subsection">
          <div className="roadmap-section-head compact-head">
            <strong>근거 문서</strong>
            <span>{ragDocuments.length}개</span>
          </div>
          <div className="roadmap-list">
            {visibleRagDocuments.length ? visibleRagDocuments.map((document) => (
              <div className="roadmap-row" key={document.id}>
                <div>
                  <strong>{document.document_title}</strong>
                  <span>
                    {document.source_type} · {document.chunk_count}개 조각 · {dateInputValue(document.checked_at)}
                  </span>
                </div>
                <button
                  disabled={busy === "rag-document"}
                  onClick={() => onDeleteRagDocument(document.id)}
                  type="button"
                >
                  삭제
                </button>
              </div>
            )) : <div className="empty-state compact-empty">등록된 근거 문서가 없습니다.</div>}
          </div>
        </div>
      </div>

      <div className="roadmap-section">
        <div className="roadmap-section-head">
          <strong>수요/비용 Preview</strong>
          <button onClick={onRefreshDemand} type="button">계산</button>
        </div>
        <div className="demand-input-grid">
          <label>
            수요 일자
            <input
              onChange={(event) => onDemandDriverDraftChange({ localDate: event.target.value })}
              type="date"
              value={demandDriverDraft.localDate}
            />
          </label>
          <label>
            구간
            <input
              onChange={(event) => onDemandDriverDraftChange({ segment: event.target.value })}
              value={demandDriverDraft.segment}
            />
          </label>
          <label>
            예상 수요
            <input
              min="0"
              onChange={(event) => onDemandDriverDraftChange({ demandCount: event.target.value })}
              type="number"
              value={demandDriverDraft.demandCount}
            />
          </label>
          <label>
            필요 인원
            <input
              min="0"
              onChange={(event) => onDemandDriverDraftChange({ requiredStaffCount: event.target.value })}
              type="number"
              value={demandDriverDraft.requiredStaffCount}
            />
          </label>
          <button disabled={busy === "demand-input"} onClick={onCreateDemandDriver} type="button">
            수요 저장
          </button>
        </div>
        <div className="demand-input-grid budget-grid">
          <label>
            예산 시작
            <input
              onChange={(event) => onLaborBudgetDraftChange({ periodStart: event.target.value })}
              type="date"
              value={laborBudgetDraft.periodStart}
            />
          </label>
          <label>
            예산 종료
            <input
              onChange={(event) => onLaborBudgetDraftChange({ periodEnd: event.target.value })}
              type="date"
              value={laborBudgetDraft.periodEnd}
            />
          </label>
          <label>
            예산 원
            <input
              min="0"
              onChange={(event) => onLaborBudgetDraftChange({ budgetAmountWon: event.target.value })}
              type="number"
              value={laborBudgetDraft.budgetAmountWon}
            />
          </label>
          <button disabled={busy === "demand-input"} onClick={onCreateLaborBudget} type="button">
            예산 저장
          </button>
        </div>
        {demandPreview ? (
          <>
            <div className="summary-metrics">
              <Metric label="필요/계획" value={`${demandPreview.required_staff_count}/${demandPreview.planned_staff_count}`} />
              <Metric label="부족/초과" value={`${demandPreview.under_staffed_count}/${demandPreview.over_staffed_count}`} />
              <Metric label="예산" value={budgetStatusLabel(demandPreview.budget_status)} />
              <Metric label="계획 비용" value={formatWonFromCents(demandPreview.planned_cost_cents)} />
              <Metric label="예산액" value={formatWonFromCents(demandPreview.budget_amount_cents)} />
            </div>
            {demandPreview.required_staff_count === 0 && demandPreview.budget_amount_cents === null ? (
              <p className="roadmap-note">수요 driver와 예산 데이터가 아직 입력되지 않았습니다.</p>
            ) : null}
          </>
        ) : <div className="empty-state compact-empty">근무표 생성 후 비용 미리보기를 계산합니다.</div>}
      </div>
    </div>
  );
}

function EmployeeMobileView({
  acknowledgements,
  busy,
  cards,
  employee,
  error,
  notifications,
  onAcknowledge,
  onSubmitRequest,
  publication,
  requestsEnabled,
  requests,
}: {
  acknowledgements: PublicationAcknowledgementItem[];
  busy: string | null;
  cards: EmployeeScheduleCard[];
  employee: Employee | null;
  error: string | null;
  notifications: PublicationNotificationItem[];
  onAcknowledge: (employeeId: string) => void;
  onSubmitRequest: (request: {
    employeeId: string;
    endsAt: string;
    note: string;
    startsAt: string;
  }) => void;
  publication: Publication | null;
  requestsEnabled: boolean;
  requests: EmployeeRequestItem[];
}) {
  const [startDate, setStartDate] = useState(todayIsoDate());
  const [endDate, setEndDate] = useState(todayIsoDate());
  const [note, setNote] = useState("");
  const acknowledgement = acknowledgements[0] ?? null;
  if (!employee) {
    return (
      <main className="employee-shell">
        <div className="employee-empty">
          <strong>직원 화면 대기</strong>
          <span>운영 콘솔에서 근무표를 생성하면 모바일 직원 화면이 표시됩니다.</span>
        </div>
      </main>
    );
  }
  return (
    <main className="employee-shell">
      <header className="employee-topbar">
        <div>
          <span>WorkScheduleAI</span>
          <h1>{employee.name}</h1>
        </div>
        <strong>{cards.length}개 근무</strong>
      </header>
      {error ? <div className="error-banner">{error}</div> : null}
      <section className="employee-section">
        <SectionTitle title="내 근무" />
        <div className="employee-day-list">
          {cards.length ? cards.map((card) => (
            <div className="employee-shift-card" key={card.assignmentId}>
              <div>
                <strong>{dateDisplayLabel(card.localDate)}</strong>
                <span>{slotDisplayLabel(card.label, card.localDate)}</span>
              </div>
              <em>{card.roleName}</em>
            </div>
          )) : <div className="empty-state compact-empty">아직 배정된 근무가 없습니다.</div>}
        </div>
      </section>
      <section className="employee-section">
        <SectionTitle title="확정 근무표 확인" />
        {publication ? (
          <div className="roadmap-row">
            <div>
              <strong>{acknowledgementStatusLabel(acknowledgement?.status ?? "pending")}</strong>
              <span>{formatDateTime(publication.published_at)}</span>
            </div>
            {acknowledgement?.status === "acknowledged" ? (
              <em>완료</em>
            ) : (
              <button
                disabled={busy === "acknowledge"}
                onClick={() => onAcknowledge(employee.id)}
                type="button"
              >
                확인 완료
              </button>
            )}
          </div>
        ) : <div className="empty-state compact-empty">확정된 근무표가 아직 없습니다.</div>}
      </section>
      {notifications.length ? (
        <section className="employee-section">
          <SectionTitle title="알림" />
          <div className="roadmap-list">
            {notifications.map((notification) => (
              <div className="roadmap-row" key={notification.id}>
                <div>
                  <strong>{publicationNotificationTypeLabel(notification.notification_type)}</strong>
                  <span>{formatDateTime(notification.created_at)}</span>
                </div>
                <em>{publicationNotificationStatusLabel(notification.status)}</em>
              </div>
            ))}
          </div>
        </section>
      ) : null}
      {requestsEnabled ? (
        <section className="employee-section">
          <SectionTitle title="불가 시간 요청" />
          <div className="employee-request-form">
            <label className="field-row">
              <span>시작일</span>
              <input onChange={(event) => setStartDate(event.target.value)} type="date" value={startDate} />
            </label>
            <label className="field-row">
              <span>종료일</span>
              <input onChange={(event) => setEndDate(event.target.value)} type="date" value={endDate} />
            </label>
            <label className="field-row field-row-wide">
              <span>메모</span>
              <textarea onChange={(event) => setNote(event.target.value)} rows={3} value={note} />
            </label>
            <button
              className="primary-action"
              disabled={busy === "employee-request"}
              onClick={() =>
                onSubmitRequest({
                  employeeId: employee.id,
                  endsAt: `${addDaysIso(endDate, 1)}T00:00:00+09:00`,
                  note,
                  startsAt: `${startDate}T00:00:00+09:00`,
                })
              }
              type="button"
            >
              요청 제출
            </button>
          </div>
        </section>
      ) : null}
      {requestsEnabled ? (
        <section className="employee-section">
          <SectionTitle title="요청 상태" />
        <div className="roadmap-list">
          {requests.length ? requests.map((request) => (
            <div className="roadmap-row" key={request.id}>
              <div>
                <strong>{employeeRequestStatusLabel(request.status)}</strong>
                <span>{dateInputValue(request.starts_at)} · {request.note ?? "메모 없음"}</span>
              </div>
            </div>
          )) : <div className="empty-state compact-empty">제출한 요청이 없습니다.</div>}
        </div>
        </section>
      ) : null}
    </main>
  );
}

function SessionPanel({
  busy,
  draft,
  onDraftChange,
  onLogin,
  onLogout,
  session,
}: {
  busy: string | null;
  draft: LoginDraft;
  onDraftChange: (patch: Partial<LoginDraft>) => void;
  onLogin: () => void;
  onLogout: () => void;
  session: AuthSession | null;
}) {
  return (
    <div className="session-panel">
      <div className="session-heading">
        <span>세션</span>
        <strong>{sessionLabel(session)}</strong>
      </div>
      {session ? (
        <button className="session-button" onClick={onLogout} type="button">
          <LogOut size={15} />
          로그아웃
        </button>
      ) : (
        <div className="session-form">
          <input
            onChange={(event) => onDraftChange({ organizationId: event.target.value })}
            placeholder="organization id"
            value={draft.organizationId}
          />
          <input
            autoComplete="username"
            onChange={(event) => onDraftChange({ email: event.target.value })}
            placeholder="email"
            type="email"
            value={draft.email}
          />
          <input
            autoComplete="current-password"
            onChange={(event) => onDraftChange({ password: event.target.value })}
            placeholder="password"
            type="password"
            value={draft.password}
          />
          <button
            className="session-button"
            disabled={busy === "login" || !draft.email || !draft.password || !draft.organizationId}
            onClick={onLogin}
            type="button"
          >
            <LogIn size={15} />
            {busy === "login" ? "확인 중" : "로그인"}
          </button>
        </div>
      )}
    </div>
  );
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
  importContentBase64,
  importFormat,
  importPreview,
  importSheetName,
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
  onImportContentBase64Change,
  onImportContentChange,
  onImportFormatChange,
  onImportSheetNameChange,
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
  importContentBase64: string;
  importFormat: ImportFormat;
  importPreview: ImportPreview | null;
  importSheetName: string;
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
  onImportContentBase64Change: (content: string) => void;
  onImportContentChange: (content: string) => void;
  onImportFormatChange: (format: ImportFormat) => void;
  onImportSheetNameChange: (sheetName: string) => void;
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
          contentBase64={importContentBase64}
          importFormat={importFormat}
          importSheetName={importSheetName}
          importType={importType}
          onApply={onApplyImport}
          onContentBase64Change={onImportContentBase64Change}
          onContentChange={onImportContentChange}
          onFormatChange={onImportFormatChange}
          onPreview={onPreviewImport}
          onSheetNameChange={onImportSheetNameChange}
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
  contentBase64,
  importFormat,
  importSheetName,
  importType,
  onApply,
  onContentBase64Change,
  onContentChange,
  onFormatChange,
  onPreview,
  onSheetNameChange,
  onTypeChange,
  preview,
}: {
  content: string;
  contentBase64: string;
  importFormat: ImportFormat;
  importSheetName: string;
  importType: ImportType;
  onApply: () => void;
  onContentBase64Change: (content: string) => void;
  onContentChange: (content: string) => void;
  onFormatChange: (format: ImportFormat) => void;
  onPreview: () => void;
  onSheetNameChange: (sheetName: string) => void;
  onTypeChange: (type: ImportType) => void;
  preview: ImportPreview | null;
}) {
  return (
    <div className="import-manager">
      <SectionTitle title="Excel 가져오기" />
      <label className="field-row field-row-wide">
        <span>대상</span>
        <select onChange={(event) => onTypeChange(event.target.value as ImportType)} value={importType}>
          <option value="employees">직원</option>
          <option value="unavailabilities">휴가/출장</option>
          <option value="pair_constraints">상극 조합</option>
          <option value="shift_types">근무유형/필요 인원</option>
          <option value="policy">정책</option>
        </select>
      </label>
      <label className="field-row field-row-wide">
        <span>형식</span>
        <select onChange={(event) => onFormatChange(event.target.value as ImportFormat)} value={importFormat}>
          <option value="delimited">CSV/TSV</option>
          <option value="xlsx">.xlsx</option>
        </select>
      </label>
      {importFormat === "xlsx" ? (
        <label className="field-row field-row-wide">
          <span>시트명</span>
          <input
            onChange={(event) => onSheetNameChange(event.target.value)}
            placeholder={importType}
            value={importSheetName}
          />
        </label>
      ) : null}
      <label className="field-row field-row-wide">
        <span>파일</span>
        <input
          accept=".csv,.tsv,.txt,.xlsx,text/csv,text/tab-separated-values,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (!file) return;
            if (isXlsxFileName(file.name)) {
              onFormatChange("xlsx");
              onContentChange(file.name);
              void file.arrayBuffer().then((buffer) => {
                onContentBase64Change(bytesToBase64(new Uint8Array(buffer)));
              });
              return;
            }
            onFormatChange("delimited");
            onContentBase64Change("");
            void file.text().then(onContentChange);
          }}
          type="file"
        />
      </label>
      {importFormat === "xlsx" ? (
        <div className={contentBase64 ? "success-box" : "subtle-box"}>
          {contentBase64 ? `${content} 파일을 불러왔습니다.` : "선택된 .xlsx 파일 없음"}
        </div>
      ) : (
        <textarea
          onChange={(event) => onContentChange(event.target.value)}
          spellCheck={false}
          value={content}
        />
      )}
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
                <div
                  className="validation-row blocking"
                  key={`${error.sheet ?? ""}-${error.row_no}-${error.column ?? error.field}-${error.code}-${error.message}`}
                >
                  <strong>
                    {error.sheet ? `${error.sheet} · ` : ""}
                    {error.row_no ?? "-"}행 {error.column ?? error.field ?? ""}
                  </strong>
                  <span>{error.code} · {error.message}</span>
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
      <SectionTitle title="현재 실행 공정성" />
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

function LongTermFairnessPanel({
  busy,
  onPeriodEndChange,
  onPeriodStartChange,
  onRefresh,
  onSourceChange,
  periodEnd,
  periodStart,
  source,
  summary,
}: {
  busy: string | null;
  onPeriodEndChange: (value: string) => void;
  onPeriodStartChange: (value: string) => void;
  onRefresh: () => void;
  onSourceChange: (value: LongTermFairnessSource) => void;
  periodEnd: string;
  periodStart: string;
  source: LongTermFairnessSource;
  summary: LongTermFairnessSummary | null;
}) {
  const rows = summary ? sortedLongTermFairnessRows(summary.rows) : [];
  return (
    <div className="visibility-panel long-term-fairness-panel">
      <SectionTitle title="장기 공정성" />
      <div className="fairness-controls">
        <label>
          <span>기준</span>
          <select
            value={source}
            onChange={(event) => onSourceChange(event.target.value as LongTermFairnessSource)}
          >
            <option value="publications">{longTermFairnessSourceLabel("publications")}</option>
            <option value="runs">{longTermFairnessSourceLabel("runs")}</option>
          </select>
        </label>
        <label>
          <span>시작</span>
          <input
            max={periodEnd}
            onChange={(event) => onPeriodStartChange(event.target.value)}
            type="date"
            value={periodStart}
          />
        </label>
        <label>
          <span>종료</span>
          <input
            min={periodStart}
            onChange={(event) => onPeriodEndChange(event.target.value)}
            type="date"
            value={periodEnd}
          />
        </label>
        <button disabled={busy === "long-term-fairness"} onClick={onRefresh} type="button">
          <RefreshCw size={16} />
          갱신
        </button>
      </div>
      {!summary ? (
        <div className="subtle-box">장기 공정성 요약이 없습니다.</div>
      ) : (
        <>
          <div className="summary-metrics">
            <Metric label="기준" value={longTermFairnessSourceLabel(summary.source)} />
            <Metric label="총 배정" value={`${summary.total_assignments}회`} />
            <Metric label="편차" value={fairnessSpreadLabel(summary)} />
          </div>
          <div className="fairness-list">
            {rows.slice(0, 8).map((row) => (
              <div className="fairness-row long-term-row" key={row.employee_id}>
                <div>
                  <strong>{row.employee_name}</strong>
                  <span>
                    {row.employee_code} · 야간 {row.night_count} · 주말 {row.weekend_count}
                  </span>
                  <small>{roleCountsLabel(row.role_counts)}</small>
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

function RunComparisonPanel({
  baseRunId,
  busy,
  candidateRunId,
  comparison,
  history,
  onBaseChange,
  onCandidateChange,
  onCompare,
}: {
  baseRunId: string;
  busy: string | null;
  candidateRunId: string;
  comparison: ScheduleRunComparison | null;
  history: ScheduleRunHistory["runs"];
  onBaseChange: (runId: string) => void;
  onCandidateChange: (runId: string) => void;
  onCompare: () => void;
}) {
  const canCompare = Boolean(baseRunId && candidateRunId && baseRunId !== candidateRunId);
  const fairnessRows = comparison ? changedFairnessRows(comparison) : [];
  return (
    <div className="visibility-panel run-comparison-panel">
      <SectionTitle title="생성 이력 비교" />
      {history.length < 2 ? (
        <div className="subtle-box">비교할 생성 이력이 부족합니다.</div>
      ) : (
        <>
          <div className="history-controls">
            <label>
              <span>기준</span>
              <select value={baseRunId} onChange={(event) => onBaseChange(event.target.value)}>
                <option value="">선택</option>
                {history.map((run) => (
                  <option key={run.id} value={run.id}>
                    {runHistoryOptionLabel(run)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>대상</span>
              <select
                value={candidateRunId}
                onChange={(event) => onCandidateChange(event.target.value)}
              >
                <option value="">선택</option>
                {history.map((run) => (
                  <option key={run.id} value={run.id}>
                    {runHistoryOptionLabel(run)}
                  </option>
                ))}
              </select>
            </label>
            <button disabled={!canCompare || busy === "compare"} onClick={onCompare} type="button">
              <ClipboardList size={16} />
              비교
            </button>
          </div>
          {comparison ? (
            <>
              <div className="summary-metrics">
                {comparisonSummaryMetrics(comparison).map((metric) => (
                  <Metric key={metric.label} label={metric.label} value={metric.value} />
                ))}
              </div>
              <div className="comparison-list">
                {comparison.assignment_changes.slice(0, 6).map((row) => (
                  <div
                    className="comparison-row"
                    key={`${row.change_type}-${row.slot_id}-${row.role_id}-${row.employee_id}`}
                  >
                    <strong>
                      {changeTypeLabel(row.change_type)} · {row.employee_name}
                    </strong>
                    <span>
                      {row.slot_id} · {row.role_name} · {optionalSourceLabel(row.before_source)} →{" "}
                      {optionalSourceLabel(row.after_source)}
                    </span>
                    <em>
                      {optionalLockLabel(row.before_locked_by_user)} →{" "}
                      {optionalLockLabel(row.after_locked_by_user)}
                    </em>
                  </div>
                ))}
              </div>
              <div className="comparison-list">
                {comparison.issue_changes.slice(0, 4).map((row) => (
                  <div
                    className="comparison-row"
                    key={`${row.change_type}-${row.slot_id ?? "all"}-${row.role_id ?? "all"}-${row.reason_code}`}
                  >
                    <strong>
                      {issueChangeTypeLabel(row.change_type)} · {row.role_name ?? "전체"}
                    </strong>
                    <span>{row.slot_id ?? "전체"} · {row.reason_code}</span>
                    <em>{deltaLabel(row.missing_delta)}명</em>
                  </div>
                ))}
              </div>
              <div className="comparison-list">
                {fairnessRows.slice(0, 4).map((row) => (
                  <div className="comparison-row" key={row.employee_id}>
                    <strong>{row.employee_name}</strong>
                    <span>
                      {row.before_assignment_count}회 → {row.after_assignment_count}회
                    </span>
                    <em>{deltaLabel(row.assignment_delta)}</em>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="subtle-box">기준과 대상을 선택하면 차이가 표시됩니다.</div>
          )}
        </>
      )}
    </div>
  );
}

function AuditLogPanel({
  busy,
  entries,
  onExport,
}: {
  busy: string | null;
  entries: AuditLogEntry[];
  onExport: () => void;
}) {
  return (
    <div className="visibility-panel">
      <div className="panel-title-row">
        <SectionTitle title="감사 로그" />
        <button disabled={busy === "audit-export"} onClick={onExport} type="button">
          <Download size={16} />
          CSV
        </button>
      </div>
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

async function api<T>(
  path: string,
  options: { method?: string; body?: unknown; headers?: Record<string, string> } = {},
): Promise<T> {
  const headers = {
    ...authHeaders(activeAuthSession),
    ...options.headers,
    ...(options.body ? { "Content-Type": "application/json" } : {}),
  };
  const response = await fetch(`${API_BASE}${path}`, {
    method: options.method ?? "GET",
    headers: Object.keys(headers).length ? headers : undefined,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(apiErrorMessage(response.status, detail));
  }
  if (response.status === 204) {
    return null as T;
  }
  return response.json() as Promise<T>;
}

function loadStoredAuthSession(): AuthSession | null {
  if (typeof window === "undefined") return null;
  const stored = window.sessionStorage.getItem(AUTH_SESSION_STORAGE_KEY);
  if (!stored) return null;
  try {
    const parsed = JSON.parse(stored) as Partial<AuthSession>;
    if (!parsed.access_token || !parsed.organization_id || !parsed.user_id || !parsed.role) {
      return null;
    }
    if (parsed.expires_at && Date.parse(parsed.expires_at) <= Date.now()) {
      return null;
    }
    return parsed as AuthSession;
  } catch {
    return null;
  }
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

function publicationNotificationTypeLabel(value: string) {
  const labels: Record<string, string> = {
    published: "확정 근무표",
    changed: "변경 알림",
  };
  return labels[value] ?? value;
}

function publicationNotificationStatusLabel(value: string) {
  const labels: Record<string, string> = {
    pending_recorded: "대기",
    sent: "발송됨",
    failed: "실패",
    suppressed: "보류",
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

function runHistoryOptionLabel(run: ScheduleRunHistory["runs"][number]) {
  return `${run.period_start}~${run.period_end} · ${formatDateTime(run.created_at)} · ${run.assignment_count}건`;
}

function optionalSourceLabel(source: string | null) {
  return source ? assignmentSourceLabel({ source }) : "없음";
}

function optionalLockLabel(lockedByUser: boolean | null) {
  return lockedByUser === null ? "없음" : assignmentLockLabel({ locked_by_user: lockedByUser });
}

function roleCountsLabel(roleCounts: Record<string, number>) {
  const entries = Object.entries(roleCounts);
  if (!entries.length) return "역할 배정 없음";
  return entries.map(([roleName, count]) => `${roleName} ${count}`).join(" · ");
}

function formatWonFromCents(value: number | null) {
  if (value === null) return "없음";
  return `${Math.round(value / 100).toLocaleString("ko-KR")}원`;
}

function todayIsoDate() {
  return new Date().toLocaleDateString("sv-SE", { timeZone: "Asia/Seoul" });
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
