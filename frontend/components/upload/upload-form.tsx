"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { FileSpreadsheet } from "lucide-react";
import { convertWorkbook, extractWorkbook, uploadWorkbook } from "@/lib/api";
import type { UploadState } from "@/components/upload/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { H1, P } from "@/components/ui/typography";
import {
  ProgressIndicator,
  type ProgressStep,
} from "@/components/shared/progress-indicator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const MAX_FILE_SIZE = 10485760; // 10 MB in bytes

export default function UploadForm() {
  const router = useRouter();
  const [state, setState] = useState<UploadState>({ step: "idle" });

  const onFileChange = async (file: File) => {
    // Check file size
    if (file.size > MAX_FILE_SIZE) {
      toast.error("File size too large", {
        description: `File size is ${(file.size / 1024 / 1024).toFixed(2)} MB. Maximum allowed is 10 MB.`,
      });
      return;
    }

    setState({ step: "uploading" });
    try {
      const res = await uploadWorkbook(file);
      const selected = res.sheets.includes("Input")
        ? "Input"
        : res.sheets[0] || null;
      setState({
        step: "uploaded",
        workbookId: res.workbook_id,
        sheets: res.sheets,
        selectedSheet: selected,
      });
      toast.success("Workbook uploaded successfully", {
        description: `Found ${res.sheets.length} sheet(s)`,
      });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Upload failed";
      toast.error("Upload failed", {
        description: msg,
      });
      setState({ step: "idle" });
    }
  };

  const onExtract = async () => {
    if (state.step !== "uploaded" || !state.selectedSheet) return;
    const { workbookId, sheets, selectedSheet } = state;
    setState({ step: "converting", workbookId, sheets, selectedSheet });
    try {
      await convertWorkbook(workbookId, selectedSheet);
      setState({ step: "extracting", workbookId, sheets, selectedSheet });
      const r = await extractWorkbook(workbookId, selectedSheet);
      setState({ step: "done", sessionId: r.session_id });
      toast.success("Extraction complete", {
        description: "Redirecting to review page...",
      });
      router.push(`/review/${r.session_id}`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Extraction failed";
      toast.error("Extraction failed", {
        description: msg,
      });
      setState({ step: "uploaded", workbookId, sheets, selectedSheet });
    }
  };

  const getProgressStep = (): ProgressStep | null => {
    if (state.step === "uploading") return "uploading";
    if (state.step === "converting") return "converting";
    if (state.step === "extracting") return "extracting";
    return null;
  };

  const isProcessing =
    state.step === "uploading" ||
    state.step === "converting" ||
    state.step === "extracting";
  const progressStep = getProgressStep();

  return (
    <div className="space-y-6">
      <div>
        <H1>Upload Workbook</H1>
        <P className="text-muted-foreground mt-2">
          Upload an Excel file to extract financial assumptions and metrics.
        </P>
      </div>

      {progressStep && (
        <ProgressIndicator currentStep={progressStep} className="my-8" />
      )}

      {!isProcessing && (
        <>
          <div className="border border-dashed rounded-lg p-8 space-y-3 text-center">
            <Label htmlFor="file" className="cursor-pointer">
              <div className="w-full space-y-2 flex flex-col items-center">
                <FileSpreadsheet className="w-12 h-12 text-muted-foreground" />
                <div className="font-medium text-center">Select Excel file</div>
                <P className="text-sm text-muted-foreground text-center">
                  Supports .xlsx, .xlsm, and .xls formats
                </P>
              </div>
            </Label>
            <Input
              id="file"
              type="file"
              accept=".xlsx,.xlsm,.xls"
              className="max-w-sm mx-auto"
              onChange={(e) => {
                const f = (e.target as HTMLInputElement).files?.[0];
                if (f) onFileChange(f);
              }}
            />
          </div>

          {state.step === "uploaded" && (
            <div className="space-y-4 border rounded-lg p-6">
              <div className="space-y-2">
                <Label htmlFor="sheet">Select Sheet to Extract</Label>
                <Select
                  value={state.selectedSheet ?? undefined}
                  onValueChange={(v) =>
                    setState({ ...state, selectedSheet: v })
                  }
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
                <P className="text-sm text-muted-foreground">
                  Choose the sheet containing the financial assumptions you want
                  to extract.
                </P>
              </div>
              <Button
                onClick={onExtract}
                disabled={!state.selectedSheet}
                size="lg"
              >
                Start Extraction
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
