import type { Metadata } from "next";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "RunTrace", template: "%s · RunTrace" },
  description: "Persistent experiment memory for autonomous research agents.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className="h-full antialiased"
    >
      <body className="min-h-full flex flex-col"><TooltipProvider>{children}<Toaster richColors /></TooltipProvider></body>
    </html>
  );
}
