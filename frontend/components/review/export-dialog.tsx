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
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-5xl max-h-[90vh]">
        <DialogHeader>
          <DialogTitle>Workbook Ready</DialogTitle>
          <DialogDescription>
            We populated the template with your mapped values. Review the
            applied fields below or download the file.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <Button asChild>
              <a
                href={exportResult.download_url}
                target="_blank"
                rel="noreferrer"
              >
                Download Workbook
              </a>
            </Button>
            <span className="text-xs text-muted-foreground">
              Saved to exports/{sessionId}
            </span>
          </div>

          <div className="rounded border overflow-hidden flex-1">
            <iframe
              src={`https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(
                exportResult.download_url
              )}`}
              width="100%"
              height="600"
              className="border-0"
              title="Excel Preview"
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
