import type { ConfidenceLevel } from "@/types/extraction";
import type { JsonValue } from "@/types/json";

export type ReviewField = {
  table: string;
  key: string;
  value: JsonValue;
  confidence?: ConfidenceLevel;
};

export type ReviewData = {
  fields: ReviewField[];
};

export type ReviewTable = {
  name: string;
  fields: ReviewField[];
};
