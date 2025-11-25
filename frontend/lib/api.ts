export type UploadResponse = {
  workbook_id: string;
  sheets: string[];
};

export type ConvertResponse = { pdf_url: string };

import type {
  SessionDetail,
  SessionListItem,
  ExtractedJson,
  Confidences,
} from "@/types/extraction";
import type { ExportResult, MappingJobStatus, MappingResult } from "@/types/mapping";

export type ExtractResponse = {
  session_id: string;
  extracted_json: ExtractedJson;
  confidences?: Confidences;
  inferred_tables?: string[];
  warnings?: string[];
};

import type { JsonObject } from "@/types/json";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

function normalizeErrorMessage(message: string, status: number): string {
  if (!message) {
    return `Request failed with status ${status}.`;
  }

  // Backend extraction: no text in PDF
  if (message.includes("PDF contains no extractable text")) {
    return "We couldn't read any text from this PDF. Make sure the worksheet exports as a text-based PDF (not an image-only scan).";
  }

  // Backend extraction: model output not parsable as JSON
  if (message.includes("Model returned no parsable JSON for this PDF")) {
    return "We couldn't interpret this sheet as structured data. Try simplifying the layout or removing unusual formatting, then run extraction again.";
  }

  // Strip raw LLM output snippet if present.
  const rawIndex = message.indexOf("Raw output (truncated):");
  if (rawIndex !== -1) {
    const trimmed = message.slice(0, rawIndex).trim();
    if (trimmed) return trimmed;
  }

  return message;
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const raw = await res.text();
    // FastAPI error responses are typically {"detail": "..."}; surface that directly.
    try {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === "object" && "detail" in parsed) {
        const detail = (parsed as { detail?: unknown }).detail;
        if (typeof detail === "string") {
          throw new Error(normalizeErrorMessage(detail, res.status));
        }
      }
    } catch {
      // fall back to raw text below
    }
    throw new Error(normalizeErrorMessage(raw, res.status));
  }
  return res.json();
}

export async function uploadWorkbook(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/workbooks/upload`, {
    method: "POST",
    body: form,
  });
  return json(res);
}

export async function convertWorkbook(id: string, sheet_name: string): Promise<ConvertResponse> {
  const res = await fetch(`${API_BASE}/workbooks/${id}/convert`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sheet_name }),
  });
  return json(res);
}

export async function extractWorkbook(id: string, sheet_name?: string): Promise<ExtractResponse> {
  const res = await fetch(`${API_BASE}/workbooks/${id}/extract`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sheet_name }),
  });
  return json(res);
}

export async function listSessions(): Promise<SessionListItem[]> {
  const res = await fetch(`${API_BASE}/sessions/`, { cache: "no-store" });
  return json(res);
}

export async function getSession(sessionId: string): Promise<SessionDetail> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}`, { cache: "no-store" });
  return json(res);
}

export async function updateSession(sessionId: string, final_json: JsonObject): Promise<SessionDetail> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ final_json }),
  });
  return json(res);
}

export async function mapSession(sessionId: string): Promise<MappingResult> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/map`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  return json(res);
}

export async function saveMapping(sessionId: string, mapping: MappingResult): Promise<MappingResult> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/mapping`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(mapping),
  });
  return json(res);
}

export async function startMappingJob(sessionId: string): Promise<MappingJobStatus> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/map/async`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  return json(res);
}

export async function getMappingStatus(sessionId: string): Promise<MappingJobStatus> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/mapping/status`, { cache: "no-store" });
  return json(res);
}

export async function exportWorkbook(sessionId: string): Promise<ExportResult> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  return json(res);
}
