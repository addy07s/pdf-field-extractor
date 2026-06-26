import { X } from "lucide-react";
import { useEffect } from "react";

import type { DocumentResult, FieldConfig } from "../types/api";
import { displayFieldValue } from "../utils/format";
import {
  fieldInspectRowClasses,
  fieldStatusBadgeClasses,
  overallStatusClasses,
} from "../utils/cellStyles";

interface InspectDetailsModalProps {
  document: DocumentResult | null;
  fields: FieldConfig[];
  onClose: () => void;
}

export function InspectDetailsModal({ document, fields, onClose }: InspectDetailsModalProps) {
  useEffect(() => {
    if (!document) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [document, onClose]);

  if (!document) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label={`Inspect ${document.source_filename}`}
      onClick={onClose}
    >
      <div
        className="flex max-h-[92vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-4">
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
              File details
            </p>
            <h3 className="mt-1 truncate text-lg font-semibold text-slate-900">
              {document.source_filename}
            </h3>
            <div className="mt-2">
              <span className={overallStatusClasses(document.overall_status)}>
                {document.overall_status}
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex shrink-0 rounded-lg p-2 text-slate-500 transition hover:bg-slate-100 hover:text-slate-800"
            aria-label="Close details panel"
          >
            <X className="h-5 w-5" aria-hidden />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {document.error_message ? (
            <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
              <p className="font-medium">Processing error</p>
              <p className="mt-1">{document.error_message}</p>
            </div>
          ) : null}

          <ul className="space-y-3">
            {fields.map((field) => {
              const fieldResult = document.fields[field.key];
              const displayValue = displayFieldValue(fieldResult);
              const status = fieldResult?.status;
              const showReason = status && status !== "OK" && fieldResult?.reason;

              return (
                <li
                  key={field.key}
                  className={fieldInspectRowClasses(status, document)}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                      {field.display_label}
                    </p>
                    <span className={fieldStatusBadgeClasses(status, document)}>
                      {status ?? "—"}
                    </span>
                  </div>

                  <p className="mt-2 text-base font-semibold text-slate-900">
                    {displayValue || <span className="font-normal text-slate-400">—</span>}
                  </p>

                  {showReason ? (
                    <p className="mt-2 text-sm leading-relaxed text-slate-600">
                      {fieldResult.reason}
                    </p>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </div>
      </div>
    </div>
  );
}
