import { X } from "lucide-react";
import { useEffect } from "react";

import type { PreviewFile } from "../types/api";
import { isImageMime, isPdfMime } from "../utils/format";

interface PreviewModalProps {
  preview: PreviewFile | null;
  onClose: () => void;
}

export function PreviewModal({ preview, onClose }: PreviewModalProps) {
  useEffect(() => {
    if (!preview) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [preview, onClose]);

  if (!preview) {
    return null;
  }

  const showPdf = isPdfMime(preview.mimeType);
  const showImage = isImageMime(preview.mimeType);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label={`Preview ${preview.filename}`}
      onClick={onClose}
    >
      <div
        className="flex max-h-[92vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="flex items-center justify-between border-b border-slate-200 px-5 py-3">
          <div className="min-w-0 pr-4">
            <h3 className="truncate text-sm font-semibold text-slate-900">{preview.filename}</h3>
            <p className="text-xs text-slate-500">Original document preview</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50"
          >
            <X className="h-4 w-4" aria-hidden />
            Close Preview
          </button>
        </header>

        <div className="flex-1 overflow-auto bg-slate-100 p-4">
          {showPdf ? (
            <iframe
              title={preview.filename}
              src={preview.url}
              className="h-[75vh] w-full rounded-lg border border-slate-200 bg-white"
            />
          ) : null}

          {showImage ? (
            <img
              src={preview.url}
              alt={preview.filename}
              className="mx-auto max-h-[75vh] max-w-full rounded-lg border border-slate-200 bg-white object-contain shadow-sm"
            />
          ) : null}

          {!showPdf && !showImage ? (
            <p className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              This file type cannot be previewed in the browser. Download the original from your
              upload folder.
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
