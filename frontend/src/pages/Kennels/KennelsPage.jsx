import { useState, useEffect } from 'react'
import Layout from '../../components/Layout'
import Modal from '../../components/Modal'
import { listKennels, getKennel, updateKennel, addHold, liftHold, getKennelIssues } from '../../api/kennels'
import { createIssue, resolveIssue } from '../../api/issues'
import { useAuth } from '../../contexts/AuthContext'
import { format } from 'date-fns'

const ISSUE_TYPES = ['Maintenance', 'Cleaning', 'Safety', 'Equipment', 'Other']

export default function KennelsPage() {
  const { user } = useAuth()
  const [kennels, setKennels]   = useState([])
  const [loading, setLoading]   = useState(true)
  const [selected, setSelected] = useState(null)
  const [issues, setIssues]     = useState([])
  const [holdForm, setHoldForm] = useState(null)
  const [issueForm, setIssueForm] = useState(null)
  const [saving, setSaving]     = useState(false)
  const [error, setError]       = useState('')

  async function load() {
    setLoading(true)
    try { setKennels(await listKennels()) } catch {}
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  async function openDetail(k) {
    const kennel = await getKennel(k.kennel_id)
    setSelected(kennel)
    const iss = await getKennelIssues(k.kennel_id)
    setIssues(iss)
  }

  async function handleAddHold() {
    if (!holdForm?.start_date || !holdForm?.start_phase || !holdForm?.end_date || !holdForm?.end_phase) {
      setError('All hold fields required'); return
    }
    setSaving(true); setError('')
    try {
      await addHold(selected.kennel_id, { ...holdForm, reason: holdForm.reason || '', created_by: user?.username })
      setHoldForm(null)
      openDetail(selected)
    } catch (e) { setError(e.response?.data?.detail || 'Failed') }
    finally { setSaving(false) }
  }

  async function handleLiftHold(holdId) {
    await liftHold(selected.kennel_id, holdId)
    openDetail(selected)
  }

  async function handleAddIssue() {
    if (!issueForm?.issue_type || !issueForm?.description) { setError('Type and description required'); return }
    setSaving(true); setError('')
    try {
      await createIssue({ kennel_id: selected.kennel_id, ...issueForm, reported_by: user?.username })
      setIssueForm(null)
      const iss = await getKennelIssues(selected.kennel_id)
      setIssues(iss)
    } catch (e) { setError(e.response?.data?.detail || 'Failed') }
    finally { setSaving(false) }
  }

  async function handleResolveIssue(issueId) {
    await resolveIssue(issueId, { resolution_notes: '', resolved_by: user?.username })
    const iss = await getKennelIssues(selected.kennel_id)
    setIssues(iss)
  }

  function statusBadge(status) {
    const cls = (status || 'Free').toLowerCase()
    return <span className={`badge badge-${cls}`}>{status || 'Free'}</span>
  }

  return (
    <Layout>
      <div className="page-content">
        <div className="page-header"><h1>Kennels</h1></div>

        <div className="card">
          {loading ? <div className="spinner" /> : (
            <table className="data-table">
              <thead><tr><th>Number</th><th>Type</th><th>Max Size</th><th>Sqft</th><th>Status</th><th>Features</th></tr></thead>
              <tbody>
                {kennels.map(k => (
                  <tr key={k.kennel_id} onClick={() => openDetail(k)}>
                    <td><strong>{k.kennel_number}</strong></td>
                    <td>{k.kennel_type}</td>
                    <td>{k.max_size_class}</td>
                    <td>{k.sqft}</td>
                    <td>{statusBadge(k.current_status)}</td>
                    <td style={{ fontSize: 12, color: 'var(--text-sub)' }}>{k.features || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {selected && (
          <Modal title={`Kennel ${selected.kennel_number}`} size="lg" onClose={() => { setSelected(null); setError('') }}
            footer={<button className="btn btn-secondary" onClick={() => setSelected(null)}>Close</button>}
          >
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px 24px', fontSize: 13, marginBottom: 16 }}>
              <div><strong>Type:</strong> {selected.kennel_type}</div>
              <div><strong>Max Size:</strong> {selected.max_size_class}</div>
              <div><strong>Sqft:</strong> {selected.sqft}</div>
              {selected.features && <div style={{ gridColumn: 'span 3' }}><strong>Features:</strong> {selected.features}</div>}
            </div>

            {/* Holds */}
            <div className="divider" />
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
              <p style={{ fontWeight: 600, fontSize: 13 }}>Manual Holds</p>
              <button className="btn btn-secondary btn-sm" onClick={() => setHoldForm({})}>+ Add Hold</button>
            </div>
            {selected.active_holds?.length ? selected.active_holds.map(h => (
              <div key={h.hold_id} style={{ fontSize: 13, padding: '6px 0', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between' }}>
                <span>{h.start_date} {h.start_phase} → {h.end_date} {h.end_phase} — {h.reason || 'No reason'}</span>
                <button className="btn btn-secondary btn-sm" onClick={() => handleLiftHold(h.hold_id)}>Lift</button>
              </div>
            )) : <p style={{ fontSize: 13, color: 'var(--text-sub)', marginBottom: 12 }}>No active holds.</p>}

            {holdForm && (
              <div style={{ background: '#f5f5f5', borderRadius: 4, padding: 12, marginBottom: 12 }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 10 }}>
                  <div className="form-field"><label>Start Date</label><input type="date" value={holdForm.start_date || ''} onChange={e => setHoldForm(f => ({...f, start_date: e.target.value}))} /></div>
                  <div className="form-field"><label>Start Phase</label>
                    <select value={holdForm.start_phase || ''} onChange={e => setHoldForm(f => ({...f, start_phase: e.target.value}))}>
                      <option value="">—</option>
                      {['Morning','Afternoon','Evening','Night'].map(p => <option key={p}>{p}</option>)}
                    </select>
                  </div>
                  <div className="form-field"><label>End Date</label><input type="date" value={holdForm.end_date || ''} onChange={e => setHoldForm(f => ({...f, end_date: e.target.value}))} /></div>
                  <div className="form-field"><label>End Phase</label>
                    <select value={holdForm.end_phase || ''} onChange={e => setHoldForm(f => ({...f, end_phase: e.target.value}))}>
                      <option value="">—</option>
                      {['Morning','Afternoon','Evening','Night'].map(p => <option key={p}>{p}</option>)}
                    </select>
                  </div>
                </div>
                <div className="form-field"><label>Reason</label><input value={holdForm.reason || ''} onChange={e => setHoldForm(f => ({...f, reason: e.target.value}))} /></div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button className="btn btn-secondary btn-sm" onClick={() => { setHoldForm(null); setError('') }}>Cancel</button>
                  <button className="btn btn-primary btn-sm" onClick={handleAddHold} disabled={saving}>Save Hold</button>
                </div>
              </div>
            )}

            {/* Issues */}
            <div className="divider" />
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
              <p style={{ fontWeight: 600, fontSize: 13 }}>Issue Reports ({issues.length})</p>
              <button className="btn btn-secondary btn-sm" onClick={() => setIssueForm({})}>+ Report Issue</button>
            </div>
            {issues.map(iss => (
              <div key={iss.issue_id} style={{ fontSize: 13, padding: '6px 0', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <strong>{iss.issue_type}</strong> — {iss.description}
                  <div style={{ fontSize: 11, color: 'var(--text-sub)', marginTop: 2 }}>by {iss.reported_by} · {iss.reported_datetime?.slice(0,10)}</div>
                </div>
                {!iss.resolved_datetime && (
                  <button className="btn btn-secondary btn-sm" onClick={() => handleResolveIssue(iss.issue_id)}>Resolve</button>
                )}
              </div>
            ))}
            {issues.length === 0 && <p style={{ fontSize: 13, color: 'var(--text-sub)' }}>No issues.</p>}

            {issueForm && (
              <div style={{ background: '#f5f5f5', borderRadius: 4, padding: 12, marginTop: 10 }}>
                <div className="form-field">
                  <label>Issue Type</label>
                  <select value={issueForm.issue_type || ''} onChange={e => setIssueForm(f => ({...f, issue_type: e.target.value}))}>
                    <option value="">— Select —</option>
                    {ISSUE_TYPES.map(t => <option key={t}>{t}</option>)}
                  </select>
                </div>
                <div className="form-field"><label>Description</label><textarea value={issueForm.description || ''} onChange={e => setIssueForm(f => ({...f, description: e.target.value}))} /></div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button className="btn btn-secondary btn-sm" onClick={() => { setIssueForm(null); setError('') }}>Cancel</button>
                  <button className="btn btn-primary btn-sm" onClick={handleAddIssue} disabled={saving}>Save</button>
                </div>
              </div>
            )}

            {error && <p className="error-text" style={{ marginTop: 8 }}>{error}</p>}
          </Modal>
        )}
      </div>
    </Layout>
  )
}
