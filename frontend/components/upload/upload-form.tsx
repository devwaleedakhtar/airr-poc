"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { convertWorkbook, extractWorkbook, uploadWorkbook } from "@/lib/api";
import type { UploadState } from "@/components/upload/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export default function UploadForm() {
  const router = useRouter();
  const [state, setState] = useState<UploadState>({ step: "idle" });
  const [error, setError] = useState<string | null>(null);

  const onFileChange = async (file: File) => {
    setError(null);
    setState({ step: "uploading" });
    try {
      const res = await uploadWorkbook(file);
      const selected = res.sheets.includes("Input") ? "Input" : res.sheets[0] || null;
      setState({ step: "uploaded", workbookId: res.workbook_id, sheets: res.sheets, selectedSheet: selected });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Upload failed";
      setError(msg);
      setState({ step: "idle" });
    }
  };

  const onExtract = async () => {
    if (state.step !== "uploaded" || !state.selectedSheet) return;
    setError(null);
    setState({ step: "converting", workbookId: state.workbookId, selectedSheet: state.selectedSheet });
    try {
      await convertWorkbook(state.workbookId, state.selectedSheet);
      setState({ step: "extracting", workbookId: state.workbookId, selectedSheet: state.selectedSheet });
      const r = await extractWorkbook(state.workbookId, state.selectedSheet);
      setState({ step: "done", sessionId: r.session_id });
      router.push(`/review/${r.session_id}`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Extraction failed";
      setError(msg);
      if (state.step === "converting" || state.step === "extracting") {
        setState({ step: "uploaded", workbookId: state.workbookId, sheets: state.sheets, selectedSheet: state.selectedSheet });
      }
    }
  };

  return (
    <div className="space-y-6">
      <H1>Upload Workbook</H1>

      <div className="border border-dashed rounded p-6 space-y-2">
        <Label htmlFor="file">Select Excel file</Label>
        <Input
          id="file"
          type="file"
          accept=".xlsx,.xlsm,.xls"
          onChange={(e) => {
            const f = (e.target as HTMLInputElement).files?.[0];
            if (f) onFileChange(f);
          }}
        />
        <P className="text-sm">Only .xlsx, .xlsm, and .xls files are supported.</P>
      </div>

      {state.step === "uploaded" && (
        <div className="space-y-3">
          <div className="space-y-2">
            <Label htmlFor="sheet">Select Sheet</Label>
            <Select
              value={state.selectedSheet ?? undefined}
              onValueChange={(v) => setState({ ...state, selectedSheet: v })}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select a sheet" />
              </SelectTrigger>
              <SelectContent>
                {state.sheets.map((s) => (
                  <SelectItem key={s} value={s}>
                    {s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button onClick={onExtract}>Extract</Button>
        </div>
      )}

      {state.step === "uploading" && <p>Analyzing workbook…</p>}
      {state.step === "converting" && <p>Converting selected sheet to PDF…</p>}
      {state.step === "extracting" && <p>Extracting assumptions…</p>}
      {error && <p className="text-red-600">{error}</p>}
    </div>
  );
}
import { H1, P } from "@/components/ui/typography";
