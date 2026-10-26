"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Logo } from "./Logo";

const NAV = [
  { href: "/#how", label: "How it works" },
  { href: "/#handles", label: "What it handles" },
  { href: "/#brain", label: "The brain" },
];

export function SiteHeader() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 border-b border-ink-200/80 bg-white/85 backdrop-blur">
      <div className="container-page flex h-16 items-center justify-between">
        <Link href="/" className="flex items-center gap-2.5" onClick={() => setOpen(false)}>
          <Logo />
          <span className="text-[15px] font-semibold tracking-tight text-ink-900">
            Brightside <span className="font-normal text-ink-500">Voice</span>
          </span>
        </Link>

        <nav className="hidden items-center gap-8 md:flex" aria-label="Main">
          {NAV.map((item) => (
            <Link key={item.href} href={item.href} className="text-sm text-ink-600 transition hover:text-ink-900">
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <Link href="/call" className={`btn-primary hidden sm:inline-flex ${pathname === "/call" ? "pointer-events-none opacity-60" : ""}`}>
            <PhoneIcon /> Start a call
          </Link>
          <button
            type="button"
            className="rounded-lg p-2 text-ink-700 hover:bg-ink-100 md:hidden"
            aria-label="Menu"
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              {open ? <path d="M6 6l12 12M18 6L6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}
            </svg>
          </button>
        </div>
      </div>

      {open && (
        <nav className="border-t border-ink-200 bg-white md:hidden" aria-label="Mobile">
          <div className="container-page flex flex-col py-3">
            {NAV.map((item) => (
              <Link key={item.href} href={item.href} className="py-2.5 text-ink-700" onClick={() => setOpen(false)}>
                {item.label}
              </Link>
            ))}
            <Link href="/call" className="btn-primary mt-2" onClick={() => setOpen(false)}>
              <PhoneIcon /> Start a call
            </Link>
          </div>
        </nav>
      )}
    </header>
  );
}

export function PhoneIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
      <path d="M5 4h3l2 5-2.5 1.5a11 11 0 005 5L14 13l5 2v3a2 2 0 01-2 2A15 15 0 013 6a2 2 0 012-2z" strokeLinejoin="round" />
    </svg>
  );
}
