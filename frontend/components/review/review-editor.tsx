"use client";

import { useState } from "react";
import type { SessionDetail } from "@/types/extraction";
import { updateSession } from "@/lib/api";
import { flattenExtracted, unflattenToJson } from "./utils";
import type { ReviewField } from "./types";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { H1, H3, P } from "@/components/ui/typography";

type Props = {
  session: SessionDetail;
};

function confidenceColor(level?: string) {
  switch (level) {
    case "high":
      return "bg-green-100 text-green-800";
    case "medium":
      return "bg-yellow-100 text-yellow-800";
    default:
      return "bg-red-100 text-red-800";
  }
}

export default function ReviewEditor({ session }: Props) {
  const { fields: initialFields } = flattenExtracted(
    session.extracted_json,
    session.confidences
  );
  const [fields, setFields] = useState<ReviewField[]>(initialFields);
  const [active, setActive] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onChange = (idx: number, value: string) => {
    setFields((prev) => prev.map((f, i) => (i === idx ? { ...f, value } : f)));
  };

  const onSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const final_json = unflattenToJson(fields);
      await updateSession(session._id, final_json);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to save";
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  const snippetFor = (table: string, key: string) =>
    session.text_snippets?.[`${table}.${key}`];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2 space-y-4">
        <H1 className="text-2xl">Review & Fix</H1>
        <P>Fill missing or low-confidence fields. Use the snippet panel for context.</P>
        <div className="space-y-3">
          {fields.map((f, idx) => (
            <div key={`${f.table}.${f.key}`} className="grid grid-cols-12 items-center gap-3">
              <div className="col-span-4">
                <H3 className="text-base font-medium">{f.table} / {f.key}</H3>
              </div>
              <div className="col-span-6">
                <Input
                  value={f.value}
                  onChange={(e) => onChange(idx, e.target.value)}
                  onFocus={() => setActive(`${f.table}.${f.key}`)}
                />
              </div>
              <div className="col-span-2">
                <Badge className={confidenceColor(f.confidence)}>{f.confidence ?? "low"}</Badge>
              </div>
            </div>
          ))}
        </div>
        <div className="pt-4">
          <Button onClick={onSave} disabled={saving}>{saving ? "Saving…" : "Save & Continue"}</Button>
          {error && <P className="text-red-600 mt-2">{error}</P>}
        </div>
      </div>
      <div className="lg:col-span-1 space-y-2">
        <H3 className="text-lg">Matched Snippet</H3>
        <ScrollArea className="h-[60vh] rounded border p-3">
          {active ? (
            <pre className="whitespace-pre-wrap text-sm text-muted-foreground">
              {(() => {
                const parts = active.split(".");
                const t = parts[0];
                const k = parts.slice(1).join(".");
                return snippetFor(t, k) || "No snippet available";
              })()}
            </pre>
          ) : (
            <P>Select a field to view the source snippet.</P>
          )}
        </ScrollArea>
      </div>
    </div>
  );
}
