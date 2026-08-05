import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "AI Video OS",
  description: "Direct, don't edit.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
