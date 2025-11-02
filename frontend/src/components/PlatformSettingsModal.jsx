import { useState, useEffect } from 'react';
import axios from 'axios';
import './PlatformSettingsModal.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Default prompt templates
const PROMPT_TEMPLATES = {
  standard: {
    name: 'Standard Briefing',
    description: 'Balanced overview of all intelligence',
    prompt: `Generate a concise daily briefing summarizing the key intelligence collected today. Focus on:
- Most important developments
- Emerging trends and patterns
- Notable competitor activities
- Strategic opportunities and risks

Keep the summary professional, actionable, and under 300 words.`
  },
  executive: {
    name: 'Executive Summary',
    description: 'High-level, strategic overview',
    prompt: `Create an executive-level daily briefing focused on strategic implications. Emphasize:
- Critical business impacts
- Strategic opportunities
- Major competitive movements
- Key risks and threats

Use concise, executive language. Maximum 200 words.`
  },
  sales: {
    name: 'Sales-Focused',
    description: 'Opportunities, leads, market signals',
    prompt: `Generate a sales-focused daily briefing highlighting:
- New business opportunities
- Potential leads and prospects
- Market signals and buying intent
- Competitor weaknesses to exploit
- Customer needs and pain points

Frame insights for sales action. Under 300 words.`
  },
  risk: {
    name: 'Risk & Threats',
    description: 'Competitive threats, regulatory issues',
    prompt: `Create a risk-focused daily briefing covering:
- Competitive threats and aggressive moves
- Regulatory changes and compliance issues
- Market disruptions
- Reputational risks
- Strategic vulnerabilities

Prioritize actionable risk mitigation. Maximum 300 words.`
  },
  technical: {
    name: 'Technical/Product',
    description: 'Technology trends, product updates',
    prompt: `Generate a technical daily briefing focusing on:
- Technology trends and innovations
- Product launches and updates
- Technical capabilities of competitors
- Engineering insights
- Technology stack changes

Use technical language appropriate for engineering teams. Under 300 words.`
  },
  custom: {
    name: 'Custom Template',
    description: 'Define your own prompt',
    prompt: ''
  }
};

export default function PlatformSettingsModal({ onClose, onSave }) {
  const [activeTab, setActiveTab] = useState('briefing');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  // Daily Briefing Settings
  const [selectedTemplate, setSelectedTemplate] = useState('standard');
  const [customPrompt, setCustomPrompt] = useState('');
  const [briefingLength, setBriefingLength] = useState('standard'); // brief, standard, detailed
  const [briefingTone, setBriefingTone] = useState('professional'); // casual, professional, technical
  const [focusAreas, setFocusAreas] = useState({
    competitive_intel: true,
    opportunities: true,
    risks: true,
    trends: true,
    product_updates: true,
    market_changes: true
  });

  // AI Configuration Settings
  const [aiModel, setAiModel] = useState('claude-3-5-sonnet-20241022');
  const [embeddingModel, setEmbeddingModel] = useState('sentence-transformers/all-MiniLM-L6-v2');

  // Collection & Retention Settings
  const [hourlyCollectionEnabled, setHourlyCollectionEnabled] = useState(true);
  const [dailyCollectionEnabled, setDailyCollectionEnabled] = useState(true);
  const [dailyCollectionHour, setDailyCollectionHour] = useState(10);
  const [retentionDays, setRetentionDays] = useState(90);

  // Clustering Settings
  const [clusteringEnabled, setClusteringEnabled] = useState(true);
  const [similarityThreshold, setSimilarityThreshold] = useState(0.50);
  const [timeWindowHours, setTimeWindowHours] = useState(96);

  // Reddit Collector Settings
  const [redditMinUpvotes, setRedditMinUpvotes] = useState(5);
  const [redditMinComments, setRedditMinComments] = useState(3);
  const [redditLargeThreadThreshold, setRedditLargeThreadThreshold] = useState(10);
  const [redditMaxCommentsAnalyze, setRedditMaxCommentsAnalyze] = useState(15);
  const [redditPostsPerSubreddit, setRedditPostsPerSubreddit] = useState(10);
  const [redditLookbackDays, setRedditLookbackDays] = useState(7);

  // Load settings on mount
  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API_URL}/api/settings/platform`);
      const settings = response.data;

      // Daily Briefing Settings
      if (settings.daily_briefing) {
        setSelectedTemplate(settings.daily_briefing.template || 'standard');
        setCustomPrompt(settings.daily_briefing.custom_prompt || '');
        setBriefingLength(settings.daily_briefing.length || 'standard');
        setBriefingTone(settings.daily_briefing.tone || 'professional');
        setFocusAreas(settings.daily_briefing.focus_areas || focusAreas);
      }

      // AI Configuration
      if (settings.ai_config) {
        setAiModel(settings.ai_config.model || 'claude-3-5-sonnet-20241022');
        setEmbeddingModel(settings.ai_config.embedding_model || 'sentence-transformers/all-MiniLM-L6-v2');
      }

      // Collection & Retention Settings
      if (settings.collection_config) {
        setHourlyCollectionEnabled(settings.collection_config.hourly_enabled !== undefined ? settings.collection_config.hourly_enabled : true);
        setDailyCollectionEnabled(settings.collection_config.daily_enabled !== undefined ? settings.collection_config.daily_enabled : true);
        setDailyCollectionHour(settings.collection_config.daily_hour || 10);
        setRetentionDays(settings.collection_config.retention_days || 90);
      }

      // Clustering Settings
      if (settings.clustering_config) {
        setClusteringEnabled(settings.clustering_config.enabled !== undefined ? settings.clustering_config.enabled : true);
        setSimilarityThreshold(settings.clustering_config.similarity_threshold || 0.50);
        setTimeWindowHours(settings.clustering_config.time_window_hours || 96);
      }

      // Reddit Collector Settings
      if (settings.collector_config?.reddit) {
        const reddit = settings.collector_config.reddit;
        setRedditMinUpvotes(reddit.min_upvotes || 5);
        setRedditMinComments(reddit.min_comments || 3);
        setRedditLargeThreadThreshold(reddit.large_thread_threshold || 10);
        setRedditMaxCommentsAnalyze(reddit.max_comments_analyze || 15);
        setRedditPostsPerSubreddit(reddit.posts_per_subreddit || 10);
        setRedditLookbackDays(reddit.lookback_days || 7);
      }
    } catch (err) {
      console.error('Failed to load settings:', err);
      // Not critical, use defaults
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);

    try {
      const settings = {
        daily_briefing: {
          template: selectedTemplate,
          custom_prompt: selectedTemplate === 'custom' ? customPrompt : '',
          length: briefingLength,
          tone: briefingTone,
          focus_areas: focusAreas,
          prompt: selectedTemplate === 'custom' ? customPrompt : PROMPT_TEMPLATES[selectedTemplate].prompt
        },
        ai_config: {
          model: aiModel,
          embedding_model: embeddingModel
        },
        collection_config: {
          hourly_enabled: hourlyCollectionEnabled,
          daily_enabled: dailyCollectionEnabled,
          daily_hour: dailyCollectionHour,
          retention_days: retentionDays
        },
        clustering_config: {
          enabled: clusteringEnabled,
          similarity_threshold: similarityThreshold,
          time_window_hours: timeWindowHours
        },
        collector_config: {
          reddit: {
            min_upvotes: redditMinUpvotes,
            min_comments: redditMinComments,
            large_thread_threshold: redditLargeThreadThreshold,
            max_comments_analyze: redditMaxCommentsAnalyze,
            posts_per_subreddit: redditPostsPerSubreddit,
            lookback_days: redditLookbackDays
          }
        }
      };

      await axios.put(`${API_URL}/api/settings/platform`, settings);

      if (onSave) {
        onSave();
      }
      onClose();
    } catch (err) {
      console.error('Failed to save settings:', err);
      setError(err.response?.data?.detail || 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  const getCurrentPrompt = () => {
    if (selectedTemplate === 'custom') {
      return customPrompt;
    }
    return PROMPT_TEMPLATES[selectedTemplate]?.prompt || '';
  };

  const toggleFocusArea = (area) => {
    setFocusAreas({
      ...focusAreas,
      [area]: !focusAreas[area]
    });
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="settings-modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Platform Settings</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        {error && (
          <div className="modal-error">
            ⚠️ {error}
          </div>
        )}

        {/* Tab Navigation */}
        <div className="settings-tabs">
          <button
            className={`settings-tab ${activeTab === 'briefing' ? 'active' : ''}`}
            onClick={() => setActiveTab('briefing')}
          >
            Daily Briefing
          </button>
          <button
            className={`settings-tab ${activeTab === 'ai' ? 'active' : ''}`}
            onClick={() => setActiveTab('ai')}
          >
            AI Configuration
          </button>
          <button
            className={`settings-tab ${activeTab === 'collection' ? 'active' : ''}`}
            onClick={() => setActiveTab('collection')}
          >
            Collection & Retention
          </button>
          <button
            className={`settings-tab ${activeTab === 'collectors' ? 'active' : ''}`}
            onClick={() => setActiveTab('collectors')}
          >
            Collector Settings
          </button>
        </div>

        <div className="settings-content">
          {loading ? (
            <div className="settings-loading">Loading settings...</div>
          ) : (
            <>
              {/* Daily Briefing Tab */}
              {activeTab === 'briefing' && (
                <div className="settings-section">
                  <h3>Daily Briefing Configuration</h3>
                  <p className="settings-description">
                    Customize how AI generates your daily intelligence summaries
                  </p>

                  {/* Template Selection */}
                  <div className="form-section">
                    <label className="section-label">Prompt Template</label>
                    <div className="template-grid">
                      {Object.entries(PROMPT_TEMPLATES).map(([key, template]) => (
                        <button
                          key={key}
                          className={`template-card ${selectedTemplate === key ? 'selected' : ''}`}
                          onClick={() => setSelectedTemplate(key)}
                        >
                          <div className="template-name">{template.name}</div>
                          <div className="template-description">{template.description}</div>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Custom Prompt Editor */}
                  {selectedTemplate === 'custom' && (
                    <div className="form-section">
                      <label className="section-label">Custom Prompt</label>
                      <textarea
                        className="custom-prompt-editor"
                        value={customPrompt}
                        onChange={(e) => setCustomPrompt(e.target.value)}
                        placeholder="Enter your custom prompt for daily briefing generation..."
                        rows="10"
                      />
                    </div>
                  )}

                  {/* Prompt Preview */}
                  <div className="form-section">
                    <label className="section-label">Current Prompt</label>
                    <div className="prompt-preview">
                      {getCurrentPrompt() || 'No prompt defined'}
                    </div>
                  </div>

                  {/* Briefing Options */}
                  <div className="form-section">
                    <label className="section-label">Briefing Style</label>
                    <div className="option-row">
                      <div className="option-group">
                        <label>Length</label>
                        <select
                          value={briefingLength}
                          onChange={(e) => setBriefingLength(e.target.value)}
                          className="settings-select"
                        >
                          <option value="brief">Brief (~150 words)</option>
                          <option value="standard">Standard (~300 words)</option>
                          <option value="detailed">Detailed (~500 words)</option>
                        </select>
                      </div>
                      <div className="option-group">
                        <label>Tone</label>
                        <select
                          value={briefingTone}
                          onChange={(e) => setBriefingTone(e.target.value)}
                          className="settings-select"
                        >
                          <option value="casual">Casual</option>
                          <option value="professional">Professional</option>
                          <option value="technical">Technical</option>
                        </select>
                      </div>
                    </div>
                  </div>

                  {/* Focus Areas */}
                  <div className="form-section">
                    <label className="section-label">Focus Areas</label>
                    <p className="section-help">Select which aspects to emphasize in daily briefings</p>
                    <div className="focus-areas-grid">
                      {Object.entries(focusAreas).map(([key, enabled]) => (
                        <label key={key} className="focus-area-checkbox">
                          <input
                            type="checkbox"
                            checked={enabled}
                            onChange={() => toggleFocusArea(key)}
                          />
                          <span>{key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* AI Configuration Tab */}
              {activeTab === 'ai' && (
                <div className="settings-section">
                  <h3>AI Configuration</h3>
                  <p className="settings-description">
                    Configure AI models used for intelligence processing
                  </p>

                  <div className="form-section">
                    <label className="section-label">Claude Model</label>
                    <p className="section-help">Model used for content analysis and summarization</p>
                    <select
                      value={aiModel}
                      onChange={(e) => setAiModel(e.target.value)}
                      className="settings-select"
                    >
                      <option value="claude-3-5-sonnet-20241022">Claude 3.5 Sonnet (Latest)</option>
                      <option value="claude-3-5-sonnet-20240620">Claude 3.5 Sonnet (June 2024)</option>
                      <option value="claude-3-opus-20240229">Claude 3 Opus</option>
                      <option value="claude-3-haiku-20240307">Claude 3 Haiku (Faster)</option>
                    </select>
                  </div>

                  <div className="form-section">
                    <label className="section-label">Embedding Model</label>
                    <p className="section-help">Model used for semantic search and clustering</p>
                    <select
                      value={embeddingModel}
                      onChange={(e) => setEmbeddingModel(e.target.value)}
                      className="settings-select"
                    >
                      <option value="sentence-transformers/all-MiniLM-L6-v2">MiniLM-L6-v2 (Fast, Good)</option>
                      <option value="sentence-transformers/all-mpnet-base-v2">MPNet-Base-v2 (Better, Slower)</option>
                      <option value="BAAI/bge-small-en-v1.5">BGE-Small (Balanced)</option>
                    </select>
                  </div>

                  <div className="settings-warning">
                    <strong>Note:</strong> Changing AI models may affect the quality and cost of intelligence processing.
                    Changing the embedding model will require rebuilding the vector store.
                  </div>
                </div>
              )}

              {/* Collection & Retention Tab */}
              {activeTab === 'collection' && (
                <div className="settings-section">
                  <h3>Collection & Retention Configuration</h3>
                  <p className="settings-description">
                    Configure automated collection schedules and data retention policies
                  </p>

                  {/* Collection Schedules */}
                  <div className="form-section">
                    <label className="section-label">Collection Schedules</label>
                    <p className="section-help">Configure when intelligence collection runs automatically</p>

                    <div className="collection-schedule-group">
                      <label className="schedule-option">
                        <input
                          type="checkbox"
                          checked={hourlyCollectionEnabled}
                          onChange={(e) => setHourlyCollectionEnabled(e.target.checked)}
                        />
                        <div className="schedule-info">
                          <div className="schedule-name">Hourly Collection</div>
                          <div className="schedule-description">
                            Run lightweight collection every hour (news, social media, RSS)
                          </div>
                        </div>
                      </label>

                      <label className="schedule-option">
                        <input
                          type="checkbox"
                          checked={dailyCollectionEnabled}
                          onChange={(e) => setDailyCollectionEnabled(e.target.checked)}
                        />
                        <div className="schedule-info">
                          <div className="schedule-name">Daily Comprehensive Collection</div>
                          <div className="schedule-description">
                            Run full collection with all sources and deep processing
                          </div>
                        </div>
                      </label>
                    </div>

                    {dailyCollectionEnabled && (
                      <div className="option-group" style={{ marginTop: '16px' }}>
                        <label>Daily Collection Time (24-hour format)</label>
                        <select
                          value={dailyCollectionHour}
                          onChange={(e) => setDailyCollectionHour(parseInt(e.target.value))}
                          className="settings-select"
                        >
                          {[...Array(24)].map((_, hour) => (
                            <option key={hour} value={hour}>
                              {hour.toString().padStart(2, '0')}:00 ({hour === 0 ? 'Midnight' : hour === 12 ? 'Noon' : hour > 12 ? `${hour - 12} PM` : `${hour} AM`})
                            </option>
                          ))}
                        </select>
                      </div>
                    )}
                  </div>

                  {/* Data Retention */}
                  <div className="form-section">
                    <label className="section-label">Data Retention</label>
                    <p className="section-help">How long to keep intelligence items before automatic deletion</p>

                    <div className="option-group">
                      <label>Retention Period</label>
                      <select
                        value={retentionDays}
                        onChange={(e) => setRetentionDays(parseInt(e.target.value))}
                        className="settings-select"
                      >
                        <option value={30}>30 days</option>
                        <option value={60}>60 days</option>
                        <option value={90}>90 days (Recommended)</option>
                        <option value={180}>180 days (6 months)</option>
                        <option value={365}>365 days (1 year)</option>
                      </select>
                      <p className="option-help">
                        Intelligence items older than {retentionDays} days will be automatically purged daily at midnight
                      </p>
                    </div>
                  </div>

                  <div className="settings-warning">
                    <strong>Note:</strong> Collection schedule changes take effect immediately. The scheduler will be updated
                    on the next scheduled run. Reducing retention period will not immediately delete old data - purge runs daily at midnight.
                  </div>

                  {/* Clustering Configuration */}
                  <div className="form-section" style={{ marginTop: '32px', paddingTop: '24px', borderTop: '1px solid #e5e7eb' }}>
                    <label className="section-label">Story Clustering</label>
                    <p className="section-help">Configure intelligent deduplication to group similar stories from different sources</p>

                    <label className="schedule-option">
                      <input
                        type="checkbox"
                        checked={clusteringEnabled}
                        onChange={(e) => setClusteringEnabled(e.target.checked)}
                      />
                      <div className="schedule-info">
                        <div className="schedule-name">Enable Story Clustering</div>
                        <div className="schedule-description">
                          Automatically group similar intelligence items from different sources into clusters
                        </div>
                      </div>
                    </label>

                    {clusteringEnabled && (
                      <>
                        <div className="option-group" style={{ marginTop: '16px' }}>
                          <label>Similarity Threshold: {(similarityThreshold * 100).toFixed(0)}%</label>
                          <input
                            type="range"
                            min="0.30"
                            max="0.80"
                            step="0.05"
                            value={similarityThreshold}
                            onChange={(e) => setSimilarityThreshold(parseFloat(e.target.value))}
                            className="similarity-slider"
                          />
                          <p className="option-help">
                            {similarityThreshold < 0.4 && "Lower threshold - more aggressive clustering (may group unrelated items)"}
                            {similarityThreshold >= 0.4 && similarityThreshold <= 0.6 && "Balanced - recommended for most use cases"}
                            {similarityThreshold > 0.6 && "Higher threshold - conservative clustering (may miss similar items)"}
                          </p>
                        </div>

                        <div className="option-group">
                          <label>Time Window</label>
                          <select
                            value={timeWindowHours}
                            onChange={(e) => setTimeWindowHours(parseInt(e.target.value))}
                            className="settings-select"
                          >
                            <option value={24}>24 hours (1 day)</option>
                            <option value={48}>48 hours (2 days)</option>
                            <option value={72}>72 hours (3 days)</option>
                            <option value={96}>96 hours (4 days) - Recommended</option>
                            <option value={168}>168 hours (7 days)</option>
                          </select>
                          <p className="option-help">
                            How far back to look when clustering new items with existing stories
                          </p>
                        </div>
                      </>
                    )}
                  </div>
                </div>
              )}

              {/* Collector Settings Tab */}
              {activeTab === 'collectors' && (
                <div className="settings-section">
                  <h3>Collector-Specific Settings</h3>
                  <p className="settings-description">
                    Fine-tune individual data collectors for optimal quality and performance
                  </p>

                  {/* Reddit Collector Settings */}
                  <div className="collector-section">
                    <div className="collector-header">
                      <h4>Reddit Collector</h4>
                      <p className="collector-description">
                        Monitor subreddit discussions with engagement filtering and AI-powered thread summarization
                      </p>
                    </div>

                    <div className="form-section">
                      <label className="section-label">Engagement Filters</label>
                      <p className="section-help">Minimum thresholds to filter low-quality posts</p>

                      <div className="option-row">
                        <div className="option-group">
                          <label>Minimum Upvotes</label>
                          <input
                            type="number"
                            min="0"
                            max="100"
                            value={redditMinUpvotes}
                            onChange={(e) => setRedditMinUpvotes(parseInt(e.target.value))}
                            className="settings-input"
                          />
                          <p className="option-help">Posts must have at least this many upvotes</p>
                        </div>

                        <div className="option-group">
                          <label>Minimum Comments</label>
                          <input
                            type="number"
                            min="0"
                            max="50"
                            value={redditMinComments}
                            onChange={(e) => setRedditMinComments(parseInt(e.target.value))}
                            className="settings-input"
                          />
                          <p className="option-help">Posts must have at least this many comments</p>
                        </div>
                      </div>
                    </div>

                    <div className="form-section">
                      <label className="section-label">AI Summarization</label>
                      <p className="section-help">Configure when and how to summarize large discussions</p>

                      <div className="option-row">
                        <div className="option-group">
                          <label>Large Thread Threshold</label>
                          <input
                            type="number"
                            min="5"
                            max="50"
                            value={redditLargeThreadThreshold}
                            onChange={(e) => setRedditLargeThreadThreshold(parseInt(e.target.value))}
                            className="settings-input"
                          />
                          <p className="option-help">Trigger AI summarization when thread has this many comments</p>
                        </div>

                        <div className="option-group">
                          <label>Max Comments to Analyze</label>
                          <input
                            type="number"
                            min="5"
                            max="50"
                            value={redditMaxCommentsAnalyze}
                            onChange={(e) => setRedditMaxCommentsAnalyze(parseInt(e.target.value))}
                            className="settings-input"
                          />
                          <p className="option-help">Number of top comments to include in AI analysis</p>
                        </div>
                      </div>
                    </div>

                    <div className="form-section">
                      <label className="section-label">Collection Limits</label>
                      <p className="section-help">Control volume and scope of collection</p>

                      <div className="option-row">
                        <div className="option-group">
                          <label>Posts Per Subreddit</label>
                          <input
                            type="number"
                            min="1"
                            max="50"
                            value={redditPostsPerSubreddit}
                            onChange={(e) => setRedditPostsPerSubreddit(parseInt(e.target.value))}
                            className="settings-input"
                          />
                          <p className="option-help">Maximum posts to collect from each subreddit</p>
                        </div>

                        <div className="option-group">
                          <label>Lookback Days</label>
                          <select
                            value={redditLookbackDays}
                            onChange={(e) => setRedditLookbackDays(parseInt(e.target.value))}
                            className="settings-select"
                          >
                            <option value={1}>1 day</option>
                            <option value={3}>3 days</option>
                            <option value={7}>7 days (Recommended)</option>
                            <option value={14}>14 days</option>
                            <option value={30}>30 days</option>
                          </select>
                          <p className="option-help">How far back to search for relevant posts</p>
                        </div>
                      </div>
                    </div>

                    <div className="settings-warning">
                      <strong>Performance Note:</strong> Lower engagement thresholds and higher limits will collect more data
                      but may increase noise. Higher AI summarization thresholds reduce API costs.
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        <div className="modal-footer">
          <button
            type="button"
            onClick={onClose}
            className="btn-cancel"
            disabled={saving}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            className="btn-save"
            disabled={saving || loading}
          >
            {saving ? 'Saving...' : 'Save Settings'}
          </button>
        </div>
      </div>
    </div>
  );
}
