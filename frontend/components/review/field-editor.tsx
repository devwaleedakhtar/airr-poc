"use client";

import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { JsonValue } from "@/types/json";

type Props = {
  value: JsonValue;
  onChange: (v: JsonValue) => void;
  onFocus?: () => void;
};

function isPrimitive(v: unknown): v is string | number | boolean | null {
  return (
    typeof v === "string" || typeof v === "number" || typeof v === "boolean" || v === null
  );
}

export default function FieldEditor({ value, onChange, onFocus }: Props) {
  const primitive = isPrimitive(value);
  const [text, setText] = useState<string>(primitive ? String(value ?? "") : "");
  const [jsonText, setJsonText] = useState<string>(
    primitive ? "" : JSON.stringify(value as Exclude<JsonValue, string | number | boolean | null>, null, 2)
  );
  const [jsonError, setJsonError] = useState<string | null>(null);

  useEffect(() => {
    if (primitive) setText(String(value ?? ""));
    else setJsonText(JSON.stringify(value as Exclude<JsonValue, string | number | boolean | null>, null, 2));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [primitive]);

  if (primitive) {
    return (
      <Input
        value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={() => onChange(text)}
        onFocus={onFocus}
      />
    );
  }

  return (
    <div className="space-y-1">
      <Textarea
        value={jsonText}
        onChange={(e) => {
          setJsonText(e.target.value);
          setJsonError(null);
        }}
        onBlur={() => {
          try {
            const parsed = JSON.parse(jsonText);
            onChange(parsed);
            setJsonError(null);
          } catch {
            setJsonError("Invalid JSON");
          }
        }}
        onFocus={onFocus}
      />
      {jsonError && <div className="text-xs text-red-600">{jsonError}</div>}
    </div>
  );
}

