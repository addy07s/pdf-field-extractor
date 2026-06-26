import { FileUp, Upload, X } from "lucide-react";
import { useCallback, useRef, useState, type DragEvent } from "react";

import { isAllowedInvoiceFile, mergeUniqueFiles } from "../utils/format";

interface FileUploadZoneProps {
  files: File[];
  maxFiles: number;
  disabled?: boolean;
  onFilesChange: (files: File[]) => void;
}

export function FileUploadZone({
  files,
  maxFiles,
  disabled = false,
  onFilesChange,
}: FileUploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  const addFiles = useCallback(
    (incoming: FileList | File[]) => {
      const selected = Array.from(incoming).filter(isAllowedInvoiceFile);
      if (selected.length === 0) {
        return;
      }
      const merged = mergeUniqueFiles(files, selected).slice(0, maxFiles);
      onFilesChange(merged);
    },
    [files, maxFiles, onFilesChange],
  );

  const onDrop = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setIsDragging(false);
      if (disabled) return;
      addFiles(event.dataTransfer.files);
    },
    [addFiles, disabled],
  );

  const removeFile = (index: number) => {
    onFilesChange(files.filter((_, fileIndex) => fileIndex !== index));
  };

  const atLimit = files.length >= maxFiles;

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Upload invoices</h2>
          <p className="mt-1 text-sm text-slate-500">
            PDF, JPG, or PNG — up to {maxFiles} files per batch.
          </p>
        </div>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
          {files.length} / {maxFiles}
        </span>
      </div>

      <div
        role="button"
        tabIndex={0}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            inputRef.current?.click();
          }
        }}
        onDragEnter={(event) => {
          event.preventDefault();
          if (!disabled) setIsDragging(true);
        }}
        onDragOver={(event) => {
          event.preventDefault();
          if (!disabled) setIsDragging(true);
        }}
        onDragLeave={(event) => {
          event.preventDefault();
          setIsDragging(false);
        }}
        onDrop={onDrop}
        onClick={() => !disabled && inputRef.current?.click()}
        className={[
          "flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 text-center transition",
          disabled ? "cursor-not-allowed opacity-60" : "hover:border-slate-400 hover:bg-slate-50",
          isDragging ? "border-sky-400 bg-sky-50" : "border-slate-300 bg-slate-50/60",
        ].join(" ")}
      >
        <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-white shadow-sm ring-1 ring-slate-200">
          {isDragging ? (
            <FileUp className="h-6 w-6 text-sky-600" aria-hidden />
          ) : (
            <Upload className="h-6 w-6 text-slate-500" aria-hidden />
          )}
        </div>
        <p className="text-sm font-medium text-slate-800">
          Drag and drop invoices here, or click to browse
        </p>
        <p className="mt-1 text-xs text-slate-500">Supported: .pdf, .jpg, .jpeg, .png</p>
      </div>

      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
        className="hidden"
        disabled={disabled || atLimit}
        onChange={(event) => {
          if (event.target.files) {
            addFiles(event.target.files);
          }
          event.target.value = "";
        }}
      />

      {files.length > 0 ? (
        <ul className="mt-4 max-h-48 space-y-2 overflow-y-auto">
          {files.map((file, index) => (
            <li
              key={`${file.name}-${file.size}-${file.lastModified}`}
              className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
            >
              <span className="truncate pr-3 text-slate-700">{file.name}</span>
              <button
                type="button"
                disabled={disabled}
                onClick={(event) => {
                  event.stopPropagation();
                  removeFile(index);
                }}
                className="inline-flex items-center rounded-md p-1 text-slate-500 hover:bg-white hover:text-slate-800 disabled:opacity-40"
                aria-label={`Remove ${file.name}`}
              >
                <X className="h-4 w-4" />
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
