import type { ConfidenceLevel } from "@/types/extraction";

export type ReviewField = {
  table: string;
  key: string;
  value: string;
  confidence?: ConfidenceLevel;
};

export type ReviewData = {
  fields: ReviewField[];
};
