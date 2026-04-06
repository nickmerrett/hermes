import React, { useState, useEffect } from 'react'
import { formatDistanceToNow, parseISO } from 'date-fns'
import { Link } from 'react-router-dom'
import { DndContext, closestCenter, PointerSensor, useSensor, useSensors } from '@dnd-kit/core'
import { SortableContext, horizontalListSortingStrategy, useSortable, arrayMove } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { useAuth } from './contexts/AuthContext'
import { apiClient } from './api/auth'
import ErrorBanner from './components/ErrorBanner'
import CustomerEditModal from './components/CustomerEditModal'
import PlatformSettingsModal from './components/PlatformSettingsModal'
import RSSTokenManager from './components/RSSTokenManager'
import './styles/App.css'

function renderTextWithCitations(text, sources) {
  if (!sources || sources.length === 0) return text
  const parts = text.split(/(\[\d+\])/)
  return parts.map((part, i) => {
    const match = part.match(/^\[(\d+)\]$/)
    if (!match) return part
    const num = parseInt(match[1], 10)
    const source = sources.find(s => s.index === num)
    if (!source) return part
    if (source.url) {
      return (
        <a key={i} href={source.url} target="_blank" rel="noopener noreferrer"
           className="citation-link" title={source.title}>
          [{num}]
        </a>
      )
    }
    return <span key={i} className="citation-link" title={source.title}>[{num}]</span>
  })
}

function SortableTab({ customer, isActive, onClick }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: customer.id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    backgroundColor: customer.tab_color || '#ffffff',
    borderColor: isActive ? '#3b82f6' : '#d1d5db',
    opacity: isDragging ? 0.5 : 1,
    zIndex: isDragging ? 10 : undefined,
  }

  return (
    <button
      ref={setNodeRef}
      style={style}
      className={`customer-tab ${isActive ? 'active' : ''}`}
      onClick={onClick}
      {...attributes}
      {...listeners}
    >
      {customer.name}
    </button>
  )
}

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
  const [summaryCollapsed, setSummaryCollapsed] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState(null)
  const [searchLoading, setSearchLoading] = useState(false)
  const [showClustered, setShowClustered] = useState(true)
  const [expandedClusters, setExpandedClusters] = useState({})
  const [clusterItems, setClusterItems] = useState({})
  const [collectionErrors, setCollectionErrors] = useState([])
  const [editingCustomer, setEditingCustomer] = useState(null)
  const [showSettingsModal, setShowSettingsModal] = useState(false)
  const [showRSSModal, setShowRSSModal] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)

  const { user, isAdmin, logout, isAuthenticated, isLoading: authLoading } = useAuth()

  // Auto-refresh settings (persisted in localStorage)
  const [autoRefreshEnabled, setAutoRefreshEnabled] = useState(() => {
    const saved = localStorage.getItem('autoRefreshEnabled')
    return saved !== null ? JSON.parse(saved) : true
  })
  const [autoRefreshInterval, setAutoRefreshInterval] = useState(() => {
    const saved = localStorage.getItem('autoRefreshInterval')
    return saved ? parseInt(saved) : 300000 // 5 minutes default
  })
  const [isAutoRefreshing, setIsAutoRefreshing] = useState(false)
  const [lastRefreshTime, setLastRefreshTime] = useState(null)

  // Persist auto-refresh settings to localStorage
  useEffect(() => {
    localStorage.setItem('autoRefreshEnabled', JSON.stringify(autoRefreshEnabled))
  }, [autoRefreshEnabled])

  useEffect(() => {
    localStorage.setItem('autoRefreshInterval', autoRefreshInterval.toString())
  }, [autoRefreshInterval])

  useEffect(() => {
    // Don't fetch until auth is ready and user is authenticated
    if (authLoading || !isAuthenticated) return

    fetchCustomers()
    fetchAnalytics()
    fetchCollectionErrors()

    // Poll for collection errors every 2 minutes
    const errorInterval = setInterval(fetchCollectionErrors, 120000)
    return () => clearInterval(errorInterval)
  }, [authLoading, isAuthenticated])

  // Auto-refresh feed
  useEffect(() => {
    if (!autoRefreshEnabled) return

    const refreshInterval = setInterval(async () => {
      setIsAutoRefreshing(true)
      await fetchFeed()
      setLastRefreshTime(new Date())
      setIsAutoRefreshing(false)
    }, autoRefreshInterval)

    return () => clearInterval(refreshInterval)
  }, [autoRefreshEnabled, autoRefreshInterval, filters, selectedCustomer, showClustered])

  useEffect(() => {
    if (!selectedCustomer) {
      setDailySummary(null)
      return
    }
    fetchFeed()
    fetchCollectionErrors()
    fetchDailySummary()
  }, [filters, selectedCustomer, showClustered])

  const fetchCustomers = async () => {
    try {
      const response = await apiClient.get(`/customers`)
      setCustomers(response.data)
      // Default to first customer if none selected
      if (response.data.length > 0 && !selectedCustomer) {
        setSelectedCustomer(response.data[0].id)
      }
    } catch (err) {
      console.error('Error fetching customers:', err)
    }
  }

  const fetchAnalytics = async () => {
    try {
      const response = await apiClient.get(`/analytics/summary`)
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
      // Load platform settings to get selected persona
      let persona = null;
      let customPersonaText = null;
      try {
        const settingsResponse = await apiClient.get(`/settings/platform`);
        const settings = settingsResponse.data;
        if (settings.daily_briefing) {
          const template = settings.daily_briefing.template;
          if (template === 'custom' && settings.daily_briefing.custom_prompt) {
            customPersonaText = settings.daily_briefing.custom_prompt;
          } else if (template) {
            persona = template;
          }
        }
      } catch (settingsErr) {
        console.warn('Failed to load persona settings:', settingsErr);
        // Continue without persona
      }

      const params = { force_refresh: forceRefresh };
      if (persona) {
        params.persona = persona;
      }
      if (customPersonaText) {
        params.custom_persona_text = customPersonaText;
      }

      const response = await apiClient.get(`/analytics/daily-summary-ai/${selectedCustomer}`, {
        params: params
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

      const response = await apiClient.get(`/feed`, { params })

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

  const handleManualRefresh = async () => {
    await fetchFeed()
    setLastRefreshTime(new Date())
  }

  const fetchClusterItems = async (clusterId) => {
    try {
      const response = await apiClient.get(`/feed/cluster/${clusterId}`)
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
    // Global collection - collect for ALL customers
    try {
      await apiClient.post(`/jobs/trigger`, {})
      // Refresh feed and summary after collection
      setTimeout(() => {
        fetchFeed()
        if (selectedCustomer) fetchDailySummary()
      }, 2000)
    } catch (err) {
      console.error('Failed to trigger collection:', err)
    }
  }

  const triggerCustomerCollection = async () => {
    // Per-customer collection - only collect for selected customer
    if (!selectedCustomer) return

    try {
      await apiClient.post(`/jobs/trigger`, {}, {
        params: { customer_id: selectedCustomer }
      })
      // Refresh feed and summary after collection
      setTimeout(() => {
        fetchFeed()
        fetchDailySummary()
      }, 2000)
    } catch (err) {
      console.error('Failed to trigger customer collection:', err)
    }
  }

  const ignoreItem = async (itemId) => {
    if (!confirm('Are you sure you want to ignore this article? It will be hidden from your feed.')) {
      return
    }

    try {
      await apiClient.patch(`/feed/${itemId}/ignore`)
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
      const response = await apiClient.get(`/feed/collection-errors`, { params })
      setCollectionErrors(response.data.errors)
    } catch (err) {
      console.error('Failed to fetch collection errors:', err)
    }
  }

  const dismissError = async (error) => {
    try {
      await apiClient.patch(`/feed/collection-errors/${error.id}/dismiss`)
      // Remove from local state
      setCollectionErrors(prev => prev.filter(e => e.id !== error.id))
    } catch (err) {
      console.error('Failed to dismiss error:', err)
      alert('Failed to dismiss error')
    }
  }

  const handleDeleteCustomer = async (customerId) => {
    try {
      await apiClient.delete(`/customers/${customerId}`)
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
      const response = await apiClient.post(`/search`, {
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

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
  )

  const handleDragEnd = async (event) => {
    const { active, over } = event
    if (!over || active.id === over.id) return

    const oldIndex = customers.findIndex(c => c.id === active.id)
    const newIndex = customers.findIndex(c => c.id === over.id)
    const reordered = arrayMove(customers, oldIndex, newIndex)
    setCustomers(reordered)

    const items = reordered.map((c, i) => ({ id: c.id, sort_order: i }))
    try {
      await apiClient.patch('/customers/reorder', items)
    } catch (err) {
      console.error('Failed to save tab order:', err)
    }
  }

  const currentCustomer = customers.find(c => c.id === selectedCustomer)

  return (
    <div className="app">
      <ErrorBanner errors={collectionErrors} onDismiss={dismissError} />

      <header className="header">
        <h1>Hermes</h1>
        <div className="header-actions">
          <button
            className={`hamburger-btn ${menuOpen ? 'open' : ''}`}
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label="Toggle menu"
          >
            <span className="hamburger-line"></span>
            <span className="hamburger-line"></span>
            <span className="hamburger-line"></span>
          </button>

          {menuOpen && <div className="menu-backdrop" onClick={() => setMenuOpen(false)} />}

          <nav className={`header-menu ${menuOpen ? 'open' : ''}`}>
            <div className="menu-header">
              <span className="user-email">{user?.email}</span>
              <button className="menu-close-btn" onClick={() => setMenuOpen(false)}>
                &times;
              </button>
            </div>

            <div className="menu-items">
              <label className="auto-refresh-toggle menu-item">
                <input
                  type="checkbox"
                  checked={autoRefreshEnabled}
                  onChange={(e) => setAutoRefreshEnabled(e.target.checked)}
                />
                <span>Auto-refresh</span>
              </label>

              <button
                onClick={() => { triggerCollection(); setMenuOpen(false); }}
                className="menu-item menu-btn"
                title="Trigger collection for ALL customers"
              >
                Full Collection
              </button>

              <button
                onClick={() => { setShowSettingsModal(true); setMenuOpen(false); }}
                className="menu-item menu-btn"
                title="Platform Settings"
              >
                Settings
              </button>

              <Link
                to="/analytics"
                className="menu-item menu-btn"
                title="Intelligence Analytics Dashboard"
                onClick={() => setMenuOpen(false)}
              >
                Analytics
              </Link>

              {isAdmin && (
                <Link
                  to="/admin"
                  className="menu-item menu-btn"
                  title="User Administration"
                  onClick={() => setMenuOpen(false)}
                >
                  Admin
                </Link>
              )}

              <button
                onClick={() => { logout(); setMenuOpen(false); }}
                className="menu-item menu-btn logout-btn"
                title="Sign out"
              >
                Logout
              </button>
            </div>
          </nav>
        </div>
      </header>

      {/* Customer Tabs */}
      <div className="customer-tabs">
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext
            items={customers.map(c => c.id)}
            strategy={horizontalListSortingStrategy}
          >
            <div className="customer-tabs-list">
              {customers.map(customer => (
                <SortableTab
                  key={customer.id}
                  customer={customer}
                  isActive={selectedCustomer === customer.id}
                  onClick={() => setSelectedCustomer(customer.id)}
                />
              ))}
              <Link
                to="/add-customer"
                className="customer-tab add-customer-btn"
                title="Add new customer using AI-powered config wizard"
              >
                + Add Customer
              </Link>
            </div>
          </SortableContext>
        </DndContext>
      </div>

      {/* Customer Info Header */}
      {selectedCustomer && currentCustomer && (
        <div
          className="customer-info-header"
          style={{
            backgroundColor: currentCustomer?.tab_color || '#ffffff'
          }}
        >
          <div>
            <h2>{currentCustomer.name}</h2>
            {currentCustomer.domain && <span className="domain">{currentCustomer.domain}</span>}
          </div>
          <div className="customer-header-actions">
            <button
              className="btn-trigger-collection"
              onClick={triggerCustomerCollection}
              title="Trigger collection for this customer only"
            >
              Collect
            </button>
            <Link
              to={`/analytics?customer=${selectedCustomer}&days=30`}
              className="btn-analytics-header"
              title="Intelligence Analytics"
            >
              Analytics
            </Link>
            <button
              className="btn-rss-header"
              onClick={() => setShowRSSModal(true)}
              title="RSS Feed"
            >
              RSS
            </button>
            <button
              className="btn-settings-header"
              onClick={() => setEditingCustomer(currentCustomer)}
              title="Customer settings"
            >
              Settings
            </button>
          </div>
        </div>
      )}

      {/* Main Content Area with Sidebar Layout */}
      <div
        className="main-layout"
        style={{
          backgroundColor: currentCustomer?.tab_color || '#ffffff',
          padding: '24px',
          borderRadius: '0 0 8px 8px'
        }}
      >
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
              <option value="youtube">YouTube</option>
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
              onClick={handleManualRefresh}
              className="btn-refresh-feed"
              title="Refresh feed"
              disabled={loading}
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

                      {/* Pain Points */}
                      {item.processed.pain_points_opportunities && item.processed.pain_points_opportunities.pain_points && item.processed.pain_points_opportunities.pain_points.length > 0 && (
                        <div className="tags">
                          {item.processed.pain_points_opportunities.pain_points.map((pain, i) => (
                            <span key={i} className="tag tag-pain-point">⚠️ {pain}</span>
                          ))}
                        </div>
                      )}

                      {/* Opportunities */}
                      {item.processed.pain_points_opportunities && item.processed.pain_points_opportunities.opportunities && item.processed.pain_points_opportunities.opportunities.length > 0 && (
                        <div className="tags">
                          {item.processed.pain_points_opportunities.opportunities.map((opp, i) => (
                            <span key={i} className="tag tag-opportunity">✨ {opp}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  </>
                )}

                <div className="item-footer">
                  <div className="item-footer-left">
                    {item.cluster_id && (
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
                {item.cluster_id && expandedClusters[item.cluster_id] && (
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

                      {/* Pain Points */}
                      {item.processed.pain_points_opportunities && item.processed.pain_points_opportunities.pain_points && item.processed.pain_points_opportunities.pain_points.length > 0 && (
                        <div className="tags">
                          {item.processed.pain_points_opportunities.pain_points.map((pain, i) => (
                            <span key={i} className="tag tag-pain-point">⚠️ {pain}</span>
                          ))}
                        </div>
                      )}

                      {/* Opportunities */}
                      {item.processed.pain_points_opportunities && item.processed.pain_points_opportunities.opportunities && item.processed.pain_points_opportunities.opportunities.length > 0 && (
                        <div className="tags">
                          {item.processed.pain_points_opportunities.opportunities.map((opp, i) => (
                            <span key={i} className="tag tag-opportunity">✨ {opp}</span>
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
            <div className={`panel-header${!summaryCollapsed ? ' panel-header--expanded' : ''}`} onClick={() => setSummaryCollapsed(c => !c)} style={{cursor: 'pointer'}}>
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
                  onClick={(e) => { e.stopPropagation(); fetchDailySummary(true); }}
                  className={`btn-refresh ${dailySummary?.loading ? 'loading' : ''}`}
                  title="Regenerate summary"
                  disabled={dailySummary?.loading}
                >
                  ↻
                </button>
                <span className="period-badge">Last 24 Hours</span>
                <span className="summary-collapse-toggle">{summaryCollapsed ? '▼' : '▲'}</span>
              </div>
            </div>

            <div className={`summary-panel-body${summaryCollapsed ? ' summary-panel-body--collapsed' : ''}`}>
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
                      {Object.entries(dailySummary.items_by_category)
                        .filter(([category]) => category !== 'unrelated' && category !== 'advertisement')
                        .map(([category, count]) => (
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
                        <p key={idx}>{renderTextWithCitations(paragraph, dailySummary.sources)}</p>
                      ))}
                    </div>
                    {dailySummary.sources && dailySummary.sources.length > 0 && (
                      <div className="citation-sources">
                        <h5>Sources</h5>
                        <ol className="sources-list">
                          {dailySummary.sources.map(source => (
                            <li key={source.index}>
                              {source.url ? (
                                <a href={source.url} target="_blank" rel="noopener noreferrer">
                                  {source.title}
                                </a>
                              ) : (
                                <span>{source.title}</span>
                              )}
                              <span className="source-type-badge">{source.source_type}</span>
                            </li>
                          ))}
                        </ol>
                      </div>
                    )}
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
            </div>
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
          onClose={() => {
            // Reload auto-refresh settings from localStorage
            const savedEnabled = localStorage.getItem('autoRefreshEnabled')
            const savedInterval = localStorage.getItem('autoRefreshInterval')
            if (savedEnabled !== null) {
              setAutoRefreshEnabled(JSON.parse(savedEnabled))
            }
            if (savedInterval) {
              setAutoRefreshInterval(parseInt(savedInterval))
            }
            setShowSettingsModal(false)
          }}
          onSave={() => {
            // Reload auto-refresh settings from localStorage
            const savedEnabled = localStorage.getItem('autoRefreshEnabled')
            const savedInterval = localStorage.getItem('autoRefreshInterval')
            if (savedEnabled !== null) {
              setAutoRefreshEnabled(JSON.parse(savedEnabled))
            }
            if (savedInterval) {
              setAutoRefreshInterval(parseInt(savedInterval))
            }
            // Refresh daily summary if settings changed
            if (selectedCustomer) {
              fetchDailySummary()
            }
            setShowSettingsModal(false)
          }}
        />
      )}

      {/* RSS Token Manager Modal */}
      {showRSSModal && selectedCustomer && currentCustomer && (
        <RSSTokenManager
          customerId={selectedCustomer}
          customerName={currentCustomer.name}
          onClose={() => setShowRSSModal(false)}
        />
      )}
    </div>
  )
}

export default App
