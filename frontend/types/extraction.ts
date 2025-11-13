import type { JsonObject, JsonValue } from "./json";

export type ConfidenceLevel = "high" | "medium" | "low";

export type ExtractedJson = Record<string, Record<string, JsonValue>>;
export type Confidences = Record<string, Record<string, ConfidenceLevel>>;

export interface SessionListItem {
  _id: string;
  workbook_id: string;
  sheet_name: string;
  created_at: string;
  updated_at: string;
}

export interface SessionDetail {
  _id: string;
  workbook_id: string;
  sheet_name: string;
  pdf_url: string;
  extracted_json: ExtractedJson;
  confidences?: Confidences;
  inferred_tables?: string[];
  warnings?: string[];
  text_snippets?: Record<string, string>;
  final_json?: JsonObject | null;
  created_at: string;
  updated_at: string;
}

