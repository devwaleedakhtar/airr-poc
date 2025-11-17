"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { mapSession, saveMapping } from "@/lib/api";
import type { MappingResult, MissingField } from "@/types/mapping";
import type { JsonValue } from "@/types/json";
import { Button } from "@/components/ui/button";
import { H1, H3, P } from "@/components/ui/typography";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import JsonPreview from "@/components/shared/json-preview";
import FieldEditor from "./field-editor";

type Props = {
  sessionId: string;
  initialMapping: MappingResult | null;
};

function isEmptyValue(value: JsonValue | undefined): boolean {
  if (value === null || value === undefined) return true;
  if (typeof value === "string") return value.trim().length === 0;
  return false;
}

function pruneMissing(
  missing: MissingField[],
  mapped: Record<string, Record<string, JsonValue>>
): MissingField[] {
  return missing.filter((item) => {
    const value = mapped?.[item.table]?.[item.field];
    return isEmptyValue(value);
  });
}

export default function MappingView({ sessionId, initialMapping }: Props) {
  const [mapping, setMapping] = useState<MappingResult | null>(initialMapping);
  const [loading, setLoading] = useState(!initialMapping);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const tableLabels = mapping?.metadata?.table_labels ?? {};
  const fieldLabels = mapping?.metadata?.field_labels ?? {};

  const fetchMapping = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await mapSession(sessionId);
      setMapping(result);
      setDirty(false);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to map session";
      setError(msg);
      toast.error("Mapping failed", { description: msg });
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    if (!initialMapping) {
      fetchMapping();
    }
  }, [initialMapping, fetchMapping]);

  const updateField = (table: string, field: string, value: JsonValue) => {
    setMapping((prev) => {
      if (!prev) return prev;
      const nextTable = { ...(prev.mapped[table] ?? {}), [field]: value };
      const mapped = { ...prev.mapped, [table]: nextTable };
      const missing = pruneMissing(prev.missing_fields, mapped);
      return { ...prev, mapped, missing_fields: missing };
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

  const unresolvedMissing = mapping ? pruneMissing(mapping.missing_fields, mapping.mapped) : [];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2 space-y-4">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <H1 className="text-2xl">Canonical Mapping</H1>
            <P className="text-sm text-muted-foreground">
              Review mapped values before exporting to the client schema.
            </P>
            {mapping?.metadata?.generated_at && (
              <P className="text-xs text-muted-foreground">
                Last generated: {new Date(mapping.metadata.generated_at).toLocaleString()}
              </P>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={fetchMapping} disabled={loading}>
              {loading ? "Running..." : "Regenerate Mapping"}
            </Button>
            <Button onClick={handleSave} disabled={!mapping || saving || !dirty}>
              {saving ? "Saving..." : "Save Mapping"}
            </Button>
          </div>
        </div>

        {loading && <P>Generating canonical mapping...</P>}
        {error && <P className="text-red-600">{error}</P>}
        {!loading && !mapping && (
          <div className="rounded border p-6">
            <P>No mapping data yet. Run the mapper to begin.</P>
          </div>
        )}

        {mapping && (
          <Accordion type="multiple" className="rounded border divide-y">
            {Object.entries(mapping.mapped).map(([tableName, fields]) => (
              <AccordionItem key={tableName} value={tableName}>
                <AccordionTrigger className="px-3 text-left">
                  <div className="flex flex-col text-left">
                    <span className="text-sm font-semibold break-words">
                      {tableLabels?.[tableName] ?? tableName}
                    </span>
                    {tableLabels?.[tableName] && (
                      <span className="text-xs text-muted-foreground break-all">{tableName}</span>
                    )}
                  </div>
                </AccordionTrigger>
                <AccordionContent className="px-3">
                  <div className="space-y-2">
                    {Object.entries(fields).map(([fieldName, value]) => {
                      const safeValue = (value === undefined ? "" : (value as JsonValue));
                      const label = fieldLabels?.[tableName]?.[fieldName] ?? fieldName;
                      return (
                        <div
                          key={`${tableName}.${fieldName}`}
                          className="grid grid-cols-12 items-start gap-3"
                        >
                          <div className="col-span-4 space-y-1">
                            <div className="font-medium text-sm break-words">{label}</div>
                            {label !== fieldName && (
                              <P className="text-xs text-muted-foreground break-all">{fieldName}</P>
                            )}
                          </div>
                          <div className="col-span-8">
                            <FieldEditor value={safeValue} onChange={(v) => updateField(tableName, fieldName, v)} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        )}
      </div>

      <div className="space-y-4">
        <div className="rounded border p-4 space-y-3">
          <H3 className="text-lg">Missing Fields</H3>
          {unresolvedMissing.length === 0 ? (
            <P className="text-sm text-muted-foreground">All canonical fields have values.</P>
          ) : (
            <div className="space-y-4">
              {unresolvedMissing.map((missing) => (
                <div key={`${missing.table}.${missing.field}`} className="space-y-2 rounded border p-3">
                  <div className="space-y-1">
                    <div className="font-medium text-sm break-words">
                      {missing.field_label ?? fieldLabels?.[missing.table]?.[missing.field] ?? missing.field}
                    </div>
                    <P className="text-xs text-muted-foreground break-words">
                      {missing.table_label ?? tableLabels?.[missing.table] ?? missing.table}
                    </P>
                    <P className="text-xs text-muted-foreground">{missing.reason}</P>
                  </div>
                  <FieldEditor
                    value={
                      (mapping?.mapped?.[missing.table]?.[missing.field] ??
                        "") as JsonValue
                    }
                    onChange={(v) => updateField(missing.table, missing.field, v)}
                  />
                  {missing.source_fields && missing.source_fields.length > 0 && (
                    <P className="text-xs text-muted-foreground">
                      Possible sources: {missing.source_fields.join(", ")}
                    </P>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="rounded border p-4">
          <H3 className="text-lg">Canonical JSON</H3>
          <JsonPreview data={mapping?.mapped ?? {}} title="Mapped JSON" />
        </div>
      </div>
    </div>
  );
}
