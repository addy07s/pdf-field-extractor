export type FieldStatus =
  | "OK"
  | "LOW_CONFIDENCE"
  | "NOT_FOUND"
  | "FAILED_VALIDATION";

export type DocumentStatus = "OK" | "PARTIAL" | "FAILED";

export type DataType = "string" | "date" | "number";

export interface FieldConfig {
  key: string;
  display_label: string;
  description: string;
  data_type: DataType;
  validators: string[];
}

export interface FieldResult {
  value: unknown;
  status: FieldStatus;
  reason: string | null;
}

export interface DocumentResult {
  source_filename: string;
  /** 1-based index of this invoice within the source file. */
  invoice_index: number;
  fields: Record<string, FieldResult>;
  overall_status: DocumentStatus;
  error_message: string | null;
}

export interface ConfigResponse {
  fields: FieldConfig[];
  provider_label: string;
  ocr_enabled: boolean;
  ocr_status: string;
  batch_concurrency: number;
  max_upload_count: number;
}

export interface ExtractResponse {
  results: DocumentResult[];
  excel_path: string;
  csv_path: string;
}

export interface PreviewFile {
  filename: string;
  url: string;
  mimeType: string;
}

export interface ApiError {
  message: string;
  status?: number;
}
