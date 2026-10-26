import Link from "next/link";
import { PhoneIcon } from "@/components/layout/SiteHeader";

const PIPELINE = [
  { step: "01", title: "Caller speaks", body: "The browser's microphone picks up the caller. You can also type." },
  { step: "02", title: "Speech to text", body: "The browser's built-in speech recognition turns it into words. No keys, no cloud bill." },
  { step: "03", title: "The brain", body: "Python rules clean the text, find the intent and details, and pick one next step." },
  { step: "04", title: "Text to speech", body: "The reply is read aloud by the browser's voice, then the mic opens again." },
];

const HANDLES = [
  { title: "Changing their mind", body: "“Actually, make it 2 PM.” The new time replaces the old one and the reason is logged.", icon: "M4 12a8 8 0 0 1 14-5.3M20 4v4h-4M20 12a8 8 0 0 1-14 5.3M4 20v-4h4" },
  { title: "Taken or closed slots", body: "Sundays, lunch hour and booked slots get the two nearest free times instead.", icon: "M4 6h16v14H4zM4 10h16M9 3v4M15 3v4M10 15l4 0" },
  { title: "Vague times", body: "“At 3” means 3 PM at a clinic. “Tomorrow afternoon” offers the free afternoon slots.", icon: "M12 21a9 9 0 1 1 0-18 9 9 0 0 1 0 18zM12 7v5l3 2" },
  { title: "Questions mid-booking", body: "Hours, address or insurance get answered, then the call goes back to the open question.", icon: "M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.7M12 17h.01M12 21a9 9 0 1 1 0-18 9 9 0 0 1 0 18z" },
  { title: "Emergencies", body: "Pain or swelling jumps to the earliest visit, with a 911 note for severe cases.", icon: "M12 3 2 20h20L12 3zM12 10v4M12 17h.01" },
  { title: "Getting lost", body: "Three turns it can't use, or a request for a person, hands the call to the front desk.", icon: "M16 11a4 4 0 1 0-8 0M4 20a8 8 0 0 1 16 0M18 8l2-2M20 10h2" },
  { title: "Move or cancel", body: "Finds the booking by name or phone number, reads it back, and confirms before changing it.", icon: "M5 12h14M13 6l6 6-6 6" },
  { title: "Saying too much at once", body: "“A checkup tomorrow at 10, I'm Sam, 555 222 3333” fills every detail in one turn.", icon: "M4 6h16M4 12h16M4 18h10" },
];

const STRIP = ["Book, move and cancel", "No AI model deciding", "Speech in the browser", "110+ automated tests", "Fake data only"];

const SAMPLE = [
  { who: "agent", text: "Thanks for calling Brightside Dental. How can I help you today?" },
  { who: "caller", text: "Hi, I'd like a cleaning next Tuesday at 3." },
  { who: "agent", text: "Great, that time is free. What's your full name?" },
  { who: "caller", text: "Jane Doe. Actually, can we make it 4?" },
];

export default function Home() {
  return (
    <>
      {/* Hero */}
      <section className="relative overflow-hidden bg-gradient-to-b from-ink-100 via-ink-50 to-white">
        <div className="bg-dots pointer-events-none absolute inset-0 [mask-image:radial-gradient(ellipse_at_top,black_30%,transparent_75%)]" />
        <div className="pointer-events-none absolute -left-40 top-10 h-96 w-96 rounded-full bg-ink-300/40 blur-3xl" />
        <div className="pointer-events-none absolute -right-24 bottom-0 h-80 w-80 rounded-full bg-ink-400/25 blur-3xl" />
        <div className="container-page relative grid items-center gap-14 py-20 lg:grid-cols-[1.1fr_1fr] lg:py-28">
          <div className="animate-fade-up">
            <span className="chip border-ink-300 bg-white/80 backdrop-blur">
              <span className="h-1.5 w-1.5 rounded-full bg-ink-900" /> Voice assistant · dental clinic
            </span>
            <h1 className="mt-6 text-4xl font-semibold leading-[1.08] tracking-tight text-ink-950 sm:text-5xl lg:text-6xl">
              The clinic phone,
              <br />
              <span className="text-graphite">answered by rules you can read.</span>
            </h1>
            <p className="mt-6 max-w-xl text-lg leading-relaxed text-ink-600">
              Brightside Voice picks up, books, moves and cancels appointments, and handles the messy parts of real
              calls. Every turn shows what it heard, what it understood and why it chose its reply.
            </p>
            <div className="mt-9 flex flex-wrap gap-3">
              <Link href="/call" className="btn-primary px-6 py-3 text-[15px] shadow-[0_12px_30px_-12px_rgba(24,24,27,0.6)]">
                <PhoneIcon /> Start a call
              </Link>
              <a href="#how" className="btn-ghost px-6 py-3 text-[15px]">
                How it works
              </a>
            </div>
            <dl className="mt-12 grid max-w-md grid-cols-3 gap-3">
              {[
                ["0", "AI models deciding"],
                ["110+", "automated tests"],
                ["3", "jobs, start to end"],
              ].map(([n, label]) => (
                <div key={label} className="rounded-xl border border-ink-200 bg-white/70 px-4 py-3 backdrop-blur">
                  <dt className="text-2xl font-semibold text-ink-900">{n}</dt>
                  <dd className="mt-0.5 text-xs text-ink-500">{label}</dd>
                </div>
              ))}
            </dl>
          </div>

          {/* Phone-style preview of a call */}
          <div className="animate-fade-up [animation-delay:120ms]">
            <div className="mx-auto max-w-md animate-float rounded-[2rem] bg-gradient-to-b from-ink-700 to-ink-900 p-3 shadow-lift">
              <div className="rounded-[1.6rem] bg-white p-5">
                <div className="flex items-center justify-between border-b border-ink-100 pb-4">
                  <div className="flex items-center gap-3">
                    <span className="relative flex h-9 w-9 items-center justify-center rounded-full bg-ink-900 text-white">
                      <span className="absolute inset-0 animate-ring rounded-full bg-ink-900" />
                      <PhoneIcon />
                    </span>
                    <div>
                      <p className="text-sm font-semibold text-ink-900">Brightside Dental</p>
                      <p className="text-xs text-ink-500">On a call · 00:42</p>
                    </div>
                  </div>
                  <Bars />
                </div>
                <ul className="mt-4 space-y-3">
                  {SAMPLE.map((m, i) => (
                    <li key={i} className={`flex ${m.who === "caller" ? "justify-end" : ""}`}>
                      <p
                        className={`max-w-[80%] rounded-2xl px-3.5 py-2 text-sm leading-snug ${
                          m.who === "caller" ? "rounded-br-md bg-ink-900 text-white" : "rounded-bl-md bg-ink-100 text-ink-800"
                        }`}
                      >
                        {m.text}
                      </p>
                    </li>
                  ))}
                </ul>
                <div className="mt-4 rounded-xl bg-ink-900 p-3 font-mono text-[11px] leading-relaxed text-ink-300">
                  <p><span className="text-ink-500">intent</span> book · <span className="text-ink-500">conf</span> 0.90</p>
                  <p><span className="text-ink-500">changed</span> time 3 PM → 4 PM</p>
                  <p><span className="text-ink-500">next</span> <span className="text-white">ask_phone</span></p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Dark strip */}
      <section className="border-y border-ink-800 bg-ink-900 text-ink-300">
        <ul className="container-page flex flex-wrap items-center justify-center gap-x-8 gap-y-3 py-5 text-sm">
          {STRIP.map((s) => (
            <li key={s} className="flex items-center gap-2.5">
              <span className="h-1.5 w-1.5 rounded-full bg-ink-500" />
              {s}
            </li>
          ))}
        </ul>
      </section>

      {/* Pipeline */}
      <section id="how" className="scroll-mt-20 py-20 lg:py-24">
        <div className="container-page">
          <p className="eyebrow">How it works</p>
          <h2 className="mt-3 max-w-2xl text-3xl font-semibold tracking-tight text-ink-950 sm:text-4xl">
            One loop, every turn, <span className="text-graphite">until the call ends.</span>
          </h2>
          <ol className="mt-12 grid gap-4 md:grid-cols-4">
            {PIPELINE.map((p, i) => (
              <li
                key={p.step}
                className="group relative rounded-2xl border border-ink-200 bg-gradient-to-b from-white to-ink-50 p-6 transition duration-300 hover:-translate-y-1 hover:border-ink-900 hover:from-ink-800 hover:to-ink-950"
              >
                <span className="grid h-10 w-10 place-items-center rounded-full bg-ink-200 font-mono text-xs font-semibold text-ink-700 transition group-hover:bg-white/10 group-hover:text-white">
                  {p.step}
                </span>
                <h3 className="mt-4 font-semibold text-ink-900 transition group-hover:text-white">{p.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-ink-600 transition group-hover:text-ink-300">{p.body}</p>
                {i < PIPELINE.length - 1 && <span className="absolute -right-3 top-11 hidden h-px w-6 bg-ink-300 md:block" aria-hidden />}
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* Messy calls */}
      <section id="handles" className="relative scroll-mt-20 overflow-hidden bg-ink-100 py-20 lg:py-24">
        <div className="bg-dots pointer-events-none absolute inset-0 opacity-60" />
        <div className="container-page relative">
          <p className="eyebrow">What it handles</p>
          <h2 className="mt-3 max-w-2xl text-3xl font-semibold tracking-tight text-ink-950 sm:text-4xl">
            Real callers are messy. <span className="text-graphite">Each of these has a test.</span>
          </h2>
          <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {HANDLES.map((h) => (
              <div key={h.title} className="group rounded-2xl border border-ink-200 bg-white p-6 transition duration-300 hover:-translate-y-1 hover:shadow-lift">
                <span className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-ink-600 to-ink-900 text-white shadow-[0_8px_20px_-8px_rgba(24,24,27,0.7)] transition-transform duration-300 group-hover:scale-110">
                  <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                    <path d={h.icon} />
                  </svg>
                </span>
                <h3 className="mt-4 font-semibold text-ink-900">{h.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-ink-600">{h.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* The brain */}
      <section id="brain" className="scroll-mt-20 bg-gradient-to-b from-white to-ink-50 py-20 lg:py-24">
        <div className="container-page grid gap-12 lg:grid-cols-2 lg:items-center">
          <div>
            <p className="eyebrow">The brain</p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight text-ink-950 sm:text-4xl">
              No model guesses <span className="text-graphite">what happens next.</span>
            </h2>
            <p className="mt-5 leading-relaxed text-ink-600">
              The brain is a small Python state machine. Weighted patterns find the intent, parsers pull out the day,
              time, name and phone, and a fixed order of checks picks one action. Same words in, same reply out, so it
              can be tested like any other code.
            </p>
            <ol className="mt-6 space-y-3 text-sm text-ink-700">
              {[
                "Requests that apply anywhere first: repeat, start over, a person, goodbye.",
                "Then the job: book, move or cancel, and what the caller just said.",
                "Then the first missing or invalid detail, checked against the real calendar.",
                "Nothing is booked until the caller hears it read back and says yes.",
              ].map((t, i) => (
                <li key={t} className="flex items-start gap-3 rounded-xl border border-ink-200 bg-white px-4 py-3">
                  <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-ink-900 font-mono text-[11px] text-white">{i + 1}</span>
                  <span className="pt-0.5">{t}</span>
                </li>
              ))}
            </ol>
          </div>
          <div className="rounded-3xl bg-gradient-to-br from-ink-300 via-ink-200 to-ink-400 p-2 shadow-lift">
            <div className="overflow-hidden rounded-[1.25rem] bg-ink-950">
              <div className="flex items-center gap-1.5 border-b border-white/10 px-4 py-3">
                {[0, 1, 2].map((d) => (
                  <span key={d} className="h-2.5 w-2.5 rounded-full bg-ink-600" />
                ))}
                <span className="ml-3 font-mono text-[11px] text-ink-500">turn 6 · decision</span>
              </div>
              <pre className="overflow-x-auto p-6 font-mono text-[12.5px] leading-relaxed text-ink-200">
{`caller  "no wait, make it friday"

normalized  no wait make it friday
intent      deny        conf 0.90
correction  yes
extracted   date = Fri, Oct 30

reasons
  · Caller changed day: Thu → Fri
action      confirm
reply       "To confirm: a whitening for
             Pat Lee on Friday, October 30
             at 9 AM ... Shall I book it?"`}
              </pre>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}

function Bars() {
  return (
    <span className="flex h-5 items-center gap-[3px]" aria-hidden>
      {[0, 1, 2, 3, 4].map((i) => (
        <span key={i} className="h-full w-[3px] origin-center animate-wave rounded-full bg-ink-800" style={{ animationDelay: `${i * 0.12}s` }} />
      ))}
    </span>
  );
}
