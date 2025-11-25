"use client";

import { useState } from "react";
import type { SessionDetail } from "@/types/extraction";
import type { JsonValue } from "@/types/json";
import { API_BASE, updateSession } from "@/lib/api";
import { groupExtracted, toNestedJson } from "./utils";
import type { ReviewTable } from "./types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { H1, H3, P } from "@/components/ui/typography";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import JsonPreview from "@/components/shared/json-preview";
import FieldEditor from "./field-editor";

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
  const { tables: initialTables } = groupExtracted(session.extracted_json, session.confidences);
  const [tables, setTables] = useState<ReviewTable[]>(initialTables);
  const [active, setActive] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewMode, setPreviewMode] = useState<"extracted" | "edited">("edited");

  const onChange = (tIdx: number, fIdx: number, value: JsonValue) => {
    setTables((prev) =>
      prev.map((t, i) =>
        i === tIdx
          ? { ...t, fields: t.fields.map((f, j) => (j === fIdx ? { ...f, value } : f)) }
          : t
      )
    );
  };

  const onSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const final_json = toNestedJson(tables);
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
    <div className="space-y-4">
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-4">
          <div className="space-y-1">
            <H1 className="text-2xl">Review & Fix</H1>
            <P>Fill missing or low-confidence fields. Use the snippet panel for context.</P>
          </div>
          {session.pdf_url && (
            <Button asChild variant="outline" size="sm">
              <a
                href={`${API_BASE}/sessions/${session._id}/pdf`}
                target="_blank"
                rel="noreferrer"
              >
                Download PDF
              </a>
            </Button>
          )}
        </div>
        <Accordion type="multiple" className="rounded border divide-y">
          {tables.map((t, ti) => (
            <AccordionItem key={t.name} value={t.name}>
              <AccordionTrigger className="px-3">{t.name}</AccordionTrigger>
              <AccordionContent className="px-3">
                <div className="space-y-2">
                  {t.fields.map((f, fi) => (
                    <div key={`${f.table}.${f.key}`} className="grid grid-cols-12 items-center gap-3">
                      <div className="col-span-4">
                        <div className="font-medium text-sm">{f.key}</div>
                      </div>
                      <div className="col-span-6">
                        <FieldEditor
                          value={f.value}
                          onChange={(v) => onChange(ti, fi, v)}
                          onFocus={() => setActive(`${f.table}.${f.key}`)}
                        />
                      </div>
                      <div className="col-span-2">
                        <Badge className={confidenceColor(f.confidence)}>{f.confidence ?? "low"}</Badge>
                      </div>
                    </div>
                  ))}
                </div>
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
        <div className="pt-4 flex items-center gap-2">
          <Button onClick={onSave} disabled={saving}>{saving ? "Saving…" : "Save & Continue"}</Button>
          {error && <P className="text-red-600">{error}</P>}
        </div>
      </div>
      <div className="hidden space-y-4">
        <div>
          <H3 className="text-lg">Matched Snippet</H3>
          <ScrollArea className="h-[40vh] rounded border p-3">
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
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Button variant={previewMode === "edited" ? "default" : "outline"} size="sm" onClick={() => setPreviewMode("edited")}>
              Edited JSON
            </Button>
            <Button variant={previewMode === "extracted" ? "default" : "outline"} size="sm" onClick={() => setPreviewMode("extracted")}>
              Extracted JSON
            </Button>
          </div>
          <JsonPreview
            title={previewMode === "edited" ? "Edited JSON" : "Extracted JSON"}
            data={previewMode === "edited" ? toNestedJson(tables) : session.extracted_json}
          />
        </div>
      </div>
    </div>
  );
}
