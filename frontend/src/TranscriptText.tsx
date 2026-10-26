import type { CSSProperties } from 'react'

// A bounded visual reveal of actual text, independent of speech and API completion.
export function TranscriptText({
  text,
  animate = false,
  live = false,
}: {
  text: string
  animate?: boolean
  live?: boolean
}) {
  if (!animate) return <>{text}</>
  return (
    <>
      <span className="sr-only">{text}</span>
      <span
        className={live ? 'transcript-reveal live-reveal' : 'transcript-reveal'}
        aria-hidden="true"
      >
        {text.split(/(\s+)/).map((word, index) =>
          /^\s+$/.test(word) ? (
            word
          ) : (
            <span
              key={`${index}-${word}`}
              className="revealed-word"
              style={
                { '--word-delay': `${live ? 0 : Math.min(index * 12, 600)}ms` } as CSSProperties
              }
            >
              {word}
            </span>
          ),
        )}
      </span>
    </>
  )
}
