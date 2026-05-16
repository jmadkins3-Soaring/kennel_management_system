import { useState, useEffect } from 'react'
import Layout from '../../components/Layout'
import Modal from '../../components/Modal'
import { listUsers, createUser, updateUser, resetPassword } from '../../api/users'

export default function UsersPage() {
  const [users, setUsers]     = useState([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)
  const [creating, setCreating] = useState(false)
  const [resetting, setResetting] = useState(null) // user object
  const [form, setForm]       = useState({})
  const [pwForm, setPwForm]   = useState({ new_password: '', confirm: '' })
  const [saving, setSaving]   = useState(false)
  const [error, setError]     = useState('')

  async function load() {
    setLoading(true)
    try { setUsers(await listUsers()) } catch {}
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  function setF(k, v) { setForm(f => ({ ...f, [k]: v })) }

  function startCreate() {
    setForm({ username: '', password: '', role: 'staff' })
    setCreating(true)
    setError('')
  }

  function startEdit(u) {
    setForm({ username: u.username, role: u.role, active: u.active })
    setSelected(u)
    setError('')
  }

  async function handleSave() {
    setSaving(true); setError('')
    try {
      if (creating) {
        await createUser(form)
        setCreating(false)
      } else {
        await updateUser(selected.user_id, form)
        setSelected(null)
      }
      load()
    } catch (e) {
      setError(e.response?.data?.detail || 'Save failed')
    } finally { setSaving(false) }
  }

  async function handleResetPassword() {
    if (pwForm.new_password !== pwForm.confirm) {
      setError('Passwords do not match'); return
    }
    setSaving(true); setError('')
    try {
      await resetPassword(resetting.user_id, pwForm.new_password)
      setResetting(null)
      setPwForm({ new_password: '', confirm: '' })
    } catch (e) {
      setError(e.response?.data?.detail || 'Reset failed')
    } finally { setSaving(false) }
  }

  return (
    <Layout>
      <div className="page-content">
        <div className="page-header">
          <h1>User Management</h1>
          <button className="btn btn-primary btn-sm" onClick={startCreate}>+ Add User</button>
        </div>

        <div className="card">
          {loading ? <div className="spinner" /> : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Username</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.length === 0
                  ? <tr><td colSpan={5} className="empty-state">No users found</td></tr>
                  : users.map(u => (
                    <tr key={u.user_id}>
                      <td><strong>{u.username}</strong></td>
                      <td>
                        <span className={`badge ${u.role === 'admin' ? 'badge-hold' : 'badge-free'}`}>
                          {u.role}
                        </span>
                      </td>
                      <td>
                        <span className={`badge ${u.active ? 'badge-free' : 'badge-used'}`}>
                          {u.active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td style={{ color: 'var(--text-sub)', fontSize: 12 }}>
                        {new Date(u.created_at).toLocaleDateString()}
                      </td>
                      <td>
                        <button className="btn btn-secondary btn-sm" onClick={() => startEdit(u)}
                          style={{ marginRight: 6 }}>Edit</button>
                        <button className="btn btn-warning btn-sm" onClick={() => { setResetting(u); setError('') }}>
                          Reset PW
                        </button>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Create / Edit modal */}
        {(creating || selected) && (
          <Modal
            title={creating ? 'Add User' : `Edit — ${selected?.username}`}
            size="sm"
            onClose={() => { setCreating(false); setSelected(null); setError('') }}
            footer={<>
              <button className="btn btn-secondary" onClick={() => { setCreating(false); setSelected(null) }}>
                Cancel
              </button>
              <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
                {creating ? 'Create' : 'Save'}
              </button>
            </>}
          >
            <div className="form-field">
              <label>Username</label>
              <input value={form.username || ''} onChange={e => setF('username', e.target.value)} />
            </div>
            {creating && (
              <div className="form-field">
                <label>Password</label>
                <input type="password" value={form.password || ''} onChange={e => setF('password', e.target.value)} />
              </div>
            )}
            <div className="form-field">
              <label>Role</label>
              <select value={form.role || 'staff'} onChange={e => setF('role', e.target.value)}>
                <option value="staff">Staff</option>
                <option value="admin">Admin</option>
              </select>
            </div>
            {!creating && (
              <div className="form-field">
                <label>Active</label>
                <select value={form.active ? 'true' : 'false'} onChange={e => setF('active', e.target.value === 'true')}>
                  <option value="true">Active</option>
                  <option value="false">Inactive</option>
                </select>
              </div>
            )}
            {error && <p className="error-text">{error}</p>}
          </Modal>
        )}

        {/* Reset password modal */}
        {resetting && (
          <Modal
            title={`Reset Password — ${resetting.username}`}
            size="sm"
            onClose={() => { setResetting(null); setPwForm({ new_password: '', confirm: '' }); setError('') }}
            footer={<>
              <button className="btn btn-secondary" onClick={() => setResetting(null)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleResetPassword} disabled={saving}>
                Reset Password
              </button>
            </>}
          >
            <div className="form-field">
              <label>New Password</label>
              <input type="password" value={pwForm.new_password}
                onChange={e => setPwForm(f => ({ ...f, new_password: e.target.value }))} />
            </div>
            <div className="form-field">
              <label>Confirm Password</label>
              <input type="password" value={pwForm.confirm}
                onChange={e => setPwForm(f => ({ ...f, confirm: e.target.value }))} />
            </div>
            {error && <p className="error-text">{error}</p>}
          </Modal>
        )}
      </div>
    </Layout>
  )
}
