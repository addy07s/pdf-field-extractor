import { AlertCircle, FileSpreadsheet, Loader2, Play, Sheet } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { basenameFromPath, exportDownloadUrl, extractInvoices, fetchConfig, isApiError } from "./api/client";
import { FileUploadZone } from "./components/FileUploadZone";
import { InspectDetailsModal } from "./components/InspectDetailsModal";
import { PreviewModal } from "./components/PreviewModal";
import { ReviewGrid } from "./components/ReviewGrid";
import type {
  ConfigResponse,
  DocumentResult,
  ExtractResponse,
  PreviewFile,
} from "./types/api";
import { buildUploadFilenameMap, mimeTypeForFilename } from "./utils/format";

const DEFAULT_MAX_UPLOAD = 100;

function countByStatus(results: DocumentResult[]) {
  return results.reduce(
    (acc, doc) => {
      acc[doc.overall_status] = (acc[doc.overall_status] ?? 0) + 1;
      return acc;
    },
    {} as Record<DocumentResult["overall_status"], number>,
  );
}

export default function App() {
  const [serverConfig, setServerConfig] = useState<ConfigResponse | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [extractError, setExtractError] = useState<string | null>(null);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [extractedResults, setExtractedResults] = useState<ExtractResponse | null>(null);
  const [activePreviewFile, setActivePreviewFile] = useState<PreviewFile | null>(null);
  const [activeInspectFile, setActiveInspectFile] = useState<DocumentResult | null>(null);

  const previewUrlRef = useRef<string | null>(null);

  const uploadFileMap = useMemo(
    () => buildUploadFilenameMap(selectedFiles),
    [selectedFiles],
  );

  const maxUploadCount = serverConfig?.max_upload_count ?? DEFAULT_MAX_UPLOAD;

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const config = await fetchConfig();
        if (!cancelled) {
          setServerConfig(config);
          setConfigError(null);
        }
      } catch (error) {
        if (!cancelled) {
          setConfigError(isApiError(error) ? error.message : "Failed to load server configuration.");
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    return () => {
      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current);
      }
    };
  }, []);

  const closePreview = useCallback(() => {
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = null;
    }
    setActivePreviewFile(null);
  }, []);

  const closeInspect = useCallback(() => {
    setActiveInspectFile(null);
  }, []);

  const handleInspectDocument = useCallback((document: DocumentResult) => {
    setActiveInspectFile(document);
  }, []);

  const canPreview = useCallback(
    (sourceFilename: string) => uploadFileMap.has(sourceFilename),
    [uploadFileMap],
  );

  const handleViewInvoice = useCallback(
    (document: DocumentResult) => {
      const file = uploadFileMap.get(document.source_filename);
      if (!file) {
        return;
      }

      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current);
      }

      const url = URL.createObjectURL(file);
      previewUrlRef.current = url;

      setActivePreviewFile({
        filename: document.source_filename,
        url,
        mimeType: mimeTypeForFilename(document.source_filename),
      });
    },
    [uploadFileMap],
  );

  const handleProcess = async () => {
    if (selectedFiles.length === 0 || isLoading) {
      return;
    }

    setIsLoading(true);
    setExtractError(null);
    closePreview();
    closeInspect();

    try {
      const response = await extractInvoices(selectedFiles);
      setExtractedResults(response);
    } catch (error) {
      setExtractedResults(null);
      setExtractError(isApiError(error) ? error.message : "Extraction failed. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  const statusCounts = extractedResults
    ? countByStatus(extractedResults.results)
    : null;

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center justify-between gap-4 px-6 py-5">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              GST Invoice Field Extractor
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Upload invoices, validate extracted fields, and review flagged cells instantly.
            </p>
          </div>

          {serverConfig ? (
            <div className="flex flex-wrap gap-2 text-xs text-slate-600">
              <span className="rounded-full bg-slate-100 px-3 py-1">{serverConfig.provider_label}</span>
              <span
                className={[
                  "rounded-full px-3 py-1",
                  serverConfig.ocr_enabled ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-800",
                ].join(" ")}
              >
                {serverConfig.ocr_status}
              </span>
              <span className="rounded-full bg-slate-100 px-3 py-1">
                Concurrency: {serverConfig.batch_concurrency}
              </span>
            </div>
          ) : null}
        </div>
      </header>

      <main className="mx-auto max-w-[1600px] space-y-6 px-6 py-8">
        {configError ? (
          <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            <p>
              <span className="font-semibold">Configuration unavailable.</span> {configError} Ensure
              the FastAPI server is running on port 8000.
            </p>
          </div>
        ) : null}

        <FileUploadZone
          files={selectedFiles}
          maxFiles={maxUploadCount}
          disabled={isLoading}
          onFilesChange={setSelectedFiles}
        />

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={handleProcess}
            disabled={isLoading || selectedFiles.length === 0 || Boolean(configError)}
            className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <Play className="h-4 w-4" aria-hidden />
            )}
            {isLoading ? "Processing…" : "Start processing"}
          </button>

          {selectedFiles.length > 0 && !isLoading ? (
            <p className="text-sm text-slate-500">
              {selectedFiles.length} file{selectedFiles.length === 1 ? "" : "s"} ready
            </p>
          ) : null}
        </div>

        {extractError ? (
          <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            <p>{extractError}</p>
          </div>
        ) : null}

        {extractedResults && statusCounts ? (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <MetricCard label="Total" value={extractedResults.results.length} />
            <MetricCard label="OK" value={statusCounts.OK ?? 0} tone="ok" />
            <MetricCard label="Needs review" value={statusCounts.PARTIAL ?? 0} tone="partial" />
            <MetricCard label="Failed" value={statusCounts.FAILED ?? 0} tone="failed" />
          </div>
        ) : null}

        {extractedResults?.excel_path && extractedResults?.csv_path ? (
          <ExportDownloads
            excelPath={extractedResults.excel_path}
            csvPath={extractedResults.csv_path}
          />
        ) : null}

        {extractedResults && serverConfig ? (
          <ReviewGrid
            results={extractedResults.results}
            fields={serverConfig.fields}
            onViewInvoice={handleViewInvoice}
            onInspectDocument={handleInspectDocument}
            canPreview={canPreview}
          />
        ) : null}
      </main>

      <PreviewModal preview={activePreviewFile} onClose={closePreview} />
      <InspectDetailsModal
        document={activeInspectFile}
        fields={serverConfig?.fields ?? []}
        onClose={closeInspect}
      />
    </div>
  );
}

interface MetricCardProps {
  label: string;
  value: number;
  tone?: "ok" | "partial" | "failed";
}

function MetricCard({ label, value, tone }: MetricCardProps) {
  const toneClasses =
    tone === "ok"
      ? "text-emerald-700"
      : tone === "partial"
        ? "text-amber-700"
        : tone === "failed"
          ? "text-red-700"
          : "text-slate-800";

  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${toneClasses}`}>{value}</p>
    </div>
  );
}

const downloadButtonClass =
  "inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-slate-400 hover:bg-slate-50";

interface ExportDownloadsProps {
  excelPath: string;
  csvPath: string;
}

function ExportDownloads({ excelPath, csvPath }: ExportDownloadsProps) {
  const excelUrl = exportDownloadUrl(excelPath);
  const csvUrl = exportDownloadUrl(csvPath);
  const excelName = basenameFromPath(excelPath);
  const csvName = basenameFromPath(csvPath);

  return (
    <section className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-white px-5 py-4 shadow-sm">
      <p className="mr-1 text-sm font-medium text-slate-700">Download exports</p>
      <a href={excelUrl} download={excelName} className={downloadButtonClass}>
        <FileSpreadsheet className="h-4 w-4 shrink-0 text-emerald-600" aria-hidden />
        Download Excel
      </a>
      <a href={csvUrl} download={csvName} className={downloadButtonClass}>
        <Sheet className="h-4 w-4 shrink-0 text-sky-600" aria-hidden />
        Download CSV
      </a>
    </section>
  );
}
