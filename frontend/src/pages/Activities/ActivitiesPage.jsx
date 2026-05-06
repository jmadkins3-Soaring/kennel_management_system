import { useState, useEffect } from 'react'
import Layout from '../../components/Layout'
import Modal from '../../components/Modal'
import { listActivityTypes, createActivityType, updateActivityType } from '../../api/activityTypes'

export default function ActivitiesPage() {
  const [types, setTypes]     = useState([])
  const [loading, setLoading] = useState(true)
  const [modal, setModal]     = useState(null) // 'create' | {editing: obj}
  const [form, setForm]       = useState({ name: '', qualifies_for_pacfa_exception: false })
  const [saving, setSaving]   = useState(false)
  const [error, setError]     = useState('')

  async function load() {
    setLoading(true)
    try { setTypes(await listActivityTypes()) } catch {}
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  function openCreate() {
    setForm({ name: '', qualifies_for_pacfa_exception: false })
    setModal('create')
    setError('')
  }

  function openEdit(t) {
    setForm({ name: t.name, qualifies_for_pacfa_exception: t.qualifies_for_pacfa_exception })
    setModal({ editing: t })
    setError('')
  }

  async function handleSave() {
    if (!form.name) { setError('Name required'); return }
    setSaving(true); setError('')
    try {
      if (modal === 'create') await createActivityType(form)
      else await updateActivityType(modal.editing.activity_type_id, form)
      setModal(null); load()
    } catch (e) { setError(e.response?.data?.detail || 'Save failed') }
    finally { setSaving(false) }
  }

  async function handleDeactivate(t) {
    await updateActivityType(t.activity_type_id, { active: false })
    load()
  }

  async function handleActivate(t) {
    await updateActivityType(t.activity_type_id, { active: true })
    load()
  }

  return (
    <Layout>
      <div className="page-content">
        <div className="page-header">
          <h1>Activity Types</h1>
          <button className="btn btn-primary btn-sm" onClick={openCreate}>+ Add Type</button>
        </div>

        <div className="card">
          {loading ? <div className="spinner" /> : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>PACFA Exception</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {types.length === 0 ? <tr><td colSpan={4} className="empty-state">No activity types</td></tr>
                : types.map(t => (
                  <tr key={t.activity_type_id}>
                    <td><strong>{t.name}</strong></td>
                    <td>{t.qualifies_for_pacfa_exception ? '✓ Yes' : '—'}</td>
                    <td>
                      {t.active !== false
                        ? <span className="badge badge-free">Active</span>
                        : <span className="badge" style={{ background: '#f5f5f5', color: 'var(--text-sub)', border: '1px solid var(--border)' }}>Inactive</span>
                      }
                    </td>
                    <td style={{ display: 'flex', gap: 8 }}>
                      <button className="btn btn-secondary btn-sm" onClick={() => openEdit(t)}>Edit</button>
                      {t.active !== false
                        ? <button className="btn btn-secondary btn-sm" onClick={() => handleDeactivate(t)}>Deactivate</button>
                        : <button className="btn btn-secondary btn-sm" onClick={() => handleActivate(t)}>Activate</button>
                      }
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {modal && (
          <Modal
            title={modal === 'create' ? 'Add Activity Type' : `Edit — ${modal.editing?.name}`}
            size="sm"
            onClose={() => { setModal(null); setError('') }}
            footer={<>
              <button className="btn btn-secondary" onClick={() => setModal(null)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
                {modal === 'create' ? 'Create' : 'Save'}
              </button>
            </>}
          >
            <div className="form-field">
              <label>Name*</label>
              <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
            </div>
            <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 13, cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={form.qualifies_for_pacfa_exception}
                onChange={e => setForm(f => ({ ...f, qualifies_for_pacfa_exception: e.target.checked }))}
              />
              Qualifies for PACFA 181-day exception
            </label>
            {error && <p className="error-text" style={{ marginTop: 10 }}>{error}</p>}
          </Modal>
        )}
      </div>
    </Layout>
  )
}
