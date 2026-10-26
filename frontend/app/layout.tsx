import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VoxDesk — Northline Studio",
  description:
    "An explainable voice receptionist. Every decision made by deterministic Python rules.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-theme="dark" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `try { if (localStorage.getItem("voxdesk.theme") === "light") document.documentElement.dataset.theme = "light"; } catch {}`,
          }}
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
