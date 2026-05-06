import { useState, useEffect } from 'react'
import Modal from '../../components/Modal'
import { getReservation, checkinReservation } from '../../api/reservations'
import { getDog } from '../../api/dogs'
import { getOwner } from '../../api/owners'
import { listBills } from '../../api/billing'

export default function CheckInModal({ reservationId, onClose, onSuccess }) {
  const [res, setRes] = useState(null)
  const [dog, setDog] = useState(null)
  const [owner, setOwner] = useState(null)
  const [unpaidBill, setUnpaidBill] = useState(false)
  const [medAck, setMedAck] = useState(false)
  const [overrideUnpaid, setOverrideUnpaid] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    async function load() {
      try {
        const r = await getReservation(reservationId)
        setRes(r)
        const [d, o] = await Promise.all([getDog(r.dog_id), getOwner(r.kennel_id)])
        setDog(d)
        // owner from dog
        const own = await getOwner(d.owner_id)
        setOwner(own)
        // Check for unpaid bills
        try {
          const bills = await import('../../api/billing').then(m => m.listBills({ reservation_id: reservationId }))
          setUnpaidBill(bills.some(b => !b.paid && b.total_due > 0))
        } catch {}
      } catch (e) {
        setError('Failed to load reservation')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [reservationId])

  async function handleSubmit() {
    if (!medAck) { setError('Please acknowledge medical/vaccination records'); return }
    if (unpaidBill && !overrideUnpaid) { setError('Unpaid bill must be acknowledged before check-in'); return }
    setSaving(true)
    setError('')
    try {
      await checkinReservation(reservationId, {
        medical_acknowledged: medAck,
        override_unpaid_bill: overrideUnpaid,
      })
      onSuccess?.()
    } catch (e) {
      setError(e.response?.data?.detail || 'Check-in failed')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <Modal title="Check In" size="sm" onClose={onClose}><div className="spinner" /></Modal>

  return (
    <Modal
      title="Check In"
      size="sm"
      onClose={onClose}
      footer={<>
        <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn btn-primary" onClick={handleSubmit} disabled={saving}>
          {saving ? 'Checking in…' : 'Confirm Check-In'}
        </button>
      </>}
    >
      {res && <>
        <div style={{ marginBottom: 16, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: 13 }}>
          <div><strong>Dog:</strong> {dog?.name}</div>
          <div><strong>Owner:</strong> {owner?.last_name}, {owner?.first_name}</div>
          <div><strong>Kennel:</strong> {res.kennel_id}</div>
          <div><strong>Drop-off:</strong> {res.dropoff_phase}</div>
        </div>

        {unpaidBill && (
          <div style={{ background: '#fff8e1', border: '1px solid #ffe082', borderRadius: 4, padding: '10px 14px', marginBottom: 14 }}>
            <p style={{ fontWeight: 600, color: '#e65100', marginBottom: 8 }}>⚠️ Unpaid bill on file</p>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
              <input type="checkbox" checked={overrideUnpaid} onChange={e => setOverrideUnpaid(e.target.checked)} />
              I acknowledge the unpaid balance and authorize check-in
            </label>
          </div>
        )}

        <label style={{ display: 'flex', alignItems: 'flex-start', gap: 8, cursor: 'pointer', marginBottom: 14 }}>
          <input type="checkbox" checked={medAck} onChange={e => setMedAck(e.target.checked)} style={{ marginTop: 2 }} />
          <span>I have reviewed the dog's medical notes and vaccination records</span>
        </label>

        {error && <p className="error-text">{error}</p>}
      </>}
    </Modal>
  )
}
