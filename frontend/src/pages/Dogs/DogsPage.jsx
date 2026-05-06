import { useState, useEffect } from 'react'
import Layout from '../../components/Layout'
import Modal from '../../components/Modal'
import { listDogs, getDog, updateDog, createDog, archiveDog, addVaccination } from '../../api/dogs'
import { listOwners } from '../../api/owners'
import { DOG_BREEDS } from '../../utils/breeds'

const SIZES = ['XS', 'S', 'M', 'L', 'XL']

export default function DogsPage() {
  const [dogs, setDogs]       = useState([])
  const [loading, setLoading] = useState(true)
  const [q, setQ]             = useState('')
  const [selected, setSelected] = useState(null) // full dog object
  const [editing, setEditing]   = useState(false)
  const [form, setForm]         = useState({})
  const [creating, setCreating] = useState(false)
  const [owners, setOwners]     = useState([])
  const [vaccForm, setVaccForm] = useState(null)
  const [saving, setSaving]     = useState(false)
  const [error, setError]       = useState('')

  async function load() {
    setLoading(true)
    try { setDogs(await listDogs(q ? { q } : {})) } catch {}
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [q])

  async function openDetail(dog) {
    const d = await getDog(dog.dog_id)
    setSelected(d)
    setForm({ name: d.name, breed: d.breed || '', size_class: d.size_class, weight_lbs: d.weight_lbs || '', medical_notes: d.medical_notes || '' })
  }

  async function startCreate() {
    const os = await listOwners({})
    setOwners(os)
    setForm({ name: '', breed: '', size_class: 'M', weight_lbs: '', medical_notes: '', owner_id: os[0]?.owner_id || '' })
    setCreating(true)
  }

  async function handleSave() {
    setSaving(true); setError('')
    try {
      const payload = { ...form, weight_lbs: form.weight_lbs ? parseFloat(form.weight_lbs) : null }
      if (creating) {
        await createDog(payload)
        setCreating(false)
      } else {
        await updateDog(selected.dog_id, payload)
        setEditing(false)
        setSelected(null)
      }
      load()
    } catch (e) { setError(e.response?.data?.detail || 'Save failed') }
    finally { setSaving(false) }
  }

  async function handleArchive() {
    if (!confirm(`Archive ${selected.name}?`)) return
    await archiveDog(selected.dog_id)
    setSelected(null); load()
  }

  async function handleAddVacc() {
    if (!vaccForm?.vaccine_name || !vaccForm?.administered_date) { setError('Name and date required'); return }
    setSaving(true)
    try {
      await addVaccination(selected.dog_id, vaccForm)
      setVaccForm(null)
      const d = await getDog(selected.dog_id)
      setSelected(d)
    } catch (e) { setError(e.response?.data?.detail || 'Failed') }
    finally { setSaving(false) }
  }

  function setF(k, v) { setForm(f => ({ ...f, [k]: v })) }

  return (
    <Layout>
      <div className="page-content">
        <div className="page-header">
          <h1>Dogs</h1>
          <div style={{ display: 'flex', gap: 10 }}>
            <input placeholder="Search…" value={q} onChange={e => setQ(e.target.value)}
              style={{ padding: '6px 10px', border: '1px solid var(--border)', borderRadius: 4, fontSize: 13, width: 200 }} />
            <button className="btn btn-primary btn-sm" onClick={startCreate}>+ Add Dog</button>
          </div>
        </div>

        <div className="card">
          {loading ? <div className="spinner" /> : (
            <table className="data-table">
              <thead><tr><th>Name</th><th>Breed</th><th>Size</th><th>Weight</th><th>Owner ID</th></tr></thead>
              <tbody>
                {dogs.length === 0 ? <tr><td colSpan={5} className="empty-state">No dogs found</td></tr>
                : dogs.map(d => (
                  <tr key={d.dog_id} onClick={() => openDetail(d)}>
                    <td><strong>{d.name}</strong></td>
                    <td>{d.breed || '—'}</td>
                    <td>{d.size_class}</td>
                    <td>{d.weight_lbs ? `${d.weight_lbs} lbs` : '—'}</td>
                    <td style={{ fontSize: 11, color: 'var(--text-sub)' }}>{d.owner_id?.slice(0,8)}…</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Detail / Edit modal */}
        {selected && !editing && (
          <Modal title={selected.name} size="md" onClose={() => setSelected(null)}
            footer={<>
              <button className="btn btn-danger btn-sm" onClick={handleArchive}>Archive</button>
              <button className="btn btn-secondary" onClick={() => setSelected(null)}>Close</button>
              <button className="btn btn-primary" onClick={() => setEditing(true)}>Edit</button>
            </>}
          >
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 24px', fontSize: 13, marginBottom: 16 }}>
              <div><strong>Breed:</strong> {selected.breed || '—'}</div>
              <div><strong>Size:</strong> {selected.size_class}</div>
              <div><strong>Weight:</strong> {selected.weight_lbs ? `${selected.weight_lbs} lbs` : '—'}</div>
              <div><strong>Owner:</strong> {selected.owner_id}</div>
            </div>
            {selected.medical_notes && (
              <div style={{ fontSize: 13, marginBottom: 16 }}>
                <strong>Medical Notes:</strong> {selected.medical_notes}
              </div>
            )}
            <div className="divider" />
            <p style={{ fontWeight: 600, marginBottom: 10, fontSize: 13 }}>Vaccination Records</p>
            {selected.vaccination_records?.length ? (
              <table className="data-table" style={{ marginBottom: 12 }}>
                <thead><tr><th>Vaccine</th><th>Date</th><th>Expires</th><th>Vet</th></tr></thead>
                <tbody>
                  {selected.vaccination_records.map((v, i) => (
                    <tr key={i}>
                      <td>{v.vaccine_name}</td>
                      <td>{v.administered_date}</td>
                      <td>{v.expiry_date || '—'}</td>
                      <td>{v.administered_by || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : <p style={{ fontSize: 13, color: 'var(--text-sub)', marginBottom: 10 }}>No vaccination records.</p>}
            {vaccForm ? (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                <div className="form-field"><label>Vaccine*</label><input value={vaccForm.vaccine_name || ''} onChange={e => setVaccForm(f => ({...f, vaccine_name: e.target.value}))} /></div>
                <div className="form-field"><label>Date*</label><input type="date" value={vaccForm.administered_date || ''} onChange={e => setVaccForm(f => ({...f, administered_date: e.target.value}))} /></div>
                <div className="form-field"><label>Expires</label><input type="date" value={vaccForm.expiry_date || ''} onChange={e => setVaccForm(f => ({...f, expiry_date: e.target.value}))} /></div>
                <div className="form-field"><label>Vet/By</label><input value={vaccForm.administered_by || ''} onChange={e => setVaccForm(f => ({...f, administered_by: e.target.value}))} /></div>
                <button className="btn btn-secondary btn-sm" onClick={() => { setVaccForm(null); setError('') }}>Cancel</button>
                <button className="btn btn-primary btn-sm" onClick={handleAddVacc} disabled={saving}>Save</button>
              </div>
            ) : (
              <button className="btn btn-secondary btn-sm" onClick={() => setVaccForm({})}>+ Add Vaccination</button>
            )}
            {error && <p className="error-text" style={{ marginTop: 8 }}>{error}</p>}
          </Modal>
        )}

        {/* Edit form */}
        {selected && editing && (
          <Modal title={`Edit — ${selected.name}`} size="sm" onClose={() => { setEditing(false); setError('') }}
            footer={<>
              <button className="btn btn-secondary" onClick={() => setEditing(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleSave} disabled={saving}>Save</button>
            </>}
          >
            <DogForm form={form} setF={setF} sizes={SIZES} />
            {error && <p className="error-text">{error}</p>}
          </Modal>
        )}

        {/* Create modal */}
        {creating && (
          <Modal title="Add Dog" size="sm" onClose={() => { setCreating(false); setError('') }}
            footer={<>
              <button className="btn btn-secondary" onClick={() => setCreating(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleSave} disabled={saving}>Create</button>
            </>}
          >
            <div className="form-field">
              <label>Owner*</label>
              <select value={form.owner_id} onChange={e => setF('owner_id', e.target.value)}>
                {owners.map(o => <option key={o.owner_id} value={o.owner_id}>{o.last_name}, {o.first_name}</option>)}
              </select>
            </div>
            <DogForm form={form} setF={setF} sizes={SIZES} />
            {error && <p className="error-text">{error}</p>}
          </Modal>
        )}
      </div>
    </Layout>
  )
}

function DogForm({ form, setF, sizes }) {
  return <>
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
      <div className="form-field"><label>Name*</label><input value={form.name || ''} onChange={e => setF('name', e.target.value)} /></div>
      <div className="form-field">
        <label>Breed*</label>
        <input list="dog-breeds-list" value={form.breed || ''} onChange={e => setF('breed', e.target.value)} placeholder="Search breeds…" />
        <datalist id="dog-breeds-list">{DOG_BREEDS.map(b => <option key={b} value={b} />)}</datalist>
      </div>
      <div className="form-field">
        <label>Size*</label>
        <select value={form.size_class || 'M'} onChange={e => setF('size_class', e.target.value)}>
          {sizes.map(s => <option key={s}>{s}</option>)}
        </select>
      </div>
      <div className="form-field"><label>Weight (lbs)</label><input type="number" value={form.weight_lbs || ''} onChange={e => setF('weight_lbs', e.target.value)} /></div>
    </div>
    <div className="form-field"><label>Medical Notes</label><textarea value={form.medical_notes || ''} onChange={e => setF('medical_notes', e.target.value)} /></div>
  </>
}
