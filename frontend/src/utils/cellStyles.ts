import type { FieldStatus } from "../types/api";
import { isDocumentFailed } from "../utils/format";
import type { DocumentResult } from "../types/api";

/**
 * Excel-identical fills (output/excel_writer.py + ui/review_workspace.py):
 * - OK: default white
 * - LOW_CONFIDENCE: #FFEB9C
 * - FAILED_VALIDATION: #FFC7CE
 * - NOT_FOUND / document FAILED: #D9D9D9
 */
export function fieldCellClasses(
  status: FieldStatus | undefined,
  document: DocumentResult,
): string {
  const base = "px-3 py-2 text-sm border border-slate-200 align-top";

  if (isDocumentFailed(document)) {
    return `${base} bg-[#d9d9d9] text-slate-700`;
  }

  switch (status) {
    case "LOW_CONFIDENCE":
      return `${base} bg-[#ffeb9c] text-amber-950`;
    case "FAILED_VALIDATION":
      return `${base} bg-[#ffc7ce] text-red-900`;
    case "NOT_FOUND":
      return `${base} bg-[#d9d9d9] text-slate-600`;
    case "OK":
    default:
      return `${base} bg-white text-slate-800`;
  }
}

export function overallStatusClasses(status: DocumentResult["overall_status"]): string {
  const base = "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold";

  switch (status) {
    case "OK":
      return `${base} bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200`;
    case "PARTIAL":
      return `${base} bg-amber-50 text-amber-800 ring-1 ring-amber-200`;
    case "FAILED":
      return `${base} bg-red-50 text-red-700 ring-1 ring-red-200`;
    default:
      return `${base} bg-slate-100 text-slate-700`;
  }
}

/** Rounded badge colors matching Excel field-status fills. */
export function fieldStatusBadgeClasses(
  status: FieldStatus | undefined,
  document: DocumentResult,
): string {
  const base = "inline-flex shrink-0 items-center rounded-full px-2.5 py-0.5 text-xs font-semibold";

  if (isDocumentFailed(document)) {
    return `${base} bg-[#d9d9d9] text-slate-700 ring-1 ring-slate-300`;
  }

  switch (status) {
    case "LOW_CONFIDENCE":
      return `${base} bg-[#ffeb9c] text-amber-950 ring-1 ring-amber-300`;
    case "FAILED_VALIDATION":
      return `${base} bg-[#ffc7ce] text-red-900 ring-1 ring-red-300`;
    case "NOT_FOUND":
      return `${base} bg-[#d9d9d9] text-slate-600 ring-1 ring-slate-300`;
    case "OK":
    default:
      return `${base} bg-white text-slate-700 ring-1 ring-slate-200`;
  }
}

export function fieldInspectRowClasses(
  status: FieldStatus | undefined,
  document: DocumentResult,
): string {
  const base = "rounded-xl border p-4";

  if (isDocumentFailed(document)) {
    return `${base} border-slate-200 bg-[#d9d9d9]/40`;
  }

  switch (status) {
    case "LOW_CONFIDENCE":
      return `${base} border-amber-200 bg-[#ffeb9c]/50`;
    case "FAILED_VALIDATION":
      return `${base} border-red-200 bg-[#ffc7ce]/50`;
    case "NOT_FOUND":
      return `${base} border-slate-200 bg-[#d9d9d9]/40`;
    case "OK":
    default:
      return `${base} border-slate-200 bg-white`;
  }
}
