import { useState, useEffect } from 'react'
import Modal from '../../components/Modal'
import { getReservation, checkoutReservation } from '../../api/reservations'
import { getDog } from '../../api/dogs'
import { getOwner } from '../../api/owners'

export default function CheckOutModal({ reservationId, onClose, onSuccess }) {
  const [res, setRes] = useState(null)
  const [dog, setDog] = useState(null)
  const [owner, setOwner] = useState(null)
  const [healthy, setHealthy] = useState(true)
  const [notes, setNotes] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
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
      } catch { setError('Failed to load reservation') }
      finally { setLoading(false) }
    }
    load()
  }, [reservationId])

  async function handleSubmit() {
    setSaving(true)
    setError('')
    try {
      await checkoutReservation(reservationId, {
        checkout_healthy: healthy,
        checkout_notes: notes || null,
      })
      onSuccess?.()
    } catch (e) {
      setError(e.response?.data?.detail || 'Check-out failed')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <Modal title="Check Out" size="sm" onClose={onClose}><div className="spinner" /></Modal>

  return (
    <Modal
      title="Check Out"
      size="sm"
      onClose={onClose}
      footer={<>
        <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn btn-primary" onClick={handleSubmit} disabled={saving}>
          {saving ? 'Checking out…' : 'Confirm Check-Out'}
        </button>
      </>}
    >
      {res && <>
        <div style={{ marginBottom: 16, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: 13 }}>
          <div><strong>Dog:</strong> {dog?.name}</div>
          <div><strong>Owner:</strong> {owner?.last_name}, {owner?.first_name}</div>
          <div><strong>Kennel:</strong> {res.kennel_id}</div>
          <div><strong>Scheduled pickup:</strong> {res.pickup_phase || '—'}</div>
        </div>

        <div className="form-field">
          <label>Leaving healthy?</label>
          <div style={{ display: 'flex', gap: 16 }}>
            <label style={{ display: 'flex', gap: 6, cursor: 'pointer' }}>
              <input type="radio" checked={healthy} onChange={() => setHealthy(true)} /> Yes
            </label>
            <label style={{ display: 'flex', gap: 6, cursor: 'pointer' }}>
              <input type="radio" checked={!healthy} onChange={() => setHealthy(false)} /> No / Concern
            </label>
          </div>
        </div>

        <div className="form-field">
          <label>Checkout notes (optional)</label>
          <textarea value={notes} onChange={e => setNotes(e.target.value)} placeholder="Any notes about the dog's condition…" />
        </div>

        {error && <p className="error-text">{error}</p>}
      </>}
    </Modal>
  )
}
