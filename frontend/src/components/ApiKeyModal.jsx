import { useState, useEffect } from 'react'
import { mcpApi } from '../api/auth'
import './ApiKeyModal.css'

export default function ApiKeyModal({ onClose }) {
  const [keys, setKeys] = useState([])
  const [loading, setLoading] = useState(true)
  const [newKey, setNewKey] = useState(null)
  const [newKeyName, setNewKeyName] = useState('')
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    fetchKeys()
  }, [])

  const fetchKeys = async () => {
    try {
      const res = await mcpApi.listApiKeys()
      setKeys(res.data)
    } catch {
      setError('Failed to load API keys')
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (e) => {
    e.preventDefault()
    if (!newKeyName.trim()) return
    setCreating(true)
    setError(null)
    try {
      const res = await mcpApi.createApiKey(newKeyName.trim())
      setNewKey(res.data)
      setNewKeyName('')
      fetchKeys()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create API key')
    } finally {
      setCreating(false)
    }
  }

  const handleDelete = async (keyId, keyName) => {
    if (!confirm(`Revoke "${keyName}"? Any integrations using it will stop working.`)) return
    try {
      await mcpApi.deleteApiKey(keyId)
      if (newKey?.id === keyId) setNewKey(null)
      fetchKeys()
    } catch {
      setError('Failed to revoke key')
    }
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(newKey.key)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const mcpUrl = `${window.location.origin}/mcp`

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="apikey-modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>MCP API Keys</h2>
          <button className="modal-close-btn" onClick={onClose}>×</button>
        </div>

        <div className="apikey-modal-body">
          <p className="apikey-description">
            Use an API key to connect Hermes to external tools and MCP-compatible agents like Claude Desktop.
            Keys are shown only once — store them safely.
          </p>

          {error && <div className="apikey-error">{error}</div>}

          {newKey && (
            <div className="apikey-reveal">
              <div className="apikey-reveal-warning">⚠ Copy this key now — it won't be shown again</div>
              <div className="apikey-reveal-row">
                <code className="apikey-value">{newKey.key}</code>
                <button className="apikey-copy-btn" onClick={handleCopy}>
                  {copied ? '✓ Copied' : 'Copy'}
                </button>
              </div>
            </div>
          )}

          <form className="apikey-create-form" onSubmit={handleCreate}>
            <input
              type="text"
              placeholder="Key name (e.g. Claude Desktop)"
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              className="apikey-name-input"
              maxLength={255}
            />
            <button
              type="submit"
              disabled={creating || !newKeyName.trim()}
              className="apikey-create-btn"
            >
              {creating ? '…' : '+ Create Key'}
            </button>
          </form>

          <div className="apikey-list">
            {loading ? (
              <p className="apikey-empty">Loading…</p>
            ) : keys.length === 0 ? (
              <p className="apikey-empty">No API keys yet. Create one above.</p>
            ) : (
              keys.map((key) => (
                <div key={key.id} className="apikey-row">
                  <div className="apikey-row-info">
                    <span className="apikey-row-name">{key.name}</span>
                    <span className="apikey-row-prefix">{key.key_prefix}…</span>
                    <span className="apikey-row-meta">
                      Created {new Date(key.created_at).toLocaleDateString()}
                      {key.last_used && ` · Last used ${new Date(key.last_used).toLocaleDateString()}`}
                    </span>
                  </div>
                  <button
                    className="apikey-revoke-btn"
                    onClick={() => handleDelete(key.id, key.name)}
                  >
                    Revoke
                  </button>
                </div>
              ))
            )}
          </div>

          <div className="apikey-usage">
            <p>Authenticate with: <code>Authorization: Bearer hrm_…</code></p>
            <p>MCP endpoint: <code>{mcpUrl}</code></p>
          </div>
        </div>
      </div>
    </div>
  )
}
