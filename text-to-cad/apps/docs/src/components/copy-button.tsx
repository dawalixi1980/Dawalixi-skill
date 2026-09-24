"use client";

import { useEffect, useState } from "react";

type CopyButtonProps = {
  text: string;
  label?: string;
  compact?: boolean;
};

type CopyStatus = "idle" | "copied" | "error";

export function CopyButton({
  text,
  label = "Copy command",
  compact = false,
}: CopyButtonProps) {
  const [status, setStatus] = useState<CopyStatus>("idle");

  useEffect(() => {
    if (status === "idle") {
      return;
    }

    const timeout = window.setTimeout(() => setStatus("idle"), 1600);
    return () => window.clearTimeout(timeout);
  }, [status]);

  const copyText = async () => {
    setStatus("copied");

    try {
      await window.navigator.clipboard.writeText(text);
    } catch {
      setStatus("error");
    }
  };

  const isCopied = status === "copied";
  const isError = status === "error";
  const buttonLabel = isCopied ? "Copied" : isError ? "Copy failed" : label;

  return (
    <button
      type="button"
      className={`min-w-[4.25rem] shrink-0 cursor-pointer border-l border-border py-[7px] text-xs uppercase leading-none tracking-wider transition-colors ${
        isCopied
          ? "bg-primary text-primary-foreground hover:text-primary-foreground"
          : isError
            ? "bg-destructive text-destructive-foreground hover:text-destructive-foreground"
            : "bg-secondary text-muted-foreground hover:text-foreground"
      } ${
        compact ? "px-2.5" : "px-3"
      }`}
      onClick={copyText}
      aria-label={buttonLabel}
      title={buttonLabel}
      aria-live="polite"
    >
      {isCopied ? "copied" : isError ? "failed" : "copy"}
    </button>
  );
}
