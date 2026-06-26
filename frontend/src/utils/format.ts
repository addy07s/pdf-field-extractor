import type { DocumentResult, FieldResult } from "../types/api";

/** Mirror backend duplicate-filename handling in app.py / api/deps.py. */
export function buildUploadFilenameMap(files: File[]): Map<string, File> {
  const map = new Map<string, File>();
  const usedNames = new Set<string>();

  files.forEach((file, index) => {
    const baseName = file.name.split(/[/\\]/).pop() ?? `upload_${index + 1}`;
    let filename = baseName;
    if (usedNames.has(filename)) {
      filename = `${index + 1}_${baseName}`;
    }
    usedNames.add(filename);
    map.set(filename, file);
  });

  return map;
}

export function displayFieldValue(field: FieldResult | undefined): string {
  if (!field || field.status === "NOT_FOUND") {
    return "";
  }

  const { value } = field;
  if (value === null || value === undefined) {
    return "";
  }

  if (typeof value === "object" && value !== null && "normalized" in value) {
    const normalized = (value as { normalized?: unknown }).normalized;
    return normalized === null || normalized === undefined ? "" : String(normalized);
  }

  return String(value);
}

export function isDocumentFailed(document: DocumentResult): boolean {
  return document.overall_status === "FAILED";
}

export function mimeTypeForFilename(filename: string): string {
  const lower = filename.toLowerCase();
  if (lower.endsWith(".pdf")) return "application/pdf";
  if (lower.endsWith(".png")) return "image/png";
  if (lower.endsWith(".jpg") || lower.endsWith(".jpeg")) return "image/jpeg";
  return "application/octet-stream";
}

export function isPdfMime(mimeType: string): boolean {
  return mimeType === "application/pdf";
}

export function isImageMime(mimeType: string): boolean {
  return mimeType.startsWith("image/");
}

const ALLOWED_EXTENSIONS = new Set([".pdf", ".jpg", ".jpeg", ".png"]);

export function isAllowedInvoiceFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return [...ALLOWED_EXTENSIONS].some((ext) => name.endsWith(ext));
}

export function mergeUniqueFiles(existing: File[], incoming: File[]): File[] {
  const seen = new Set(existing.map((file) => `${file.name}:${file.size}:${file.lastModified}`));
  const merged = [...existing];

  for (const file of incoming) {
    const key = `${file.name}:${file.size}:${file.lastModified}`;
    if (!seen.has(key)) {
      seen.add(key);
      merged.push(file);
    }
  }

  return merged;
}
