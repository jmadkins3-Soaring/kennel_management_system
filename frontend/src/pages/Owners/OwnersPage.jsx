import { useState, useEffect } from 'react'
import Layout from '../../components/Layout'
import Modal from '../../components/Modal'
import { listOwners, getOwner, createOwner, updateOwner, archiveOwner, getOwnerDogs } from '../../api/owners'

export default function OwnersPage() {
  const [owners, setOwners]   = useState([])
  const [loading, setLoading] = useState(true)
  const [q, setQ]             = useState('')
  const [selected, setSelected] = useState(null)
  const [dogs, setDogs]       = useState([])
  const [editing, setEditing] = useState(false)
  const [creating, setCreating] = useState(false)
  const [form, setForm]       = useState({})
  const [saving, setSaving]   = useState(false)
  const [error, setError]     = useState('')

  async function load() {
    setLoading(true)
    try { setOwners(await listOwners(q ? { q } : {})) } catch {}
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [q])

  async function openDetail(owner) {
    const o = await getOwner(owner.owner_id)
    setSelected(o)
    setForm({ first_name: o.first_name, last_name: o.last_name, phone: o.phone || '', email: o.email || '', emergency_contact: o.emergency_contact || '', notes: o.notes || '' })
    const ds = await getOwnerDogs(o.owner_id)
    setDogs(ds)
  }

  function startCreate() {
    setForm({ first_name: '', last_name: '', phone: '', email: '', emergency_contact: '', notes: '' })
    setCreating(true)
  }

  function setF(k, v) { setForm(f => ({ ...f, [k]: v })) }

  async function handleSave() {
    setSaving(true); setError('')
    try {
      if (creating) { await createOwner(form); setCreating(false) }
      else { await updateOwner(selected.owner_id, form); setEditing(false); setSelected(null) }
      load()
    } catch (e) { setError(e.response?.data?.detail || 'Save failed') }
    finally { setSaving(false) }
  }

  async function handleArchive() {
    if (!confirm(`Archive ${selected.first_name} ${selected.last_name}?`)) return
    await archiveOwner(selected.owner_id)
    setSelected(null); load()
  }

  return (
    <Layout>
      <div className="page-content">
        <div className="page-header">
          <h1>Owners</h1>
          <div style={{ display: 'flex', gap: 10 }}>
            <input placeholder="Search…" value={q} onChange={e => setQ(e.target.value)}
              style={{ padding: '6px 10px', border: '1px solid var(--border)', borderRadius: 4, fontSize: 13, width: 200 }} />
            <button className="btn btn-primary btn-sm" onClick={startCreate}>+ Add Owner</button>
          </div>
        </div>

        <div className="card">
          {loading ? <div className="spinner" /> : (
            <table className="data-table">
              <thead><tr><th>Name</th><th>Phone</th><th>Email</th><th>Emergency Contact</th></tr></thead>
              <tbody>
                {owners.length === 0 ? <tr><td colSpan={4} className="empty-state">No owners found</td></tr>
                : owners.map(o => (
                  <tr key={o.owner_id} onClick={() => openDetail(o)}>
                    <td><strong>{o.last_name}, {o.first_name}</strong></td>
                    <td>{o.phone || '—'}</td>
                    <td>{o.email || '—'}</td>
                    <td>{o.emergency_contact || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {selected && !editing && (
          <Modal title={`${selected.first_name} ${selected.last_name}`} size="md" onClose={() => setSelected(null)}
            footer={<>
              <button className="btn btn-danger btn-sm" onClick={handleArchive}>Archive</button>
              <button className="btn btn-secondary" onClick={() => setSelected(null)}>Close</button>
              <button className="btn btn-primary" onClick={() => setEditing(true)}>Edit</button>
            </>}
          >
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 24px', fontSize: 13, marginBottom: 16 }}>
              <div><strong>Phone:</strong> {selected.phone || '—'}</div>
              <div><strong>Email:</strong> {selected.email || '—'}</div>
              <div><strong>Emergency:</strong> {selected.emergency_contact || '—'}</div>
            </div>
            {selected.notes && <div style={{ fontSize: 13, marginBottom: 12 }}><strong>Notes:</strong> {selected.notes}</div>}
            <div className="divider" />
            <p style={{ fontWeight: 600, fontSize: 13, marginBottom: 8 }}>Dogs ({dogs.length})</p>
            {dogs.length ? dogs.map(d => (
              <div key={d.dog_id} style={{ fontSize: 13, padding: '4px 0', borderBottom: '1px solid var(--border)' }}>
                <strong>{d.name}</strong> · {d.breed || '?'} · {d.size_class}
              </div>
            )) : <p style={{ fontSize: 13, color: 'var(--text-sub)' }}>No dogs on file.</p>}
          </Modal>
        )}

        {(editing || creating) && (
          <Modal title={creating ? 'Add Owner' : `Edit — ${selected?.first_name}`} size="sm"
            onClose={() => { setEditing(false); setCreating(false); setError('') }}
            footer={<>
              <button className="btn btn-secondary" onClick={() => { setEditing(false); setCreating(false) }}>Cancel</button>
              <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
                {creating ? 'Create' : 'Save'}
              </button>
            </>}
          >
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="form-field"><label>First Name*</label><input value={form.first_name || ''} onChange={e => setF('first_name', e.target.value)} /></div>
              <div className="form-field"><label>Last Name*</label><input value={form.last_name || ''} onChange={e => setF('last_name', e.target.value)} /></div>
              <div className="form-field"><label>Phone</label><input value={form.phone || ''} onChange={e => setF('phone', e.target.value)} /></div>
              <div className="form-field"><label>Email</label><input type="email" value={form.email || ''} onChange={e => setF('email', e.target.value)} /></div>
            </div>
            <div className="form-field"><label>Emergency Contact</label><input value={form.emergency_contact || ''} onChange={e => setF('emergency_contact', e.target.value)} /></div>
            <div className="form-field"><label>Notes</label><textarea value={form.notes || ''} onChange={e => setF('notes', e.target.value)} /></div>
            {error && <p className="error-text">{error}</p>}
          </Modal>
        )}
      </div>
    </Layout>
  )
}
