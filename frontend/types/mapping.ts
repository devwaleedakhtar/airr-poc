import type { JsonValue } from "./json";

export type CanonicalMapping = Record<string, JsonValue>;

export type MissingField = {
  table: string;
  field: string;
  reason: string;
  confidence?: string | null;
  source_fields?: string[] | null;
  table_label?: string | null;
  field_label?: string | null;
};

export type MappingMetadata = {
  generated_at: string;
  warnings?: string[] | null;
  model_version?: string | null;
  table_labels?: Record<string, string>;
  field_labels?: Record<string, Record<string, string>>;
};

export type MappingResult = {
  mapped: CanonicalMapping;
  missing_fields: MissingField[];
  metadata: MappingMetadata;
};

export type ExportAppliedField = {
  table: string;
  field: string;
  cell: string;
  value: unknown;
};

export type ExportResult = {
  download_url: string;
  applied_fields: ExportAppliedField[];
};
