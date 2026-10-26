import { useEffect, useState } from 'react'
import App from './App.jsx'
import Admin from './Admin.jsx'

function routeFromHash() {
  const h = (window.location.hash || '#/').replace(/^#/, '') || '/'
  if (h.startsWith('/admin')) return 'admin'
  return 'talk'
}

export default function Shell() {
  const [route, setRoute] = useState(routeFromHash)

  useEffect(() => {
    const onHash = () => setRoute(routeFromHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  return route === 'admin' ? <Admin /> : <App />
}
