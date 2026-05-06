import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  verifyToken, getPortalDogs, getPortalReservations,
  createPortalReservation, updatePortalReservation,
  cancelPortalReservation, getPortalAvailability, requestLink,
} from '../../api/portal'
import { format, parseISO, addDays } from 'date-fns'
import Modal from '../../components/Modal'

function fmt(dt) {
  try { return format(parseISO(dt), 'MMM d, yyyy h:mm a') } catch { return dt || '—' }
}

// Token verification gate
export function PortalEntry() {
  const { token } = useParams()
  const [status, setStatus] = useState('verifying') // verifying | ok | error
  const [error, setError]   = useState('')

  useEffect(() => {
    if (!token) { setStatus('error'); setError('No token provided'); return }
    verifyToken(token)
      .then(data => {
        sessionStorage.setItem('portal_token', data.session_token)
        setStatus('ok')
      })
      .catch(e => {
        setStatus('error')
        setError(e.response?.data?.detail || 'Invalid or expired link')
      })
  }, [token])

  if (status === 'verifying') return <PortalShell><div className="spinner" /></PortalShell>
  if (status === 'error') return (
    <PortalShell>
      <div style={{ textAlign: 'center', padding: 40 }}>
        <p style={{ fontSize: 16, color: '#c62828', marginBottom: 20 }}>⚠️ {error}</p>
        <p style={{ fontSize: 13, color: 'var(--text-sub)' }}>
          This link may have expired. Enter your email below to receive a new link.
        </p>
        <RequestNewLink />
      </div>
    </PortalShell>
  )
  return <PortalHome />
}

function RequestNewLink() {
  const [email, setEmail] = useState('')
  const [sent, setSent]   = useState(false)
  const [err, setErr]     = useState('')

  async function submit(e) {
    e.preventDefault()
    try { await requestLink(email); setSent(true) }
    catch (e) { setErr(e.response?.data?.detail || 'Failed') }
  }

  if (sent) return <p style={{ color: '#2e7d32', marginTop: 16 }}>✓ Link sent — check your email.</p>

  return (
    <form onSubmit={submit} style={{ marginTop: 20, display: 'flex', gap: 10, justifyContent: 'center' }}>
      <input type="email" placeholder="Your email" value={email} onChange={e => setEmail(e.target.value)}
        style={{ padding: '7px 12px', border: '1px solid var(--border)', borderRadius: 4, fontSize: 13, width: 240 }} />
      <button type="submit" className="btn btn-primary btn-sm">Request Link</button>
      {err && <p className="error-text">{err}</p>}
    </form>
  )
}

function PortalShell({ children }) {
  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)' }}>
      <div style={{ background: 'var(--nav-bg)', color: '#fff', padding: '14px 24px', fontSize: 16, fontWeight: 700 }}>
        Soaring Heights — Owner Portal
      </div>
      <div style={{ maxWidth: 800, margin: '0 auto', padding: 24 }}>
        {children}
      </div>
    </div>
  )
}

function PortalHome() {
  const [tab, setTab] = useState('dogs') // dogs | reservations | availability
  const [dogs, setDogs]           = useState([])
  const [reservations, setReservations] = useState([])
  const [loading, setLoading]     = useState(false)
  const [editRes, setEditRes]     = useState(null)
  const [newRes, setNewRes]       = useState(false)
  const [error, setError]         = useState('')

  async function loadDogs() {
    setLoading(true)
    try { setDogs(await getPortalDogs()) } catch {}
    finally { setLoading(false) }
  }

  async function loadReservations() {
    setLoading(true)
    try { setReservations(await getPortalReservations()) } catch {}
    finally { setLoading(false) }
  }

  useEffect(() => {
    if (tab === 'dogs') loadDogs()
    else if (tab === 'reservations') loadReservations()
  }, [tab])

  function statusBadge(r) {
    if (r.cancelled) return <span style={{ color: '#c62828', fontWeight: 600 }}>Cancelled</span>
    if (r.checkout_datetime) return <span style={{ color: '#2e7d32' }}>Completed</span>
    if (r.checkin_datetime) return <span style={{ color: '#1565c0', fontWeight: 600 }}>Checked In</span>
    return <span style={{ color: '#0d47a1' }}>Scheduled</span>
  }

  async function handleCancel(resId) {
    if (!confirm('Request cancellation of this reservation?')) return
    try {
      await cancelPortalReservation(resId, {})
      loadReservations()
    } catch (e) { setError(e.response?.data?.detail || 'Failed') }
  }

  return (
    <PortalShell>
      <div style={{ display: 'flex', gap: 12, marginBottom: 20, borderBottom: '1px solid var(--border)', paddingBottom: 12 }}>
        {['dogs', 'reservations', 'availability'].map(t => (
          <button key={t} onClick={() => setTab(t)}
            style={{ background: tab === t ? '#1565c0' : '#fff', color: tab === t ? '#fff' : 'var(--text)', border: '1px solid var(--border)', padding: '6px 16px', borderRadius: 4, cursor: 'pointer', fontWeight: tab === t ? 600 : 400, fontSize: 13 }}>
            {t === 'dogs' ? 'My Dogs' : t === 'reservations' ? 'Reservations' : 'Availability'}
          </button>
        ))}
        <button className="btn btn-primary btn-sm" style={{ marginLeft: 'auto' }} onClick={() => setNewRes(true)}>+ Book Stay</button>
      </div>

      {error && <p className="error-text" style={{ marginBottom: 12 }}>{error}</p>}

      {loading && <div className="spinner" />}

      {!loading && tab === 'dogs' && (
        dogs.length === 0
          ? <p style={{ color: 'var(--text-sub)', fontSize: 13 }}>No dogs on file.</p>
          : dogs.map(d => (
            <div key={d.dog_id} className="card" style={{ padding: 16, marginBottom: 12 }}>
              <strong style={{ fontSize: 15 }}>{d.name}</strong>
              <span style={{ fontSize: 13, color: 'var(--text-sub)', marginLeft: 12 }}>{d.breed} · {d.size_class}</span>
              {d.medical_notes && <p style={{ fontSize: 12, color: '#c62828', marginTop: 6 }}>⚕ {d.medical_notes}</p>}
              {d.vaccination_records?.length > 0 && (
                <details style={{ marginTop: 8, fontSize: 12 }}>
                  <summary style={{ cursor: 'pointer', color: 'var(--text-sub)' }}>Vaccinations ({d.vaccination_records.length})</summary>
                  {d.vaccination_records.map((v, i) => (
                    <div key={i} style={{ padding: '4px 0', borderBottom: '1px solid var(--border)' }}>
                      {v.vaccine_name} — {v.administered_date}{v.expiry_date ? ` (expires ${v.expiry_date})` : ''}
                    </div>
                  ))}
                </details>
              )}
            </div>
          ))
      )}

      {!loading && tab === 'reservations' && (
        reservations.length === 0
          ? <p style={{ color: 'var(--text-sub)', fontSize: 13 }}>No reservations found.</p>
          : reservations.map(r => (
            <div key={r.reservation_id} className="card" style={{ padding: 16, marginBottom: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 6 }}>{statusBadge(r)}</div>
                  <div style={{ fontSize: 13 }}>Drop-off: {fmt(r.dropoff_datetime)}</div>
                  <div style={{ fontSize: 13 }}>Pick-up: {r.pickup_open_ended ? 'Open-ended' : fmt(r.pickup_datetime)}</div>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  {!r.cancelled && !r.checkin_datetime && (
                    <>
                      <button className="btn btn-secondary btn-sm" onClick={() => setEditRes(r)}>Modify</button>
                      <button className="btn btn-danger btn-sm" onClick={() => handleCancel(r.reservation_id)}>Cancel</button>
                    </>
                  )}
                </div>
              </div>
              {r.notes && <p style={{ fontSize: 12, color: 'var(--text-sub)', marginTop: 8 }}>{r.notes}</p>}
            </div>
          ))
      )}

      {!loading && tab === 'availability' && <AvailabilityTab />}

      {editRes && (
        <PortalEditModal
          reservation={editRes}
          dogs={dogs}
          onClose={() => setEditRes(null)}
          onSuccess={() => { setEditRes(null); loadReservations() }}
        />
      )}

      {newRes && (
        <PortalNewReservationModal
          dogs={dogs}
          onClose={() => setNewRes(false)}
          onSuccess={() => { setNewRes(false); setTab('reservations'); loadReservations() }}
        />
      )}
    </PortalShell>
  )
}

function AvailabilityTab() {
  const [sizeClass, setSizeClass] = useState('M')
  const [startDate, setStartDate] = useState(format(new Date(), 'yyyy-MM-dd'))
  const [endDate,   setEndDate]   = useState(format(addDays(new Date(), 14), 'yyyy-MM-dd'))
  const [data, setData]           = useState(null)
  const [loading, setLoading]     = useState(false)

  async function load() {
    setLoading(true)
    try { setData(await getPortalAvailability({ size_class: sizeClass, start_date: startDate, end_date: endDate })) }
    catch {}
    finally { setLoading(false) }
  }

  return (
    <div>
      <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <div className="form-field" style={{ marginBottom: 0 }}>
          <label>Size Class</label>
          <select value={sizeClass} onChange={e => setSizeClass(e.target.value)}>
            {['XS','S','M','L','XL'].map(s => <option key={s}>{s}</option>)}
          </select>
        </div>
        <div className="form-field" style={{ marginBottom: 0 }}>
          <label>Start</label>
          <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} />
        </div>
        <div className="form-field" style={{ marginBottom: 0 }}>
          <label>End</label>
          <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} />
        </div>
        <button className="btn btn-primary btn-sm" onClick={load} disabled={loading}>Check Availability</button>
      </div>
      {loading && <div className="spinner" />}
      {data && (
        <table className="data-table">
          <thead><tr><th>Date</th><th>Availability</th></tr></thead>
          <tbody>
            {data.map(d => (
              <tr key={d.date}>
                <td>{d.date}</td>
                <td>
                  {d.available
                    ? <span style={{ color: '#2e7d32', fontWeight: 600 }}>Available</span>
                    : <span style={{ color: '#c62828' }}>Busy</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

function PortalEditModal({ reservation, dogs, onClose, onSuccess }) {
  const [pickupDate, setPickupDate] = useState(reservation.pickup_datetime ? format(parseISO(reservation.pickup_datetime), 'yyyy-MM-dd') : '')
  const [pickupTime, setPickupTime] = useState(reservation.pickup_datetime ? format(parseISO(reservation.pickup_datetime), 'HH:mm') : '09:00')
  const [notes, setNotes]           = useState(reservation.notes || '')
  const [saving, setSaving]         = useState(false)
  const [error, setError]           = useState('')

  async function handleSave() {
    setSaving(true); setError('')
    try {
      await updatePortalReservation(reservation.reservation_id, {
        pickup_datetime: pickupDate ? `${pickupDate}T${pickupTime}:00` : null,
        notes: notes || null,
      })
      onSuccess()
    } catch (e) { setError(e.response?.data?.detail || 'Save failed') }
    finally { setSaving(false) }
  }

  return (
    <Modal title="Modify Reservation" size="sm" onClose={onClose}
      footer={<>
        <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn btn-primary" onClick={handleSave} disabled={saving}>Save</button>
      </>}
    >
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="form-field"><label>Pick-up Date</label><input type="date" value={pickupDate} onChange={e => setPickupDate(e.target.value)} /></div>
        <div className="form-field"><label>Pick-up Time</label><input type="time" value={pickupTime} onChange={e => setPickupTime(e.target.value)} /></div>
      </div>
      <div className="form-field"><label>Notes</label><textarea value={notes} onChange={e => setNotes(e.target.value)} /></div>
      {error && <p className="error-text">{error}</p>}
    </Modal>
  )
}

function PortalNewReservationModal({ dogs, onClose, onSuccess }) {
  const [form, setForm] = useState({ dog_id: dogs[0]?.dog_id || '', dropoff_date: '', dropoff_time: '09:00', pickup_date: '', pickup_time: '09:00', notes: '' })
  const [saving, setSaving] = useState(false)
  const [error, setError]   = useState('')

  function setF(k, v) { setForm(f => ({ ...f, [k]: v })) }

  async function handleSubmit() {
    if (!form.dog_id || !form.dropoff_date || !form.pickup_date) { setError('Dog, drop-off, and pick-up required'); return }
    setSaving(true); setError('')
    try {
      await createPortalReservation({
        dog_id: form.dog_id,
        dropoff_datetime: `${form.dropoff_date}T${form.dropoff_time}:00`,
        pickup_datetime:  `${form.pickup_date}T${form.pickup_time}:00`,
        notes: form.notes || null,
      })
      onSuccess()
    } catch (e) { setError(e.response?.data?.detail || 'Failed') }
    finally { setSaving(false) }
  }

  return (
    <Modal title="Book a Stay" size="sm" onClose={onClose}
      footer={<>
        <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn btn-primary" onClick={handleSubmit} disabled={saving}>Book</button>
      </>}
    >
      <div className="form-field">
        <label>Dog*</label>
        <select value={form.dog_id} onChange={e => setF('dog_id', e.target.value)}>
          {dogs.map(d => <option key={d.dog_id} value={d.dog_id}>{d.name}</option>)}
        </select>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="form-field"><label>Drop-off Date*</label><input type="date" value={form.dropoff_date} onChange={e => setF('dropoff_date', e.target.value)} /></div>
        <div className="form-field"><label>Drop-off Time</label><input type="time" value={form.dropoff_time} onChange={e => setF('dropoff_time', e.target.value)} /></div>
        <div className="form-field"><label>Pick-up Date*</label><input type="date" value={form.pickup_date} min={form.dropoff_date} onChange={e => setF('pickup_date', e.target.value)} /></div>
        <div className="form-field"><label>Pick-up Time</label><input type="time" value={form.pickup_time} onChange={e => setF('pickup_time', e.target.value)} /></div>
      </div>
      <div className="form-field"><label>Notes</label><textarea value={form.notes} onChange={e => setF('notes', e.target.value)} /></div>
      {error && <p className="error-text">{error}</p>}
    </Modal>
  )
}
