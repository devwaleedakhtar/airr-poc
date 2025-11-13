export type UploadResponse = {
  workbook_id: string;
  sheets: string[];
};

export type ConvertResponse = { pdf_url: string };

import type { SessionDetail, SessionListItem, ExtractedJson, Confidences } from "@/types/extraction";

export type ExtractResponse = {
  session_id: string;
  extracted_json: ExtractedJson;
  confidences?: Confidences;
  inferred_tables?: string[];
  warnings?: string[];
};

import type { JsonObject } from "@/types/json";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const msg = await res.text();
    throw new Error(msg || `HTTP ${res.status}`);
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
