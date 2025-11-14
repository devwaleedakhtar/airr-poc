import type { ReviewData, ReviewField, ReviewTable } from "./types";
import type { ExtractedJson, Confidences } from "@/types/extraction";
import type { JsonObject, JsonValue } from "@/types/json";

export function flattenExtracted(
  extracted: ExtractedJson,
  confidences?: Confidences
): ReviewData {
  const fields: ReviewField[] = [];
  Object.entries(extracted || {}).forEach(([table, kv]) => {
    if (kv && typeof kv === "object") {
      Object.entries(kv).forEach(([key, value]) => {
        const conf = confidences?.[table]?.[key] as ReviewField["confidence"] | undefined;
        fields.push({ table, key, value: String(value ?? ""), confidence: conf });
      });
    }
  });
  return { fields };
}

import type { JsonObject } from "@/types/json";

export function unflattenToJson(fields: ReviewField[]): JsonObject {
  const out: JsonObject = {};
  for (const f of fields) {
    if (!out[f.table]) out[f.table] = {};
    out[f.table][f.key] = f.value;
  }
  return out;
}

export function groupExtracted(
  extracted: ExtractedJson,
  confidences?: Confidences
): { tables: ReviewTable[] } {
  const tables: ReviewTable[] = [];
  Object.entries(extracted || {}).forEach(([table, kv]) => {
    const fields: ReviewField[] = [];
    if (kv && typeof kv === "object") {
      Object.entries(kv).forEach(([key, value]) => {
        const conf = confidences?.[table]?.[key] as ReviewField["confidence"] | undefined;
        fields.push({ table, key, value: (value ?? "") as JsonValue, confidence: conf });
      });
    }
    tables.push({ name: table, fields });
  });
  return { tables };
}

export function toNestedJson(tables: ReviewTable[]): JsonObject {
  const out: JsonObject = {};
  for (const t of tables) {
    out[t.name] = out[t.name] || {};
    for (const f of t.fields) {
      out[t.name][f.key] = f.value;
    }
  }
  return out;
}
