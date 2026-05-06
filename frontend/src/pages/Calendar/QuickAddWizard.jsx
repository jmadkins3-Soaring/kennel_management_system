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

function dogKey(d) {
  return d.isNew ? d.tempId : d.dog_id
}

function blankDogForm() {
  return { name: '', breed: '', size_class: 'M', weight_lbs: '', medical_notes: '' }
}

export default function QuickAddWizard({ prefill, onClose, onSuccess }) {
  const [step, setStep] = useState(1)
  const [error, setError] = useState('')

  // Step 1: Owner
  const [ownerQuery, setOwnerQuery] = useState('')
  const [ownerResults, setOwnerResults] = useState([])
  const [owner, setOwner] = useState(null)
  const [newOwner, setNewOwner] = useState(false)
  const [ownerForm, setOwnerForm] = useState({ first_name: '', last_name: '', phone_number: '', email: '', emergency_contact_name: '', notes: '' })

  // Step 2: Dogs — multi-select
  const [existingDogs, setExistingDogs] = useState([])
  const [selectedDogs, setSelectedDogs] = useState([])   // {dog_id|tempId, name, breed, size_class, isNew?}
  const [addingNew, setAddingNew] = useState(false)
  const [dogForm, setDogForm] = useState(blankDogForm())
  let newDogCounter = 0

  // Step 3: Dates
  const [dropoffDate, setDropoffDate] = useState(prefill?.date || format(new Date(), 'yyyy-MM-dd'))
  const [dropoffTime, setDropoffTime] = useState('09:00')
  const [pickupDate,  setPickupDate]  = useState('')
  const [pickupTime,  setPickupTime]  = useState('09:00')
  const [openEnded,   setOpenEnded]   = useState(false)
  const [overrideConflict, setOverrideConflict] = useState(false)
  const [conflictMsg, setConflictMsg] = useState('')

  // Step 4: Kennel assignment — one kennel per dog
  const [kennels, setKennels] = useState([])
  const [assignments, setAssignments] = useState({})   // dogKey -> kennel object
  const [focusedKey, setFocusedKey] = useState(null)

  // Step 5: Activities
  const [activityTypes, setActivityTypes] = useState([])
  const [activities, setActivities] = useState([])

  const [saving, setSaving] = useState(false)

  // Owner search
  useEffect(() => {
    if (!ownerQuery.trim()) { setOwnerResults([]); return }
    const t = setTimeout(async () => {
      try { setOwnerResults(await listOwners({ q: ownerQuery })) } catch {}
    }, 300)
    return () => clearTimeout(t)
  }, [ownerQuery])

  // Load owner's existing dogs when owner selected
  useEffect(() => {
    if (!owner) return
    getOwnerDogs(owner.owner_id).then(setExistingDogs).catch(() => setExistingDogs([]))
  }, [owner])

  // Load kennels at step 4
  useEffect(() => {
    if (step !== 4) return
    const params = {}
    if (dropoffDate) {
      params.for_date = dropoffDate
      params.for_phase = phaseFromTime(dropoffTime)
    }
    listKennels(params).then(k => {
      setKennels(k)
      // Pre-assign prefill kennel to the first dog
      if (prefill?.kennelId && selectedDogs.length > 0) {
        const pk = k.find(x => x.kennel_id === prefill.kennelId)
        if (pk) {
          const firstKey = dogKey(selectedDogs[0])
          setAssignments({ [firstKey]: pk })
          setFocusedKey(firstKey)
        }
      } else if (selectedDogs.length > 0) {
        setFocusedKey(dogKey(selectedDogs[0]))
      }
    }).catch(() => setKennels([]))
  }, [step, dropoffDate, dropoffTime])

  // Load activity types at step 5
  useEffect(() => {
    if (step !== 5) return
    listActivityTypes().then(ts => setActivityTypes(ts.filter(t => t.active !== false))).catch(() => {})
  }, [step])

  function setO(key, val) { setOwnerForm(f => ({ ...f, [key]: val })) }
  function setD(key, val) { setDogForm(f => ({ ...f, [key]: val })) }

  function nextStep() { setError(''); setStep(s => s + 1) }

  // --- Step handlers ---

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

  function toggleDog(d) {
    const key = dogKey(d)
    setSelectedDogs(prev =>
      prev.find(x => dogKey(x) === key)
        ? prev.filter(x => dogKey(x) !== key)
        : [...prev, d]
    )
  }

  function addNewDogToList() {
    if (!dogForm.name || !dogForm.size_class) { setError('Name and size class required'); return }
    setError('')
    const tempId = `new-${Date.now()}`
    const pending = { ...dogForm, tempId, isNew: true, weight_lbs: dogForm.weight_lbs ? parseFloat(dogForm.weight_lbs) : null }
    setSelectedDogs(prev => [...prev, pending])
    setAddingNew(false)
    setDogForm(blankDogForm())
  }

  function handleDogStep() {
    if (selectedDogs.length === 0) { setError('Select at least one dog'); return }
    nextStep()
  }

  function handleDateStep() {
    if (!dropoffDate || !dropoffTime) { setError('Drop-off date and time required'); return }
    if (!openEnded && (!pickupDate || !pickupTime)) { setError('Pick-up date/time required (or mark open-ended)'); return }
    nextStep()
  }

  function handleKennelStep() {
    const unassigned = selectedDogs.filter(d => !assignments[dogKey(d)])
    if (unassigned.length > 0) {
      setError(`Assign a kennel to: ${unassigned.map(d => d.name).join(', ')}`)
      return
    }
    nextStep()
  }

  function assignKennel(kennel) {
    if (!focusedKey) return
    setAssignments(prev => ({ ...prev, [focusedKey]: kennel }))
    // Auto-advance focus to next unassigned dog
    const nextUnassigned = selectedDogs.find(d => {
      const k = dogKey(d)
      return k !== focusedKey && !assignments[k]
    })
    if (nextUnassigned) setFocusedKey(dogKey(nextUnassigned))
  }

  async function handleSubmit() {
    setSaving(true)
    setError('')
    setConflictMsg('')
    const dropoff = `${dropoffDate}T${dropoffTime}:00`
    const pickup  = openEnded ? null : `${pickupDate}T${pickupTime}:00`

    try {
      // Create any pending new dogs first
      const dogIdMap = {}  // tempId -> real dog_id
      for (const d of selectedDogs) {
        if (d.isNew) {
          const created = await createDog({
            name: d.name,
            breed: d.breed,
            size_class: d.size_class,
            weight_lbs: d.weight_lbs,
            medical_notes: d.medical_notes,
            owner_id: owner.owner_id,
          })
          dogIdMap[d.tempId] = created.dog_id
        }
      }

      // Create one reservation per dog
      const errors = []
      for (const d of selectedDogs) {
        const realDogId = d.isNew ? dogIdMap[d.tempId] : d.dog_id
        const kennel = assignments[dogKey(d)]
        try {
          await createReservation({
            dog_id: realDogId,
            kennel_id: kennel.kennel_id,
            dropoff_datetime: dropoff,
            pickup_datetime: pickup,
            pickup_open_ended: openEnded,
            prescheduled_activities: activities.length ? activities : undefined,
            override_phase_conflict: overrideConflict,
          })
        } catch (e) {
          const detail = e.response?.data?.detail || 'Failed'
          errors.push(`${d.name} (${kennel.kennel_number}): ${detail}`)
        }
      }

      if (errors.length > 0) {
        const hasConflict = errors.some(e => e.toLowerCase().includes('conflict'))
        if (hasConflict) {
          setConflictMsg(errors.join('\n'))
          setStep(3)
        } else {
          setError(errors.join('\n'))
        }
      } else {
        onSuccess?.()
      }
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

  const dropoffPhase = phaseFromTime(dropoffTime)
  const pickupPhase  = phaseFromTime(pickupTime)
  const focusedDog   = selectedDogs.find(d => dogKey(d) === focusedKey)

  // Which kennels are already assigned to another dog in this batch?
  const batchAssignedKennelIds = new Set(
    Object.entries(assignments)
      .filter(([k]) => k !== focusedKey)
      .map(([, kn]) => kn.kennel_id)
  )

  return (
    <Modal
      title={`Quick Add Reservation — Step ${step} of 5`}
      size="lg"
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
            {saving ? 'Saving…' : `Create ${selectedDogs.length} Reservation${selectedDogs.length !== 1 ? 's' : ''}`}
          </button>
        )}
      </>}
    >
      {error && <p className="error-text" style={{ marginBottom: 12, whiteSpace: 'pre-line' }}>{error}</p>}

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
              <button className="btn btn-secondary btn-sm" style={{ marginLeft: 12 }} onClick={() => { setOwner(null); setOwnerQuery(''); setSelectedDogs([]) }}>Change</button>
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

      {/* Step 2: Dogs — multi-select */}
      {step === 2 && (
        <div>
          <p style={{ marginBottom: 12, fontSize: 13, color: 'var(--text-sub)' }}>
            Owner: <strong>{owner?.last_name}, {owner?.first_name}</strong> — select one or more dogs.
          </p>

          {/* Existing dogs checklist */}
          {existingDogs.length > 0 && (
            <div className="card" style={{ marginBottom: 12 }}>
              {existingDogs.map(d => {
                const checked = !!selectedDogs.find(x => dogKey(x) === d.dog_id)
                return (
                  <label key={d.dog_id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 14px', cursor: 'pointer', borderBottom: '1px solid var(--border)', fontSize: 13 }}>
                    <input type="checkbox" checked={checked} onChange={() => toggleDog(d)} />
                    <span><strong>{d.name}</strong> <span style={{ color: 'var(--text-sub)' }}>{d.breed} · {d.size_class}</span></span>
                  </label>
                )
              })}
            </div>
          )}

          {existingDogs.length === 0 && !addingNew && (
            <p style={{ fontSize: 13, color: 'var(--text-sub)', marginBottom: 12 }}>No dogs on file for this owner.</p>
          )}

          {/* Pending new dogs added this session */}
          {selectedDogs.filter(d => d.isNew).map(d => (
            <div key={d.tempId} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: '#f1f8e9', borderRadius: 4, padding: '6px 12px', marginBottom: 6, fontSize: 13 }}>
              <span><strong>{d.name}</strong> <span style={{ color: 'var(--text-sub)' }}>{d.breed} · {d.size_class}</span> <span style={{ color: '#558b2f', fontSize: 11 }}>new</span></span>
              <button className="btn btn-secondary btn-sm" onClick={() => setSelectedDogs(prev => prev.filter(x => dogKey(x) !== d.tempId))}>✕</button>
            </div>
          ))}

          {/* Add new dog form */}
          {addingNew ? (
            <div style={{ border: '1px solid var(--border)', borderRadius: 6, padding: 14, marginTop: 10 }}>
              <p style={{ fontWeight: 600, fontSize: 13, marginBottom: 10 }}>New Dog</p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div className="form-field"><label>Name*</label><input value={dogForm.name} onChange={e => setD('name', e.target.value)} /></div>
                <div className="form-field">
                  <label>Breed</label>
                  <input list="dog-breeds-wiz" value={dogForm.breed} onChange={e => setD('breed', e.target.value)} placeholder="Search breeds…" />
                  <datalist id="dog-breeds-wiz">{DOG_BREEDS.map(b => <option key={b} value={b} />)}</datalist>
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
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn btn-primary btn-sm" onClick={addNewDogToList}>Add to List</button>
                <button className="btn btn-secondary btn-sm" onClick={() => { setAddingNew(false); setDogForm(blankDogForm()) }}>Cancel</button>
              </div>
            </div>
          ) : (
            <button className="btn btn-secondary btn-sm" style={{ marginTop: 8 }} onClick={() => setAddingNew(true)}>+ Add New Dog</button>
          )}

          {selectedDogs.length > 0 && (
            <div style={{ marginTop: 14, padding: '8px 12px', background: '#e3f2fd', borderRadius: 4, fontSize: 13 }}>
              Selected: {selectedDogs.map(d => d.name).join(', ')} ({selectedDogs.length} dog{selectedDogs.length !== 1 ? 's' : ''})
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

          {conflictMsg && (
            <div style={{ background: '#fff8e1', border: '1px solid #ffe082', borderRadius: 4, padding: '10px 14px', marginTop: 10 }}>
              <p style={{ fontWeight: 600, color: '#e65100', marginBottom: 8, whiteSpace: 'pre-line' }}>⚠️ {conflictMsg}</p>
              <label style={{ display: 'flex', gap: 8, cursor: 'pointer', fontSize: 13 }}>
                <input type="checkbox" checked={overrideConflict} onChange={e => setOverrideConflict(e.target.checked)} />
                Override conflicts and proceed
              </label>
            </div>
          )}
        </div>
      )}

      {/* Step 4: Kennel assignment */}
      {step === 4 && (
        <div style={{ display: 'grid', gridTemplateColumns: '200px 1fr', gap: 16, minHeight: 320 }}>
          {/* Left: dog list */}
          <div>
            <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-sub)', textTransform: 'uppercase', letterSpacing: '.05em', marginBottom: 8 }}>Dogs</p>
            {selectedDogs.map(d => {
              const key = dogKey(d)
              const assigned = assignments[key]
              const focused = key === focusedKey
              return (
                <div
                  key={key}
                  onClick={() => setFocusedKey(key)}
                  style={{
                    padding: '8px 10px',
                    marginBottom: 6,
                    borderRadius: 4,
                    cursor: 'pointer',
                    border: focused ? '2px solid var(--color-primary, #1976d2)' : '2px solid var(--border)',
                    background: focused ? '#e3f2fd' : '#fff',
                    fontSize: 13,
                  }}
                >
                  <div style={{ fontWeight: 600 }}>{d.name} <span style={{ fontWeight: 400, color: 'var(--text-sub)' }}>({d.size_class})</span></div>
                  {assigned
                    ? <div style={{ fontSize: 11, color: '#2e7d32', marginTop: 2 }}>K-{assigned.kennel_number} ✓</div>
                    : <div style={{ fontSize: 11, color: '#e65100', marginTop: 2 }}>— pick kennel</div>
                  }
                </div>
              )
            })}
          </div>

          {/* Right: kennel list */}
          <div>
            <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-sub)', textTransform: 'uppercase', letterSpacing: '.05em', marginBottom: 8 }}>
              {focusedDog ? <>Assign kennel to <strong>{focusedDog.name}</strong></> : 'Select a dog first'}
            </p>
            <div className="card" style={{ maxHeight: 300, overflowY: 'auto', opacity: focusedKey ? 1 : 0.5, pointerEvents: focusedKey ? 'auto' : 'none' }}>
              {kennels.length === 0 && <p style={{ padding: 12, fontSize: 13, color: 'var(--text-sub)' }}>No kennels found.</p>}
              {kennels.map(k => {
                const st = k.current_status || 'Free'
                const isHold = st === 'Hold'
                const isBatchAssigned = batchAssignedKennelIds.has(k.kennel_id)
                const isThisAssigned = focusedKey && assignments[focusedKey]?.kennel_id === k.kennel_id
                const existingDogs = k.current_dogs || []
                const statusColor = isHold ? '#6a1b9a' : (st === 'Free' ? '#2e7d32' : '#e65100')

                return (
                  <div
                    key={k.kennel_id}
                    onClick={() => !isHold && assignKennel(k)}
                    style={{
                      padding: '8px 12px',
                      borderBottom: '1px solid var(--border)',
                      cursor: isHold ? 'not-allowed' : 'pointer',
                      background: isThisAssigned ? '#e3f2fd' : isBatchAssigned ? '#f3e5f5' : '',
                      opacity: isHold ? 0.5 : 1,
                    }}
                    onMouseEnter={e => { if (!isHold) e.currentTarget.style.background = isThisAssigned ? '#e3f2fd' : '#f5f9ff' }}
                    onMouseLeave={e => { e.currentTarget.style.background = isThisAssigned ? '#e3f2fd' : isBatchAssigned ? '#f3e5f5' : '' }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 13 }}>
                      <span>
                        <strong>{k.kennel_number}</strong>
                        <span style={{ color: 'var(--text-sub)', marginLeft: 8 }}>{k.max_size_class} · {k.sqft} sqft</span>
                        {k.features && <span style={{ color: 'var(--text-sub)', marginLeft: 6 }}>{k.features}</span>}
                      </span>
                      <span style={{ fontSize: 11, fontWeight: 600, color: statusColor }}>
                        {isThisAssigned ? '✓ selected' : st}
                      </span>
                    </div>
                    {existingDogs.length > 0 && (
                      <div style={{ fontSize: 11, color: '#e65100', marginTop: 2 }}>
                        Co-house: {existingDogs.map(d => `${d.dog_name} (${d.size_class})`).join(' · ')}
                      </div>
                    )}
                    {isBatchAssigned && !isThisAssigned && (
                      <div style={{ fontSize: 11, color: '#6a1b9a', marginTop: 2 }}>
                        Co-house: {Object.entries(assignments).filter(([, kn]) => kn.kennel_id === k.kennel_id).map(([key]) => selectedDogs.find(d => dogKey(d) === key)?.name).filter(Boolean).join(', ')} (this batch)
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {/* Step 5: Activities + confirm */}
      {step === 5 && (
        <div>
          <div style={{ fontSize: 13, marginBottom: 16 }}>
            <p style={{ fontWeight: 600, marginBottom: 8 }}>Reservations to create:</p>
            {selectedDogs.map(d => {
              const kennel = assignments[dogKey(d)]
              return (
                <div key={dogKey(d)} style={{ display: 'flex', justifyContent: 'space-between', padding: '5px 0', borderBottom: '1px solid var(--border)', fontSize: 13 }}>
                  <span><strong>{d.name}</strong> <span style={{ color: 'var(--text-sub)' }}>({d.size_class}{d.isNew ? ' · new' : ''})</span></span>
                  <span style={{ color: 'var(--text-sub)' }}>Kennel {kennel?.kennel_number}</span>
                </div>
              )
            })}
            <div style={{ marginTop: 10, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 24px' }}>
              <div><strong>Owner:</strong> {owner?.last_name}, {owner?.first_name}</div>
              <div><strong>Drop-off:</strong> {dropoffDate} {dropoffTime}</div>
              <div><strong>Pick-up:</strong> {openEnded ? 'Open-ended' : `${pickupDate} ${pickupTime}`}</div>
            </div>
          </div>

          {activityTypes.length > 0 && (
            <>
              <div className="divider" />
              <p style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>Pre-schedule Activities (applied to all dogs)</p>
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
