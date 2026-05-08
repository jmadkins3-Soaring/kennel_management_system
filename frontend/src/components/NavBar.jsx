import { useState, useRef, useEffect, useCallback } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { globalSearch } from '../api/search'
import './NavBar.css'

export default function NavBar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState(null)
  const [searching, setSearching] = useState(false)
  const timerRef = useRef(null)
  const wrapRef = useRef(null)

  const doSearch = useCallback(async q => {
    if (!q.trim()) { setResults(null); return }
    setSearching(true)
    try {
      const data = await globalSearch(q)
      setResults(data)
    } catch { setResults(null) }
    finally { setSearching(false) }
  }, [])

  useEffect(() => {
    clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => doSearch(query), 300)
    return () => clearTimeout(timerRef.current)
  }, [query, doSearch])

  useEffect(() => {
    const handler = e => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setResults(null)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  function navigateTo(item) {
    setResults(null)
    setQuery('')
    if (item.type === 'reservation') navigate(`/reservations?highlight=${item.id}`)
    else if (item.type === 'dog') navigate(`/dogs?highlight=${item.id}`)
    else if (item.type === 'owner') navigate(`/owners?highlight=${item.id}`)
    else if (item.type === 'bill') navigate(`/reservations?highlight=${item.reservation_id}`)
  }

  return (
    <nav className="navbar">
      <div className="navbar-brand">
        <img src="/logo.png" alt="Soaring Heights" className="navbar-logo" />
        <span>Soaring Heights</span>
      </div>
      <div className="navbar-links">
        <NavLink to="/calendar"     className={({ isActive }) => isActive ? 'active' : ''}>Calendar</NavLink>
        <NavLink to="/reservations" className={({ isActive }) => isActive ? 'active' : ''}>Reservations</NavLink>
        <NavLink to="/dogs"         className={({ isActive }) => isActive ? 'active' : ''}>Dogs</NavLink>
        <NavLink to="/owners"       className={({ isActive }) => isActive ? 'active' : ''}>Owners</NavLink>
        <NavLink to="/kennels"      className={({ isActive }) => isActive ? 'active' : ''}>Kennels</NavLink>
        <NavLink to="/reports"      className={({ isActive }) => isActive ? 'active' : ''}>Reports</NavLink>
        <NavLink to="/activities"   className={({ isActive }) => isActive ? 'active' : ''}>Activities</NavLink>
      </div>

      <div className="navbar-search" ref={wrapRef}>
        <span className="search-icon">🔍</span>
        <input
          placeholder="Search owners, dogs, reservations…"
          value={query}
          onChange={e => setQuery(e.target.value)}
          onFocus={() => query && doSearch(query)}
        />
        {results && (
          <div className="search-results">
            {results.active?.length > 0 && <>
              <div className="search-section-title">Active &amp; Upcoming</div>
              {results.active.map(item => (
                <div key={item.id} className="search-result-item" onClick={() => navigateTo(item)}>
                  <span className="search-result-main">{item.label}</span>
                  <span className="search-result-sub">{item.sublabel}</span>
                </div>
              ))}
            </>}
            {results.historical?.length > 0 && <>
              <div className="search-section-title">Historical</div>
              {results.historical.map(item => (
                <div key={item.id} className="search-result-item" onClick={() => navigateTo(item)}>
                  <span className="search-result-main">{item.label}</span>
                  <span className="search-result-sub">{item.sublabel}</span>
                </div>
              ))}
            </>}
            {!results.active?.length && !results.historical?.length && (
              <div className="empty-state" style={{ padding: '16px' }}>No results</div>
            )}
          </div>
        )}
      </div>

      <div className="navbar-user">
        {user?.username}
        <button onClick={logout}>Logout</button>
      </div>
    </nav>
  )
}
