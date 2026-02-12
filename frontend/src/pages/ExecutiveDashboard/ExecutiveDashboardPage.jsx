import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { formatDistanceToNow, parseISO } from 'date-fns';
import { apiClient } from '../../api/auth';
import './ExecutiveDashboardPage.css';

function getInitials(name) {
  if (!name) return '?';
  return name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
}

function formatActivityDate(iso) {
  if (!iso) return 'Unknown date';
  try {
    return formatDistanceToNow(parseISO(iso), { addSuffix: true });
  } catch {
    return 'Unknown date';
  }
}

function getSentimentColor(sentiment) {
  const colors = { positive: '#10b981', negative: '#ef4444', neutral: '#6b7280' };
  return colors[sentiment] || '#6b7280';
}

function getPriorityLabel(score) {
  if (!score && score !== 0) return null;
  if (score >= 0.8) return 'High';
  if (score >= 0.6) return 'Medium';
  return 'Low';
}

export default function ExecutiveDashboardPage() {
  const { executiveId } = useParams();
  const navigate = useNavigate();

  // Data state
  const [profile, setProfile] = useState(null);
  const [activity, setActivity] = useState(null);
  const [connections, setConnections] = useState(null);
  const [talkingPoints, setTalkingPoints] = useState(null);
  const [customers, setCustomers] = useState([]);
  const [customerId, setCustomerId] = useState('');

  // Loading state per section
  const [sectionLoading, setSectionLoading] = useState({
    profile: false,
    activity: false,
    connections: false,
    talkingPoints: false,
  });
  const [error, setError] = useState(null);
  const [activityDays, setActivityDays] = useState(90);

  const setLoading = (section, value) => {
    setSectionLoading(prev => ({ ...prev, [section]: value }));
  };

  const fetchActivity = useCallback(async (days) => {
    setLoading('activity', true);
    try {
      const response = await apiClient.get(`/executives/${executiveId}/activity`, {
        params: { days },
      });
      setActivity(response.data);
    } catch (err) {
      console.error('Error fetching activity:', err);
    } finally {
      setLoading('activity', false);
    }
  }, [executiveId]);

  useEffect(() => {
    if (!executiveId) return;

    const fetchData = async () => {
      setError(null);
      setSectionLoading({ profile: true, activity: true, connections: true, talkingPoints: false });

      const [profileRes, activityRes, connectionsRes] = await Promise.allSettled([
        apiClient.get(`/executives/${executiveId}/profile`),
        apiClient.get(`/executives/${executiveId}/activity`, { params: { days: activityDays } }),
        apiClient.get(`/executives/${executiveId}/connections`),
      ]);

      if (profileRes.status === 'fulfilled') {
        setProfile(profileRes.value.data);
      } else {
        setError(profileRes.reason?.response?.data?.detail || 'Failed to load executive profile');
      }
      setLoading('profile', false);

      if (activityRes.status === 'fulfilled') {
        setActivity(activityRes.value.data);
      }
      setLoading('activity', false);

      if (connectionsRes.status === 'fulfilled') {
        setConnections(connectionsRes.value.data);
      }
      setLoading('connections', false);
    };

    fetchData();

    // Fetch customers for talking points dropdown
    apiClient.get('/customers').then(res => setCustomers(res.data)).catch(() => {});
  }, [executiveId]);

  // Re-fetch activity when days changes (but not on initial load)
  useEffect(() => {
    if (!executiveId || !activity) return;
    fetchActivity(activityDays);
  }, [activityDays]);

  const generateTalkingPoints = async () => {
    if (!customerId) return;
    setLoading('talkingPoints', true);
    setTalkingPoints(null);
    try {
      const response = await apiClient.post(
        `/executives/${executiveId}/talking-points`,
        null,
        { params: { customer_id: customerId } }
      );
      setTalkingPoints(response.data);
    } catch (err) {
      console.error('Error generating talking points:', err);
    } finally {
      setLoading('talkingPoints', false);
    }
  };

  // Error view
  if (error && !profile) {
    return (
      <div className="exec-dashboard">
        <div className="exec-error-container">
          <h2>Error Loading Profile</h2>
          <p>{error}</p>
          <button onClick={() => navigate('/analytics')} className="exec-btn-primary">
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  // Loading view (initial load, profile not yet available)
  if (sectionLoading.profile && !profile) {
    return (
      <div className="exec-dashboard">
        <div className="exec-loading-container">
          <div className="exec-spinner"></div>
          <p>Loading executive profile...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="exec-dashboard">
      {/* Header */}
      <div className="exec-header">
        <div className="exec-header-left">
          <button onClick={() => navigate('/analytics')} className="exec-btn-back">
            Back to Dashboard
          </button>
          <h1>Executive Relationship Dashboard</h1>
        </div>
        <div className="exec-header-right">
          <label htmlFor="customer-select" className="exec-customer-label">Customer Context:</label>
          <select
            id="customer-select"
            value={customerId}
            onChange={(e) => setCustomerId(e.target.value)}
            className="exec-customer-select"
          >
            <option value="">Select customer...</option>
            {customers.map(c => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Dashboard Grid */}
      <div className="exec-grid">
        {/* Left Column */}
        <div className="exec-grid-col">
          {/* Profile Card */}
          <div className="exec-card">
            <div className="exec-card-header">
              <h2>Profile</h2>
            </div>
            {profile ? (
              <div className="exec-profile">
                <div className="exec-profile-top">
                  <div className="exec-avatar">{getInitials(profile.name)}</div>
                  <div className="exec-profile-info">
                    <h3 className="exec-profile-name">{profile.name}</h3>
                    {profile.title && <p className="exec-profile-title">{profile.title}</p>}
                    {profile.company && <p className="exec-profile-company">{profile.company}</p>}
                    {profile.location && <p className="exec-profile-location">{profile.location}</p>}
                    {profile.linkedin_url && (
                      <a
                        href={profile.linkedin_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="exec-linkedin-link"
                      >
                        LinkedIn Profile
                      </a>
                    )}
                  </div>
                </div>

                {profile.current_focus && profile.current_focus.length > 0 && (
                  <div className="exec-tags-section">
                    <h4>Current Focus</h4>
                    <div className="exec-tags">
                      {profile.current_focus.map((tag, i) => (
                        <span key={i} className="exec-tag exec-tag-focus">{tag}</span>
                      ))}
                    </div>
                  </div>
                )}

                {profile.interests && profile.interests.length > 0 && (
                  <div className="exec-tags-section">
                    <h4>Interests</h4>
                    <div className="exec-tags">
                      {profile.interests.map((tag, i) => (
                        <span key={i} className="exec-tag exec-tag-interest">{tag}</span>
                      ))}
                    </div>
                  </div>
                )}

                {profile.background && profile.background.length > 0 && (
                  <div className="exec-background">
                    <h4>Background</h4>
                    <div className="exec-timeline">
                      {profile.background.map((item, i) => (
                        <div key={i} className="exec-timeline-item">
                          <div className="exec-timeline-dot"></div>
                          <div className="exec-timeline-content">
                            <p className="exec-timeline-role">{item.role}</p>
                            <p className="exec-timeline-company">{item.company}</p>
                            {(item.start_date || item.end_date) && (
                              <p className="exec-timeline-dates">
                                {item.start_date || '?'} &mdash; {item.end_date || 'Present'}
                              </p>
                            )}
                            {item.description && (
                              <p className="exec-timeline-desc">{item.description}</p>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <p className="exec-empty">No profile data available.</p>
            )}
          </div>

          {/* Connections Card */}
          <div className="exec-card">
            <div className="exec-card-header">
              <h2>Connections</h2>
              {connections && (
                <span className="exec-count-badge">{connections.total_paths} paths</span>
              )}
            </div>
            {sectionLoading.connections ? (
              <div className="exec-section-loading"><div className="exec-spinner-sm"></div></div>
            ) : connections && connections.connection_paths && connections.connection_paths.length > 0 ? (
              <div className="exec-connections-list">
                {connections.connection_paths.map((conn, i) => (
                  <div key={i} className="exec-connection-item">
                    <div className="exec-connection-top">
                      <div className="exec-connection-info">
                        <p className="exec-connection-name">{conn.mutual_connection_name}</p>
                        {conn.mutual_connection_title && (
                          <p className="exec-connection-title">{conn.mutual_connection_title}</p>
                        )}
                        {conn.mutual_connection_company && (
                          <p className="exec-connection-company">{conn.mutual_connection_company}</p>
                        )}
                      </div>
                      <span
                        className="exec-strength-badge"
                        data-strength={conn.relationship_strength}
                      >
                        {conn.relationship_strength}
                      </span>
                    </div>
                    {conn.introduction_context && (
                      <p className="exec-connection-context">{conn.introduction_context}</p>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="exec-empty">No connection paths found.</p>
            )}
          </div>
        </div>

        {/* Right Column */}
        <div className="exec-grid-col">
          {/* Activity Card */}
          <div className="exec-card">
            <div className="exec-card-header">
              <h2>Activity</h2>
              <div className="exec-activity-controls">
                {activity && (
                  <span className="exec-count-badge">{activity.total_count} items</span>
                )}
                <select
                  value={activityDays}
                  onChange={(e) => setActivityDays(Number(e.target.value))}
                  className="exec-days-select"
                >
                  <option value={30}>Last 30 days</option>
                  <option value={90}>Last 90 days</option>
                  <option value={180}>Last 180 days</option>
                  <option value={365}>Last year</option>
                </select>
              </div>
            </div>
            {sectionLoading.activity ? (
              <div className="exec-section-loading"><div className="exec-spinner-sm"></div></div>
            ) : activity && activity.activities && activity.activities.length > 0 ? (
              <div className="exec-activity-list">
                {activity.activities.map((item, i) => (
                  <div key={i} className="exec-activity-item">
                    <div className="exec-activity-top">
                      <span className="exec-activity-date">{formatActivityDate(item.date)}</span>
                      <span className="exec-type-badge" data-type={item.activity_type}>
                        {item.activity_type}
                      </span>
                    </div>
                    <p className="exec-activity-title">{item.title}</p>
                    {item.content && <p className="exec-activity-content">{item.content}</p>}
                    <div className="exec-activity-meta">
                      <span className="exec-activity-source">{item.source}</span>
                      {item.sentiment && (
                        <span
                          className="exec-sentiment-badge"
                          style={{ color: getSentimentColor(item.sentiment) }}
                        >
                          {item.sentiment}
                        </span>
                      )}
                      {getPriorityLabel(item.priority_score) && (
                        <span className={`exec-priority-badge exec-priority-${getPriorityLabel(item.priority_score).toLowerCase()}`}>
                          {getPriorityLabel(item.priority_score)} Priority
                        </span>
                      )}
                      {item.url && (
                        <a href={item.url} target="_blank" rel="noopener noreferrer" className="exec-source-link">
                          View Source
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="exec-empty">No activity found for the last {activityDays} days.</p>
            )}
          </div>

          {/* Talking Points Card */}
          <div className="exec-card">
            <div className="exec-card-header">
              <h2>Talking Points</h2>
            </div>
            {!customerId ? (
              <p className="exec-empty">Select a customer above to generate talking points.</p>
            ) : (
              <div className="exec-talking-points">
                <div className="exec-tp-actions">
                  <button
                    onClick={generateTalkingPoints}
                    className="exec-btn-primary"
                    disabled={sectionLoading.talkingPoints}
                  >
                    {sectionLoading.talkingPoints
                      ? 'Generating...'
                      : talkingPoints
                        ? 'Regenerate'
                        : 'Generate Talking Points'}
                  </button>
                </div>

                {sectionLoading.talkingPoints && (
                  <div className="exec-section-loading"><div className="exec-spinner-sm"></div></div>
                )}

                {talkingPoints && !sectionLoading.talkingPoints && (
                  <div className="exec-tp-results">
                    {talkingPoints.ice_breakers && talkingPoints.ice_breakers.length > 0 && (
                      <div className="exec-tp-section">
                        <h4>Ice Breakers</h4>
                        <ul className="exec-tp-list">
                          {talkingPoints.ice_breakers.map((item, i) => (
                            <li key={i}>{item}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {talkingPoints.discussion_topics && talkingPoints.discussion_topics.length > 0 && (
                      <div className="exec-tp-section">
                        <h4>Discussion Topics</h4>
                        <div className="exec-tp-topics">
                          {talkingPoints.discussion_topics.map((topic, i) => (
                            <div key={i} className="exec-tp-topic-card">
                              <h5>{topic.topic}</h5>
                              {topic.context && <p className="exec-tp-context">{topic.context}</p>}
                              {topic.suggested_approach && (
                                <p className="exec-tp-approach">
                                  <strong>Approach:</strong> {topic.suggested_approach}
                                </p>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {talkingPoints.competitive_intelligence && talkingPoints.competitive_intelligence.length > 0 && (
                      <div className="exec-tp-section">
                        <h4>Competitive Intelligence</h4>
                        <ul className="exec-tp-list">
                          {talkingPoints.competitive_intelligence.map((item, i) => (
                            <li key={i}>{item}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {talkingPoints.action_items && talkingPoints.action_items.length > 0 && (
                      <div className="exec-tp-section">
                        <h4>Action Items</h4>
                        <ul className="exec-tp-list exec-tp-actions-list">
                          {talkingPoints.action_items.map((item, i) => (
                            <li key={i}>{item}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
