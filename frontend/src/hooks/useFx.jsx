import { useEffect } from 'react'

const CARDS = '.metric-panel, .surface-panel, .availability-note, .inline-trace, .call-trace, .hero-stats li, .bento-card, .quote-card'
const STAGES = '.hero-stage, .call-page-visual'
const FLAT = '.surface-panel, .availability-note, .inline-trace, .call-trace'

export default function useFx() {
  useEffect(() => {
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches
    const fine = matchMedia('(hover: hover) and (pointer: fine)').matches
    let frame = 0

    const tag = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        document.querySelectorAll(CARDS).forEach((el) => { el.dataset.fx = '' })
        document.querySelectorAll(STAGES).forEach((el) => { el.dataset.stage = '' })
      })
    }
    tag()
    const observer = new MutationObserver(tag)
    observer.observe(document.getElementById('root'), { childList: true, subtree: true })

    const find = (target) => target.closest?.('[data-fx], [data-stage]')
    const move = (event) => {
      const el = find(event.target)
      if (!el) return
      const rect = el.getBoundingClientRect()
      const x = (event.clientX - rect.left) / rect.width
      const y = (event.clientY - rect.top) / rect.height
      const max = 'stage' in el.dataset ? 10 : el.matches(FLAT) ? 0 : 3
      el.style.setProperty('--mx', `${x * 100}%`)
      el.style.setProperty('--my', `${y * 100}%`)
      el.style.setProperty('--ry', `${(x - 0.5) * max}deg`)
      el.style.setProperty('--rx', `${(0.5 - y) * max}deg`)
    }
    const leave = (event) => {
      const el = find(event.target)
      if (!el || el.contains(event.relatedTarget)) return
      el.style.setProperty('--rx', '0deg')
      el.style.setProperty('--ry', '0deg')
    }

    if (!reduce && fine) {
      document.addEventListener('pointermove', move, { passive: true })
      document.addEventListener('pointerout', leave, { passive: true })
    }
    return () => {
      observer.disconnect()
      cancelAnimationFrame(frame)
      document.removeEventListener('pointermove', move)
      document.removeEventListener('pointerout', leave)
    }
  }, [])
}