export type ImportType =
  | "employees"
  | "unavailabilities"
  | "pair_constraints"
  | "policy"
  | "shift_types";

export type ImportFormat = "delimited" | "xlsx";

export type ImportError = {
  code: string;
  message: string;
  sheet?: string | null;
  field: string | null;
  column?: string | null;
  row_no: number | null;
};

export type ImportPreview = {
  valid: boolean;
  rows: Record<string, string>[];
  errors: ImportError[];
  applied_count?: number;
};

const REQUIRED_COLUMNS: Record<ImportType, string[]> = {
  employees: ["employee_code", "name", "roles", "max_shifts_per_week"],
  unavailabilities: ["employee_code", "type", "starts_at", "ends_at", "override_allowed"],
  pair_constraints: [
    "employee_code_a",
    "employee_code_b",
    "type",
    "severity",
    "override_allowed",
  ],
  policy: ["key", "value"],
  shift_types: [
    "shift_type",
    "local_start_time",
    "local_end_time",
    "timezone",
    "crosses_midnight",
    "active_weekdays",
    "active",
    "role_name",
    "required_count",
    "unfilled_weight_override",
  ],
};

const REQUIRED_VALUE_COLUMNS: Record<ImportType, string[]> = {
  ...REQUIRED_COLUMNS,
  shift_types: REQUIRED_COLUMNS.shift_types.filter(
    (column) => column !== "unfilled_weight_override",
  ),
};

export function detectDelimiter(text: string): "," | "\t" {
  const firstLine = text.trim().split(/\r?\n/)[0] ?? "";
  return firstLine.includes("\t") ? "\t" : ",";
}

export function parseDelimitedText(text: string): Record<string, string>[] {
  const normalized = text.trim();
  if (!normalized) return [];
  const delimiter = detectDelimiter(normalized);
  const [headerLine, ...lines] = normalized.split(/\r?\n/);
  const headers = headerLine.split(delimiter).map((header) => header.trim());
  return lines
    .filter((line) => line.trim())
    .map((line) => {
      const values = line.split(delimiter);
      return Object.fromEntries(
        headers.map((header, index) => [header, (values[index] ?? "").trim()]),
      );
    });
}

export function validateImportRows(
  type: ImportType,
  rows: Record<string, string>[],
): ImportPreview {
  const errors: ImportError[] = [];
  const requiredColumns = REQUIRED_COLUMNS[type];
  if (!rows.length) {
    errors.push({
      code: "NO_ROWS",
      message: "가져올 행이 없습니다.",
      field: null,
      row_no: null,
    });
    return { valid: false, rows, errors };
  }
  for (const column of requiredColumns) {
    if (!(column in rows[0])) {
      errors.push({
        code: "MISSING_COLUMN",
        message: "필수 컬럼이 없습니다.",
        field: column,
        row_no: 1,
      });
    }
  }
  const requiredValueColumns = REQUIRED_VALUE_COLUMNS[type];
  rows.forEach((row, index) => {
    requiredValueColumns.forEach((column) => {
      if (!row[column]) {
        errors.push({
          code: "REQUIRED",
          message: "필수 값이 없습니다.",
          field: column,
          row_no: index + 1,
        });
      }
    });
  });
  return { valid: !errors.length, rows, errors };
}

export function parseImportBoolean(rawValue: string): boolean | null {
  const normalized = rawValue.trim().toLowerCase();
  if (["true", "1", "yes", "y", "허용"].includes(normalized)) return true;
  if (["false", "0", "no", "n", "불가"].includes(normalized)) return false;
  return null;
}

export function isXlsxFileName(fileName: string): boolean {
  return fileName.trim().toLowerCase().endsWith(".xlsx");
}

export function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  const chunkSize = 0x8000;
  for (let index = 0; index < bytes.length; index += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(index, index + chunkSize));
  }
  return btoa(binary);
}
