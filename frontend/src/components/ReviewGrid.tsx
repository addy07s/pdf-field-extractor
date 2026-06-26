import { Eye, LayoutList } from "lucide-react";

import type { DocumentResult, FieldConfig } from "../types/api";
import { displayFieldValue } from "../utils/format";
import { fieldCellClasses, overallStatusClasses } from "../utils/cellStyles";

interface ReviewGridProps {
  results: DocumentResult[];
  fields: FieldConfig[];
  onViewInvoice: (document: DocumentResult) => void;
  onInspectDocument: (document: DocumentResult) => void;
  canPreview: (sourceFilename: string) => boolean;
}

const actionButtonClass =
  "inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-xs font-medium text-slate-700 shadow-sm transition hover:border-slate-400 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40";

export function ReviewGrid({
  results,
  fields,
  onViewInvoice,
  onInspectDocument,
  canPreview,
}: ReviewGridProps) {
  if (results.length === 0) {
    return null;
  }

  return (
    <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 px-5 py-4">
        <h2 className="text-lg font-semibold text-slate-900">Review workspace</h2>
        <p className="mt-1 text-sm text-slate-500">
          {results.length} invoice{results.length === 1 ? "" : "s"} processed. Flagged cells match
          Excel export highlighting.
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse text-left">
          <thead>
            <tr className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-600">
              <th className="sticky left-0 z-10 min-w-[9.5rem] border-b border-slate-200 bg-slate-50 px-3 py-3">
                Actions
              </th>
              <th className="min-w-[12rem] border-b border-slate-200 px-3 py-3">Source file</th>
              <th className="min-w-[7rem] border-b border-slate-200 px-3 py-3">Status</th>
              {fields.map((field) => (
                <th
                  key={field.key}
                  className="min-w-[10rem] border-b border-slate-200 px-3 py-3"
                  title={field.description}
                >
                  {field.display_label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {results.map((document) => {
              const previewReady = canPreview(document.source_filename);

              return (
                <tr key={document.source_filename} className="border-b border-slate-100 last:border-0">
                  <td className="sticky left-0 z-10 bg-white px-3 py-2">
                    <div className="flex flex-col gap-1.5 sm:flex-row sm:items-center">
                      <button
                        type="button"
                        onClick={() => onViewInvoice(document)}
                        disabled={!previewReady}
                        title={
                          previewReady
                            ? "View original invoice"
                            : "Original file not available in this session"
                        }
                        className={actionButtonClass}
                      >
                        <Eye className="h-3.5 w-3.5 shrink-0" aria-hidden />
                        View
                      </button>
                      <button
                        type="button"
                        onClick={() => onInspectDocument(document)}
                        title="Inspect extracted field details"
                        className={actionButtonClass}
                      >
                        <LayoutList className="h-3.5 w-3.5 shrink-0" aria-hidden />
                        Details
                      </button>
                    </div>
                  </td>

                  <td className="px-3 py-2 text-sm font-medium text-slate-800">
                    {document.source_filename}
                  </td>

                  <td className="px-3 py-2">
                    <span className={overallStatusClasses(document.overall_status)}>
                      {document.overall_status}
                    </span>
                    {document.error_message ? (
                      <p className="mt-1 max-w-xs text-xs text-slate-500" title={document.error_message}>
                        {document.error_message}
                      </p>
                    ) : null}
                  </td>

                  {fields.map((field) => {
                    const fieldResult = document.fields[field.key];
                    const displayValue = displayFieldValue(fieldResult);
                    const title = fieldResult?.reason ?? undefined;

                    return (
                      <td
                        key={`${document.source_filename}-${field.key}`}
                        className={fieldCellClasses(fieldResult?.status, document)}
                        title={title}
                      >
                        {displayValue || (
                          <span className="text-slate-400">{fieldResult ? "—" : ""}</span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
