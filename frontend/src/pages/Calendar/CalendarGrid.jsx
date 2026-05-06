import { useState, useEffect, useCallback, useRef } from 'react'
import { format, addDays, startOfWeek, isToday, parseISO } from 'date-fns'
import { getCalendar } from '../../api/calendar'
import CellContextMenu from './CellContextMenu'
import './CalendarGrid.css'

const PHASES = ['Morning', 'Afternoon', 'Evening', 'Night']
const PHASE_ABBR = { Morning: 'AM', Afternoon: 'Noon', Evening: 'Eve', Night: 'Ngt' }

function statusClass(status) {
  return (status || 'Free').toLowerCase()
}

function computeSpans(k) {
  const flat = []
  k.days.forEach(day => {
    PHASES.forEach((ph, pi) => {
      flat.push({ date: day.date, ph, pi, cell: day.phases[ph] || {}, isLastPhase: pi === 3 })
    })
  })
  const spans = []
  let i = 0
  while (i < flat.length) {
    const item = flat[i]
    const resId = item.cell.reservation_id
    if (resId) {
      let j = i + 1
      while (j < flat.length && flat[j].cell.reservation_id === resId) j++
      spans.push({ ...item, colSpan: j - i, phaseLastBorder: flat[j - 1].isLastPhase })
      i = j
    } else {
      spans.push({ ...item, colSpan: 1, phaseLastBorder: item.isLastPhase })
      i++
    }
  }
  return spans
}

export default function CalendarGrid({ onAction }) {
  const [startDate, setStartDate] = useState(() => startOfWeek(new Date(), { weekStartsOn: 0 }))
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [menu, setMenu] = useState(null)
  const refreshTimer = useRef(null)

  const load = useCallback(async (date) => {
    setLoading(true)
    setError(null)
    try {
      const d = await getCalendar(date, 10)
      setData(d)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load calendar')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load(startDate)
    clearInterval(refreshTimer.current)
    refreshTimer.current = setInterval(() => load(startDate), 60 * 60 * 1000)
    return () => clearInterval(refreshTimer.current)
  }, [startDate, load])

  function prev() { setStartDate(d => addDays(d, -10)) }
  function next() { setStartDate(d => addDays(d, 10)) }
  function jumpTo(e) {
    const val = e.target.value
    if (val) setStartDate(startOfWeek(parseISO(val), { weekStartsOn: 0 }))
  }

  function openMenu(e, cell) {
    e.preventDefault()
    setMenu({ x: e.clientX, y: e.clientY, cell })
  }

  function closeMenu() { setMenu(null) }

  function handleMenuAction(action, cell) {
    closeMenu()
    onAction?.(action, cell)
  }

  const dates = Array.from({ length: 10 }, (_, i) => addDays(startDate, i))
  const todayStr = format(new Date(), 'yyyy-MM-dd')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="cal-header-bar">
        <button className="cal-nav-btn" onClick={prev}>← Prev</button>
        <span className="cal-date-label">
          {format(startDate, 'MMM d')} – {format(addDays(startDate, 9), 'MMM d, yyyy')}
        </span>
        <button className="cal-nav-btn" onClick={next}>Next →</button>
        <input
          type="date"
          className="cal-date-picker"
          onChange={jumpTo}
          title="Jump to date"
        />
        <div className="cal-legend">
          <span><span className="legend-dot" style={{ background: 'var(--color-free-border)' }}/>Free</span>
          <span><span className="legend-dot" style={{ background: 'var(--color-hold-border)' }}/>Hold</span>
          <span><span className="legend-dot" style={{ background: 'var(--color-assigned-border)' }}/>Assigned</span>
          <span><span className="legend-dot" style={{ background: 'var(--color-used-border)' }}/>Used</span>
        </div>
        <button className="cal-refresh-btn" onClick={() => load(startDate)} title="Refresh">↻ Refresh</button>
      </div>

      {data?.alerts?.length > 0 && (
        <div className="pacfa-alert-bar">
          ⚠️ PACFA 181-day alert: {data.alerts.map(a => `${a.dog_name} (${a.duration_days} days)`).join(', ')} — qualifying activity not confirmed today
        </div>
      )}

      {loading && !data && <div className="cal-loading"><div className="spinner" /></div>}
      {error && <div className="cal-loading" style={{ color: '#c62828' }}>{error}</div>}

      {data && (
        <div className="cal-wrap">
          <table className="cal-table">
            <thead>
              <tr>
                <th className="kennel-th" rowSpan={2} style={{ padding: '8px 10px', textAlign: 'left', fontSize: 11 }}>
                  Kennel
                </th>
                {dates.map(d => (
                  <th
                    key={d.toISOString()}
                    colSpan={4}
                    className={`day-th${isToday(d) ? ' today' : ''}`}
                  >
                    {format(d, 'EEE M/d')}
                  </th>
                ))}
              </tr>
              <tr>
                {dates.map(d =>
                  PHASES.map((ph, pi) => (
                    <th
                      key={`${d.toISOString()}-${ph}`}
                      className={`phase-th${pi === 3 ? ' phase-last' : ''}`}
                    >
                      {PHASE_ABBR[ph]}
                    </th>
                  ))
                )}
              </tr>
            </thead>
            <tbody>
              {data.kennels.map(k => (
                <tr key={k.kennel_id}>
                  <td className="kennel-td">
                    <div className="kennel-num">{k.kennel_number}</div>
                  </td>
                  {computeSpans(k).map(span => {
                    const status = span.cell.status || 'Free'
                    const cls = statusClass(status)
                    const isToday = span.date === todayStr
                    const isPendingCI = status === 'Assigned' && isToday
                    const isPendingCO = status === 'Used' && isToday
                    const merged = span.colSpan > 1
                    return (
                      <td
                        key={`${span.date}-${span.ph}`}
                        colSpan={span.colSpan}
                        className={`cal-cell ${cls}${span.phaseLastBorder ? ' phase-last' : ''}${merged ? ' merged' : ''}`}
                        title={`${span.ph} · ${status}${span.cell.owner_last_name ? ` · ${span.cell.owner_last_name}` : ''}`}
                        onClick={e => openMenu(e, {
                          kennelId: k.kennel_id,
                          kennelNumber: k.kennel_number,
                          date: span.date,
                          phase: span.ph,
                          status,
                          reservationId: span.cell.reservation_id || null,
                          ownerLastName: span.cell.owner_last_name || null,
                        })}
                      >
                        {span.cell.owner_last_name && (
                          <span className="cell-label">{span.cell.owner_last_name}</span>
                        )}
                        {(isPendingCI || isPendingCO) && (
                          <span className="cell-pending">{isPendingCI ? '▼' : '▲'}</span>
                        )}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {menu && (
        <CellContextMenu
          x={menu.x}
          y={menu.y}
          cell={menu.cell}
          onAction={handleMenuAction}
          onClose={closeMenu}
        />
      )}
    </div>
  )
}
