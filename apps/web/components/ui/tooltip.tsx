"use client";
import * as React from "react";
import * as T from "@radix-ui/react-tooltip";

export function Tooltip({ content, children, open, onOpenChange }: { content: React.ReactNode; children: React.ReactNode; open?: boolean; onOpenChange?: (o: boolean) => void }) {
  return (
    <T.Root delayDuration={150} open={open} onOpenChange={onOpenChange}>
      <T.Trigger asChild>{children}</T.Trigger>
      <T.Portal>
        <T.Content sideOffset={4} className="z-50 max-w-xs rounded-xl border border-line bg-panel px-3 py-2 text-xs leading-relaxed text-fg shadow-lg">
          {content}
        </T.Content>
      </T.Portal>
    </T.Root>
  );
}

export const TooltipProvider = T.Provider;
