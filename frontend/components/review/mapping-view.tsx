"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { exportWorkbook, getMappingStatus, saveMapping, startMappingJob } from "@/lib/api";
import type { MappingResult, MappingJobStatus, MissingField } from "@/types/mapping";
import type { JsonValue } from "@/types/json";
import { Button } from "@/components/ui/button";
import { H1, H3, P } from "@/components/ui/typography";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { AlertCircle, Loader2 } from "lucide-react";
import FieldEditor from "./field-editor";

const CHATBOT_URL =
  process.env.NEXT_PUBLIC_CHATBOT_URL || "http://localhost:8501";

type Props = {
  sessionId: string;
  initialMapping: MappingResult | null;
};

function isEmptyValue(value: JsonValue | undefined): boolean {
  if (value === null || value === undefined) return true;
  if (typeof value === "string") return value.trim().length === 0;
  return false;
}

function formatLabel(label: string): string {
  return label
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
}

function pruneMissing(
  missing: MissingField[],
  mapped: Record<string, JsonValue>
): MissingField[] {
  return missing.filter((item) => {
    const tableVal = mapped?.[item.table];
    // Only enforce missing for scalar groups (object maps), skip arrays
    if (Array.isArray(tableVal)) return false;
    const value = (tableVal as Record<string, JsonValue> | undefined)?.[
      item.field
    ];
    return isEmptyValue(value);
  });
}

export default function MappingView({ sessionId, initialMapping }: Props) {
  const [mapping, setMapping] = useState<MappingResult | null>(initialMapping);
  const [loading, setLoading] = useState(!initialMapping);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [jobStatus, setJobStatus] = useState<MappingJobStatus | null>(null);
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollAttempts = useRef(0);
  const tableLabels = mapping?.metadata?.table_labels ?? {};
  const fieldLabels = mapping?.metadata?.field_labels ?? {};
  const isMappingRunning =
    loading || jobStatus?.status === "running" || jobStatus?.status === "pending";
  const canAskAi = !!mapping && !isMappingRunning;

  const stopPolling = useCallback(() => {
    if (pollTimer.current) {
      clearTimeout(pollTimer.current);
      pollTimer.current = null;
    }
    pollAttempts.current = 0;
  }, []);

  const pollStatus = useCallback(async () => {
    try {
      const status = await getMappingStatus(sessionId);
      setJobStatus(status);
      if (status.status === "succeeded") {
        if (status.mapping) {
          setMapping(status.mapping);
          setDirty(false);
        }
        setLoading(false);
        stopPolling();
        return;
      }
      if (status.status === "failed") {
        const msg = status.error || "Mapping failed";
        setError(msg);
        toast.error("Mapping failed", { description: msg });
        setLoading(false);
        stopPolling();
        return;
      }
      pollAttempts.current += 1;
      // Cap ~500s: 50 attempts * 10s interval
      if (pollAttempts.current >= 50) {
        const msg = "Mapping is taking longer than expected. Please retry.";
        setError(msg);
        setJobStatus({ status: "failed", error: msg });
        stopPolling();
        setLoading(false);
        return;
      }
      pollTimer.current = setTimeout(pollStatus, 10000);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to check mapping status";
      setError(msg);
      toast.error("Mapping status error", { description: msg });
      stopPolling();
      setLoading(false);
    }
  }, [sessionId, stopPolling]);

  const beginMappingJob = useCallback(async () => {
    stopPolling();
    setLoading(true);
    setError(null);
    setMapping(null);
    setDirty(false);
    try {
      const status = await startMappingJob(sessionId);
      setJobStatus(status);
      pollStatus();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to start mapping";
      setError(msg);
      toast.error("Mapping failed", { description: msg });
      setLoading(false);
    }
  }, [pollStatus, sessionId, stopPolling]);

  useEffect(() => {
    if (!initialMapping) {
      beginMappingJob();
    }
  }, [beginMappingJob, initialMapping]);

  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  const updateField = (table: string, field: string, value: JsonValue) => {
    setMapping((prev) => {
      if (!prev) return prev;
      const baseTable = prev.mapped[table];
      if (Array.isArray(baseTable)) {
        // Coerce scalar edit into the first row for arrays if needed
        const rows =
          baseTable.length > 0
            ? baseTable.map((r) =>
                r && typeof r === "object"
                  ? { ...(r as Record<string, JsonValue>) }
                  : { value: r as JsonValue }
              )
            : [{}];
        rows[0] = { ...rows[0], [field]: value };
        const mapped = { ...prev.mapped, [table]: rows };
        const missing = pruneMissing(prev.missing_fields, mapped);
        return { ...prev, mapped, missing_fields: missing };
      }
      const nextTable = {
        ...(baseTable as Record<string, JsonValue> | undefined),
        [field]: value,
      };
      const mapped = { ...prev.mapped, [table]: nextTable };
      const missing = pruneMissing(prev.missing_fields, mapped);
      return { ...prev, mapped, missing_fields: missing };
    });
    setDirty(true);
  };

  const updateTableCell = (
    table: string,
    rowIndex: number,
    column: string,
    value: JsonValue
  ) => {
    setMapping((prev) => {
      if (!prev) return prev;
      const existing = prev.mapped[table];
      const rows: Array<Record<string, JsonValue>> = Array.isArray(existing)
        ? existing.map((row) =>
            row && typeof row === "object" && !Array.isArray(row)
              ? { ...(row as Record<string, JsonValue>) }
              : { value: row as JsonValue }
          )
        : [];
      while (rows.length <= rowIndex) rows.push({});
      rows[rowIndex] = { ...rows[rowIndex], [column]: value };
      // Ensure canonical columns stay visible: if field labels exist, add missing columns with empty string
      const labelLookup = fieldLabels?.[table] ?? {};
      Object.keys(labelLookup).forEach((col) => {
        if (!(col in rows[rowIndex])) {
          rows[rowIndex][col] = "";
        }
      });
      const mapped = { ...prev.mapped, [table]: rows };
      const missing = pruneMissing(prev.missing_fields, mapped);
      return { ...prev, mapped, missing_fields: missing };
    });
    setDirty(true);
  };

  const addTableRow = (table: string) => {
    setMapping((prev) => {
      if (!prev) return prev;
      const existing = prev.mapped[table];
      const rows: Array<Record<string, JsonValue>> = Array.isArray(existing)
        ? existing.map((row) =>
            row && typeof row === "object" && !Array.isArray(row)
              ? { ...(row as Record<string, JsonValue>) }
              : { value: row as JsonValue }
          )
        : [];
      rows.push({});
      const mapped = { ...prev.mapped, [table]: rows };
      return {
        ...prev,
        mapped,
        missing_fields: pruneMissing(prev.missing_fields, mapped),
      };
    });
    setDirty(true);
  };

  const handleSave = async () => {
    if (!mapping) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await saveMapping(sessionId, mapping);
      setMapping(updated);
      setDirty(false);
      toast.success("Mapping saved");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to save mapping";
      setError(msg);
      toast.error("Save failed", { description: msg });
    } finally {
      setSaving(false);
    }
  };

  const unresolvedMissing = mapping
    ? pruneMissing(mapping.missing_fields, mapping.mapped)
    : [];

  // Group missing fields by table
  const missingByTable = unresolvedMissing.reduce((acc, missing) => {
    if (!acc[missing.table]) {
      acc[missing.table] = [];
    }
    acc[missing.table].push(missing);
    return acc;
  }, {} as Record<string, MissingField[]>);

  return (
    <>
      <div className="space-y-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex-1">
            <H1 className="text-2xl">Canonical Mapping</H1>
            <P className="text-sm text-muted-foreground mt-1">
              Review mapped values before exporting to the client schema.
            </P>
            {mapping?.metadata?.generated_at && (
              <P className="text-xs text-muted-foreground mt-1.5">
                Last generated:{" "}
                {new Date(mapping.metadata.generated_at).toLocaleString()}
              </P>
            )}
            {jobStatus?.status === "running" && (
              <div className="mt-2">
                <Badge variant="secondary">Mapping in progress, this can take some time...</Badge>
              </div>
            )}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Button variant="outline" onClick={beginMappingJob} disabled={isMappingRunning}>
              {isMappingRunning && <Loader2 className="h-4 w-4 animate-spin mr-1" />}
              {isMappingRunning ? "Running..." : "Regenerate Mapping"}
            </Button>
            <Button
              variant="outline"
              onClick={async () => {
                if (!mapping) return;
                setExporting(true);
                setError(null);
                try {
                  const result = await exportWorkbook(sessionId);
                  const url =
                    result.download_url.startsWith("http") ||
                    result.download_url.startsWith("https")
                      ? result.download_url
                      : `${window.location.origin.replace(/\/$/, "")}${result.download_url}`;
                  window.open(url, "_blank", "noopener,noreferrer");
                  toast.success("Excel generated");
                } catch (err) {
                  const msg =
                    err instanceof Error
                      ? err.message
                      : "Failed to generate Excel";
                  setError(msg);
                  toast.error("Export failed", { description: msg });
                } finally {
                  setExporting(false);
                }
              }}
              disabled={!mapping || exporting || isMappingRunning}
            >
              {exporting && <Loader2 className="h-4 w-4 animate-spin mr-1" />}
              {exporting ? "Generating..." : "Generate Excel"}
            </Button>
            <Button
              onClick={handleSave}
              disabled={!mapping || saving || !dirty || isMappingRunning}
            >
              {saving && <Loader2 className="h-4 w-4 animate-spin mr-1" />}
              {saving ? "Saving..." : "Save Mapping"}
            </Button>
            <Button
              variant="outline"
              disabled={!canAskAi}
              onClick={() => {
                if (!canAskAi) return;
                const url = `${CHATBOT_URL}?session_id=${encodeURIComponent(
                  sessionId
                )}`;
                window.open(url, "_blank", "noopener,noreferrer");
              }}
            >
              Ask AI
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-4">
            {loading && (
              <div className="space-y-4">
                <div className="rounded border p-6 space-y-4">
                  <div className="flex items-center gap-3">
                    <div className="relative">
                      <div className="h-10 w-10 rounded-full border-4 border-muted" />
                      <div className="absolute inset-0 h-10 w-10 animate-spin rounded-full border-4 border-transparent border-t-primary" />
                    </div>
                    <div className="space-y-2 flex-1">
                      <Skeleton className="h-5 w-48" />
                      <Skeleton className="h-4 w-96" />
                    </div>
                  </div>
                  <div className="space-y-3">
                    <Skeleton className="h-12 w-full" />
                    <Skeleton className="h-12 w-full" />
                    <Skeleton className="h-12 w-full" />
                  </div>
                </div>
              </div>
            )}
            {error && (
              <div className="rounded border border-red-200 bg-red-50 p-4 flex items-start gap-3">
                <AlertCircle className="h-5 w-5 text-red-600 mt-0.5" />
                <div>
                  <P className="text-sm font-medium text-red-900">
                    Mapping Error
                  </P>
                  <P className="text-sm text-red-700">{error}</P>
                </div>
              </div>
            )}
            {!loading && !mapping && (
              <div className="rounded border p-6">
                <P>No mapping data yet. Run the mapper to begin.</P>
              </div>
            )}

            {mapping && (
              <Accordion type="multiple" className="rounded border divide-y">
                {Object.entries(mapping.mapped).map(
                  ([tableName, tableValue]) => (
                    <AccordionItem key={tableName} value={tableName}>
                      <AccordionTrigger className="px-3 text-left">
                        <div className="flex flex-col text-left">
                          <span className="text-sm font-semibold break-words">
                            {formatLabel(tableLabels?.[tableName] ?? tableName)}
                          </span>
                          {tableLabels?.[tableName] && (
                            <span className="text-xs text-muted-foreground break-all">
                              {tableName}
                            </span>
                          )}
                        </div>
                      </AccordionTrigger>
                      <AccordionContent className="px-3">
                        <div className="space-y-2">
                          {Array.isArray(tableValue) ? (
                            <div className="space-y-3">
                              <div className="flex items-center justify-between">
                                <P className="text-sm text-muted-foreground">
                                  {tableValue.length} row
                                  {tableValue.length === 1 ? "" : "s"}
                                </P>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => addTableRow(tableName)}
                                >
                                  Add row
                                </Button>
                              </div>
                              <div className="overflow-auto rounded border">
                                <table className="w-full text-sm">
                                  <thead>
                                    <tr className="bg-muted/50 text-left">
                                      {(() => {
                                        const labelLookup =
                                          fieldLabels?.[tableName] ?? {};
                                        const rowKeys = new Set<string>();
                                        tableValue.forEach((row) => {
                                          if (
                                            row &&
                                            typeof row === "object" &&
                                            !Array.isArray(row)
                                          ) {
                                            Object.keys(
                                              row as Record<string, JsonValue>
                                            ).forEach((k) => rowKeys.add(k));
                                          }
                                        });
                                        const columns = [
                                          ...Object.keys(labelLookup),
                                          ...Array.from(rowKeys).filter(
                                            (k) =>
                                              !(labelLookup && labelLookup[k])
                                          ),
                                        ];
                                        return columns.map((col) => (
                                          <th
                                            key={col}
                                            className="px-3 py-2 border-b font-semibold"
                                          >
                                            {formatLabel(
                                              labelLookup[col] ?? col
                                            )}
                                          </th>
                                        ));
                                      })()}
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {tableValue.map((row, ri) => {
                                      const labelLookup =
                                        fieldLabels?.[tableName] ?? {};
                                      const rowKeys = new Set<string>();
                                      if (
                                        row &&
                                        typeof row === "object" &&
                                        !Array.isArray(row)
                                      ) {
                                        Object.keys(
                                          row as Record<string, JsonValue>
                                        ).forEach((k) => rowKeys.add(k));
                                      }
                                      const columns = [
                                        ...Object.keys(labelLookup),
                                        ...Array.from(rowKeys).filter(
                                          (k) =>
                                            !(labelLookup && labelLookup[k])
                                        ),
                                      ];
                                      return (
                                        <tr
                                          key={`${tableName}-row-${ri}`}
                                          className="border-b last:border-b-0"
                                        >
                                          {columns.map((col) => {
                                            const value =
                                              row &&
                                              typeof row === "object" &&
                                              !Array.isArray(row)
                                                ? (
                                                    row as Record<
                                                      string,
                                                      JsonValue
                                                    >
                                                  )[col]
                                                : row;
                                            return (
                                              <td
                                                key={`${tableName}-${ri}-${col}`}
                                                className="px-3 py-2 align-top"
                                              >
                                                <FieldEditor
                                                  value={value as JsonValue}
                                                  onChange={(v) =>
                                                    updateTableCell(
                                                      tableName,
                                                      ri,
                                                      col,
                                                      v
                                                    )
                                                  }
                                                />
                                              </td>
                                            );
                                          })}
                                        </tr>
                                      );
                                    })}
                                  </tbody>
                                </table>
                              </div>
                            </div>
                          ) : (
                            (() => {
                              const fields =
                                tableValue && typeof tableValue === "object"
                                  ? (tableValue as Record<string, JsonValue>)
                                  : { value: tableValue as JsonValue };
                              return Object.entries(fields).map(
                                ([fieldName, value]) => {
                                  const safeValue =
                                    value === undefined
                                      ? ""
                                      : (value as JsonValue);
                                  const label = formatLabel(
                                    fieldLabels?.[tableName]?.[fieldName] ??
                                      fieldName
                                  );
                                  return (
                                    <div
                                      key={`${tableName}.${fieldName}`}
                                      className="grid grid-cols-12 items-start gap-3"
                                    >
                                      <div className="col-span-4 space-y-1">
                                        <div className="font-medium text-sm break-words">
                                          {label}
                                        </div>
                                        {label !== fieldName && (
                                          <P className="text-xs text-muted-foreground break-all">
                                            {fieldName}
                                          </P>
                                        )}
                                      </div>
                                      <div className="col-span-8">
                                        <FieldEditor
                                          value={safeValue}
                                          onChange={(v) =>
                                            updateField(tableName, fieldName, v)
                                          }
                                        />
                                      </div>
                                    </div>
                                  );
                                }
                              );
                            })()
                          )}
                        </div>
                      </AccordionContent>
                    </AccordionItem>
                  )
                )}
              </Accordion>
            )}
          </div>

          <div className="space-y-4">
            <div className="rounded border border-red-200 bg-red-50/50 overflow-hidden">
              <div className="p-4 border-b border-red-200 bg-red-100/50">
                <div className="flex items-center gap-2">
                  <AlertCircle className="h-5 w-5 text-red-600" />
                  <H3 className="text-lg font-semibold text-red-900">
                    Missing Fields
                  </H3>
                  {unresolvedMissing.length > 0 && (
                    <Badge variant="destructive" className="ml-auto">
                      {unresolvedMissing.length}
                    </Badge>
                  )}
                </div>
                <P className="text-xs text-red-700 mt-1">
                  Fields that could not be mapped from the source data
                </P>
              </div>
              <ScrollArea className="h-[600px]">
                <div className="p-4">
                  {loading ? (
                    <div className="space-y-3 py-4">
                      <Skeleton className="h-12 w-full" />
                      <Skeleton className="h-12 w-full" />
                      <Skeleton className="h-12 w-full" />
                    </div>
                  ) : unresolvedMissing.length === 0 ? (
                    <div className="text-center py-8">
                      <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-green-100 mb-3">
                        <svg
                          className="w-6 h-6 text-green-600"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M5 13l4 4L19 7"
                          />
                        </svg>
                      </div>
                      <P className="text-sm font-medium text-green-900">
                        All fields mapped!
                      </P>
                      <P className="text-xs text-green-700 mt-1">
                        All canonical fields have values.
                      </P>
                    </div>
                  ) : (
                    <Accordion type="multiple" className="space-y-2">
                      {Object.entries(missingByTable).map(
                        ([tableName, fields]) => (
                          <AccordionItem
                            key={tableName}
                            value={tableName}
                            className="rounded border border-red-300 bg-white overflow-hidden"
                          >
                            <AccordionTrigger className="px-3 py-2 hover:bg-red-50/50 transition-colors">
                              <div className="flex items-center gap-2 text-left w-full">
                                <span className="text-sm font-semibold text-red-900 flex-1">
                                  {formatLabel(
                                    tableLabels?.[tableName] ?? tableName
                                  )}
                                </span>
                                <Badge
                                  variant="destructive"
                                  className="bg-red-600"
                                >
                                  {fields.length}
                                </Badge>
                              </div>
                            </AccordionTrigger>
                            <AccordionContent className="px-3 pb-3 bg-white">
                              <div className="space-y-2 pt-2">
                                {fields.map((missing) => (
                                  <div
                                    key={`${missing.table}.${missing.field}`}
                                    className="text-sm p-2 rounded bg-red-50/50 border border-red-200"
                                  >
                                    <div className="font-medium text-red-900">
                                      {formatLabel(
                                        missing.field_label ??
                                          fieldLabels?.[missing.table]?.[
                                            missing.field
                                          ] ??
                                          missing.field
                                      )}
                                    </div>
                                    {missing.reason && (
                                      <P className="text-xs text-red-600 mt-1">
                                        {missing.reason}
                                      </P>
                                    )}
                                  </div>
                                ))}
                              </div>
                            </AccordionContent>
                          </AccordionItem>
                        )
                      )}
                    </Accordion>
                  )}
                </div>
              </ScrollArea>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
