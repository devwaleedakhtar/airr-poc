"use client";

import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { H3 } from "@/components/ui/typography";

type JsonPreviewProps = {
  data: unknown;
  title?: string;
};

export default function JsonPreview({ data, title = "JSON Preview" }: JsonPreviewProps) {
  const [copied, setCopied] = useState(false);
  const pretty = useMemo(() => JSON.stringify(data ?? {}, null, 2), [data]);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <H3 className="text-base">{title}</H3>
        <Button
          variant="outline"
          size="sm"
          onClick={async () => {
            await navigator.clipboard.writeText(pretty);
            setCopied(true);
            setTimeout(() => setCopied(false), 1200);
          }}
        >
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      <ScrollArea className="h-64 rounded border p-3 bg-secondary/20">
        <pre className="text-xs whitespace-pre-wrap break-words">{pretty}</pre>
      </ScrollArea>
    </div>
  );
}

