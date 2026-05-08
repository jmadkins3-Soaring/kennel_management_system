import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import Layout from '../../components/Layout'
import ReservationDetailModal from '../Calendar/ReservationDetailModal'
import { listReservations } from '../../api/reservations'
import { format, parseISO } from 'date-fns'

function fmt(dt) {
  try { return format(parseISO(dt), 'MMM d h:mm a') } catch { return dt || '—' }
}

export default function ReservationsPage() {
  const [params] = useSearchParams()
  const highlight = params.get('highlight')

  const [reservations, setReservations] = useState([])
  const [loading, setLoading] = useState(true)
  const [q, setQ] = useState('')
  const [selected, setSelected] = useState(highlight || null)

  async function load() {
    setLoading(true)
    try {
      const data = await listReservations(q ? { q } : {})
      setReservations(data)
    } catch {}
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [q])

  function statusBadge(r) {
    if (r.cancelled) return <span className="badge" style={{ background: '#ffebee', color: '#c62828', border: 'none' }}>Cancelled</span>
    if (r.checkout_datetime) return <span className="badge badge-free">Checked Out</span>
    if (r.checkin_datetime) return <span className="badge badge-used">Checked In</span>
    return <span className="badge badge-assigned">Scheduled</span>
  }

  return (
    <Layout>
      <div className="page-content">
        <div className="page-header">
          <h1>Reservations</h1>
          <div style={{ display: 'flex', gap: 10 }}>
            <input
              placeholder="Search…"
              value={q}
              onChange={e => setQ(e.target.value)}
              style={{ padding: '6px 10px', border: '1px solid var(--border)', borderRadius: 4, fontSize: 13, width: 200 }}
            />
          </div>
        </div>

        <div className="card">
          {loading ? <div className="spinner" /> : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Dog</th>
                  <th>Owner</th>
                  <th>Kennel</th>
                  <th>Drop-off</th>
                  <th>Pick-up</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {reservations.length === 0 ? (
                  <tr><td colSpan={6} className="empty-state">No reservations found</td></tr>
                ) : reservations.map(r => (
                  <tr
                    key={r.reservation_id}
                    onClick={() => setSelected(r.reservation_id)}
                    style={r.reservation_id === highlight ? { background: '#e3f2fd' } : {}}
                  >
                    <td>{r.dog_name || r.dog_id}</td>
                    <td>—</td>
                    <td>{r.kennel_id}</td>
                    <td>{fmt(r.dropoff_datetime)}</td>
                    <td>{r.pickup_open_ended ? 'Open-ended' : fmt(r.pickup_datetime)}</td>
                    <td>{statusBadge(r)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {selected && (
          <ReservationDetailModal
            reservationId={selected}
            onClose={() => setSelected(null)}
            onRefresh={load}
          />
        )}
      </div>
    </Layout>
  )
}
