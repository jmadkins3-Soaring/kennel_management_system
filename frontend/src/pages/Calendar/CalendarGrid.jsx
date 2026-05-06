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

function cellTip(phase, status, ownerLast, reservationId) {
  const lines = [`Phase: ${phase}`, `Status: ${status || 'Free'}`]
  if (ownerLast) lines.push(`Owner: ${ownerLast}`)
  return lines.join('\n')
}

export default function CalendarGrid({ onAction }) {
  const [startDate, setStartDate] = useState(() => startOfWeek(new Date(), { weekStartsOn: 0 }))
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [menu, setMenu] = useState(null) // { x, y, cell }
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

  // Build date range
  const dates = Array.from({ length: 10 }, (_, i) => addDays(startDate, i))

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
                    <div className="kennel-meta">
                      {k.days?.[0] && (() => {
                        // pull size/sqft from first cell's kennel data if available
                        return null
                      })()}
                    </div>
                  </td>
                  {k.days.map(day =>
                    PHASES.map((ph, pi) => {
                      const cell = day.phases[ph] || {}
                      const status = cell.status || 'Free'
                      const cls = statusClass(status)
                      const todayDate = format(parseISO(day.date), 'yyyy-MM-dd') === format(new Date(), 'yyyy-MM-dd')
                      const isPendingCI = status === 'Assigned' && todayDate
                      const isPendingCO = status === 'Used' && todayDate
                      return (
                        <td
                          key={`${day.date}-${ph}`}
                          className={`cal-cell ${cls}${pi === 3 ? ' phase-last' : ''}`}
                          data-tip={cellTip(ph, status, cell.owner_last_name, cell.reservation_id)}
                          onClick={e => {
                            const cellInfo = {
                              kennelId: k.kennel_id,
                              kennelNumber: k.kennel_number,
                              date: day.date,
                              phase: ph,
                              status,
                              reservationId: cell.reservation_id || null,
                              ownerLastName: cell.owner_last_name || null,
                            }
                            openMenu(e, cellInfo)
                          }}
                        >
                          {cell.owner_last_name && (
                            <span className="cell-label">{cell.owner_last_name}</span>
                          )}
                          {(isPendingCI || isPendingCO) && (
                            <span className="cell-pending">{isPendingCI ? '▼' : '▲'}</span>
                          )}
                        </td>
                      )
                    })
                  )}
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
