import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Green Valley Clinic · Voice Assistant",
  description: "Rule-based voice assistant that books, reschedules and cancels clinic appointments.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
