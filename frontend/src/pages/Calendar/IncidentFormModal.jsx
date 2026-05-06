import { useState, useEffect } from 'react'
import Modal from '../../components/Modal'
import { createIncident } from '../../api/incidents'
import { getReservation } from '../../api/reservations'
import { getDog } from '../../api/dogs'
import { useAuth } from '../../contexts/AuthContext'

const INCIDENT_TYPES = ['Injury', 'Illness', 'Escape Attempt', 'Aggression', 'Medication Issue', 'Other']

export default function IncidentFormModal({ reservationId, dogId, onClose, onSuccess }) {
  const { user } = useAuth()
  const [dog, setDog] = useState(null)
  const [form, setForm] = useState({
    incident_type: '',
    description: '',
    visible_to_owner: false,
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    async function load() {
      try {
        const dId = dogId || (await getReservation(reservationId)).dog_id
        setDog(await getDog(dId))
      } catch {}
    }
    load()
  }, [reservationId, dogId])

  function set(key, val) { setForm(f => ({ ...f, [key]: val })) }

  async function handleSubmit() {
    if (!form.incident_type || !form.description) {
      setError('Type and description are required')
      return
    }
    setSaving(true)
    setError('')
    try {
      await createIncident({
        dog_id: dog?.dog_id,
        reservation_id: reservationId || null,
        incident_type: form.incident_type,
        description: form.description,
        visible_to_owner: form.visible_to_owner,
        reported_by: user?.username,
      })
      onSuccess?.()
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to save incident')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      title="Add Incident Report"
      size="sm"
      onClose={onClose}
      footer={<>
        <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn btn-danger" onClick={handleSubmit} disabled={saving}>
          {saving ? 'Saving…' : 'Save Incident'}
        </button>
      </>}
    >
      {dog && <p style={{ fontSize: 13, marginBottom: 14 }}>Dog: <strong>{dog.name}</strong></p>}

      <div className="form-field">
        <label>Incident Type</label>
        <select value={form.incident_type} onChange={e => set('incident_type', e.target.value)}>
          <option value="">— Select —</option>
          {INCIDENT_TYPES.map(t => <option key={t}>{t}</option>)}
        </select>
      </div>

      <div className="form-field">
        <label>Description</label>
        <textarea value={form.description} onChange={e => set('description', e.target.value)} />
      </div>

      <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 13, cursor: 'pointer' }}>
        <input type="checkbox" checked={form.visible_to_owner} onChange={e => set('visible_to_owner', e.target.checked)} />
        Visible to owner in portal
      </label>

      {error && <p className="error-text" style={{ marginTop: 10 }}>{error}</p>}
    </Modal>
  )
}
