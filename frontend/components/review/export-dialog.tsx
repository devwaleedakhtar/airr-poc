"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import type { ExportResult } from "@/types/mapping";
import { API_BASE } from "@/lib/api";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  exportResult: ExportResult;
  sessionId: string;
};

export default function ExportDialog({
  open,
  onOpenChange,
  exportResult,
  sessionId,
}: Props) {
  const downloadUrl = exportResult.download_url.startsWith("http")
    ? exportResult.download_url
    : `${API_BASE}${exportResult.download_url}`;
  const canEmbed =
    downloadUrl.startsWith("https://") &&
    !downloadUrl.includes("localhost") &&
    !downloadUrl.includes("127.0.0.1");
  const iframeSrc = canEmbed
    ? `https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(
        downloadUrl
      )}`
    : null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[90%] h-[90vh]">
        <DialogHeader>
          <DialogTitle>Workbook Ready</DialogTitle>
          <DialogDescription>
            We populated the template with your mapped values. Review the
            applied fields below or download the file.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="flex items-center justify-end gap-2">
            <div className="flex flex-col gap-2">
              <Button asChild>
                <a href={downloadUrl} target="_blank" rel="noreferrer">
                  Download Workbook
                </a>
              </Button>

              <span className="text-xs text-muted-foreground">
                Saved to exports/{sessionId}
              </span>
            </div>
          </div>

          <div className="rounded border overflow-hidden flex-1 overflow-hidden">
            {iframeSrc ? (
              <iframe
                src={iframeSrc}
                width="100%"
                height="500"
                className="border-0"
                title="Excel Preview"
              />
            ) : (
              <div className="p-4 text-sm text-muted-foreground">
                Preview is unavailable. Use{" "}
                <span className="font-medium">Download Workbook</span> to open
                the file in Excel.
              </div>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
