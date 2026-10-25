import type { Metadata } from "next";
import { Toaster } from "sonner";
import "./globals.css";
import { Shell } from "@/components/shell";
import { TooltipProvider } from "@/components/ui/tooltip";
import { THEME_SCRIPT } from "@/components/theme";

export const metadata: Metadata = {
  title: "TechFocus · Creator",
  description: "What to post, how to hook, what works",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body>
        <TooltipProvider>
          <Shell>{children}</Shell>
        </TooltipProvider>
        <Toaster theme="system" position="bottom-right" richColors closeButton />
      </body>
    </html>
  );
}
