import { useState, useEffect } from 'react';
import { apiClient } from '../api/auth';
import './PlatformSettingsModal.css';

// Persona name mappings for display (fallback if API doesn't provide names)
const PERSONA_DISPLAY_NAMES = {
  executive: 'Executive Summary',
  technical: 'Technical Analysis',
  sales: 'Sales Intelligence',
  analyst: 'Analytical Report',
  brief: 'Brief Bullets',
  custom: 'Custom Template'
};

// Persona description mappings for display (fallback if API doesn't provide descriptions)
const PERSONA_DESCRIPTIONS = {
  executive: 'High-level, strategic overview',
  technical: 'Technology trends, product updates',
  sales: 'Opportunities, leads, market signals',
  analyst: 'Data-driven insights and analysis',
  brief: 'Concise bullet-point briefing',
  custom: 'Define your own prompt'
};

export default function PlatformSettingsModal({ onClose, onSave }) {
  const [activeTab, setActiveTab] = useState('briefing');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  // Personas from template system
  const [personas, setPersonas] = useState({});
  const [personaList, setPersonaList] = useState([]);
  const [templateBased, setTemplateBased] = useState(false);

  // Daily Briefing Settings
  const [selectedTemplate, setSelectedTemplate] = useState('executive');
  const [customPrompt, setCustomPrompt] = useState('');
  const [summaryScheduleEnabled, setSummaryScheduleEnabled] = useState(false);
  const [summaryScheduleHour, setSummaryScheduleHour] = useState(8);
  const [summaryScheduleMinute, setSummaryScheduleMinute] = useState(0);
  const [summaryScheduleDays, setSummaryScheduleDays] = useState({
    mon: true,
    tue: true,
    wed: true,
    thu: true,
    fri: true,
    sat: false,
    sun: false
  });

  // AI Configuration Settings
  const [aiModel, setAiModel] = useState('claude-3-5-sonnet-20241022');
  const [aiModelCheap, setAiModelCheap] = useState('claude-3-5-haiku-20241022');
  const [embeddingModel, setEmbeddingModel] = useState('sentence-transformers/all-MiniLM-L6-v2');
  const [modelOverrideEnabled, setModelOverrideEnabled] = useState(false);
  const [envValues, setEnvValues] = useState({
    ai_model: '',
    ai_model_cheap: '',
    ai_provider: '',
    ai_provider_cheap: ''
  });

  // Collection & Retention Settings
  const [hourlyCollectionEnabled, setHourlyCollectionEnabled] = useState(true);
  const [dailyCollectionEnabled, setDailyCollectionEnabled] = useState(true);
  const [dailyCollectionHour, setDailyCollectionHour] = useState(10);
  const [retentionDays, setRetentionDays] = useState(90);
  const [collectionDays, setCollectionDays] = useState({
    mon: true,
    tue: true,
    wed: true,
    thu: true,
    fri: true,
    sat: true,
    sun: true
  });

  // Source Intervals Settings (in hours)
  const [sourceIntervals, setSourceIntervals] = useState({
    news_api: 1,
    rss: 1,
    yahoo_finance_news: 1,
    australian_news: 6,
    google_news: 6,
    twitter: 3,
    youtube: 12,
    reddit: 24,
    linkedin: 24,
    linkedin_user: 24,
    pressrelease: 12,
    web_scrape: 12
  });

  // Domain Blacklist Settings
  const [blacklistEnabled, setBlacklistEnabled] = useState(true);
  const [blacklistedDomains, setBlacklistedDomains] = useState([
    'yahoo.com',
    'msn.com',
    'aol.com',
    'bing.com',
    'pinterest.com',
    'tumblr.com'
  ]);
  const [newDomain, setNewDomain] = useState('');

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

  // YouTube Collector Settings
  const [youtubeMinViews, setYoutubeMinViews] = useState(100);
  const [youtubeMinChannelSubscribers, setYoutubeMinChannelSubscribers] = useState(1000);
  const [youtubeEnableKeywordSearch, setYoutubeEnableKeywordSearch] = useState(true);

  // LinkedIn Collector Settings
  const [linkedinScrapingStrategy, setLinkedinScrapingStrategy] = useState('conservative');
  const [linkedinDelayProfilesMin, setLinkedinDelayProfilesMin] = useState(60);
  const [linkedinDelayProfilesMax, setLinkedinDelayProfilesMax] = useState(120);
  const [linkedinDelayCustomersMin, setLinkedinDelayCustomersMin] = useState(300);
  const [linkedinDelayCustomersMax, setLinkedinDelayCustomersMax] = useState(600);

  // Australian News Sources Settings
  const [australianNewsSources, setAustralianNewsSources] = useState({
    sources: []
  });

  // Smart Feed Settings
  const [smartFeedEnabled, setSmartFeedEnabled] = useState(true);
  const [smartFeedMinPriority, setSmartFeedMinPriority] = useState(0.3);
  const [smartFeedHighPriorityThreshold, setSmartFeedHighPriorityThreshold] = useState(0.7);
  const [recencyBoostEnabled, setRecencyBoostEnabled] = useState(true);
  const [recencyBoostAmount, setRecencyBoostAmount] = useState(0.1);
  const [recencyBoostHours, setRecencyBoostHours] = useState(24);
  const [categoryPreferences, setCategoryPreferences] = useState({
    product_update: false,
    financial: true,
    market_news: false,
    competitor: true,
    challenge: true,
    opportunity: true,
    leadership: true,
    partnership: true,
    advertisement: false,
    unrelated: false,
    other: false
  });
  const [sourcePreferences, setSourcePreferences] = useState({
    linkedin: true,
    press_release: true,
    reddit: false,
    twitter: false,
    youtube: false,
    rss: true,
    google_news: false,
    yahoo_finance_news: true,
    yahoo_news: false,
    australian_news: false,
    news_api: false,
    web_scraper: false
  });
  const [diversityEnabled, setDiversityEnabled] = useState(true);
  const [maxConsecutiveSameSource, setMaxConsecutiveSameSource] = useState(3);

  // Load settings on mount
  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    setLoading(true);
    try {
      // Load personas from template system
      try {
        const personasResponse = await apiClient.get(`/settings/daily-summary-personas`);
        const personasData = personasResponse.data;
        if (personasData.template_based) {
          setPersonas(personasData.personas);
          setPersonaList(personasData.persona_list);
          setTemplateBased(true);
        }
      } catch (err) {
        console.warn('Failed to load personas from template:', err);
        // Continue with defaults
      }

      // Load AI config status (override enabled, env values)
      const aiConfigStatusResponse = await apiClient.get(`/settings/ai-config-status`);
      const aiConfigStatus = aiConfigStatusResponse.data;
      setModelOverrideEnabled(aiConfigStatus.model_override_enabled);
      setEnvValues(aiConfigStatus.env_values);

      const response = await apiClient.get(`/settings/platform`);
      const settings = response.data;

      // Daily Briefing Settings
      if (settings.daily_briefing) {
        setSelectedTemplate(settings.daily_briefing.template || 'standard');

        // Load schedule settings
        if (settings.daily_briefing.schedule) {
          setSummaryScheduleEnabled(settings.daily_briefing.schedule.enabled || false);
          setSummaryScheduleHour(settings.daily_briefing.schedule.hour || 8);
          setSummaryScheduleMinute(settings.daily_briefing.schedule.minute || 0);

          // Load days of week (default: Monday-Friday)
          if (settings.daily_briefing.schedule.days_of_week) {
            const daysArray = Array.isArray(settings.daily_briefing.schedule.days_of_week)
              ? settings.daily_briefing.schedule.days_of_week
              : settings.daily_briefing.schedule.days_of_week.split(',');

            const daysObj = {
              mon: daysArray.includes('mon'),
              tue: daysArray.includes('tue'),
              wed: daysArray.includes('wed'),
              thu: daysArray.includes('thu'),
              fri: daysArray.includes('fri'),
              sat: daysArray.includes('sat'),
              sun: daysArray.includes('sun')
            };
            setSummaryScheduleDays(daysObj);
          }
        }
        setCustomPrompt(settings.daily_briefing.custom_prompt || '');
      }

      // AI Configuration
      if (settings.ai_config) {
        setAiModel(settings.ai_config.model || 'claude-3-5-sonnet-20241022');
        setAiModelCheap(settings.ai_config.model_cheap || 'claude-3-5-haiku-20241022');
        setEmbeddingModel(settings.ai_config.embedding_model || 'sentence-transformers/all-MiniLM-L6-v2');
      }

      // Collection & Retention Settings
      if (settings.collection_config) {
        setHourlyCollectionEnabled(settings.collection_config.hourly_enabled !== undefined ? settings.collection_config.hourly_enabled : true);
        setDailyCollectionEnabled(settings.collection_config.daily_enabled !== undefined ? settings.collection_config.daily_enabled : true);
        setDailyCollectionHour(settings.collection_config.daily_hour || 10);
        setRetentionDays(settings.collection_config.retention_days || 90);

        // Load collection days (default: all days)
        if (settings.collection_config.collection_days) {
          const daysArray = Array.isArray(settings.collection_config.collection_days)
            ? settings.collection_config.collection_days
            : settings.collection_config.collection_days.split(',');

          const daysObj = {
            mon: daysArray.includes('mon'),
            tue: daysArray.includes('tue'),
            wed: daysArray.includes('wed'),
            thu: daysArray.includes('thu'),
            fri: daysArray.includes('fri'),
            sat: daysArray.includes('sat'),
            sun: daysArray.includes('sun')
          };
          setCollectionDays(daysObj);
        }

        // Domain Blacklist
        if (settings.collection_config.domain_blacklist) {
          setBlacklistEnabled(settings.collection_config.domain_blacklist.enabled !== undefined ? settings.collection_config.domain_blacklist.enabled : true);
          setBlacklistedDomains(settings.collection_config.domain_blacklist.domains || []);
        }
      }

      // Source Intervals Settings
      if (settings.source_intervals) {
        setSourceIntervals(settings.source_intervals);
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

      // YouTube Collector Settings
      if (settings.collector_config?.youtube) {
        const youtube = settings.collector_config.youtube;
        setYoutubeMinViews(youtube.min_views || 100);
        setYoutubeMinChannelSubscribers(youtube.min_channel_subscribers || 1000);
        setYoutubeEnableKeywordSearch(youtube.enable_keyword_search !== undefined ? youtube.enable_keyword_search : true);
      }

      // LinkedIn Collector Settings
      if (settings.collector_config?.linkedin) {
        const linkedin = settings.collector_config.linkedin;
        setLinkedinScrapingStrategy(linkedin.scraping_strategy || 'conservative');
        setLinkedinDelayProfilesMin(linkedin.delay_between_profiles_min || 60);
        setLinkedinDelayProfilesMax(linkedin.delay_between_profiles_max || 120);
        setLinkedinDelayCustomersMin(linkedin.delay_between_customers_min || 300);
        setLinkedinDelayCustomersMax(linkedin.delay_between_customers_max || 600);
      }

      // Australian News Sources
      if (settings.australian_news_sources) {
        setAustralianNewsSources(settings.australian_news_sources);
      }

      // Smart Feed Settings
      if (settings.smart_feed_config) {
        const sf = settings.smart_feed_config;
        setSmartFeedEnabled(sf.enabled !== undefined ? sf.enabled : true);
        setSmartFeedMinPriority(sf.min_priority || 0.3);
        setSmartFeedHighPriorityThreshold(sf.high_priority_threshold || 0.7);

        if (sf.recency_boost) {
          setRecencyBoostEnabled(sf.recency_boost.enabled !== undefined ? sf.recency_boost.enabled : true);
          setRecencyBoostAmount(sf.recency_boost.boost_amount || 0.1);
          setRecencyBoostHours(sf.recency_boost.time_threshold_hours || 24);
        }

        if (sf.category_preferences) {
          setCategoryPreferences(sf.category_preferences);
        }

        if (sf.source_preferences) {
          setSourcePreferences(sf.source_preferences);
        }

        if (sf.diversity) {
          setDiversityEnabled(sf.diversity.enabled !== undefined ? sf.diversity.enabled : true);
          setMaxConsecutiveSameSource(sf.diversity.max_consecutive_same_source || 3);
        }
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
          schedule: {
            enabled: summaryScheduleEnabled,
            hour: summaryScheduleHour,
            minute: summaryScheduleMinute,
            days_of_week: Object.keys(summaryScheduleDays).filter(day => summaryScheduleDays[day])
          }
        },
        ai_config: {
          model: aiModel,
          model_cheap: aiModelCheap,
          embedding_model: embeddingModel
        },
        collection_config: {
          hourly_enabled: hourlyCollectionEnabled,
          daily_enabled: dailyCollectionEnabled,
          daily_hour: dailyCollectionHour,
          retention_days: retentionDays,
          collection_days: Object.keys(collectionDays).filter(day => collectionDays[day]),
          domain_blacklist: {
            enabled: blacklistEnabled,
            domains: blacklistedDomains
          }
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
          },
          youtube: {
            min_views: youtubeMinViews,
            min_channel_subscribers: youtubeMinChannelSubscribers,
            enable_keyword_search: youtubeEnableKeywordSearch
          },
          linkedin: {
            scraping_strategy: linkedinScrapingStrategy,
            delay_between_profiles_min: linkedinDelayProfilesMin,
            delay_between_profiles_max: linkedinDelayProfilesMax,
            delay_between_customers_min: linkedinDelayCustomersMin,
            delay_between_customers_max: linkedinDelayCustomersMax
          }
        },
        smart_feed_config: {
          enabled: smartFeedEnabled,
          min_priority: smartFeedMinPriority,
          high_priority_threshold: smartFeedHighPriorityThreshold,
          recency_boost: {
            enabled: recencyBoostEnabled,
            boost_amount: recencyBoostAmount,
            time_threshold_hours: recencyBoostHours
          },
          category_preferences: categoryPreferences,
          source_preferences: sourcePreferences,
          diversity: {
            enabled: diversityEnabled,
            max_consecutive_same_source: maxConsecutiveSameSource
          }
        },
        source_intervals: sourceIntervals,
        australian_news_sources: australianNewsSources
      };

      await apiClient.put(`/settings/platform`, settings);

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
    // Use personas from template system if available
    if (templateBased && personas[selectedTemplate]) {
      return personas[selectedTemplate];
    }
    return '';
  };

  const toggleCategoryPreference = (category) => {
    setCategoryPreferences({
      ...categoryPreferences,
      [category]: !categoryPreferences[category]
    });
  };

  const toggleSourcePreference = (source) => {
    setSourcePreferences({
      ...sourcePreferences,
      [source]: !sourcePreferences[source]
    });
  };

  const addBlacklistedDomain = () => {
    const domain = newDomain.trim().toLowerCase();
    if (domain && !blacklistedDomains.includes(domain)) {
      setBlacklistedDomains([...blacklistedDomains, domain]);
      setNewDomain('');
    }
  };

  const removeBlacklistedDomain = (domain) => {
    setBlacklistedDomains(blacklistedDomains.filter(d => d !== domain));
  };

  const updateSourceInterval = (source, interval) => {
    setSourceIntervals({
      ...sourceIntervals,
      [source]: interval
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
          <button
            className={`settings-tab ${activeTab === 'smartfeed' ? 'active' : ''}`}
            onClick={() => setActiveTab('smartfeed')}
          >
            Smart Feed
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
                      {/* Render personas from template system if available */}
                      {templateBased && personaList.length > 0 ? (
                        <>
                          {personaList.map((key) => (
                            <button
                              key={key}
                              className={`template-card ${selectedTemplate === key ? 'selected' : ''}`}
                              onClick={() => setSelectedTemplate(key)}
                            >
                              <div className="template-name">
                                {PERSONA_DISPLAY_NAMES[key] || key.charAt(0).toUpperCase() + key.slice(1)}
                              </div>
                              <div className="template-description">
                                {PERSONA_DESCRIPTIONS[key] || 'Template-based persona'}
                              </div>
                            </button>
                          ))}
                          {/* Always include Custom option */}
                          <button
                            key="custom"
                            className={`template-card ${selectedTemplate === 'custom' ? 'selected' : ''}`}
                            onClick={() => setSelectedTemplate('custom')}
                          >
                            <div className="template-name">{PERSONA_DISPLAY_NAMES.custom}</div>
                            <div className="template-description">{PERSONA_DESCRIPTIONS.custom}</div>
                          </button>
                        </>
                      ) : (
                        <>
                          {/* Fallback: Show default personas if API not available */}
                          {Object.entries(PERSONA_DISPLAY_NAMES).map(([key, name]) => (
                            <button
                              key={key}
                              className={`template-card ${selectedTemplate === key ? 'selected' : ''}`}
                              onClick={() => setSelectedTemplate(key)}
                            >
                              <div className="template-name">{name}</div>
                              <div className="template-description">{PERSONA_DESCRIPTIONS[key]}</div>
                            </button>
                          ))}
                        </>
                      )}
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

                  {/* Automatic Summary Generation Schedule */}
                  <div className="form-section">
                    <label className="section-label">Automatic Generation Schedule</label>
                    <p className="section-help">Automatically generate daily summaries at a scheduled time</p>

                    <div className="collection-schedule-group">
                      <label className="schedule-option">
                        <input
                          type="checkbox"
                          checked={summaryScheduleEnabled}
                          onChange={(e) => setSummaryScheduleEnabled(e.target.checked)}
                        />
                        <div className="schedule-info">
                          <div className="schedule-name">Enable Automatic Daily Summary Generation</div>
                          <div className="schedule-description">
                            Generate AI summaries for all customers at the scheduled time each day
                          </div>
                        </div>
                      </label>

                      {summaryScheduleEnabled && (
                        <div style={{ marginTop: '16px', paddingLeft: '32px' }}>
                          <label className="section-label" style={{ fontSize: '14px', marginBottom: '8px' }}>
                            Generation Time
                          </label>
                          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                            <div>
                              <label style={{ fontSize: '13px', color: '#6b7280', marginBottom: '4px', display: 'block' }}>
                                Hour
                              </label>
                              <select
                                value={summaryScheduleHour}
                                onChange={(e) => setSummaryScheduleHour(parseInt(e.target.value))}
                                className="settings-select"
                                style={{ width: '100px' }}
                              >
                                {Array.from({ length: 24 }, (_, i) => (
                                  <option key={i} value={i}>
                                    {i.toString().padStart(2, '0')}:00
                                  </option>
                                ))}
                              </select>
                            </div>
                            <p className="option-help" style={{ margin: 0 }}>
                              Summaries will be generated at {summaryScheduleHour.toString().padStart(2, '0')}:{summaryScheduleMinute.toString().padStart(2, '0')} server time
                            </p>
                          </div>

                          <div style={{ marginTop: '20px' }}>
                            <label className="section-label" style={{ fontSize: '14px', marginBottom: '8px' }}>
                              Days of Week
                            </label>
                            <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                              {[
                                { key: 'mon', label: 'Monday' },
                                { key: 'tue', label: 'Tuesday' },
                                { key: 'wed', label: 'Wednesday' },
                                { key: 'thu', label: 'Thursday' },
                                { key: 'fri', label: 'Friday' },
                                { key: 'sat', label: 'Saturday' },
                                { key: 'sun', label: 'Sunday' }
                              ].map(({ key, label }) => (
                                <label key={key} className="toggle-field" style={{ flex: '0 0 auto' }}>
                                  <input
                                    type="checkbox"
                                    checked={summaryScheduleDays[key]}
                                    onChange={(e) => setSummaryScheduleDays({
                                      ...summaryScheduleDays,
                                      [key]: e.target.checked
                                    })}
                                  />
                                  <span>{label}</span>
                                </label>
                              ))}
                            </div>
                            <p className="option-help" style={{ marginTop: '8px' }}>
                              Select which days of the week to generate summaries (default: Monday-Friday)
                            </p>
                          </div>
                        </div>
                      )}
                    </div>

                    <div className="settings-info" style={{ marginTop: '12px' }}>
                      <strong>Note:</strong> When enabled, daily summaries will be automatically generated for all customers at the scheduled time.
                      You can also manually refresh summaries anytime in the Executive Summary section.
                      Changing this setting requires a server restart to take effect.
                    </div>
                  </div>
                </div>
              )}

              {/* AI Configuration Tab */}
              {activeTab === 'ai' && (
                <div className="settings-section">
                  <h3>AI Configuration</h3>
                  <p className="settings-description">
                    Configure AI models for intelligence processing
                  </p>

                  {!modelOverrideEnabled && (
                    <div className="settings-info" style={{ marginBottom: '20px' }}>
                      <strong>Environment Variable Mode:</strong> AI model configuration is controlled by environment variables.
                      Model settings below are read-only and reflect values from docker-compose.yml or .env file.
                      To enable UI override, set <code style={{ background: '#f3f4f6', padding: '2px 6px', borderRadius: '4px' }}>MODEL_OVERRIDE_IN_UI=true</code> in your environment configuration.
                    </div>
                  )}

                  {/* Premium Model Configuration */}
                  <div className="form-section">
                    <label className="section-label">Premium Model (Daily Summaries)</label>
                    <p className="section-help">Higher quality model used for daily briefings and complex analysis</p>
                    <input
                      type="text"
                      value={modelOverrideEnabled ? aiModel : envValues.ai_model}
                      onChange={(e) => setAiModel(e.target.value)}
                      placeholder="claude-sonnet-4-5-20250929, gpt-4, or custom model name"
                      className="settings-input"
                      disabled={!modelOverrideEnabled}
                      style={!modelOverrideEnabled ? { backgroundColor: '#f3f4f6', cursor: 'not-allowed', color: '#6b7280' } : {}}
                    />
                    <p className="option-help">
                      {modelOverrideEnabled ? (
                        "Model name for premium tasks. Examples: claude-sonnet-4-5-20250929, gpt-4, gpt-4-turbo"
                      ) : (
                        `Current value from AI_MODEL environment variable. Provider: ${envValues.ai_provider}`
                      )}
                    </p>
                  </div>

                  {/* Economy Model Configuration */}
                  <div className="form-section">
                    <label className="section-label">Economy Model (Article Processing)</label>
                    <p className="section-help">Faster, cheaper model for entity extraction, filtering, and article summaries</p>
                    <input
                      type="text"
                      value={modelOverrideEnabled ? aiModelCheap : envValues.ai_model_cheap}
                      onChange={(e) => setAiModelCheap(e.target.value)}
                      placeholder="claude-haiku-4-5-20250929, gpt-3.5-turbo, or custom model name"
                      className="settings-input"
                      disabled={!modelOverrideEnabled}
                      style={!modelOverrideEnabled ? { backgroundColor: '#f3f4f6', cursor: 'not-allowed', color: '#6b7280' } : {}}
                    />
                    <p className="option-help">
                      {modelOverrideEnabled ? (
                        "Model name for high-volume tasks. Examples: claude-haiku-4-5-20250929, gpt-3.5-turbo, gpt-4o-mini"
                      ) : (
                        `Current value from AI_MODEL_CHEAP environment variable. Provider: ${envValues.ai_provider_cheap}`
                      )}
                    </p>
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
                    <strong>Cost Optimization:</strong> The economy model handles high-volume tasks (article processing, entity extraction, filtering)
                    while the premium model is reserved for daily summaries. This reduces costs by 80-90% without sacrificing quality on important briefings.
                  </div>
                  <div className="settings-info">
                    <strong>Provider Configuration:</strong> AI providers and API credentials are configured via environment variables:
                    <ul style={{ marginTop: '8px', marginLeft: '20px' }}>
                      <li><strong>AI_PROVIDER</strong>: anthropic or openai (for premium model) - Current: {envValues.ai_provider}</li>
                      <li><strong>AI_PROVIDER_CHEAP</strong>: anthropic or openai (for economy model) - Current: {envValues.ai_provider_cheap}</li>
                      <li><strong>MODEL_OVERRIDE_IN_UI</strong>: {modelOverrideEnabled ? 'true (UI can override)' : 'false (env vars control models)'}</li>
                      <li><strong>ANTHROPIC_API_KEY</strong>: Your Anthropic API key</li>
                      <li><strong>OPENAI_API_KEY</strong>: Your OpenAI API key</li>
                      <li><strong>OPENAI_BASE_URL</strong>: API endpoint (default: https://api.openai.com/v1)</li>
                    </ul>
                    <p style={{ marginTop: '8px' }}>
                      OpenAI base URL supports: OpenAI, Azure OpenAI, LM Studio (http://localhost:1234/v1),
                      Ollama (http://localhost:11434/v1), Together AI, Groq, and any OpenAI-compatible API.
                    </p>
                  </div>
                  <div className="settings-info" style={{ marginTop: '12px' }}>
                    <strong>Note:</strong> Changing the embedding model will require rebuilding the vector store. Model changes take effect immediately.
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

                  {/* Collection Timing */}
                  <div className="form-section">
                    <label className="section-label">Collection Timing</label>
                    <p className="section-help">Configure automated collection schedule and per-source intervals</p>

                    <div className="collection-schedule-group" style={{ marginBottom: '24px' }}>
                      <label className="schedule-option">
                        <input
                          type="checkbox"
                          checked={hourlyCollectionEnabled || dailyCollectionEnabled}
                          onChange={(e) => {
                            setHourlyCollectionEnabled(e.target.checked);
                            setDailyCollectionEnabled(e.target.checked);
                          }}
                        />
                        <div className="schedule-info">
                          <div className="schedule-name">Enable Periodic Collection</div>
                          <div className="schedule-description">
                            Runs every hour and collects from sources where enough time has elapsed based on their configured intervals
                          </div>
                        </div>
                      </label>

                      {(hourlyCollectionEnabled || dailyCollectionEnabled) && (
                        <div style={{ marginTop: '16px', paddingLeft: '32px' }}>
                          <label className="section-label" style={{ fontSize: '14px', marginBottom: '8px' }}>
                            Collection Days
                          </label>
                          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                            {[
                              { key: 'mon', label: 'Monday' },
                              { key: 'tue', label: 'Tuesday' },
                              { key: 'wed', label: 'Wednesday' },
                              { key: 'thu', label: 'Thursday' },
                              { key: 'fri', label: 'Friday' },
                              { key: 'sat', label: 'Saturday' },
                              { key: 'sun', label: 'Sunday' }
                            ].map(({ key, label }) => (
                              <label key={key} className="toggle-field" style={{ flex: '0 0 auto' }}>
                                <input
                                  type="checkbox"
                                  checked={collectionDays[key]}
                                  onChange={(e) => setCollectionDays({
                                    ...collectionDays,
                                    [key]: e.target.checked
                                  })}
                                />
                                <span>{label}</span>
                              </label>
                            ))}
                          </div>
                          <p className="option-help" style={{ marginTop: '8px' }}>
                            Select which days of the week to run collection (default: all days)
                          </p>
                        </div>
                      )}
                    </div>

                    <div style={{ borderTop: '1px solid #e5e7eb', paddingTop: '20px' }}>
                      <label className="section-label" style={{ fontSize: '15px', marginBottom: '8px' }}>Source Intervals</label>
                      <p className="section-help">Configure how often each source is checked for new content</p>

                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '12px', marginTop: '16px' }}>
                        {Object.entries({
                          news_api: 'News API',
                          rss: 'RSS Feeds',
                          yahoo_finance_news: 'Yahoo Finance News',
                          australian_news: 'Australian News',
                          google_news: 'Google News',
                          twitter: 'Twitter/X',
                          youtube: 'YouTube',
                          reddit: 'Reddit',
                          linkedin: 'LinkedIn (Company)',
                          linkedin_user: 'LinkedIn (User Profiles)',
                          pressrelease: 'Press Releases',
                          web_scrape: 'Web Scraper'
                        }).map(([key, label]) => (
                          <div key={key} className="interval-setting">
                            <label>{label}</label>
                            <select
                              value={sourceIntervals[key]}
                              onChange={(e) => updateSourceInterval(key, parseInt(e.target.value))}
                              className="settings-select"
                            >
                              <option value={1}>Every hour</option>
                              <option value={3}>Every 3 hours</option>
                              <option value={6}>Every 6 hours</option>
                              <option value={12}>Every 12 hours</option>
                              <option value={24}>Every 24 hours (daily)</option>
                              <option value={48}>Every 2 days</option>
                              <option value={168}>Every week</option>
                            </select>
                          </div>
                        ))}
                      </div>

                      <p className="option-help" style={{ marginTop: '16px' }}>
                        The periodic job runs every hour at :00 (1:00, 2:00, etc.) and checks each source's last collection time.
                        Sources are only collected when their configured interval has elapsed since the last run.
                      </p>
                    </div>

                    <div className="settings-warning" style={{ marginTop: '20px' }}>
                      <strong>Note:</strong> Source interval changes take effect on the next periodic collection run (top of each hour).
                      The collection logic checks elapsed time since last run for each source and only collects when the configured
                      interval has passed.
                    </div>

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

                  {/* Domain Blacklist */}
                  <div className="form-section" style={{ marginTop: '32px', paddingTop: '24px', borderTop: '1px solid #e5e7eb' }}>
                    <label className="section-label">Domain Blacklist</label>
                    <p className="section-help">Block intelligence items from low-quality or spammy domains</p>

                    <label className="schedule-option">
                      <input
                        type="checkbox"
                        checked={blacklistEnabled}
                        onChange={(e) => setBlacklistEnabled(e.target.checked)}
                      />
                      <div className="schedule-info">
                        <div className="schedule-name">Enable Domain Blacklist</div>
                        <div className="schedule-description">
                          Filter out URLs from blacklisted domains during collection
                        </div>
                      </div>
                    </label>

                    {blacklistEnabled && (
                      <>
                        <div className="option-group" style={{ marginTop: '16px' }}>
                          <label>Add Domain to Blacklist</label>
                          <div style={{ display: 'flex', gap: '8px' }}>
                            <input
                              type="text"
                              value={newDomain}
                              onChange={(e) => setNewDomain(e.target.value)}
                              onKeyPress={(e) => {
                                if (e.key === 'Enter') {
                                  e.preventDefault();
                                  addBlacklistedDomain();
                                }
                              }}
                              placeholder="example.com"
                              className="settings-input"
                              style={{ flex: 1 }}
                            />
                            <button
                              type="button"
                              onClick={addBlacklistedDomain}
                              className="btn-save"
                              style={{ padding: '8px 16px' }}
                            >
                              Add
                            </button>
                          </div>
                          <p className="option-help">
                            Enter domain names to block (e.g., yahoo.com, msn.com)
                          </p>
                        </div>

                        {blacklistedDomains.length > 0 && (
                          <div className="option-group">
                            <label>Blacklisted Domains ({blacklistedDomains.length})</label>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '8px' }}>
                              {blacklistedDomains.map(domain => (
                                <div
                                  key={domain}
                                  style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '6px',
                                    padding: '6px 12px',
                                    background: '#f3f4f6',
                                    borderRadius: '6px',
                                    fontSize: '14px'
                                  }}
                                >
                                  <span>{domain}</span>
                                  <button
                                    type="button"
                                    onClick={() => removeBlacklistedDomain(domain)}
                                    style={{
                                      background: 'none',
                                      border: 'none',
                                      color: '#ef4444',
                                      cursor: 'pointer',
                                      padding: '0 4px',
                                      fontSize: '16px',
                                      fontWeight: 'bold'
                                    }}
                                    title="Remove domain"
                                  >
                                    ×
                                  </button>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </>
                    )}
                  </div>

                  {/* UI Auto-Refresh */}
                  <div className="form-section" style={{ marginTop: '32px', paddingTop: '24px', borderTop: '1px solid #e5e7eb' }}>
                    <label className="section-label">UI Auto-Refresh</label>
                    <p className="section-help">Configure how often the feed automatically refreshes with new intelligence</p>

                    <label className="schedule-option">
                      <input
                        type="checkbox"
                        checked={localStorage.getItem('autoRefreshEnabled') !== 'false'}
                        onChange={(e) => localStorage.setItem('autoRefreshEnabled', e.target.checked)}
                      />
                      <div className="schedule-info">
                        <div className="schedule-name">Enable Auto-Refresh</div>
                        <div className="schedule-description">
                          Automatically poll for new intelligence items at the configured interval
                        </div>
                      </div>
                    </label>

                    <div className="option-group" style={{ marginTop: '16px' }}>
                      <label>Refresh Interval</label>
                      <select
                        value={localStorage.getItem('autoRefreshInterval') || '300000'}
                        onChange={(e) => localStorage.setItem('autoRefreshInterval', e.target.value)}
                        className="settings-select"
                      >
                        <option value="60000">1 minute (Frequent)</option>
                        <option value="120000">2 minutes</option>
                        <option value="300000">5 minutes (Recommended)</option>
                        <option value="600000">10 minutes</option>
                        <option value="900000">15 minutes</option>
                        <option value="1800000">30 minutes</option>
                      </select>
                      <p className="option-help">
                        How often to check for new intelligence items. Shorter intervals provide more up-to-date information but may use more resources.
                      </p>
                    </div>
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

                  {/* YouTube Collector Settings */}
                  <div className="collector-section">
                    <div className="collector-header">
                      <h4>YouTube Collector</h4>
                      <p className="collector-description">
                        Monitor YouTube videos via transcripts with quality filters for views and channel size
                      </p>
                    </div>

                    <div className="form-section">
                      <label className="section-label">Collection Options</label>
                      <p className="section-help">Configure what types of videos to collect</p>

                      <div style={{ marginBottom: '20px' }}>
                        <label className="toggle-field">
                          <input
                            type="checkbox"
                            checked={youtubeEnableKeywordSearch}
                            onChange={(e) => setYoutubeEnableKeywordSearch(e.target.checked)}
                          />
                          <span>Enable Keyword Search</span>
                        </label>
                        <p className="option-help" style={{ marginLeft: '24px', marginTop: '4px' }}>
                          Search YouTube for videos matching customer keywords. Disable to only monitor configured channels.
                        </p>
                      </div>
                    </div>

                    <div className="form-section">
                      <label className="section-label">Quality Filters</label>
                      <p className="section-help">Minimum thresholds to filter low-quality or unpopular videos</p>

                      <div className="option-row">
                        <div className="option-group">
                          <label>Minimum Views</label>
                          <input
                            type="number"
                            min="0"
                            max="100000"
                            step="100"
                            value={youtubeMinViews}
                            onChange={(e) => setYoutubeMinViews(parseInt(e.target.value))}
                            className="settings-input"
                          />
                          <p className="option-help">Videos must have at least this many views</p>
                        </div>

                        <div className="option-group">
                          <label>Minimum Channel Subscribers</label>
                          <input
                            type="number"
                            min="0"
                            max="1000000"
                            step="1000"
                            value={youtubeMinChannelSubscribers}
                            onChange={(e) => setYoutubeMinChannelSubscribers(parseInt(e.target.value))}
                            className="settings-input"
                          />
                          <p className="option-help">Channel must have at least this many subscribers</p>
                        </div>
                      </div>
                    </div>

                    <div className="settings-warning">
                      <strong>Note:</strong> Higher thresholds filter out smaller channels and less popular videos.
                      Set to 0 to disable filtering. Configured channels in customer settings will always be collected regardless of filters.
                    </div>
                  </div>

                  {/* LinkedIn Collector Settings */}
                  <div className="collector-section">
                    <div className="collector-header">
                      <h4>LinkedIn Collector</h4>
                      <p className="collector-description">
                        Configure rate limiting and scraping strategy to avoid LinkedIn detection and blocking
                      </p>
                    </div>

                    <div className="form-section">
                      <label className="section-label">Scraping Strategy</label>
                      <p className="section-help">Preset timing configurations balancing speed vs. stealth</p>

                      <div className="option-group">
                        <select
                          value={linkedinScrapingStrategy}
                          onChange={(e) => {
                            const strategy = e.target.value;
                            setLinkedinScrapingStrategy(strategy);

                            // Update delays based on strategy
                            if (strategy === 'conservative') {
                              setLinkedinDelayProfilesMin(60);
                              setLinkedinDelayProfilesMax(120);
                              setLinkedinDelayCustomersMin(300);
                              setLinkedinDelayCustomersMax(600);
                            } else if (strategy === 'moderate') {
                              setLinkedinDelayProfilesMin(30);
                              setLinkedinDelayProfilesMax(60);
                              setLinkedinDelayCustomersMin(120);
                              setLinkedinDelayCustomersMax(240);
                            } else if (strategy === 'aggressive') {
                              setLinkedinDelayProfilesMin(3);
                              setLinkedinDelayProfilesMax(6);
                              setLinkedinDelayCustomersMin(10);
                              setLinkedinDelayCustomersMax(15);
                            }
                          }}
                          className="settings-select"
                        >
                          <option value="conservative">Conservative (Recommended) - ~1 hour/customer</option>
                          <option value="moderate">Moderate - ~30 min/customer</option>
                          <option value="aggressive">Aggressive - ~15 min/customer (High risk)</option>
                        </select>
                        <p className="option-help">Conservative is slowest but safest. Aggressive is faster but risks getting blocked.</p>
                      </div>
                    </div>

                    <div className="form-section">
                      <label className="section-label">Delay Between Profiles</label>
                      <p className="section-help">Wait time between scraping individual LinkedIn profiles (seconds)</p>

                      <div className="option-row">
                        <div className="option-group">
                          <label>Minimum Delay (seconds)</label>
                          <input
                            type="number"
                            min="3"
                            max="300"
                            value={linkedinDelayProfilesMin}
                            onChange={(e) => setLinkedinDelayProfilesMin(parseFloat(e.target.value))}
                            className="settings-input"
                          />
                          <p className="option-help">Shortest wait between profiles</p>
                        </div>

                        <div className="option-group">
                          <label>Maximum Delay (seconds)</label>
                          <input
                            type="number"
                            min="3"
                            max="300"
                            value={linkedinDelayProfilesMax}
                            onChange={(e) => setLinkedinDelayProfilesMax(parseFloat(e.target.value))}
                            className="settings-input"
                          />
                          <p className="option-help">Longest wait between profiles</p>
                        </div>
                      </div>

                      <div className="settings-info">
                        Current range: {linkedinDelayProfilesMin}-{linkedinDelayProfilesMax} seconds
                        ({(linkedinDelayProfilesMin/60).toFixed(1)}-{(linkedinDelayProfilesMax/60).toFixed(1)} minutes)
                      </div>
                    </div>

                    <div className="form-section">
                      <label className="section-label">Delay Between Customers</label>
                      <p className="section-help">Wait time between collecting different customers (seconds)</p>

                      <div className="option-row">
                        <div className="option-group">
                          <label>Minimum Delay (seconds)</label>
                          <input
                            type="number"
                            min="10"
                            max="3600"
                            value={linkedinDelayCustomersMin}
                            onChange={(e) => setLinkedinDelayCustomersMin(parseFloat(e.target.value))}
                            className="settings-input"
                          />
                          <p className="option-help">Shortest wait between customers</p>
                        </div>

                        <div className="option-group">
                          <label>Maximum Delay (seconds)</label>
                          <input
                            type="number"
                            min="10"
                            max="3600"
                            value={linkedinDelayCustomersMax}
                            onChange={(e) => setLinkedinDelayCustomersMax(parseFloat(e.target.value))}
                            className="settings-input"
                          />
                          <p className="option-help">Longest wait between customers</p>
                        </div>
                      </div>

                      <div className="settings-info">
                        Current range: {linkedinDelayCustomersMin}-{linkedinDelayCustomersMax} seconds
                        ({(linkedinDelayCustomersMin/60).toFixed(1)}-{(linkedinDelayCustomersMax/60).toFixed(1)} minutes)
                      </div>
                    </div>

                    <div className="settings-warning">
                      <strong>⚠️ Important:</strong> LinkedIn actively detects and blocks scraping. Conservative settings are strongly
                      recommended. Aggressive settings may result in account suspension or IP blocking. Randomized delays help
                      appear more human-like.
                    </div>
                  </div>

                  {/* Australian News Sources */}
                  <div className="collector-section">
                    <div className="collector-header">
                      <h4>Australian News Sources</h4>
                      <p className="collector-description">
                        Configure RSS feeds from Australian news outlets to monitor
                      </p>
                    </div>

                    <div className="form-section">
                      <label className="section-label">News Sources</label>
                      <p className="section-help">Enable/disable sources and manage RSS feeds</p>

                      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                        {australianNewsSources.sources && australianNewsSources.sources.map((source, idx) => (
                          <div key={idx} style={{
                            border: '1px solid #e5e7eb',
                            borderRadius: '8px',
                            padding: '16px',
                            backgroundColor: source.enabled ? '#ffffff' : '#f9fafb'
                          }}>
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                              <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: '500' }}>
                                <input
                                  type="checkbox"
                                  checked={source.enabled}
                                  onChange={(e) => {
                                    const newSources = [...australianNewsSources.sources];
                                    newSources[idx].enabled = e.target.checked;
                                    setAustralianNewsSources({ sources: newSources });
                                  }}
                                />
                                {source.name}
                              </label>
                              <button
                                className="btn-secondary"
                                onClick={() => {
                                  const newSources = australianNewsSources.sources.filter((_, i) => i !== idx);
                                  setAustralianNewsSources({ sources: newSources });
                                }}
                                style={{ padding: '4px 12px', fontSize: '14px', width: 'auto', height: 'auto' }}
                              >
                                Remove
                              </button>
                            </div>

                            <div style={{ marginBottom: '8px' }}>
                              <label style={{ fontSize: '13px', color: '#6b7280', marginBottom: '4px', display: 'block' }}>
                                Source Name
                              </label>
                              <input
                                type="text"
                                value={source.name}
                                onChange={(e) => {
                                  const newSources = [...australianNewsSources.sources];
                                  newSources[idx].name = e.target.value;
                                  setAustralianNewsSources({ sources: newSources });
                                }}
                                className="settings-input"
                                placeholder="e.g., ABC News"
                              />
                            </div>

                            <div>
                              <label style={{ fontSize: '13px', color: '#6b7280', marginBottom: '4px', display: 'block' }}>
                                RSS Feed URLs (one per line)
                              </label>
                              <textarea
                                value={source.feeds.join('\n')}
                                onChange={(e) => {
                                  const newSources = [...australianNewsSources.sources];
                                  newSources[idx].feeds = e.target.value.split('\n').filter(f => f.trim());
                                  setAustralianNewsSources({ sources: newSources });
                                }}
                                className="settings-input"
                                rows="3"
                                placeholder="https://example.com/rss.xml"
                                style={{ fontFamily: 'monospace', fontSize: '13px' }}
                              />
                            </div>
                          </div>
                        ))}

                        <button
                          className="btn-primary"
                          onClick={() => {
                            const newSources = [
                              ...australianNewsSources.sources,
                              {
                                name: 'New Source',
                                enabled: true,
                                feeds: []
                              }
                            ];
                            setAustralianNewsSources({ sources: newSources });
                          }}
                          style={{ alignSelf: 'flex-start' }}
                        >
                          + Add News Source
                        </button>
                      </div>
                    </div>

                    <div className="settings-info">
                      <strong>Note:</strong> Australian News collector uses these RSS feeds to monitor regional news sources.
                      Disable sources you don't need to reduce collection time and noise.
                    </div>
                  </div>
                </div>
              )}

              {/* Smart Feed Tab */}
              {activeTab === 'smartfeed' && (
                <div className="settings-section">
                  <h3>Smart Feed Configuration</h3>
                  <p className="settings-description">
                    Configure intelligent filtering to show the most relevant intelligence in your feed
                  </p>

                  {/* Enable/Disable Smart Feed */}
                  <div className="form-section">
                    <label className="schedule-option">
                      <input
                        type="checkbox"
                        checked={smartFeedEnabled}
                        onChange={(e) => setSmartFeedEnabled(e.target.checked)}
                      />
                      <div className="schedule-info">
                        <div className="schedule-name">Enable Smart Feed Filtering</div>
                        <div className="schedule-description">
                          Apply intelligent filtering when Smart Feed toggle is enabled in the main feed
                        </div>
                      </div>
                    </label>
                  </div>

                  {smartFeedEnabled && (
                    <>
                      {/* Priority Thresholds */}
                      <div className="form-section">
                        <label className="section-label">Priority Filtering</label>
                        <p className="section-help">Filter items based on AI-calculated priority scores</p>

                        <div className="option-group" style={{ marginTop: '16px' }}>
                          <label>Minimum Priority: {(smartFeedMinPriority * 100).toFixed(0)}%</label>
                          <input
                            type="range"
                            min="0.0"
                            max="1.0"
                            step="0.1"
                            value={smartFeedMinPriority}
                            onChange={(e) => setSmartFeedMinPriority(parseFloat(e.target.value))}
                            className="similarity-slider"
                          />
                          <p className="option-help">
                            Items below this priority will be filtered out from the smart feed
                          </p>
                        </div>

                        <div className="option-group">
                          <label>High Priority Threshold: {(smartFeedHighPriorityThreshold * 100).toFixed(0)}%</label>
                          <input
                            type="range"
                            min="0.0"
                            max="1.0"
                            step="0.1"
                            value={smartFeedHighPriorityThreshold}
                            onChange={(e) => setSmartFeedHighPriorityThreshold(parseFloat(e.target.value))}
                            className="similarity-slider"
                          />
                          <p className="option-help">
                            Single-source items above this threshold always show, even if unclustered
                          </p>
                        </div>
                      </div>

                      {/* Recency Boost */}
                      <div className="form-section">
                        <label className="section-label">Recency Boost</label>
                        <p className="section-help">Boost priority for recent items to surface fresh intelligence</p>

                        <label className="schedule-option">
                          <input
                            type="checkbox"
                            checked={recencyBoostEnabled}
                            onChange={(e) => setRecencyBoostEnabled(e.target.checked)}
                          />
                          <div className="schedule-info">
                            <div className="schedule-name">Enable Recency Boost</div>
                            <div className="schedule-description">
                              Automatically increase priority for recently published items
                            </div>
                          </div>
                        </label>

                        {recencyBoostEnabled && (
                          <>
                            <div className="option-group" style={{ marginTop: '16px' }}>
                              <label>Boost Amount: +{(recencyBoostAmount * 100).toFixed(0)}%</label>
                              <input
                                type="range"
                                min="0.0"
                                max="0.3"
                                step="0.05"
                                value={recencyBoostAmount}
                                onChange={(e) => setRecencyBoostAmount(parseFloat(e.target.value))}
                                className="similarity-slider"
                              />
                              <p className="option-help">
                                Amount to add to priority score for recent items
                              </p>
                            </div>

                            <div className="option-group">
                              <label>Time Threshold</label>
                              <select
                                value={recencyBoostHours}
                                onChange={(e) => setRecencyBoostHours(parseInt(e.target.value))}
                                className="settings-select"
                              >
                                <option value={6}>6 hours</option>
                                <option value={12}>12 hours</option>
                                <option value={24}>24 hours (Recommended)</option>
                                <option value={48}>48 hours</option>
                                <option value={72}>72 hours</option>
                              </select>
                              <p className="option-help">
                                Items newer than this get the recency boost
                              </p>
                            </div>
                          </>
                        )}
                      </div>

                      {/* Category Preferences */}
                      <div className="form-section">
                        <label className="section-label">Category Preferences</label>
                        <p className="section-help">Always show items from selected categories, regardless of priority</p>
                        <div className="focus-areas-grid">
                          {Object.entries(categoryPreferences).map(([key, enabled]) => (
                            <label key={key} className="focus-area-checkbox">
                              <input
                                type="checkbox"
                                checked={enabled}
                                onChange={() => toggleCategoryPreference(key)}
                              />
                              <span>{key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</span>
                            </label>
                          ))}
                        </div>
                      </div>

                      {/* Source Preferences */}
                      <div className="form-section">
                        <label className="section-label">Source Preferences</label>
                        <p className="section-help">Always show items from selected sources, regardless of priority</p>
                        <div className="focus-areas-grid">
                          {Object.entries(sourcePreferences).map(([key, enabled]) => (
                            <label key={key} className="focus-area-checkbox">
                              <input
                                type="checkbox"
                                checked={enabled}
                                onChange={() => toggleSourcePreference(key)}
                              />
                              <span>{key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</span>
                            </label>
                          ))}
                        </div>
                      </div>

                      {/* Diversity Settings */}
                      <div className="form-section">
                        <label className="section-label">Feed Diversity</label>
                        <p className="section-help">Prevent feed from being dominated by a single source</p>

                        <label className="schedule-option">
                          <input
                            type="checkbox"
                            checked={diversityEnabled}
                            onChange={(e) => setDiversityEnabled(e.target.checked)}
                          />
                          <div className="schedule-info">
                            <div className="schedule-name">Enable Diversity Control</div>
                            <div className="schedule-description">
                              Limit consecutive items from the same source for variety
                            </div>
                          </div>
                        </label>

                        {diversityEnabled && (
                          <div className="option-group" style={{ marginTop: '16px' }}>
                            <label>Max Consecutive Same Source</label>
                            <input
                              type="number"
                              min="1"
                              max="10"
                              value={maxConsecutiveSameSource}
                              onChange={(e) => setMaxConsecutiveSameSource(parseInt(e.target.value))}
                              className="settings-input"
                            />
                            <p className="option-help">
                              Maximum number of items from the same source before requiring a different source
                            </p>
                          </div>
                        )}
                      </div>

                      <div className="settings-info" style={{ marginTop: '24px' }}>
                        <strong>How Smart Feed Works:</strong> When enabled, the feed applies priority filtering,
                        category/source preferences, recency boosts, and diversity controls to surface the most
                        relevant intelligence while filtering noise. Use Full Feed to see everything unfiltered.
                      </div>
                    </>
                  )}
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
