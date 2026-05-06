import { dismissOverdue } from '../../api/calendar'
import './OverdueBanner.css'

export default function OverdueBanner({ items, onDismiss }) {
  const visible = items?.filter(i => !i.dismissed)
  if (!visible?.length) return null

  async function handleDismiss(reservationId) {
    try {
      await dismissOverdue(reservationId)
      onDismiss?.(reservationId)
    } catch {}
  }

  return (
    <div className="overdue-banner">
      {visible.map(item => (
        <div key={item.reservation_id} className="overdue-item">
          <span className="overdue-icon">🚨</span>
          <span className="overdue-text">
            <strong>{item.dog_name}</strong> ({item.owner_last_name}) —{' '}
            Kennel {item.kennel_number} — Pickup overdue{' '}
            <span className="overdue-hours">{item.hours_overdue.toFixed(1)} hrs</span>
          </span>
          <button className="overdue-dismiss" onClick={() => handleDismiss(item.reservation_id)}>
            Dismiss
          </button>
        </div>
      ))}
    </div>
  )
}
