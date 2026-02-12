import { useState, useEffect, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from 'recharts';
import { apiClient } from '../../api/auth';
import WordCloud from './WordCloud';
import './AnalyticsDashboardPage.css';

const CATEGORY_COLORS = {
  product_update: '#3b82f6',
  financial: '#10b981',
  market_news: '#6366f1',
  competitor: '#ef4444',
  challenge: '#f59e0b',
  opportunity: '#14b8a6',
  leadership: '#8b5cf6',
  partnership: '#ec4899',
  advertisement: '#a3a3a3',
  uncategorized: '#d1d5db',
};

const SENTIMENT_COLORS = {
  positive: '#10b981',
  negative: '#ef4444',
  neutral: '#6b7280',
  mixed: '#f59e0b',
};

const SOURCE_COLORS = [
  '#3b82f6', '#10b981', '#6366f1', '#ef4444',
  '#f59e0b', '#14b8a6', '#8b5cf6', '#ec4899',
  '#a3a3a3', '#64748b',
];

function formatCategoryLabel(cat) {
  return (cat || 'unknown').replace(/_/g, ' ');
}

export default function AnalyticsDashboardPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [customers, setCustomers] = useState([]);
  const [selectedCustomer, setSelectedCustomer] = useState(
    searchParams.get('customer') ? Number(searchParams.get('customer')) : null
  );
  const [periodDays, setPeriodDays] = useState(
    searchParams.get('days') ? Number(searchParams.get('days')) : 30
  );
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [execSearchInput, setExecSearchInput] = useState('');

  // Fetch customers on mount
  useEffect(() => {
    apiClient.get('/customers').then(res => {
      setCustomers(res.data);
      if (!selectedCustomer && res.data.length > 0) {
        setSelectedCustomer(res.data[0].id);
      }
    }).catch(err => {
      console.error('Error fetching customers:', err);
      setError('Failed to load customers');
    });
  }, []);

  // Fetch dashboard data when customer or period changes
  useEffect(() => {
    if (!selectedCustomer) return;

    setSearchParams({ customer: selectedCustomer, days: periodDays });
    setLoading(true);
    setError(null);

    apiClient.get(`/analytics/dashboard/${selectedCustomer}`, {
      params: { days: periodDays },
    }).then(res => {
      if (res.data.error) {
        setError(res.data.error);
        setDashboard(null);
      } else {
        setDashboard(res.data);
      }
    }).catch(err => {
      console.error('Error fetching dashboard:', err);
      setError('Failed to load analytics data');
      setDashboard(null);
    }).finally(() => {
      setLoading(false);
    });
  }, [selectedCustomer, periodDays]);

  // Transform timeline data for stacked area chart
  const timelineData = useMemo(() => {
    if (!dashboard?.timeline) return [];
    return dashboard.timeline.map(day => ({
      date: day.date.slice(5), // MM-DD
      ...day.breakdown,
    }));
  }, [dashboard]);

  const timelineCategories = useMemo(() => {
    if (!dashboard?.timeline) return [];
    const cats = new Set();
    dashboard.timeline.forEach(d => {
      Object.keys(d.breakdown).forEach(c => cats.add(c));
    });
    return [...cats];
  }, [dashboard]);

  // Category bar chart data (horizontal)
  const categoryData = useMemo(() => {
    if (!dashboard?.items_by_category) return [];
    return Object.entries(dashboard.items_by_category)
      .map(([cat, count]) => ({ name: formatCategoryLabel(cat), count, key: cat }))
      .sort((a, b) => b.count - a.count);
  }, [dashboard]);

  // Sentiment bar chart data
  const sentimentData = useMemo(() => {
    if (!dashboard?.items_by_sentiment) return [];
    return Object.entries(dashboard.items_by_sentiment)
      .map(([sent, count]) => ({ name: sent, count }));
  }, [dashboard]);

  // Source donut data
  const sourceData = useMemo(() => {
    if (!dashboard?.items_by_source) return [];
    return Object.entries(dashboard.items_by_source)
      .map(([src, count]) => ({ name: src.replace(/_/g, ' '), count }));
  }, [dashboard]);

  // Sparkline data per category
  const sparklineData = useMemo(() => {
    if (!dashboard?.weekly_trends || !dashboard?.items_by_category) return [];
    const categories = Object.keys(dashboard.items_by_category);
    return categories.map(cat => ({
      category: cat,
      data: dashboard.weekly_trends.map(w => ({
        week: w.week_start,
        count: w.by_category[cat] || 0,
      })),
    }));
  }, [dashboard]);

  const handleExecNav = () => {
    if (execSearchInput.trim()) {
      navigate(`/executive/${encodeURIComponent(execSearchInput.trim())}`);
    }
  };

  if (loading && !dashboard) {
    return (
      <div className="analytics-dashboard">
        <div className="analytics-loading">
          <div className="analytics-spinner"></div>
          <p>Loading analytics...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="analytics-dashboard">
      {/* Header */}
      <div className="analytics-header">
        <div className="analytics-header-left">
          <button onClick={() => navigate('/')} className="analytics-btn-back">
            Back
          </button>
          <h1>Intelligence Analytics</h1>
        </div>
        <div className="analytics-header-right">
          <select
            className="analytics-select"
            value={selectedCustomer || ''}
            onChange={e => setSelectedCustomer(Number(e.target.value))}
          >
            {customers.map(c => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          <select
            className="analytics-select"
            value={periodDays}
            onChange={e => setPeriodDays(Number(e.target.value))}
            style={{ minWidth: 120 }}
          >
            <option value={30}>Last 30 days</option>
            <option value={60}>Last 60 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        </div>
      </div>

      {/* Meeting Prep */}
      <div className="analytics-meeting-prep">
        <label>Meeting Prep:</label>
        <input
          type="text"
          placeholder="Executive ID (e.g. jane-smith)"
          value={execSearchInput}
          onChange={e => setExecSearchInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleExecNav()}
        />
        <button
          className="analytics-btn-meeting"
          onClick={handleExecNav}
          disabled={!execSearchInput.trim()}
        >
          View Executive
        </button>
      </div>

      {error && <div className="analytics-error">{error}</div>}

      {dashboard && (
        <>
          {/* Stats Row */}
          <div className="analytics-stats-row">
            <div className="analytics-stat-card">
              <div className="analytics-stat-value">{dashboard.total_items}</div>
              <div className="analytics-stat-label">Total Items</div>
            </div>
            <div className="analytics-stat-card">
              <div className="analytics-stat-value highlight">{dashboard.high_priority_count}</div>
              <div className="analytics-stat-label">High Priority</div>
            </div>
            <div className="analytics-stat-card">
              <div className="analytics-stat-value">{dashboard.avg_priority}</div>
              <div className="analytics-stat-label">Avg Priority</div>
            </div>
            <div className="analytics-stat-card">
              <div className="analytics-stat-value">{dashboard.sources_active}</div>
              <div className="analytics-stat-label">Active Sources</div>
            </div>
          </div>

          {/* Timeline (full-width) */}
          <div className="analytics-full-row">
            <div className="analytics-card">
              <h3>Items Over Time</h3>
              <div className="analytics-chart-container">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={timelineData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Legend />
                    {timelineCategories.map(cat => (
                      <Area
                        key={cat}
                        type="monotone"
                        dataKey={cat}
                        name={formatCategoryLabel(cat)}
                        stackId="1"
                        fill={CATEGORY_COLORS[cat] || '#94a3b8'}
                        stroke={CATEGORY_COLORS[cat] || '#94a3b8'}
                        fillOpacity={0.6}
                      />
                    ))}
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* Word Cloud + Category Bar */}
          <div className="analytics-two-col">
            <div className="analytics-card">
              <h3>Tag Cloud</h3>
              <WordCloud tags={dashboard.tag_frequencies} />
            </div>
            <div className="analytics-card">
              <h3>Items by Category</h3>
              <div className="analytics-chart-container">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={categoryData} layout="vertical" margin={{ left: 80 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                    <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={75} />
                    <Tooltip />
                    <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                      {categoryData.map((entry) => (
                        <Cell key={entry.key} fill={CATEGORY_COLORS[entry.key] || '#94a3b8'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* Sentiment Bar + Source Donut */}
          <div className="analytics-two-col">
            <div className="analytics-card">
              <h3>Sentiment Distribution</h3>
              <div className="analytics-chart-container">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={sentimentData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                      {sentimentData.map((entry) => (
                        <Cell key={entry.name} fill={SENTIMENT_COLORS[entry.name] || '#94a3b8'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
            <div className="analytics-card">
              <h3>Items by Source</h3>
              <div className="analytics-chart-container">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={sourceData}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={100}
                      paddingAngle={2}
                      dataKey="count"
                      nameKey="name"
                      label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                      labelLine={true}
                    >
                      {sourceData.map((_, i) => (
                        <Cell key={i} fill={SOURCE_COLORS[i % SOURCE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* Priority Histogram + Top Entities */}
          <div className="analytics-two-col">
            <div className="analytics-card">
              <h3>Priority Distribution</h3>
              <div className="analytics-chart-container">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={dashboard.priority_histogram}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
            <div className="analytics-card">
              <h3>Top Entities</h3>
              {dashboard.top_entities && Object.keys(dashboard.top_entities).length > 0 ? (
                <div className="analytics-entities">
                  {Object.entries(dashboard.top_entities).map(([type, entities]) => (
                    entities.length > 0 && (
                      <div key={type} className="analytics-entity-section">
                        <h4>{type.replace(/_/g, ' ')}</h4>
                        <div className="analytics-entity-list">
                          {entities.slice(0, 8).map(e => (
                            <div key={e.name} className="analytics-entity-row">
                              <span className="analytics-entity-name">{e.name}</span>
                              <span className="analytics-entity-count">{e.count}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )
                  ))}
                </div>
              ) : (
                <div className="analytics-empty">No entity data available</div>
              )}
            </div>
          </div>

          {/* Weekly Sparklines */}
          {sparklineData.length > 0 && (
            <div className="analytics-full-row">
              <div className="analytics-card">
                <h3>Weekly Trends by Category</h3>
                <div className="analytics-sparklines">
                  {sparklineData.map(({ category, data }) => (
                    <div key={category} className="analytics-sparkline-card">
                      <h4>{formatCategoryLabel(category)}</h4>
                      <ResponsiveContainer width="100%" height={80}>
                        <LineChart data={data}>
                          <Line
                            type="monotone"
                            dataKey="count"
                            stroke={CATEGORY_COLORS[category] || '#94a3b8'}
                            strokeWidth={2}
                            dot={false}
                          />
                          <Tooltip
                            formatter={(value) => [value, 'items']}
                            labelFormatter={(label) => `Week ${label}`}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
