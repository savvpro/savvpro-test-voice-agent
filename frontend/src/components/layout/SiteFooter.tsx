import Link from "next/link";
import { Logo } from "./Logo";
import { PhoneIcon } from "./SiteHeader";

const highlights = [
  { label: "Speech", value: "In the browser, no keys", icon: "M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3zM5 11a7 7 0 0 0 14 0M12 18v3" },
  { label: "Decisions", value: "Rule-based, no AI model", icon: "M9 12l2 2 4-4M12 21a9 9 0 1 1 0-18 9 9 0 0 1 0 18z" },
  { label: "Data", value: "Fake clinic, nothing shared", icon: "M12 3 5 6v6c0 4.5 3 7.5 7 9 4-1.5 7-4.5 7-9V6z" },
];

const columns = [
  {
    title: "Product",
    links: [
      { href: "/call", label: "Start a call" },
      { href: "/#how", label: "How it works" },
      { href: "/#handles", label: "What it handles" },
      { href: "/#brain", label: "The brain" },
    ],
  },
  {
    title: "Demo clinic",
    links: [
      { href: "/call", label: "Brightside Dental (fictional)" },
      { href: "/call", label: "Mon to Fri, 9 AM to 5 PM" },
      { href: "/call", label: "Sat, 9 AM to 1 PM" },
      { href: "/call", label: "Demo booking: Jordan Lee" },
    ],
  },
];

export function SiteFooter() {
  return (
    <footer className="relative overflow-hidden bg-ink-950 text-white">
      <div className="bg-grid pointer-events-none absolute inset-0 opacity-40 [mask-image:linear-gradient(to_bottom,black,transparent)]" />
      <div className="pointer-events-none absolute -right-32 -top-32 h-96 w-96 rounded-full bg-ink-500/25 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-40 -left-24 h-80 w-80 rounded-full bg-ink-600/20 blur-3xl" />

      <div className="container-page relative">
        {/* call to action */}
        <div className="flex flex-col gap-8 border-b border-white/10 py-14 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-ink-400">Phones, answered</p>
            <h2 className="mt-3 text-4xl font-light leading-tight tracking-tight sm:text-5xl">
              Give the clinic <span className="text-silver font-semibold">a call.</span>
            </h2>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link
              href="/call"
              className="group inline-flex items-center gap-2 rounded-lg bg-white px-5 py-3 text-sm font-semibold text-ink-900 transition hover:bg-ink-100"
            >
              <PhoneIcon /> Start a call <span className="transition-transform duration-300 group-hover:translate-x-1">→</span>
            </Link>
            <Link
              href="/#how"
              className="inline-flex items-center rounded-lg px-5 py-3 text-sm font-semibold text-white ring-1 ring-white/30 transition hover:bg-white/10 hover:ring-white/60"
            >
              See how it works
            </Link>
          </div>
        </div>

        {/* highlight cards */}
        <div className="grid gap-4 py-10 sm:grid-cols-3">
          {highlights.map((h) => (
            <div
              key={h.label}
              className="group flex items-center gap-4 rounded-xl bg-white/[0.04] p-5 ring-1 ring-white/10 transition duration-300 hover:-translate-y-1 hover:bg-white/[0.08] hover:ring-white/25"
            >
              <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-ink-500 to-ink-700 shadow-[0_10px_30px_-10px_rgba(0,0,0,0.8)] ring-1 ring-white/10 transition-transform duration-300 group-hover:scale-110">
                <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
                  <path d={h.icon} />
                </svg>
              </span>
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-ink-400">{h.label}</p>
                <p className="mt-0.5 font-semibold">{h.value}</p>
              </div>
            </div>
          ))}
        </div>

        {/* brand + links */}
        <div className="grid gap-10 py-8 md:grid-cols-[1.4fr_1fr_1fr]">
          <div>
            <div className="flex items-center gap-2.5">
              <Logo light />
              <span className="text-[15px] font-semibold tracking-tight">
                Brightside <span className="font-normal text-ink-400">Voice</span>
              </span>
            </div>
            <p className="mt-4 max-w-sm text-sm leading-relaxed text-ink-400">
              A phone receptionist for a dental clinic. It books, moves and cancels appointments, and every decision is
              made by plain rules you can read and test.
            </p>
          </div>
          {columns.map((col) => (
            <div key={col.title}>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-ink-500">{col.title}</p>
              <ul className="mt-4 space-y-2.5">
                {col.links.map((l) => (
                  <li key={l.label}>
                    <Link href={l.href} className="group inline-flex items-center gap-1.5 text-sm text-ink-300 transition-colors hover:text-white">
                      <span className="h-px w-0 bg-ink-300 transition-all duration-300 group-hover:w-3" />
                      {l.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* oversized outline wordmark */}
        <p
          aria-hidden
          className="pointer-events-none select-none text-center text-[17vw] font-bold leading-[0.8] tracking-tighter text-transparent [-webkit-text-stroke:1px_rgba(201,201,207,0.18)] lg:text-[180px]"
        >
          Brightside
        </p>
      </div>

      <div className="relative border-t border-white/10 bg-black/30">
        <div className="container-page flex flex-col gap-3 py-5 text-xs text-ink-400 sm:flex-row sm:items-center sm:justify-between">
          <p>© {new Date().getFullYear()} Brightside Voice · Voice Agent assessment by Hammad Shabbir · Demo data only</p>
          <a
            href="#"
            aria-label="Back to top"
            className="grid h-9 w-9 place-items-center self-start rounded-full ring-1 ring-white/25 transition hover:-translate-y-0.5 hover:bg-white hover:text-ink-900 sm:self-auto"
          >
            ↑
          </a>
        </div>
      </div>
    </footer>
  );
}
