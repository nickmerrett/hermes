import React, { useState, useEffect } from 'react'
import { rssApi } from '../api/auth'
import './RSSTokenManager.css'

function RSSTokenManager({ customerId, customerName, onClose }) {
  const [tokens, setTokens] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [newTokenName, setNewTokenName] = useState('')
  const [creating, setCreating] = useState(false)
  const [copiedId, setCopiedId] = useState(null)

  // Smart feed settings state
  const [showSettings, setShowSettings] = useState(false)
  const [settingsLoading, setSettingsLoading] = useState(false)
  const [settingsSaving, setSettingsSaving] = useState(false)
  const [feedSettings, setFeedSettings] = useState(null)
  const [useCustomSettings, setUseCustomSettings] = useState(false)
  const [customSettings, setCustomSettings] = useState({})

  const API_URL = import.meta.env.VITE_API_URL || window.location.origin + '/api'

  useEffect(() => {
    fetchTokens()
  }, [])

  const fetchTokens = async () => {
    try {
      setLoading(true)
      const response = await rssApi.listTokens()
      // Filter to only show tokens for this customer
      const customerTokens = response.data.tokens.filter(t => t.customer_id === customerId)
      setTokens(customerTokens)
      setError(null)
    } catch (err) {
      setError('Failed to load RSS tokens')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const fetchSettings = async () => {
    try {
      setSettingsLoading(true)
      const response = await rssApi.getSettings(customerId)
      setFeedSettings(response.data)
      setUseCustomSettings(response.data.use_custom || false)
      setCustomSettings(response.data.customer_settings || {})
    } catch (err) {
      console.error('Failed to load feed settings:', err)
    } finally {
      setSettingsLoading(false)
    }
  }

  const handleToggleSettings = () => {
    if (!showSettings && !feedSettings) {
      fetchSettings()
    }
    setShowSettings(!showSettings)
  }

  const handleSaveSettings = async () => {
    try {
      setSettingsSaving(true)
      const settingsToSave = {
        use_custom: useCustomSettings,
        ...customSettings
      }
      await rssApi.updateSettings(customerId, settingsToSave)
      await fetchSettings()
      setError(null)
    } catch (err) {
      setError('Failed to save settings')
      console.error(err)
    } finally {
      setSettingsSaving(false)
    }
  }

  const updateCustomSetting = (key, value) => {
    setCustomSettings(prev => ({
      ...prev,
      [key]: value
    }))
  }

  const updateNestedSetting = (parent, key, value) => {
    setCustomSettings(prev => ({
      ...prev,
      [parent]: {
        ...(prev[parent] || {}),
        [key]: value
      }
    }))
  }

  const handleCreateToken = async (e) => {
    e.preventDefault()
    if (!newTokenName.trim()) return

    try {
      setCreating(true)
      await rssApi.createToken(newTokenName.trim(), customerId)
      setNewTokenName('')
      setShowCreateForm(false)
      fetchTokens()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create token')
    } finally {
      setCreating(false)
    }
  }

  const handleDeleteToken = async (tokenId) => {
    if (!confirm('Are you sure you want to revoke this RSS token? Any RSS readers using this token will no longer be able to access the feed.')) return

    try {
      await rssApi.deleteToken(tokenId)
      fetchTokens()
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to revoke token')
    }
  }

  const copyToClipboard = async (text, tokenId) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedId(tokenId)
      setTimeout(() => setCopiedId(null), 2000)
    } catch (err) {
      // Fallback for older browsers
      const textarea = document.createElement('textarea')
      textarea.value = text
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
      setCopiedId(tokenId)
      setTimeout(() => setCopiedId(null), 2000)
    }
  }

  const getRssUrl = (token) => {
    const baseUrl = API_URL.replace('/api', '')
    return `${baseUrl}/api/rss/feed?token=${token}`
  }

  const effectiveValue = (key, defaultVal) => {
    if (useCustomSettings && customSettings[key] !== undefined) {
      return customSettings[key]
    }
    return feedSettings?.effective_settings?.[key] ?? defaultVal
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="rss-modal-content" onClick={e => e.stopPropagation()}>
        <div className="rss-modal-header">
          <div>
            <h2>RSS Feed</h2>
            <p className="customer-label">{customerName}</p>
          </div>
          <button className="modal-close" onClick={onClose}>x</button>
        </div>

        {error && <div className="rss-error">{error}</div>}

        {/* Feed Settings Section */}
        <div className="feed-settings-section">
          <button
            className="btn-toggle-settings"
            onClick={handleToggleSettings}
          >
            {showSettings ? '▼' : '▶'} Feed Settings
          </button>

          {showSettings && (
            <div className="feed-settings-content">
              {settingsLoading ? (
                <div className="settings-loading">Loading settings...</div>
              ) : feedSettings ? (
                <>
                  <div className="setting-row">
                    <label className="setting-toggle">
                      <input
                        type="checkbox"
                        checked={useCustomSettings}
                        onChange={e => setUseCustomSettings(e.target.checked)}
                      />
                      <span>Use custom settings for this customer</span>
                    </label>
                    <p className="setting-hint">
                      {useCustomSettings
                        ? 'Custom settings override global defaults'
                        : 'Using global smart feed settings'}
                    </p>
                  </div>

                  {useCustomSettings && (
                    <div className="custom-settings">
                      <div className="setting-group">
                        <h4>Feed Limits</h4>
                        <div className="setting-row">
                          <label>Max Items</label>
                          <input
                            type="number"
                            min="10"
                            max="200"
                            value={customSettings.max_items ?? feedSettings.defaults.max_items ?? 50}
                            onChange={e => updateCustomSetting('max_items', parseInt(e.target.value))}
                          />
                        </div>
                        <div className="setting-row">
                          <label>Min Priority (0-1)</label>
                          <input
                            type="number"
                            min="0"
                            max="1"
                            step="0.1"
                            value={customSettings.min_priority ?? feedSettings.defaults.min_priority ?? 0.3}
                            onChange={e => updateCustomSetting('min_priority', parseFloat(e.target.value))}
                          />
                        </div>
                      </div>

                      <div className="setting-group">
                        <h4>Recency Boost</h4>
                        <div className="setting-row">
                          <label className="setting-toggle">
                            <input
                              type="checkbox"
                              checked={customSettings.recency_boost?.enabled ?? feedSettings.defaults.recency_boost?.enabled ?? true}
                              onChange={e => updateNestedSetting('recency_boost', 'enabled', e.target.checked)}
                            />
                            <span>Enable recency boost</span>
                          </label>
                        </div>
                        <div className="setting-row">
                          <label>Boost Amount</label>
                          <input
                            type="number"
                            min="0"
                            max="0.5"
                            step="0.05"
                            value={customSettings.recency_boost?.boost_amount ?? feedSettings.defaults.recency_boost?.boost_amount ?? 0.1}
                            onChange={e => updateNestedSetting('recency_boost', 'boost_amount', parseFloat(e.target.value))}
                          />
                        </div>
                        <div className="setting-row">
                          <label>Time Threshold (hours)</label>
                          <input
                            type="number"
                            min="1"
                            max="168"
                            value={customSettings.recency_boost?.time_threshold_hours ?? feedSettings.defaults.recency_boost?.time_threshold_hours ?? 24}
                            onChange={e => updateNestedSetting('recency_boost', 'time_threshold_hours', parseInt(e.target.value))}
                          />
                        </div>
                      </div>

                      <div className="setting-group">
                        <h4>Category Filters</h4>
                        <p className="setting-hint">Enabled categories are always included regardless of priority</p>
                        <div className="category-grid">
                          {Object.entries(feedSettings.defaults.category_preferences || {}).map(([cat, defaultVal]) => (
                            <label key={cat} className="category-toggle">
                              <input
                                type="checkbox"
                                checked={customSettings.category_preferences?.[cat] ?? defaultVal}
                                onChange={e => {
                                  const newCatPrefs = {
                                    ...(customSettings.category_preferences || {}),
                                    [cat]: e.target.checked
                                  }
                                  updateCustomSetting('category_preferences', newCatPrefs)
                                }}
                              />
                              <span>{cat.replace(/_/g, ' ')}</span>
                            </label>
                          ))}
                        </div>
                      </div>

                      <div className="setting-group">
                        <h4>Source Filters</h4>
                        <p className="setting-hint">Enabled sources are always included regardless of priority</p>
                        <div className="category-grid">
                          {Object.entries(feedSettings.defaults.source_preferences || {}).map(([src, defaultVal]) => (
                            <label key={src} className="category-toggle">
                              <input
                                type="checkbox"
                                checked={customSettings.source_preferences?.[src] ?? defaultVal}
                                onChange={e => {
                                  const newSrcPrefs = {
                                    ...(customSettings.source_preferences || {}),
                                    [src]: e.target.checked
                                  }
                                  updateCustomSetting('source_preferences', newSrcPrefs)
                                }}
                              />
                              <span>{src.replace(/_/g, ' ')}</span>
                            </label>
                          ))}
                        </div>
                      </div>

                      <div className="settings-actions">
                        <button
                          className="btn-save-settings"
                          onClick={handleSaveSettings}
                          disabled={settingsSaving}
                        >
                          {settingsSaving ? 'Saving...' : 'Save Settings'}
                        </button>
                      </div>
                    </div>
                  )}

                  {!useCustomSettings && (
                    <div className="global-settings-preview">
                      <p>Current effective settings:</p>
                      <ul>
                        <li>Max items: {feedSettings.effective_settings?.max_items ?? 50}</li>
                        <li>Min priority: {feedSettings.effective_settings?.min_priority ?? 0.3}</li>
                        <li>Recency boost: {feedSettings.effective_settings?.recency_boost?.enabled ? 'Enabled' : 'Disabled'}</li>
                      </ul>
                    </div>
                  )}
                </>
              ) : (
                <div className="settings-error">Failed to load settings</div>
              )}
            </div>
          )}
        </div>

        <div className="rss-divider"></div>

        <h3 className="tokens-header">Feed Tokens</h3>
        <div className="rss-info">
          <p>
            Create tokens to subscribe to this feed in any RSS reader.
          </p>
        </div>

        {loading ? (
          <div className="rss-loading">Loading tokens...</div>
        ) : (
          <>
            {tokens.length === 0 ? (
              <div className="rss-empty">
                <p>No RSS tokens created yet for this customer.</p>
              </div>
            ) : (
              <div className="rss-tokens-list">
                {tokens.map(token => (
                  <div key={token.id} className="rss-token-item">
                    <div className="token-info">
                      <div className="token-name">{token.name}</div>
                      <div className="token-meta">
                        Created: {new Date(token.created_at).toLocaleDateString()}
                        {token.last_used && (
                          <span> | Last used: {new Date(token.last_used).toLocaleDateString()}</span>
                        )}
                      </div>
                      <div className="token-url">
                        <code>{getRssUrl(token.token)}</code>
                      </div>
                    </div>
                    <div className="token-actions">
                      <button
                        className={`btn-copy ${copiedId === token.id ? 'copied' : ''}`}
                        onClick={() => copyToClipboard(getRssUrl(token.token), token.id)}
                      >
                        {copiedId === token.id ? 'Copied!' : 'Copy URL'}
                      </button>
                      <button
                        className="btn-revoke"
                        onClick={() => handleDeleteToken(token.id)}
                      >
                        Revoke
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {showCreateForm ? (
              <form onSubmit={handleCreateToken} className="create-token-form">
                <input
                  type="text"
                  value={newTokenName}
                  onChange={e => setNewTokenName(e.target.value)}
                  placeholder="Token name (e.g., 'My Feedly', 'Work RSS Reader')"
                  disabled={creating}
                  autoFocus
                />
                <div className="form-actions">
                  <button type="button" onClick={() => setShowCreateForm(false)} disabled={creating}>
                    Cancel
                  </button>
                  <button type="submit" className="btn-create" disabled={creating || !newTokenName.trim()}>
                    {creating ? 'Creating...' : 'Create Token'}
                  </button>
                </div>
              </form>
            ) : (
              <button className="btn-new-token" onClick={() => setShowCreateForm(true)}>
                + Create New RSS Token
              </button>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default RSSTokenManager
