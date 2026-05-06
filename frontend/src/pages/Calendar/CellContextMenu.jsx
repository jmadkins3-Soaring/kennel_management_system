import { useEffect, useRef } from 'react'
import './CellContextMenu.css'

export default function CellContextMenu({ x, y, cell, onAction, onClose }) {
  const menuRef = useRef(null)

  // Adjust position to stay within viewport
  const style = { left: x, top: y }
  if (x + 220 > window.innerWidth) style.left = x - 220
  if (y + 240 > window.innerHeight) style.top = y - 240

  useEffect(() => {
    const handler = e => {
      if (menuRef.current && !menuRef.current.contains(e.target)) onClose()
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [onClose])

  const isAssigned = cell.status === 'Assigned'
  const isUsed = cell.status === 'Used'
  const hasFuture = new Date(cell.date) > new Date() || cell.status === 'Free'

  return (
    <div className="ctx-overlay" onClick={onClose}>
      <div className="ctx-menu" style={style} ref={menuRef} onClick={e => e.stopPropagation()}>
        <div className="ctx-header">
          {cell.kennelNumber} · {cell.date} · {cell.phase}
        </div>

        {cell.reservationId && (
          <button className="ctx-item" onClick={() => onAction('view-reservation', cell)}>
            View Reservation Details
          </button>
        )}

        <button
          className="ctx-item"
          disabled={!isAssigned}
          onClick={() => isAssigned && onAction('checkin', cell)}
        >
          Check In
        </button>

        <button
          className="ctx-item"
          disabled={!isUsed}
          onClick={() => isUsed && onAction('checkout', cell)}
        >
          Check Out
        </button>

        {cell.reservationId && (
          <>
            <button className="ctx-item" onClick={() => onAction('view-dog', cell)}>
              View Dog Profile
            </button>
            <button className="ctx-item" onClick={() => onAction('view-owner', cell)}>
              View Owner Profile
            </button>
            <button className="ctx-item" onClick={() => onAction('add-incident', cell)}>
              Add Incident Report
            </button>
          </>
        )}

        {(cell.status === 'Free' || !cell.status) && (
          <button className="ctx-item" onClick={() => onAction('new-reservation', cell)}>
            New Reservation Here
          </button>
        )}
      </div>
    </div>
  )
}
