import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Smile Dental voice assistant",
  description: "A phone-style booking assistant whose brain is plain rules, not an LLM.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
