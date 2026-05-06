import { useState, useEffect } from 'react'
import Modal from '../../components/Modal'
import { getReservation, cancelReservation } from '../../api/reservations'
import { getDog } from '../../api/dogs'
import { getOwner } from '../../api/owners'
import { format, parseISO } from 'date-fns'

function fmt(dt) {
  try { return format(parseISO(dt), 'MMM d, yyyy h:mm a') } catch { return dt || '—' }
}

export default function ReservationDetailModal({ reservationId, onClose, onRefresh }) {
  const [res, setRes]     = useState(null)
  const [dog, setDog]     = useState(null)
  const [owner, setOwner] = useState(null)
  const [loading, setLoading]   = useState(true)
  const [cancelling, setCancelling] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    async function load() {
      try {
        const r = await getReservation(reservationId)
        setRes(r)
        const d = await getDog(r.dog_id)
        setDog(d)
        const o = await getOwner(d.owner_id)
        setOwner(o)
      } catch { setError('Failed to load') }
      finally { setLoading(false) }
    }
    load()
  }, [reservationId])

  async function handleCancel() {
    if (!confirm('Cancel this reservation?')) return
    setCancelling(true)
    try {
      await cancelReservation(reservationId, { cancel_requested_by: 'Staff' })
      onRefresh?.()
      onClose()
    } catch (e) {
      setError(e.response?.data?.detail || 'Cancel failed')
      setCancelling(false)
    }
  }

  if (loading) return <Modal title="Reservation" size="md" onClose={onClose}><div className="spinner" /></Modal>

  return (
    <Modal
      title={`Reservation — ${dog?.name || ''}`}
      size="md"
      onClose={onClose}
      footer={<>
        {res && !res.cancelled && !res.checkin_datetime && (
          <button className="btn btn-danger btn-sm" onClick={handleCancel} disabled={cancelling}>
            Cancel Reservation
          </button>
        )}
        <button className="btn btn-secondary" onClick={onClose}>Close</button>
      </>}
    >
      {res && <>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px 24px', fontSize: 13, marginBottom: 16 }}>
          <div><strong>Dog</strong><br />{dog?.name} ({dog?.size_class})</div>
          <div><strong>Owner</strong><br />{owner?.first_name} {owner?.last_name}</div>
          <div><strong>Kennel</strong><br />{res.kennel_id}</div>
          <div><strong>Status</strong><br />
            {res.cancelled ? <span className="badge" style={{background:'#ffebee',color:'#c62828'}}>Cancelled</span>
             : res.checkout_datetime ? <span className="badge badge-free">Checked Out</span>
             : res.checkin_datetime ? <span className="badge badge-used">Checked In</span>
             : <span className="badge badge-assigned">Scheduled</span>}
          </div>
          <div><strong>Drop-off</strong><br />{fmt(res.dropoff_datetime)} ({res.dropoff_phase})</div>
          <div><strong>Pick-up</strong><br />{res.pickup_open_ended ? 'Open-ended' : fmt(res.pickup_datetime)} {res.pickup_phase ? `(${res.pickup_phase})` : ''}</div>
          {res.checkin_datetime && <div><strong>Checked In</strong><br />{fmt(res.checkin_datetime)} by {res.checkin_staff}</div>}
          {res.checkout_datetime && <div><strong>Checked Out</strong><br />{fmt(res.checkout_datetime)} by {res.checkout_staff}</div>}
        </div>
        {res.notes && <div style={{ fontSize: 13, marginBottom: 12 }}><strong>Notes:</strong> {res.notes}</div>}
        {error && <p className="error-text">{error}</p>}
      </>}
    </Modal>
  )
}
