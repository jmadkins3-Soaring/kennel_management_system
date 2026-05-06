import { useState, useEffect } from 'react'
import Modal from '../../components/Modal'
import { listOwners, createOwner, getOwnerDogs } from '../../api/owners'
import { createDog } from '../../api/dogs'
import { listKennels } from '../../api/kennels'
import { DOG_BREEDS } from '../../utils/breeds'
import { createReservation } from '../../api/reservations'
import { listActivityTypes } from '../../api/activityTypes'
import { format } from 'date-fns'

const SIZE_CLASSES = ['XS', 'S', 'M', 'L', 'XL']
const PHASES = ['Morning', 'Afternoon', 'Evening', 'Night']

function phaseFromTime(timeStr) {
  if (!timeStr) return null
  const [h] = timeStr.split(':').map(Number)
  if (h >= 6  && h < 12) return 'Morning'
  if (h >= 12 && h < 17) return 'Afternoon'
  if (h >= 17 && h < 21) return 'Evening'
  return 'Night'
}

export default function QuickAddWizard({ prefill, onClose, onSuccess }) {
  const [step, setStep] = useState(1)
  const [error, setError] = useState('')

  // Step 1: Owner search/select
  const [ownerQuery, setOwnerQuery] = useState('')
  const [ownerResults, setOwnerResults] = useState([])
  const [owner, setOwner] = useState(null)
  const [newOwner, setNewOwner] = useState(false)
  const [ownerForm, setOwnerForm] = useState({ first_name: '', last_name: '', phone_number: '', email: '', emergency_contact_name: '', notes: '' })

  // Step 2: Dog select
  const [dogs, setDogs] = useState([])
  const [dog, setDog] = useState(null)
  const [newDog, setNewDog] = useState(false)
  const [dogForm, setDogForm] = useState({ name: '', breed: '', size_class: 'M', weight_lbs: '', medical_notes: '' })

  // Step 3: Dates
  const [dropoffDate, setDropoffDate] = useState(prefill?.date || format(new Date(), 'yyyy-MM-dd'))
  const [dropoffTime, setDropoffTime] = useState('09:00')
  const [pickupDate,  setPickupDate]  = useState('')
  const [pickupTime,  setPickupTime]  = useState('09:00')
  const [openEnded,   setOpenEnded]   = useState(false)
  const [overridePickup, setOverridePickup] = useState(false)

  // Step 4: Kennel
  const [kennels, setKennels] = useState([])
  const [kennel, setKennel] = useState(prefill?.kennelId ? { kennel_id: prefill.kennelId, kennel_number: prefill.kennelNumber } : null)
  const [kennelConflict, setKennelConflict] = useState(null)

  // Step 5: Activities
  const [activityTypes, setActivityTypes] = useState([])
  const [activities, setActivities] = useState([])

  const [saving, setSaving] = useState(false)

  // Owner search
  useEffect(() => {
    if (!ownerQuery.trim()) { setOwnerResults([]); return }
    const t = setTimeout(async () => {
      try {
        const r = await listOwners({ q: ownerQuery })
        setOwnerResults(r)
      } catch {}
    }, 300)
    return () => clearTimeout(t)
  }, [ownerQuery])

  // Load dogs when owner selected
  useEffect(() => {
    if (!owner) return
    getOwnerDogs(owner.owner_id).then(setDogs).catch(() => setDogs([]))
  }, [owner])

  // Load kennels at step 4 — include status at dropoff date/phase
  useEffect(() => {
    if (step !== 4) return
    const params = {}
    if (dropoffDate) {
      params.for_date = dropoffDate
      params.for_phase = phaseFromTime(dropoffTime)
    }
    listKennels(params).then(setKennels).catch(() => setKennels([]))
  }, [step, dropoffDate, dropoffTime])

  // Load activity types at step 5
  useEffect(() => {
    if (step !== 5) return
    listActivityTypes().then(ts => setActivityTypes(ts.filter(t => t.active !== false))).catch(() => {})
  }, [step])

  function setO(key, val) { setOwnerForm(f => ({ ...f, [key]: val })) }
  function setD(key, val) { setDogForm(f => ({ ...f, [key]: val })) }

  function nextStep() { setError(''); setStep(s => s + 1) }

  async function handleOwnerStep() {
    if (!newOwner && !owner) { setError('Select or create an owner'); return }
    if (newOwner) {
      if (!ownerForm.last_name || !ownerForm.first_name) { setError('First and last name required'); return }
      try {
        const o = await createOwner(ownerForm)
        setOwner(o)
      } catch (e) { setError(e.response?.data?.detail || 'Failed to create owner'); return }
    }
    nextStep()
  }

  async function handleDogStep() {
    if (!newDog && !dog) { setError('Select or add a dog'); return }
    if (newDog) {
      if (!dogForm.name || !dogForm.size_class) { setError('Name and size class required'); return }
      try {
        const d = await createDog({ ...dogForm, owner_id: owner.owner_id, weight_lbs: dogForm.weight_lbs ? parseFloat(dogForm.weight_lbs) : null })
        setDog(d)
      } catch (e) { setError(e.response?.data?.detail || 'Failed to create dog'); return }
    }
    nextStep()
  }

  function handleDateStep() {
    if (!dropoffDate || !dropoffTime) { setError('Drop-off date and time required'); return }
    if (!openEnded && (!pickupDate || !pickupTime)) { setError('Pick-up date/time required (or mark open-ended)'); return }
    nextStep()
  }

  function handleKennelStep() {
    if (!kennel) { setError('Select a kennel'); return }
    nextStep()
  }

  async function handleSubmit() {
    setSaving(true)
    setError('')
    const dropoff = `${dropoffDate}T${dropoffTime}:00`
    const pickup  = openEnded ? null : `${pickupDate}T${pickupTime}:00`
    try {
      await createReservation({
        dog_id: dog.dog_id,
        kennel_id: kennel.kennel_id,
        dropoff_datetime: dropoff,
        pickup_datetime: pickup,
        pickup_open_ended: openEnded,
        prescheduled_activities: activities.length ? activities : undefined,
        override_phase_conflict: overridePickup,
      })
      onSuccess?.()
    } catch (e) {
      const detail = e.response?.data?.detail || 'Failed to create reservation'
      if (typeof detail === 'string' && detail.includes('conflict')) {
        setKennelConflict(detail)
      } else {
        setError(detail)
      }
    } finally {
      setSaving(false)
    }
  }

  const dropoffPhase = phaseFromTime(dropoffTime)
  const pickupPhase  = phaseFromTime(pickupTime)

  return (
    <Modal
      title={`Quick Add Reservation — Step ${step} of 5`}
      size="md"
      onClose={onClose}
      footer={<>
        {step > 1 && <button className="btn btn-secondary" onClick={() => { setError(''); setStep(s => s - 1) }}>Back</button>}
        {step < 5 && (
          <button className="btn btn-primary" onClick={
            step === 1 ? handleOwnerStep :
            step === 2 ? handleDogStep :
            step === 3 ? handleDateStep :
            step === 4 ? handleKennelStep :
            nextStep
          }>Next</button>
        )}
        {step === 5 && (
          <button className="btn btn-primary" onClick={handleSubmit} disabled={saving}>
            {saving ? 'Saving…' : 'Create Reservation'}
          </button>
        )}
      </>}
    >
      {error && <p className="error-text" style={{ marginBottom: 12 }}>{error}</p>}

      {/* Step 1: Owner */}
      {step === 1 && (
        <div>
          <p style={{ marginBottom: 12, fontSize: 13, color: 'var(--text-sub)' }}>Search for an existing owner or create a new one.</p>
          {!newOwner && !owner && <>
            <div className="form-field">
              <label>Search by last name</label>
              <input value={ownerQuery} onChange={e => setOwnerQuery(e.target.value)} placeholder="Last name…" />
            </div>
            {ownerResults.length > 0 && (
              <div className="card" style={{ marginBottom: 12 }}>
                {ownerResults.map(o => (
                  <div key={o.owner_id}
                    onClick={() => { setOwner(o); setOwnerQuery(''); setOwnerResults([]) }}
                    style={{ padding: '8px 14px', cursor: 'pointer', borderBottom: '1px solid var(--border)', fontSize: 13 }}
                    onMouseEnter={e => e.currentTarget.style.background = '#f5f9ff'}
                    onMouseLeave={e => e.currentTarget.style.background = ''}
                  >
                    <strong>{o.last_name}, {o.first_name}</strong>
                    <span style={{ color: 'var(--text-sub)', marginLeft: 8 }}>{o.phone_number}</span>
                  </div>
                ))}
              </div>
            )}
            <button className="btn btn-secondary btn-sm" onClick={() => setNewOwner(true)}>+ Create New Owner</button>
          </>}

          {owner && !newOwner && (
            <div style={{ background: '#e3f2fd', borderRadius: 4, padding: '10px 14px', fontSize: 13, marginBottom: 10 }}>
              Selected: <strong>{owner.last_name}, {owner.first_name}</strong>
              <button className="btn btn-secondary btn-sm" style={{ marginLeft: 12 }} onClick={() => { setOwner(null); setOwnerQuery('') }}>Change</button>
            </div>
          )}

          {newOwner && (
            <div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div className="form-field"><label>First Name*</label><input value={ownerForm.first_name} onChange={e => setO('first_name', e.target.value)} /></div>
                <div className="form-field"><label>Last Name*</label><input value={ownerForm.last_name} onChange={e => setO('last_name', e.target.value)} /></div>
                <div className="form-field"><label>Phone</label><input value={ownerForm.phone_number} onChange={e => setO('phone_number', e.target.value)} /></div>
                <div className="form-field"><label>Email</label><input type="email" value={ownerForm.email} onChange={e => setO('email', e.target.value)} /></div>
              </div>
              <div className="form-field"><label>Emergency Contact</label><input value={ownerForm.emergency_contact_name} onChange={e => setO('emergency_contact_name', e.target.value)} /></div>
              <div className="form-field"><label>Notes</label><textarea value={ownerForm.notes} onChange={e => setO('notes', e.target.value)} /></div>
              <button className="btn btn-secondary btn-sm" onClick={() => setNewOwner(false)}>← Back to Search</button>
            </div>
          )}
        </div>
      )}

      {/* Step 2: Dog */}
      {step === 2 && (
        <div>
          <p style={{ marginBottom: 12, fontSize: 13, color: 'var(--text-sub)' }}>
            Owner: <strong>{owner?.last_name}, {owner?.first_name}</strong>
          </p>
          {!newDog && !dog && <>
            {dogs.length > 0 ? (
              <div className="card" style={{ marginBottom: 12 }}>
                {dogs.map(d => (
                  <div key={d.dog_id}
                    onClick={() => setDog(d)}
                    style={{ padding: '8px 14px', cursor: 'pointer', borderBottom: '1px solid var(--border)', fontSize: 13 }}
                    onMouseEnter={e => e.currentTarget.style.background = '#f5f9ff'}
                    onMouseLeave={e => e.currentTarget.style.background = ''}
                  >
                    <strong>{d.name}</strong>
                    <span style={{ color: 'var(--text-sub)', marginLeft: 8 }}>{d.breed} · {d.size_class}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p style={{ fontSize: 13, color: 'var(--text-sub)', marginBottom: 12 }}>No dogs on file for this owner.</p>
            )}
            <button className="btn btn-secondary btn-sm" onClick={() => setNewDog(true)}>+ Add New Dog</button>
          </>}

          {dog && !newDog && (
            <div style={{ background: '#e3f2fd', borderRadius: 4, padding: '10px 14px', fontSize: 13, marginBottom: 10 }}>
              Selected: <strong>{dog.name}</strong> ({dog.breed} · {dog.size_class})
              <button className="btn btn-secondary btn-sm" style={{ marginLeft: 12 }} onClick={() => setDog(null)}>Change</button>
            </div>
          )}

          {newDog && (
            <div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div className="form-field"><label>Dog Name*</label><input value={dogForm.name} onChange={e => setD('name', e.target.value)} /></div>
                <div className="form-field">
                  <label>Breed</label>
                  <input list="dog-breeds-list-wiz" value={dogForm.breed} onChange={e => setD('breed', e.target.value)} placeholder="Search breeds…" />
                  <datalist id="dog-breeds-list-wiz">{DOG_BREEDS.map(b => <option key={b} value={b} />)}</datalist>
                </div>
                <div className="form-field">
                  <label>Size Class*</label>
                  <select value={dogForm.size_class} onChange={e => setD('size_class', e.target.value)}>
                    {SIZE_CLASSES.map(s => <option key={s}>{s}</option>)}
                  </select>
                </div>
                <div className="form-field"><label>Weight (lbs)</label><input type="number" value={dogForm.weight_lbs} onChange={e => setD('weight_lbs', e.target.value)} /></div>
              </div>
              <div className="form-field"><label>Medical Notes</label><textarea value={dogForm.medical_notes} onChange={e => setD('medical_notes', e.target.value)} /></div>
              <button className="btn btn-secondary btn-sm" onClick={() => setNewDog(false)}>← Back to List</button>
            </div>
          )}
        </div>
      )}

      {/* Step 3: Dates */}
      {step === 3 && (
        <div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div className="form-field">
              <label>Drop-off Date*</label>
              <input type="date" value={dropoffDate} onChange={e => setDropoffDate(e.target.value)} />
            </div>
            <div className="form-field">
              <label>Drop-off Time*</label>
              <input type="time" value={dropoffTime} onChange={e => setDropoffTime(e.target.value)} />
            </div>
          </div>
          {dropoffPhase && <p style={{ fontSize: 12, color: 'var(--text-sub)', marginBottom: 14 }}>Phase: <strong>{dropoffPhase}</strong></p>}

          <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 13, marginBottom: 12, cursor: 'pointer' }}>
            <input type="checkbox" checked={openEnded} onChange={e => setOpenEnded(e.target.checked)} />
            Open-ended pick-up (no fixed date)
          </label>

          {!openEnded && <>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="form-field">
                <label>Pick-up Date*</label>
                <input type="date" value={pickupDate} min={dropoffDate} onChange={e => setPickupDate(e.target.value)} />
              </div>
              <div className="form-field">
                <label>Pick-up Time*</label>
                <input type="time" value={pickupTime} onChange={e => setPickupTime(e.target.value)} />
              </div>
            </div>
            {pickupPhase && <p style={{ fontSize: 12, color: 'var(--text-sub)', marginBottom: 14 }}>Phase: <strong>{pickupPhase}</strong></p>}
          </>}

          {kennelConflict && (
            <div style={{ background: '#fff8e1', border: '1px solid #ffe082', borderRadius: 4, padding: '10px 14px', marginTop: 10 }}>
              <p style={{ fontWeight: 600, color: '#e65100', marginBottom: 8 }}>⚠️ {kennelConflict}</p>
              <label style={{ display: 'flex', gap: 8, cursor: 'pointer', fontSize: 13 }}>
                <input type="checkbox" checked={overridePickup} onChange={e => setOverridePickup(e.target.checked)} />
                Override conflict and proceed
              </label>
            </div>
          )}
        </div>
      )}

      {/* Step 4: Kennel */}
      {step === 4 && (
        <div>
          <p style={{ marginBottom: 12, fontSize: 13, color: 'var(--text-sub)' }}>
            Available kennels for size <strong>{dog?.size_class || dogForm.size_class}</strong>:
          </p>
          {kennels.length === 0 && <p style={{ fontSize: 13, color: 'var(--text-sub)' }}>No available kennels found.</p>}
          <div className="card" style={{ maxHeight: 280, overflowY: 'auto' }}>
            {kennels.map(k => {
              const st = k.current_status || 'Free'
              const occupied = st === 'Assigned' || st === 'Used'
              const isHold = st === 'Hold'
              const selected = kennel?.kennel_id === k.kennel_id
              const statusColor = occupied ? '#e65100' : isHold ? '#6a1b9a' : '#2e7d32'
              const currentDogs = k.current_dogs || []
              const statusLabel = occupied
                ? currentDogs.length > 0
                  ? `${st} — co-house w/ ${currentDogs.map(d => d.dog_name).join(', ')}`
                  : `${st} — co-house`
                : st
              return (
                <div
                  key={k.kennel_id}
                  onClick={() => setKennel(k)}
                  style={{
                    padding: '8px 14px',
                    cursor: 'pointer',
                    borderBottom: '1px solid var(--border)',
                    fontSize: 13,
                    background: selected ? '#e3f2fd' : '',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span>
                      <strong>{k.kennel_number}</strong>
                      <span style={{ color: 'var(--text-sub)', marginLeft: 8 }}>{k.max_size_class} · {k.sqft} sqft</span>
                      {k.features && <span style={{ color: 'var(--text-sub)', marginLeft: 8 }}>{k.features}</span>}
                    </span>
                    <span style={{ fontSize: 11, fontWeight: 600, color: statusColor, marginLeft: 12, whiteSpace: 'nowrap' }}>
                      {occupied ? st : st}
                    </span>
                  </div>
                  {occupied && currentDogs.length > 0 && (
                    <div style={{ fontSize: 11, color: '#e65100', marginTop: 3 }}>
                      Co-house with: {currentDogs.map(d => `${d.dog_name} (${d.size_class}, ${d.owner_last_name})`).join(' · ')}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Step 5: Activities + confirm */}
      {step === 5 && (
        <div>
          <div style={{ fontSize: 13, marginBottom: 16, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 24px' }}>
            <div><strong>Dog:</strong> {dog?.name}</div>
            <div><strong>Owner:</strong> {owner?.last_name}, {owner?.first_name}</div>
            <div><strong>Kennel:</strong> {kennel?.kennel_number}</div>
            <div><strong>Drop-off:</strong> {dropoffDate} {dropoffTime}</div>
            <div><strong>Pick-up:</strong> {openEnded ? 'Open-ended' : `${pickupDate} ${pickupTime}`}</div>
          </div>

          {activityTypes.length > 0 && (
            <>
              <div className="divider" />
              <p style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>Pre-schedule Activities (optional)</p>
              {activities.map((act, i) => (
                <div key={i} style={{ display: 'flex', gap: 8, marginBottom: 8, alignItems: 'center' }}>
                  <select value={act.activity_type_id} onChange={e => {
                    const upd = [...activities]; upd[i].activity_type_id = e.target.value; setActivities(upd)
                  }} style={{ flex: 1 }}>
                    <option value="">— Type —</option>
                    {activityTypes.map(t => <option key={t.activity_type_id} value={t.activity_type_id}>{t.name}</option>)}
                  </select>
                  <input type="date" value={act.scheduled_date} onChange={e => {
                    const upd = [...activities]; upd[i].scheduled_date = e.target.value; setActivities(upd)
                  }} style={{ width: 140 }} />
                  <button className="btn btn-secondary btn-sm" onClick={() => setActivities(a => a.filter((_, j) => j !== i))}>✕</button>
                </div>
              ))}
              <button className="btn btn-secondary btn-sm" onClick={() => setActivities(a => [...a, { activity_type_id: '', scheduled_date: dropoffDate }])}>
                + Add Activity
              </button>
            </>
          )}
        </div>
      )}
    </Modal>
  )
}
