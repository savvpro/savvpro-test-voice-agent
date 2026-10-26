export function Logo({ className = "h-8 w-8", light = false }: { className?: string; light?: boolean }) {
  return (
    <span className={`relative inline-flex items-center justify-center rounded-xl ${light ? "bg-white" : "bg-ink-900"} ${className}`} aria-hidden>
      <span className="flex h-3.5 items-center gap-[3px]">
        {[0.5, 1, 0.7, 0.9, 0.45].map((h, i) => (
          <span key={i} className={`w-[2.5px] rounded-full ${light ? "bg-ink-900" : "bg-white"}`} style={{ height: `${h * 100}%` }} />
        ))}
      </span>
    </span>
  );
}
