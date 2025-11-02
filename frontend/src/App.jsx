import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { formatDistanceToNow, parseISO } from 'date-fns'
import { Link } from 'react-router-dom'
import ErrorBanner from './components/ErrorBanner'
import CustomerEditModal from './components/CustomerEditModal'
import PlatformSettingsModal from './components/PlatformSettingsModal'
import './styles/App.css'

const API_URL = import.meta.env.VITE_API_URL || '/api'

function App() {
  const [feed, setFeed] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filters, setFilters] = useState({
    category: '',
    sentiment: '',
    source_type: '',
    min_priority: ''
  })
  const [customers, setCustomers] = useState([])
  const [selectedCustomer, setSelectedCustomer] = useState(null)
  const [analytics, setAnalytics] = useState(null)
  const [dailySummary, setDailySummary] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState(null)
  const [searchLoading, setSearchLoading] = useState(false)
  const [showClustered, setShowClustered] = useState(true)
  const [expandedClusters, setExpandedClusters] = useState({})
  const [clusterItems, setClusterItems] = useState({})
  const [collectionErrors, setCollectionErrors] = useState([])
  const [dismissedErrors, setDismissedErrors] = useState([])
  const [editingCustomer, setEditingCustomer] = useState(null)
  const [showSettingsModal, setShowSettingsModal] = useState(false)

  useEffect(() => {
    fetchCustomers()
    fetchAnalytics()
    fetchCollectionErrors()

    // Poll for collection errors every 2 minutes
    const errorInterval = setInterval(fetchCollectionErrors, 120000)
    return () => clearInterval(errorInterval)
  }, [])

  useEffect(() => {
    fetchFeed()
    fetchCollectionErrors()
    if (selectedCustomer) {
      fetchDailySummary()
    } else {
      setDailySummary(null)
    }
  }, [filters, selectedCustomer, showClustered])

  const fetchCustomers = async () => {
    try {
      const response = await axios.get(`${API_URL}/customers`)
      setCustomers(response.data)
      // Auto-select first customer if available
      if (response.data.length > 0 && !selectedCustomer) {
        setSelectedCustomer(response.data[0].id)
      }
    } catch (err) {
      console.error('Error fetching customers:', err)
    }
  }

  const fetchAnalytics = async () => {
    try {
      const response = await axios.get(`${API_URL}/analytics/summary`)
      setAnalytics(response.data)
    } catch (err) {
      console.error('Error fetching analytics:', err)
    }
  }

  const fetchDailySummary = async (forceRefresh = false) => {
    if (!selectedCustomer) return

    // Show loading state if forcing refresh
    if (forceRefresh) {
      setDailySummary({ loading: true })
    }

    try {
      const response = await axios.get(`${API_URL}/analytics/daily-summary-ai/${selectedCustomer}`, {
        params: { force_refresh: forceRefresh }
      })
      // If response is null/empty, keep dailySummary as null to show placeholder
      setDailySummary(response.data || null)
    } catch (err) {
      console.error('Error fetching daily summary:', err)
      // On error, set to null to show placeholder
      setDailySummary(null)
    }
  }

  const fetchFeed = async () => {
    setLoading(true)
    try {
      const params = {
        ...filters,
        customer_id: selectedCustomer,
        limit: 50,
        clustered: showClustered
      }
      // Remove empty filters
      Object.keys(params).forEach(key => {
        if (params[key] === '' || params[key] === null) delete params[key]
      })

      const response = await axios.get(`${API_URL}/feed`, { params })

      // Filter out 'unrelated' items unless explicitly selected
      let filteredItems = response.data.items
      if (filters.category !== 'unrelated') {
        filteredItems = filteredItems.filter(item =>
          !item.processed || item.processed.category !== 'unrelated'
        )
      }

      setFeed(filteredItems)
      setError(null)
    } catch (err) {
      setError('Failed to load intelligence feed')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const fetchClusterItems = async (clusterId) => {
    try {
      const response = await axios.get(`${API_URL}/feed/cluster/${clusterId}`)
      setClusterItems(prev => ({
        ...prev,
        [clusterId]: response.data.items
      }))
    } catch (err) {
      console.error('Failed to fetch cluster items:', err)
    }
  }

  const toggleCluster = (clusterId) => {
    const isExpanding = !expandedClusters[clusterId]

    setExpandedClusters(prev => ({
      ...prev,
      [clusterId]: isExpanding
    }))

    // Fetch cluster items if expanding and not already loaded
    if (isExpanding && !clusterItems[clusterId]) {
      fetchClusterItems(clusterId)
    }
  }

  const triggerCollection = async () => {
    try {
      await axios.post(`${API_URL}/jobs/trigger`, {}, {
        params: selectedCustomer ? { customer_id: selectedCustomer } : {}
      })
      // Refresh feed and summary after collection
      setTimeout(() => {
        fetchFeed()
        if (selectedCustomer) fetchDailySummary()
      }, 2000)
    } catch (err) {
      console.error('Failed to trigger collection:', err)
    }
  }

  const ignoreItem = async (itemId) => {
    if (!confirm('Are you sure you want to ignore this article?')) {
      return
    }

    try {
      await axios.delete(`${API_URL}/feed/${itemId}`)
      // Remove item from feed or search results locally
      if (searchResults) {
        setSearchResults({
          ...searchResults,
          results: searchResults.results.filter(r => r.item.id !== itemId)
        })
      } else {
        setFeed(feed.filter(item => item.id !== itemId))
      }
      // Refresh daily summary
      if (selectedCustomer) fetchDailySummary()
    } catch (err) {
      alert('Failed to ignore article')
      console.error(err)
    }
  }

  const fetchCollectionErrors = async () => {
    try {
      const params = selectedCustomer ? { customer_id: selectedCustomer } : {}
      const response = await axios.get(`${API_URL}/feed/collection-errors`, { params })

      // Filter out dismissed errors
      const errors = response.data.errors.filter(error => {
        const key = `${error.customer_id}-${error.source_type}`
        return !dismissedErrors.includes(key)
      })

      setCollectionErrors(errors)
    } catch (err) {
      console.error('Failed to fetch collection errors:', err)
    }
  }

  const dismissError = (error) => {
    const key = `${error.customer_id}-${error.source_type}`
    setDismissedErrors(prev => [...prev, key])
    setCollectionErrors(prev => prev.filter(e => {
      const eKey = `${e.customer_id}-${e.source_type}`
      return eKey !== key
    }))
  }

  const handleDeleteCustomer = async (customerId) => {
    try {
      await axios.delete(`${API_URL}/api/customers/${customerId}`)
      // Refresh customer list
      fetchCustomers()
      // Clear selection if deleted customer was selected
      if (selectedCustomer === customerId) {
        setSelectedCustomer(null)
      }
      // Close edit modal
      setEditingCustomer(null)
    } catch (err) {
      alert('Failed to delete customer')
      console.error(err)
    }
  }

  const performSearch = async (e) => {
    e.preventDefault()
    if (!searchQuery.trim()) {
      setSearchResults(null)
      return
    }

    setSearchLoading(true)
    try {
      const response = await axios.post(`${API_URL}/search`, {
        query: searchQuery,
        customer_id: selectedCustomer,
        limit: 20,
        min_similarity: 0.3
      })
      setSearchResults(response.data)
      setError(null)
    } catch (err) {
      setError('Search failed')
      console.error(err)
    } finally {
      setSearchLoading(false)
    }
  }

  const clearSearch = () => {
    setSearchQuery('')
    setSearchResults(null)
  }

  const getSentimentColor = (sentiment) => {
    const colors = {
      positive: '#10b981',
      negative: '#ef4444',
      neutral: '#6b7280',
      mixed: '#f59e0b'
    }
    return colors[sentiment] || '#6b7280'
  }

  const getPriorityBadge = (score) => {
    if (score >= 0.8) return { label: 'High', color: '#ef4444' }
    if (score >= 0.6) return { label: 'Medium', color: '#f59e0b' }
    return { label: 'Low', color: '#6b7280' }
  }

  const formatDate = (dateString) => {
    if (!dateString) return 'Unknown date'

    try {
      // Parse ISO string which is in UTC
      const date = parseISO(dateString)

      // formatDistanceToNow automatically uses local time
      return formatDistanceToNow(date, { addSuffix: true })
    } catch (e) {
      console.error('Error parsing date:', dateString, e)
      return 'Unknown date'
    }
  }

  const currentCustomer = customers.find(c => c.id === selectedCustomer)

  return (
    <div className="app">
      <ErrorBanner errors={collectionErrors} onDismiss={dismissError} />

      <header className="header">
        <h1>Hermes</h1>
        <div className="header-actions">
          <button onClick={() => setShowSettingsModal(true)} className="btn-secondary">
            ⚙ Settings
          </button>
          <button onClick={triggerCollection} className="btn-primary">
            Trigger Collection
          </button>
        </div>
      </header>

      {/* Customer Tabs */}
      <div className="customer-tabs">
        <div className="customer-tabs-list">
          {customers.map(customer => (
            <button
              key={customer.id}
              className={`customer-tab ${selectedCustomer === customer.id ? 'active' : ''}`}
              onClick={() => setSelectedCustomer(customer.id)}
            >
              {customer.name}
            </button>
          ))}
          <Link
            to="/add-customer"
            className="customer-tab add-customer-btn"
            title="Add new customer using AI-powered config wizard"
          >
            + Add Customer
          </Link>
        </div>
      </div>

      {/* Customer Info Header */}
      {selectedCustomer && currentCustomer && (
        <div className="customer-info-header">
          <div>
            <h2>{currentCustomer.name}</h2>
            {currentCustomer.domain && <span className="domain">{currentCustomer.domain}</span>}
          </div>
          <button
            className="btn-settings-header"
            onClick={() => setEditingCustomer(currentCustomer)}
            title="Customer settings"
          >
            ⚙
          </button>
        </div>
      )}

      {/* Main Content Area with Sidebar Layout */}
      <div className="main-layout">
        {/* Left Side - Main Feed */}
        <div className="main-content">

          <div className="search-section">
            <form onSubmit={performSearch} className="search-form">
              <input
                type="text"
                placeholder="Semantic search across all articles..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="search-input"
              />
              <button type="submit" className="btn-search" disabled={searchLoading}>
                {searchLoading ? 'Searching...' : 'Search'}
              </button>
              {searchResults && (
                <button type="button" onClick={clearSearch} className="btn-clear">
                  Clear Search
                </button>
              )}
            </form>
            {searchResults && (
              <div className="search-info">
                Found {searchResults.results.length} similar articles for "{searchResults.query}"
              </div>
            )}
          </div>

          <div className="filters">
            <div className="view-toggle">
              <button
                className={`toggle-btn ${showClustered ? 'active' : ''}`}
                onClick={() => setShowClustered(true)}
              >
                📰 Smart Feed
              </button>
              <button
                className={`toggle-btn ${!showClustered ? 'active' : ''}`}
                onClick={() => setShowClustered(false)}
              >
                📋 Full Feed
              </button>
            </div>

            <select
              value={filters.category}
              onChange={(e) => setFilters({ ...filters, category: e.target.value })}
            >
              <option value="">All Categories</option>
              <option value="product_update">Product Update</option>
              <option value="financial">Financial</option>
              <option value="market_news">Market News</option>
              <option value="competitor">Competitor</option>
              <option value="challenge">Challenge</option>
              <option value="opportunity">Opportunity</option>
              <option value="leadership">Leadership</option>
              <option value="partnership">Partnership</option>
              <option value="advertisement">Advertisement</option>
              <option value="unrelated">Unrelated</option>
            </select>

            <select
              value={filters.sentiment}
              onChange={(e) => setFilters({ ...filters, sentiment: e.target.value })}
            >
              <option value="">All Sentiments</option>
              <option value="positive">Positive</option>
              <option value="negative">Negative</option>
              <option value="neutral">Neutral</option>
              <option value="mixed">Mixed</option>
            </select>

            <select
              value={filters.source_type}
              onChange={(e) => setFilters({ ...filters, source_type: e.target.value })}
            >
              <option value="">All Sources</option>
              <option value="news_api">News API</option>
              <option value="google_news">Google News</option>
              <option value="rss">RSS Feed</option>
              <option value="reddit">Reddit</option>
              <option value="stock">Stock Market</option>
              <option value="australian_news">Australian News</option>
              <option value="web_scrape">Web Scrape</option>
              <option value="linkedin_user">LinkedIn</option>
            </select>

            <select
              value={filters.min_priority}
              onChange={(e) => setFilters({ ...filters, min_priority: e.target.value })}
            >
              <option value="">All Priorities</option>
              <option value="0.8">High Priority</option>
              <option value="0.6">Medium+ Priority</option>
            </select>

            <button
              onClick={() => fetchFeed()}
              className="btn-refresh-feed"
              title="Refresh feed"
            >
              ↻ Refresh
            </button>
          </div>

          <div className="feed">
            {(loading || searchLoading) && <div className="loading">Loading...</div>}
            {error && <div className="error">{error}</div>}

            {!loading && !searchLoading && !searchResults && !error && feed.length === 0 && (
              <div className="empty">No intelligence items found. Try adjusting filters or trigger a collection.</div>
            )}

            {!searchLoading && searchResults && searchResults.results.length === 0 && (
              <div className="empty">No similar articles found. Try a different search query.</div>
            )}

            {!loading && !searchResults && feed.map(item => (
              <div key={item.id} className="feed-item">
                <div className="item-header">
                  <h3>{item.title}</h3>
                  <div className="item-header-actions">
                    {item.source_tier && (
                      <span className="tier-badge tier-{item.source_tier}">{item.source_tier}</span>
                    )}
                    <span className="source-badge">{item.source_type}</span>
                    <button
                      onClick={() => ignoreItem(item.id)}
                      className="btn-ignore"
                      title="Ignore this article"
                    >
                      ✕
                    </button>
                  </div>
                </div>

                {item.processed && (
                  <>
                    <p className="summary">{item.processed.summary}</p>

                    <div className="item-meta">
                      <span
                        className="badge"
                        style={{ backgroundColor: getSentimentColor(item.processed.sentiment) }}
                      >
                        {item.processed.sentiment}
                      </span>

                      <span className="badge category-badge">
                        {item.processed.category?.replace('_', ' ')}
                      </span>

                      {item.processed.priority_score && (
                        <span
                          className="badge"
                          style={{ backgroundColor: getPriorityBadge(item.processed.priority_score).color }}
                        >
                          {getPriorityBadge(item.processed.priority_score).label} Priority
                        </span>
                      )}

                      {item.processed.needs_reprocessing && (
                        <span
                          className="badge reprocessing-badge"
                          title={`AI processing failed after ${item.processed.processing_attempts || 0} attempts${item.processed.last_processing_error ? ': ' + item.processed.last_processing_error : ''}`}
                        >
                          ⚠️ Needs Reprocessing
                        </span>
                      )}

                      {item.processed.tags && item.processed.tags.length > 0 && (
                        <div className="tags">
                          {item.processed.tags.slice(0, 3).map((tag, i) => (
                            <span key={i} className="tag">{tag}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  </>
                )}

                <div className="item-footer">
                  <div className="item-footer-left">
                    {showClustered && (
                      <button
                        className="source-count-badge"
                        onClick={() => toggleCluster(item.cluster_id)}
                        title={item.cluster_member_count > 1 ? `View all ${item.cluster_member_count} sources` : 'Single source'}
                      >
                        {expandedClusters[item.cluster_id] ? '▼' : '▶'} {item.cluster_member_count || 1} {(item.cluster_member_count || 1) === 1 ? 'source' : 'sources'}
                      </button>
                    )}
                    {item.url && (
                      <a href={item.url} target="_blank" rel="noopener noreferrer">
                        View Source →
                      </a>
                    )}
                  </div>
                  <span className="timestamp">
                    {formatDate(item.published_date)}
                  </span>
                </div>

                {/* Cluster Items - Shown when expanded */}
                {showClustered && expandedClusters[item.cluster_id] && (
                  <div className="cluster-items">
                    <div className="cluster-header">
                      <h4>All Sources for This Story</h4>
                    </div>
                    {clusterItems[item.cluster_id] ? (
                      <div className="cluster-sources">
                        {clusterItems[item.cluster_id]
                          .filter(clusterItem => clusterItem.id !== item.id)
                          .map(clusterItem => (
                            <div key={clusterItem.id} className="cluster-source-item">
                              <div className="cluster-source-header">
                                <span className="source-badge">{clusterItem.source_type}</span>
                                {clusterItem.source_tier && (
                                  <span className="tier-badge tier-{clusterItem.source_tier}">
                                    {clusterItem.source_tier}
                                  </span>
                                )}
                                <span className="timestamp">
                                  {formatDate(clusterItem.published_date)}
                                </span>
                              </div>
                              <div className="cluster-source-title">
                                {clusterItem.url ? (
                                  <a href={clusterItem.url} target="_blank" rel="noopener noreferrer">
                                    {clusterItem.title} →
                                  </a>
                                ) : (
                                  clusterItem.title
                                )}
                              </div>
                            </div>
                          ))
                        }
                      </div>
                    ) : (
                      <div className="cluster-loading">Loading cluster items...</div>
                    )}
                  </div>
                )}
              </div>
            ))}

            {!searchLoading && searchResults && searchResults.results.map(({ item, similarity }) => (
              <div key={item.id} className="feed-item">
                <div className="item-header">
                  <h3>{item.title}</h3>
                  <div className="item-header-actions">
                    <span className="similarity-badge" title="Similarity Score">
                      {(similarity * 100).toFixed(0)}% match
                    </span>
                    <span className="source-badge">{item.source_type}</span>
                    <button
                      onClick={() => ignoreItem(item.id)}
                      className="btn-ignore"
                      title="Ignore this article"
                    >
                      ✕
                    </button>
                  </div>
                </div>

                {item.processed && (
                  <>
                    <p className="summary">{item.processed.summary}</p>

                    <div className="item-meta">
                      <span
                        className="badge"
                        style={{ backgroundColor: getSentimentColor(item.processed.sentiment) }}
                      >
                        {item.processed.sentiment}
                      </span>

                      <span className="badge category-badge">
                        {item.processed.category?.replace('_', ' ')}
                      </span>

                      {item.processed.priority_score && (
                        <span
                          className="badge"
                          style={{ backgroundColor: getPriorityBadge(item.processed.priority_score).color }}
                        >
                          {getPriorityBadge(item.processed.priority_score).label} Priority
                        </span>
                      )}

                      {item.processed.needs_reprocessing && (
                        <span
                          className="badge reprocessing-badge"
                          title={`AI processing failed after ${item.processed.processing_attempts || 0} attempts${item.processed.last_processing_error ? ': ' + item.processed.last_processing_error : ''}`}
                        >
                          ⚠️ Needs Reprocessing
                        </span>
                      )}

                      {item.processed.tags && item.processed.tags.length > 0 && (
                        <div className="tags">
                          {item.processed.tags.slice(0, 3).map((tag, i) => (
                            <span key={i} className="tag">{tag}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  </>
                )}

                <div className="item-footer">
                  {item.url && (
                    <a href={item.url} target="_blank" rel="noopener noreferrer">
                      View Source →
                    </a>
                  )}
                  <span className="timestamp">
                    {formatDate(item.published_date)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right Side - Daily Summary Panel */}
        {selectedCustomer && (
          <aside className="daily-summary-panel">
            <div className="panel-header">
              <div>
                <h3>Daily Briefing</h3>
                {dailySummary?.cached && dailySummary?.generated_at && (
                  <span className="cache-indicator">
                    Cached • {formatDate(dailySummary.generated_at)}
                  </span>
                )}
              </div>
              <div className="panel-actions">
                <button
                  onClick={() => fetchDailySummary(true)}
                  className={`btn-refresh ${dailySummary?.loading ? 'loading' : ''}`}
                  title="Regenerate summary"
                  disabled={dailySummary?.loading}
                >
                  ↻
                </button>
                <span className="period-badge">Last 24 Hours</span>
              </div>
            </div>

            {!dailySummary || dailySummary.loading ? (
              <div className="summary-placeholder">
                <div className="placeholder-icon">📊</div>
                <p className="placeholder-text">
                  {dailySummary?.loading
                    ? 'Generating summary...'
                    : 'No summary generated for today'}
                </p>
                {!dailySummary?.loading && (
                  <p className="placeholder-hint">
                    Click the refresh button above to generate today's briefing
                  </p>
                )}
              </div>
            ) : (
              <>
                <div className="summary-stats">
                  <div className="summary-stat">
                    <div className="stat-value">{dailySummary.total_items || 0}</div>
                    <div className="stat-label">Total Items</div>
                  </div>
                  <div className="summary-stat highlight">
                    <div className="stat-value">{dailySummary.high_priority_count || 0}</div>
                    <div className="stat-label">High Priority</div>
                  </div>
                </div>

                {dailySummary.items_by_category && Object.keys(dailySummary.items_by_category).length > 0 && (
                  <div className="category-breakdown">
                    <h4>Intelligence By Category</h4>
                    <div className="category-list">
                      {Object.entries(dailySummary.items_by_category).map(([category, count]) => (
                        <div key={category} className="category-item">
                          <span className="category-name">{category.replace('_', ' ')}</span>
                          <span className="category-count">{count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {dailySummary.summary ? (
                  <div className="ai-summary-section">
                    <h4>Executive Summary</h4>
                    <div className="ai-summary-content">
                      {dailySummary.summary.split('\n\n').map((paragraph, idx) => (
                        <p key={idx}>{paragraph}</p>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="summary-placeholder">
                    <div className="placeholder-icon">📊</div>
                    <p className="placeholder-text">No summary generated yet</p>
                    <p className="placeholder-hint">
                      Click the refresh button above to generate today's briefing
                    </p>
                  </div>
                )}
              </>
            )}
          </aside>
        )}

      </div>

      {/* Edit Customer Modal */}
      {editingCustomer && (
        <CustomerEditModal
          customer={editingCustomer}
          onClose={() => setEditingCustomer(null)}
          onSave={() => {
            fetchCustomers()
            setEditingCustomer(null)
          }}
          onDelete={() => handleDeleteCustomer(editingCustomer.id)}
        />
      )}

      {/* Platform Settings Modal */}
      {showSettingsModal && (
        <PlatformSettingsModal
          onClose={() => setShowSettingsModal(false)}
          onSave={() => {
            // Refresh daily summary if settings changed
            if (selectedCustomer) {
              fetchDailySummary()
            }
            setShowSettingsModal(false)
          }}
        />
      )}
    </div>
  )
}

export default App
