import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { authApi } from '../api/auth'
import { useAuth } from '../contexts/AuthContext'
import './AdminPanel.css'

function AdminPanel() {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingUser, setEditingUser] = useState(null)
  const { user: currentUser } = useAuth()

  useEffect(() => {
    fetchUsers()
  }, [])

  const fetchUsers = async () => {
    try {
      setLoading(true)
      const response = await authApi.listUsers()
      setUsers(response.data.users)
      setError(null)
    } catch (err) {
      setError('Failed to load users')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleDeleteUser = async (userId) => {
    if (!confirm('Are you sure you want to delete this user?')) return

    try {
      await authApi.deleteUser(userId)
      fetchUsers()
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to delete user')
    }
  }

  return (
    <div className="admin-panel">
      <header className="admin-header">
        <div className="admin-header-left">
          <Link to="/" className="back-link">Back to Dashboard</Link>
          <h1>User Administration</h1>
        </div>
        <button className="btn-create" onClick={() => setShowCreateModal(true)}>
          + Create User
        </button>
      </header>

      {error && <div className="admin-error">{error}</div>}

      {loading ? (
        <div className="admin-loading">Loading users...</div>
      ) : (
        <div className="users-table-container">
          <table className="users-table">
            <thead>
              <tr>
                <th>Email</th>
                <th>Role</th>
                <th>Status</th>
                <th>Last Login</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map(user => (
                <tr key={user.id} className={!user.is_active ? 'inactive' : ''}>
                  <td>
                    {user.email}
                    {user.id === currentUser?.id && (
                      <span className="current-user-badge">You</span>
                    )}
                  </td>
                  <td>
                    <span className={`role-badge ${user.role}`}>
                      {user.role === 'platform_admin' ? 'Admin' : 'User'}
                    </span>
                  </td>
                  <td>
                    <span className={`status-badge ${user.is_active ? 'active' : 'inactive'}`}>
                      {user.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td>
                    {user.last_login
                      ? new Date(user.last_login).toLocaleDateString()
                      : 'Never'}
                  </td>
                  <td>{new Date(user.created_at).toLocaleDateString()}</td>
                  <td>
                    <div className="action-buttons">
                      <button
                        className="btn-edit"
                        onClick={() => setEditingUser(user)}
                      >
                        Edit
                      </button>
                      <button
                        className="btn-delete"
                        onClick={() => handleDeleteUser(user.id)}
                        disabled={user.id === currentUser?.id}
                        title={user.id === currentUser?.id ? 'Cannot delete yourself' : ''}
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showCreateModal && (
        <UserModal
          onClose={() => setShowCreateModal(false)}
          onSave={() => {
            setShowCreateModal(false)
            fetchUsers()
          }}
        />
      )}

      {editingUser && (
        <UserModal
          user={editingUser}
          onClose={() => setEditingUser(null)}
          onSave={() => {
            setEditingUser(null)
            fetchUsers()
          }}
        />
      )}
    </div>
  )
}

function UserModal({ user, onClose, onSave }) {
  const [email, setEmail] = useState(user?.email || '')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState(user?.role || 'user')
  const [isActive, setIsActive] = useState(user?.is_active ?? true)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  const isEditing = !!user

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setSaving(true)

    try {
      if (isEditing) {
        const updateData = { email, role, is_active: isActive }
        if (password) updateData.password = password
        await authApi.updateUser(user.id, updateData)
      } else {
        await authApi.createUser({ email, password, role })
      }
      onSave()
    } catch (err) {
      setError(err.response?.data?.detail || 'Operation failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{isEditing ? 'Edit User' : 'Create User'}</h2>
          <button className="modal-close" onClick={onClose}>x</button>
        </div>

        <form onSubmit={handleSubmit}>
          {error && <div className="modal-error">{error}</div>}

          <div className="form-group">
            <label>Email</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              disabled={saving}
            />
          </div>

          <div className="form-group">
            <label>{isEditing ? 'New Password (leave blank to keep)' : 'Password'}</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required={!isEditing}
              minLength={8}
              placeholder={isEditing ? 'Leave blank to keep current' : 'Min 8 characters'}
              disabled={saving}
            />
          </div>

          <div className="form-group">
            <label>Role</label>
            <select value={role} onChange={e => setRole(e.target.value)} disabled={saving}>
              <option value="user">User</option>
              <option value="platform_admin">Admin</option>
            </select>
          </div>

          {isEditing && (
            <div className="form-group checkbox">
              <label>
                <input
                  type="checkbox"
                  checked={isActive}
                  onChange={e => setIsActive(e.target.checked)}
                  disabled={saving}
                />
                Active
              </label>
            </div>
          )}

          <div className="modal-actions">
            <button type="button" className="btn-cancel" onClick={onClose} disabled={saving}>
              Cancel
            </button>
            <button type="submit" className="btn-save" disabled={saving}>
              {saving ? 'Saving...' : (isEditing ? 'Update' : 'Create')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default AdminPanel
