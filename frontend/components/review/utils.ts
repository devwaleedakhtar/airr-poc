import type { ReviewData, ReviewField } from "./types";
import type { ExtractedJson, Confidences } from "@/types/extraction";

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
