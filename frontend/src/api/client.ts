import type {
  ApiError,
  ConfigResponse,
  ExtractResponse,
} from "../types/api";

const JSON_HEADERS = {
  Accept: "application/json",
} as const;

async function parseError(response: Response): Promise<ApiError> {
  let message = `Request failed (${response.status})`;

  try {
    const body = (await response.json()) as { detail?: string | { msg?: string }[] };
    if (typeof body.detail === "string") {
      message = body.detail;
    } else if (Array.isArray(body.detail) && body.detail.length > 0) {
      message = body.detail.map((item) => item.msg ?? "Validation error").join("; ");
    }
  } catch {
    // Response body was not JSON — keep default message.
  }

  return { message, status: response.status };
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as T;
}

export async function fetchConfig(): Promise<ConfigResponse> {
  const response = await fetch("/api/config", {
    method: "GET",
    headers: JSON_HEADERS,
  });
  return handleResponse<ConfigResponse>(response);
}

export async function extractInvoices(files: File[]): Promise<ExtractResponse> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file, file.name);
  }

  const response = await fetch("/api/extract", {
    method: "POST",
    body: formData,
  });

  return handleResponse<ExtractResponse>(response);
}

export function isApiError(error: unknown): error is ApiError {
  return (
    typeof error === "object" &&
    error !== null &&
    "message" in error &&
    typeof (error as ApiError).message === "string"
  );
}

/** Build a same-origin URL for server-written export files (dev proxy + production). */
export function exportDownloadUrl(serverPath: string): string {
  const normalized = serverPath.replace(/\\/g, "/").replace(/^\/+/, "");
  return `/${normalized}`;
}

export function basenameFromPath(serverPath: string): string {
  const segments = serverPath.replace(/\\/g, "/").split("/");
  return segments[segments.length - 1] || serverPath;
}
