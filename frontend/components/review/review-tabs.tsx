"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import type { SessionDetail } from "@/types/extraction";
import ReviewEditor from "./review-editor";
import MappingView from "./mapping-view";

type Tab = "extraction" | "mapping";

type Props = {
  session: SessionDetail;
};

const tabs: { id: Tab; label: string }[] = [
  { id: "extraction", label: "Extraction" },
  { id: "mapping", label: "Mapping" },
];

export default function ReviewTabs({ session }: Props) {
  const [active, setActive] = useState<Tab>("extraction");

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 border-b">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActive(tab.id)}
            className={cn(
              "px-4 py-2 text-sm font-medium transition-colors",
              active === tab.id
                ? "border-b-2 border-black text-black"
                : "text-muted-foreground hover:text-foreground"
            )}
            aria-pressed={active === tab.id}
          >
            {tab.label}
          </button>
        ))}
      </div>
      {active === "extraction" ? (
        <ReviewEditor session={session} />
      ) : (
        <MappingView sessionId={session._id} initialMapping={session.mapping ?? null} />
      )}
    </div>
  );
}
