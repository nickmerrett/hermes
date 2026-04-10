import { useState, useEffect } from 'react';
import { apiClient } from '../api/auth';
import './CustomerEditModal.css';

export default function CustomerEditModal({ customer, onClose, onSave, onDelete }) {
  const [formData, setFormData] = useState({
    name: '',
    domain: '',
    keywords: [],
    competitors: [],
    stock_symbol: '',
    tab_color: '#ffffff',
    config: {
      description: '',
      notes: '',
      twitter_handle: '',
      linkedin_company_url: '',
      linkedin_company_id: '',
      rss_feeds: [],
      linkedin_user_profiles: [],
      collection_config: {
        excluded_keywords: [],
        news_enabled: true,
        yahoo_finance_news_enabled: false,
        asx_announcements_enabled: false,
        rss_enabled: true,
        australian_news_enabled: true,
        google_news_enabled: true,
        reddit_enabled: false,
        youtube_enabled: false,
        twitter_enabled: false,
        linkedin_enabled: false,
        linkedin_user_enabled: false,
        pressrelease_enabled: false,
        reddit_subreddits: [],
        youtube_channels: [],
        priority_keywords: [],
        web_scrape_sources: [],
        gmail_enabled: false,
        gmail_config: {
          use_sender_whitelist: false,
          sender_whitelist: [],
          label_config: {
            mark_as_read: true,
            apply_label: ''
          }
        },
        mailsac_enabled: false,
        mailsac_config: {
          email_addresses: [],
          extract_links: true,
          delete_after_processing: true,
          max_age_days: 7
        }
      }
    }
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [gmailStatus, setGmailStatus] = useState({ connected: false, email: null, loading: true });

  useEffect(() => {
    if (customer) {
      const config = customer.config || {};

      // The database stores collection_config fields at the TOP level of config
      // So we need to handle both nested (config.collection_config) and flat (config directly) structures
      const collectionConfig = config.collection_config || config;

      setFormData({
        name: customer.name || '',
        domain: customer.domain || '',
        keywords: customer.keywords || [],
        competitors: customer.competitors || [],
        stock_symbol: customer.stock_symbol || '',
        tab_color: customer.tab_color || '#ffffff',
        config: {
          description: config.description || '',
          notes: config.notes || '',
          twitter_handle: config.twitter_handle || '',
          linkedin_company_url: config.linkedin_company_url || '',
          linkedin_company_id: config.linkedin_company_id || '',
          rss_feeds: config.rss_feeds || [],
          linkedin_user_profiles: config.linkedin_user_profiles || [],
          collection_config: {
            excluded_keywords: collectionConfig.excluded_keywords || [],
            news_enabled: collectionConfig.news_enabled !== undefined ? collectionConfig.news_enabled : true,
            yahoo_finance_news_enabled: collectionConfig.yahoo_finance_news_enabled || collectionConfig.stock_enabled || false,
            asx_announcements_enabled: collectionConfig.asx_announcements_enabled || false,
            rss_enabled: collectionConfig.rss_enabled !== undefined ? collectionConfig.rss_enabled : true,
            australian_news_enabled: collectionConfig.australian_news_enabled !== undefined ? collectionConfig.australian_news_enabled : true,
            google_news_enabled: collectionConfig.google_news_enabled !== undefined ? collectionConfig.google_news_enabled : true,
            reddit_enabled: collectionConfig.reddit_enabled || false,
            youtube_enabled: collectionConfig.youtube_enabled || false,
            twitter_enabled: collectionConfig.twitter_enabled || false,
            linkedin_enabled: collectionConfig.linkedin_enabled || false,
            linkedin_user_enabled: collectionConfig.linkedin_user_enabled || false,
            pressrelease_enabled: collectionConfig.pressrelease_enabled || false,
            reddit_subreddits: collectionConfig.reddit_subreddits || [],
            youtube_channels: collectionConfig.youtube_channels || [],
            priority_keywords: collectionConfig.priority_keywords || [],
            web_scrape_sources: (collectionConfig.web_scrape_sources || []).map(source => ({
              name: source.name || '',
              url: source.url || '',
              selectors: {
                article_list: source.selectors?.article_list || '',
                link: source.selectors?.link || ''
              },
              max_articles: source.max_articles || 20,
              extract_full_content: source.extract_full_content !== undefined ? source.extract_full_content : true
            })),
            gmail_enabled: collectionConfig.gmail_enabled || false,
            gmail_config: {
              use_sender_whitelist: config.gmail_config?.use_sender_whitelist || false,
              sender_whitelist: config.gmail_config?.sender_whitelist || [],
              label_config: {
                mark_as_read: config.gmail_config?.label_config?.mark_as_read !== undefined ? config.gmail_config.label_config.mark_as_read : true,
                apply_label: config.gmail_config?.label_config?.apply_label || ''
              }
            },
            mailsac_enabled: collectionConfig.mailsac_enabled || false,
            mailsac_config: {
              email_addresses: config.mailsac_config?.email_addresses || [],
              extract_links: config.mailsac_config?.extract_links !== undefined ? config.mailsac_config.extract_links : true,
              delete_after_processing: config.mailsac_config?.delete_after_processing !== undefined ? config.mailsac_config.delete_after_processing : true,
              max_age_days: config.mailsac_config?.max_age_days || 7
            }
          }
        }
      });

      // Fetch Gmail connection status
      fetchGmailStatus();
    }
  }, [customer]);

  const fetchGmailStatus = async () => {
    if (!customer?.id) return;

    try {
      const response = await apiClient.get(`/gmail/status/${customer.id}`);
      setGmailStatus({
        connected: response.data.connected,
        email: response.data.email,
        loading: false
      });
    } catch (err) {
      console.error('Error fetching Gmail status:', err);
      setGmailStatus({ connected: false, email: null, loading: false });
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    // Validate web scrape sources have required fields
    const webSources = formData.config.collection_config.web_scrape_sources || [];
    for (let i = 0; i < webSources.length; i++) {
      const src = webSources[i];
      if (!src.name?.trim() || !src.url?.trim() || !src.selectors?.article_list?.trim()) {
        setError(`Web Scrape Source #${i + 1}: Name, URL, and Article List Selector are required`);
        setLoading(false);
        return;
      }
    }

    try {
      // Flatten the config structure to match how the backend stores it
      // Backend stores collection_config fields at the TOP level of config
      const flatConfig = {
        description: formData.config.description,
        notes: formData.config.notes,
        twitter_handle: formData.config.twitter_handle,
        linkedin_company_url: formData.config.linkedin_company_url,
        linkedin_company_id: formData.config.linkedin_company_id,
        github_org: formData.config.github_org,
        github_repos: formData.config.github_repos,
        rss_feeds: formData.config.rss_feeds,
        linkedin_user_profiles: formData.config.linkedin_user_profiles,
        // Flatten collection_config to top level
        ...formData.config.collection_config
      };

      const payload = {
        name: formData.name,
        domain: formData.domain,
        keywords: formData.keywords,
        competitors: formData.competitors,
        stock_symbol: formData.stock_symbol,
        tab_color: formData.tab_color,
        config: flatConfig
      };

      await apiClient.put(`/customers/${customer.id}`, payload);
      onSave();
      onClose();
    } catch (err) {
      console.error('Update customer error:', err);
      setError(err.response?.data?.detail || 'Failed to update customer');
    } finally {
      setLoading(false);
    }
  };

  const updateArrayField = (field, index, value) => {
    const newArray = [...formData[field]];
    newArray[index] = value;
    setFormData({ ...formData, [field]: newArray });
  };

  const addArrayItem = (field) => {
    setFormData({
      ...formData,
      [field]: [...formData[field], '']
    });
  };

  const removeArrayItem = (field, index) => {
    const newArray = formData[field].filter((_, i) => i !== index);
    setFormData({ ...formData, [field]: newArray });
  };

  // RSS Feed management
  const addRssFeed = () => {
    const newFeeds = [...formData.config.rss_feeds, { url: '', name: '' }];
    setFormData({
      ...formData,
      config: { ...formData.config, rss_feeds: newFeeds }
    });
  };

  const updateRssFeed = (index, field, value) => {
    const newFeeds = [...formData.config.rss_feeds];
    newFeeds[index] = { ...newFeeds[index], [field]: value };
    setFormData({
      ...formData,
      config: { ...formData.config, rss_feeds: newFeeds }
    });
  };

  const removeRssFeed = (index) => {
    const newFeeds = formData.config.rss_feeds.filter((_, i) => i !== index);
    setFormData({
      ...formData,
      config: { ...formData.config, rss_feeds: newFeeds }
    });
  };

  // LinkedIn User Profile management
  const addLinkedInProfile = () => {
    const newProfiles = [...formData.config.linkedin_user_profiles, {
      profile_url: '',
      name: '',
      role: '',
      notes: ''
    }];
    setFormData({
      ...formData,
      config: { ...formData.config, linkedin_user_profiles: newProfiles }
    });
  };

  const updateLinkedInProfile = (index, field, value) => {
    const newProfiles = [...formData.config.linkedin_user_profiles];
    newProfiles[index] = { ...newProfiles[index], [field]: value };
    setFormData({
      ...formData,
      config: { ...formData.config, linkedin_user_profiles: newProfiles }
    });
  };

  const removeLinkedInProfile = (index) => {
    const newProfiles = formData.config.linkedin_user_profiles.filter((_, i) => i !== index);
    setFormData({
      ...formData,
      config: { ...formData.config, linkedin_user_profiles: newProfiles }
    });
  };

  // Web Scrape Source management
  const addWebScrapeSource = () => {
    const newSources = [...formData.config.collection_config.web_scrape_sources, {
      name: '',
      url: '',
      selectors: {
        article_list: '',
        link: ''
      },
      max_articles: 20,
      extract_full_content: true
    }];
    setFormData({
      ...formData,
      config: {
        ...formData.config,
        collection_config: {
          ...formData.config.collection_config,
          web_scrape_sources: newSources
        }
      }
    });
  };

  const updateWebScrapeSource = (index, field, value) => {
    const newSources = [...formData.config.collection_config.web_scrape_sources];
    if (field.startsWith('selectors.')) {
      const selectorField = field.split('.')[1];
      newSources[index] = {
        ...newSources[index],
        selectors: {
          ...newSources[index].selectors,
          [selectorField]: value
        }
      };
    } else {
      newSources[index] = { ...newSources[index], [field]: value };
    }
    setFormData({
      ...formData,
      config: {
        ...formData.config,
        collection_config: {
          ...formData.config.collection_config,
          web_scrape_sources: newSources
        }
      }
    });
  };

  const removeWebScrapeSource = (index) => {
    const newSources = formData.config.collection_config.web_scrape_sources.filter((_, i) => i !== index);
    setFormData({
      ...formData,
      config: {
        ...formData.config,
        collection_config: {
          ...formData.config.collection_config,
          web_scrape_sources: newSources
        }
      }
    });
  };

  // Gmail OAuth functions
  const handleConnectGmail = async () => {
    try {
      const response = await apiClient.get(`/gmail/oauth/start/${customer.id}`);
      const authUrl = response.data.auth_url;

      // Open OAuth popup
      const width = 600;
      const height = 700;
      const left = window.screen.width / 2 - width / 2;
      const top = window.screen.height / 2 - height / 2;

      const popup = window.open(
        authUrl,
        'Gmail OAuth',
        `width=${width},height=${height},left=${left},top=${top}`
      );

      // Poll for popup close and refresh status
      const pollTimer = setInterval(() => {
        if (popup && popup.closed) {
          clearInterval(pollTimer);
          // Refresh Gmail status after a short delay
          setTimeout(() => {
            fetchGmailStatus();
          }, 1000);
        }
      }, 500);
    } catch (err) {
      console.error('Error starting Gmail OAuth:', err);
      setError('Failed to connect Gmail: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleDisconnectGmail = async () => {
    if (!window.confirm('Disconnect Gmail? This will stop monitoring press release digests.')) {
      return;
    }

    try {
      await apiClient.post(`/gmail/disconnect/${customer.id}`);
      setGmailStatus({ connected: false, email: null, loading: false });

      // Also disable Gmail in form
      setFormData({
        ...formData,
        config: {
          ...formData.config,
          collection_config: {
            ...formData.config.collection_config,
            gmail_enabled: false
          }
        }
      });
    } catch (err) {
      console.error('Error disconnecting Gmail:', err);
      setError('Failed to disconnect Gmail: ' + (err.response?.data?.detail || err.message));
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Edit Customer</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        {error && (
          <div className="modal-error">
            ⚠️ {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="modal-form">
          <div className="form-section">
            <h3>Basic Information</h3>

            <div className="form-field">
              <label>Company Name *</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                required
              />
            </div>

            <div className="form-field">
              <label>Domain</label>
              <input
                type="text"
                value={formData.domain}
                onChange={(e) => setFormData({ ...formData, domain: e.target.value })}
                placeholder="example.com"
              />
            </div>

            <div className="form-field">
              <label>Stock Symbol</label>
              <input
                type="text"
                value={formData.stock_symbol}
                onChange={(e) => setFormData({ ...formData, stock_symbol: e.target.value })}
                placeholder="AAPL, TEAM, CBA.AX"
              />
            </div>

            <div className="form-field">
              <label>Tab Color</label>
              <div style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
                <input
                  type="color"
                  value={formData.tab_color}
                  onChange={(e) => setFormData({ ...formData, tab_color: e.target.value })}
                  style={{ width: '60px', height: '40px', cursor: 'pointer', border: '1px solid #d1d5db', borderRadius: '4px' }}
                />
                <span style={{ fontSize: '14px', color: '#6b7280' }}>{formData.tab_color}</span>
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                  {['#ffffff', '#fef3c7', '#fecaca', '#fed7aa', '#bbf7d0', '#bfdbfe', '#ddd6fe', '#fbcfe8', '#e5e7eb'].map(color => (
                    <button
                      key={color}
                      type="button"
                      onClick={() => setFormData({ ...formData, tab_color: color })}
                      style={{
                        width: '32px',
                        height: '32px',
                        backgroundColor: color,
                        border: formData.tab_color === color ? '3px solid #3b82f6' : '1px solid #d1d5db',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        padding: 0
                      }}
                      title={color}
                    />
                  ))}
                </div>
              </div>
              <small style={{ display: 'block', marginTop: '6px', color: '#6b7280' }}>
                Choose a background color for this customer's tab for quick visual identification
              </small>
            </div>

            <div className="form-field">
              <label>Description</label>
              <textarea
                value={formData.config.description}
                onChange={(e) => setFormData({
                  ...formData,
                  config: { ...formData.config, description: e.target.value }
                })}
                placeholder="Brief description of the company"
                rows="2"
              />
            </div>

            <div className="form-field">
              <label>Notes</label>
              <textarea
                value={formData.config.notes}
                onChange={(e) => setFormData({
                  ...formData,
                  config: { ...formData.config, notes: e.target.value }
                })}
                placeholder="Internal notes or context"
                rows="2"
              />
            </div>
          </div>

          <div className="form-section">
            <h3>Social Media & External Links</h3>

            <div className="form-field">
              <label>Twitter Handle</label>
              <input
                type="text"
                value={formData.config.twitter_handle}
                onChange={(e) => setFormData({
                  ...formData,
                  config: { ...formData.config, twitter_handle: e.target.value }
                })}
                placeholder="@company"
              />
            </div>

            <div className="form-field">
              <label>LinkedIn Company URL</label>
              <input
                type="text"
                value={formData.config.linkedin_company_url}
                onChange={(e) => setFormData({
                  ...formData,
                  config: { ...formData.config, linkedin_company_url: e.target.value }
                })}
                placeholder="https://www.linkedin.com/company/..."
              />
            </div>

            <div className="form-field">
              <label>LinkedIn Company ID</label>
              <input
                type="text"
                value={formData.config.linkedin_company_id}
                onChange={(e) => setFormData({
                  ...formData,
                  config: { ...formData.config, linkedin_company_id: e.target.value }
                })}
                placeholder="company-name"
              />
            </div>
          </div>

          <div className="form-section">
            <div className="section-header">
              <h3>Keywords</h3>
              <button type="button" onClick={() => addArrayItem('keywords')} className="btn-add-small">
                + Add
              </button>
            </div>
            <div className="tag-list">
              {formData.keywords.map((keyword, idx) => (
                <div key={idx} className="tag-item">
                  <input
                    type="text"
                    value={keyword}
                    onChange={(e) => updateArrayField('keywords', idx, e.target.value)}
                    placeholder="keyword"
                  />
                  <button
                    type="button"
                    onClick={() => removeArrayItem('keywords', idx)}
                    className="tag-remove"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="form-section">
            <div className="section-header">
              <h3>Competitors</h3>
              <button type="button" onClick={() => addArrayItem('competitors')} className="btn-add-small">
                + Add
              </button>
            </div>
            <div className="tag-list">
              {formData.competitors.map((competitor, idx) => (
                <div key={idx} className="tag-item">
                  <input
                    type="text"
                    value={competitor}
                    onChange={(e) => updateArrayField('competitors', idx, e.target.value)}
                    placeholder="competitor"
                  />
                  <button
                    type="button"
                    onClick={() => removeArrayItem('competitors', idx)}
                    className="tag-remove"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="form-section">
            <div className="section-header">
              <h3>Excluded Keywords</h3>
              <button type="button" onClick={() => {
                const newKeywords = [...formData.config.collection_config.excluded_keywords, ''];
                setFormData({
                  ...formData,
                  config: {
                    ...formData.config,
                    collection_config: {
                      ...formData.config.collection_config,
                      excluded_keywords: newKeywords
                    }
                  }
                });
              }} className="btn-add-small">
                + Add
              </button>
            </div>
            <p className="section-description">Articles with these words in the title will be dropped before AI processing (e.g. NRL, AFL, lottery).</p>
            <div className="tag-list">
              {formData.config.collection_config.excluded_keywords.map((keyword, idx) => (
                <div key={idx} className="tag-item">
                  <input
                    type="text"
                    value={keyword}
                    onChange={(e) => {
                      const newKeywords = [...formData.config.collection_config.excluded_keywords];
                      newKeywords[idx] = e.target.value;
                      setFormData({
                        ...formData,
                        config: {
                          ...formData.config,
                          collection_config: {
                            ...formData.config.collection_config,
                            excluded_keywords: newKeywords
                          }
                        }
                      });
                    }}
                    placeholder="e.g. NRL"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      const newKeywords = formData.config.collection_config.excluded_keywords.filter((_, i) => i !== idx);
                      setFormData({
                        ...formData,
                        config: {
                          ...formData.config,
                          collection_config: {
                            ...formData.config.collection_config,
                            excluded_keywords: newKeywords
                          }
                        }
                      });
                    }}
                    className="tag-remove"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="form-section">
            <div className="section-header">
              <h3>Priority Keywords</h3>
              <button type="button" onClick={() => {
                const newKeywords = [...formData.config.collection_config.priority_keywords, ''];
                setFormData({
                  ...formData,
                  config: {
                    ...formData.config,
                    collection_config: {
                      ...formData.config.collection_config,
                      priority_keywords: newKeywords
                    }
                  }
                });
              }} className="btn-add-small">
                + Add
              </button>
            </div>
            <div className="tag-list">
              {formData.config.collection_config.priority_keywords.map((keyword, idx) => (
                <div key={idx} className="tag-item">
                  <input
                    type="text"
                    value={keyword}
                    onChange={(e) => {
                      const newKeywords = [...formData.config.collection_config.priority_keywords];
                      newKeywords[idx] = e.target.value;
                      setFormData({
                        ...formData,
                        config: {
                          ...formData.config,
                          collection_config: {
                            ...formData.config.collection_config,
                            priority_keywords: newKeywords
                          }
                        }
                      });
                    }}
                    placeholder="priority keyword"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      const newKeywords = formData.config.collection_config.priority_keywords.filter((_, i) => i !== idx);
                      setFormData({
                        ...formData,
                        config: {
                          ...formData.config,
                          collection_config: {
                            ...formData.config.collection_config,
                            priority_keywords: newKeywords
                          }
                        }
                      });
                    }}
                    className="tag-remove"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="form-section">
            <div className="section-header">
              <h3>Reddit Subreddits</h3>
              <button type="button" onClick={() => {
                const newSubreddits = [...formData.config.collection_config.reddit_subreddits, ''];
                setFormData({
                  ...formData,
                  config: {
                    ...formData.config,
                    collection_config: {
                      ...formData.config.collection_config,
                      reddit_subreddits: newSubreddits
                    }
                  }
                });
              }} className="btn-add-small">
                + Add
              </button>
            </div>
            <div className="tag-list">
              {formData.config.collection_config.reddit_subreddits.map((subreddit, idx) => (
                <div key={idx} className="tag-item">
                  <input
                    type="text"
                    value={subreddit}
                    onChange={(e) => {
                      const newSubreddits = [...formData.config.collection_config.reddit_subreddits];
                      newSubreddits[idx] = e.target.value;
                      setFormData({
                        ...formData,
                        config: {
                          ...formData.config,
                          collection_config: {
                            ...formData.config.collection_config,
                            reddit_subreddits: newSubreddits
                          }
                        }
                      });
                    }}
                    placeholder="subreddit name"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      const newSubreddits = formData.config.collection_config.reddit_subreddits.filter((_, i) => i !== idx);
                      setFormData({
                        ...formData,
                        config: {
                          ...formData.config,
                          collection_config: {
                            ...formData.config.collection_config,
                            reddit_subreddits: newSubreddits
                          }
                        }
                      });
                    }}
                    className="tag-remove"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="form-section">
            <div className="section-header">
              <h3>YouTube Channels to Monitor</h3>
              <button type="button" onClick={() => {
                const newChannels = [...formData.config.collection_config.youtube_channels, { channel_id: '', name: '' }];
                setFormData({
                  ...formData,
                  config: {
                    ...formData.config,
                    collection_config: {
                      ...formData.config.collection_config,
                      youtube_channels: newChannels
                    }
                  }
                });
              }} className="btn-add-small">
                + Add Channel
              </button>
            </div>
            <div className="complex-list">
              {formData.config.collection_config.youtube_channels.map((channel, idx) => (
                <div key={idx} className="complex-item">
                  <div className="complex-item-header">
                    <span className="complex-item-number">Channel #{idx + 1}</span>
                    <button
                      type="button"
                      onClick={() => {
                        const newChannels = formData.config.collection_config.youtube_channels.filter((_, i) => i !== idx);
                        setFormData({
                          ...formData,
                          config: {
                            ...formData.config,
                            collection_config: {
                              ...formData.config.collection_config,
                              youtube_channels: newChannels
                            }
                          }
                        });
                      }}
                      className="tag-remove"
                    >
                      ✕
                    </button>
                  </div>
                  <div className="complex-item-fields">
                    <div className="form-field">
                      <label>Channel ID</label>
                      <input
                        type="text"
                        value={channel.channel_id}
                        onChange={(e) => {
                          const newChannels = [...formData.config.collection_config.youtube_channels];
                          newChannels[idx] = { ...newChannels[idx], channel_id: e.target.value };
                          setFormData({
                            ...formData,
                            config: {
                              ...formData.config,
                              collection_config: {
                                ...formData.config.collection_config,
                                youtube_channels: newChannels
                              }
                            }
                          });
                        }}
                        placeholder="UCxxx... (from YouTube channel URL)"
                      />
                    </div>
                    <div className="form-field">
                      <label>Channel Name</label>
                      <input
                        type="text"
                        value={channel.name}
                        onChange={(e) => {
                          const newChannels = [...formData.config.collection_config.youtube_channels];
                          newChannels[idx] = { ...newChannels[idx], name: e.target.value };
                          setFormData({
                            ...formData,
                            config: {
                              ...formData.config,
                              collection_config: {
                                ...formData.config.collection_config,
                                youtube_channels: newChannels
                              }
                            }
                          });
                        }}
                        placeholder="e.g., Company Official Channel"
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <p className="option-help" style={{ marginTop: '12px' }}>
              YouTube will also search for videos using your customer's general keywords. Only videos with available transcripts will be processed.
            </p>
          </div>

          <div className="form-section">
            <h3>Collection Sources</h3>
            <div className="toggles-grid">
              <label className="toggle-field">
                <input
                  type="checkbox"
                  checked={formData.config.collection_config.news_enabled}
                  onChange={(e) => setFormData({
                    ...formData,
                    config: {
                      ...formData.config,
                      collection_config: {
                        ...formData.config.collection_config,
                        news_enabled: e.target.checked
                      }
                    }
                  })}
                />
                <span>News API</span>
              </label>
              <label className="toggle-field">
                <input
                  type="checkbox"
                  checked={formData.config.collection_config.google_news_enabled}
                  onChange={(e) => setFormData({
                    ...formData,
                    config: {
                      ...formData.config,
                      collection_config: {
                        ...formData.config.collection_config,
                        google_news_enabled: e.target.checked
                      }
                    }
                  })}
                />
                <span>Google News</span>
              </label>
              <label className="toggle-field">
                <input
                  type="checkbox"
                  checked={formData.config.collection_config.australian_news_enabled}
                  onChange={(e) => setFormData({
                    ...formData,
                    config: {
                      ...formData.config,
                      collection_config: {
                        ...formData.config.collection_config,
                        australian_news_enabled: e.target.checked
                      }
                    }
                  })}
                />
                <span>Australian News</span>
              </label>
              <label className="toggle-field">
                <input
                  type="checkbox"
                  checked={formData.config.collection_config.yahoo_finance_news_enabled}
                  onChange={(e) => setFormData({
                    ...formData,
                    config: {
                      ...formData.config,
                      collection_config: {
                        ...formData.config.collection_config,
                        yahoo_finance_news_enabled: e.target.checked
                      }
                    }
                  })}
                />
                <span>Yahoo Finance News</span>
              </label>
              <label className="toggle-field">
                <input
                  type="checkbox"
                  checked={formData.config.collection_config.asx_announcements_enabled}
                  onChange={(e) => setFormData({
                    ...formData,
                    config: {
                      ...formData.config,
                      collection_config: {
                        ...formData.config.collection_config,
                        asx_announcements_enabled: e.target.checked
                      }
                    }
                  })}
                />
                <span>ASX Announcements</span>
              </label>
              <label className="toggle-field">
                <input
                  type="checkbox"
                  checked={formData.config.collection_config.rss_enabled}
                  onChange={(e) => setFormData({
                    ...formData,
                    config: {
                      ...formData.config,
                      collection_config: {
                        ...formData.config.collection_config,
                        rss_enabled: e.target.checked
                      }
                    }
                  })}
                />
                <span>RSS Feeds</span>
              </label>
              <label className="toggle-field">
                <input
                  type="checkbox"
                  checked={formData.config.collection_config.reddit_enabled}
                  onChange={(e) => setFormData({
                    ...formData,
                    config: {
                      ...formData.config,
                      collection_config: {
                        ...formData.config.collection_config,
                        reddit_enabled: e.target.checked
                      }
                    }
                  })}
                />
                <span>Reddit</span>
              </label>
              <label className="toggle-field">
                <input
                  type="checkbox"
                  checked={formData.config.collection_config.youtube_enabled}
                  onChange={(e) => setFormData({
                    ...formData,
                    config: {
                      ...formData.config,
                      collection_config: {
                        ...formData.config.collection_config,
                        youtube_enabled: e.target.checked
                      }
                    }
                  })}
                />
                <span>YouTube</span>
              </label>
              <label className="toggle-field">
                <input
                  type="checkbox"
                  checked={formData.config.collection_config.linkedin_enabled}
                  onChange={(e) => setFormData({
                    ...formData,
                    config: {
                      ...formData.config,
                      collection_config: {
                        ...formData.config.collection_config,
                        linkedin_enabled: e.target.checked
                      }
                    }
                  })}
                />
                <span>LinkedIn Company</span>
              </label>
              <label className="toggle-field">
                <input
                  type="checkbox"
                  checked={formData.config.collection_config.linkedin_user_enabled}
                  onChange={(e) => setFormData({
                    ...formData,
                    config: {
                      ...formData.config,
                      collection_config: {
                        ...formData.config.collection_config,
                        linkedin_user_enabled: e.target.checked
                      }
                    }
                  })}
                />
                <span>LinkedIn User Profiles</span>
              </label>
              <label className="toggle-field">
                <input
                  type="checkbox"
                  checked={formData.config.collection_config.twitter_enabled}
                  onChange={(e) => setFormData({
                    ...formData,
                    config: {
                      ...formData.config,
                      collection_config: {
                        ...formData.config.collection_config,
                        twitter_enabled: e.target.checked
                      }
                    }
                  })}
                />
                <span>Twitter</span>
              </label>
              <label className="toggle-field">
                <input
                  type="checkbox"
                  checked={formData.config.collection_config.pressrelease_enabled}
                  onChange={(e) => setFormData({
                    ...formData,
                    config: {
                      ...formData.config,
                      collection_config: {
                        ...formData.config.collection_config,
                        pressrelease_enabled: e.target.checked
                      }
                    }
                  })}
                />
                <span>Press Releases</span>
              </label>
              <label className="toggle-field">
                <input
                  type="checkbox"
                  checked={formData.config.collection_config.gmail_enabled}
                  onChange={(e) => setFormData({
                    ...formData,
                    config: {
                      ...formData.config,
                      collection_config: {
                        ...formData.config.collection_config,
                        gmail_enabled: e.target.checked
                      }
                    }
                  })}
                  disabled={!gmailStatus.connected}
                />
                <span>Gmail Digest Monitoring</span>
              </label>
              <label className="toggle-field">
                <input
                  type="checkbox"
                  checked={formData.config.collection_config.mailsac_enabled}
                  onChange={(e) => setFormData({
                    ...formData,
                    config: {
                      ...formData.config,
                      collection_config: {
                        ...formData.config.collection_config,
                        mailsac_enabled: e.target.checked
                      }
                    }
                  })}
                />
                <span>Mailsac Newsletters</span>
              </label>
            </div>
          </div>

          <div className="form-section">
            <div className="section-header">
              <h3>RSS Feeds</h3>
              <button type="button" onClick={addRssFeed} className="btn-add-small">
                + Add
              </button>
            </div>
            <div className="complex-list">
              {formData.config.rss_feeds.map((feed, idx) => (
                <div key={idx} className="complex-item">
                  <div className="complex-item-header">
                    <span className="complex-item-number">Feed #{idx + 1}</span>
                    <button
                      type="button"
                      onClick={() => removeRssFeed(idx)}
                      className="tag-remove"
                    >
                      ✕
                    </button>
                  </div>
                  <div className="complex-item-fields">
                    <div className="form-field">
                      <label>Feed Name</label>
                      <input
                        type="text"
                        value={feed.name}
                        onChange={(e) => updateRssFeed(idx, 'name', e.target.value)}
                        placeholder="e.g., Company Blog"
                      />
                    </div>
                    <div className="form-field">
                      <label>Feed URL</label>
                      <input
                        type="text"
                        value={feed.url}
                        onChange={(e) => updateRssFeed(idx, 'url', e.target.value)}
                        placeholder="https://example.com/feed.xml"
                      />
                    </div>
                    <label className="toggle-field" style={{ marginTop: '8px' }}>
                      <input
                        type="checkbox"
                        checked={feed.trusted || false}
                        onChange={(e) => updateRssFeed(idx, 'trusted', e.target.checked)}
                      />
                      <span>Trusted Source</span>
                      <small style={{ display: 'block', marginLeft: '24px', color: '#6b7280', marginTop: '4px' }}>
                        Official newsroom/press releases - never marked as irrelevant
                      </small>
                    </label>
                  </div>
                </div>
              ))}
            </div>
            <p className="option-help" style={{ marginTop: '12px' }}>
              Mark RSS feeds from official company newsrooms or press release pages as "Trusted" to ensure they're never categorized as irrelevant or advertisements.
            </p>
          </div>

          <div className="form-section">
            <div className="section-header">
              <h3>LinkedIn User Profiles to Monitor</h3>
              <button type="button" onClick={addLinkedInProfile} className="btn-add-small">
                + Add
              </button>
            </div>
            <div className="complex-list">
              {formData.config.linkedin_user_profiles.map((profile, idx) => (
                <div key={idx} className="complex-item">
                  <div className="complex-item-header">
                    <span className="complex-item-number">Profile #{idx + 1}</span>
                    <button
                      type="button"
                      onClick={() => removeLinkedInProfile(idx)}
                      className="tag-remove"
                    >
                      ✕
                    </button>
                  </div>
                  <div className="complex-item-fields">
                    <div className="form-field">
                      <label>Name</label>
                      <input
                        type="text"
                        value={profile.name}
                        onChange={(e) => updateLinkedInProfile(idx, 'name', e.target.value)}
                        placeholder="e.g., John Smith"
                      />
                    </div>
                    <div className="form-field">
                      <label>Profile URL</label>
                      <input
                        type="text"
                        value={profile.profile_url}
                        onChange={(e) => updateLinkedInProfile(idx, 'profile_url', e.target.value)}
                        placeholder="https://linkedin.com/in/..."
                      />
                    </div>
                    <div className="form-field">
                      <label>Role</label>
                      <input
                        type="text"
                        value={profile.role}
                        onChange={(e) => updateLinkedInProfile(idx, 'role', e.target.value)}
                        placeholder="e.g., CEO, CTO"
                      />
                    </div>
                    <div className="form-field">
                      <label>Notes</label>
                      <textarea
                        value={profile.notes}
                        onChange={(e) => updateLinkedInProfile(idx, 'notes', e.target.value)}
                        placeholder="Why are we monitoring this person?"
                        rows="2"
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="form-section">
            <div className="section-header">
              <h3>Web Scrape Sources</h3>
              <button type="button" onClick={addWebScrapeSource} className="btn-add-small">
                + Add
              </button>
            </div>
            <div className="complex-list">
              {formData.config.collection_config.web_scrape_sources.map((source, idx) => (
                <div key={idx} className="complex-item">
                  <div className="complex-item-header">
                    <span className="complex-item-number">Source #{idx + 1}</span>
                    <button
                      type="button"
                      onClick={() => removeWebScrapeSource(idx)}
                      className="tag-remove"
                    >
                      ✕
                    </button>
                  </div>
                  <div className="complex-item-fields">
                    <div className="form-field">
                      <label>Source Name <span className="required">*</span></label>
                      <input
                        type="text"
                        value={source.name}
                        onChange={(e) => updateWebScrapeSource(idx, 'name', e.target.value)}
                        placeholder="e.g., Company Newsroom"
                        required
                      />
                    </div>
                    <div className="form-field">
                      <label>URL <span className="required">*</span></label>
                      <input
                        type="text"
                        value={source.url}
                        onChange={(e) => updateWebScrapeSource(idx, 'url', e.target.value)}
                        placeholder="https://example.com/news"
                        required
                      />
                    </div>
                    <div className="form-field">
                      <label>Article List Selector <span className="required">*</span></label>
                      <input
                        type="text"
                        value={source.selectors.article_list}
                        onChange={(e) => updateWebScrapeSource(idx, 'selectors.article_list', e.target.value)}
                        placeholder="CSS selector (e.g., div.article)"
                        required
                      />
                    </div>
                    <div className="form-field">
                      <label>Link Selector</label>
                      <input
                        type="text"
                        value={source.selectors.link}
                        onChange={(e) => updateWebScrapeSource(idx, 'selectors.link', e.target.value)}
                        placeholder="CSS selector (e.g., a.title)"
                      />
                    </div>
                    <div className="form-field">
                      <label>Max Articles</label>
                      <input
                        type="number"
                        value={source.max_articles}
                        onChange={(e) => updateWebScrapeSource(idx, 'max_articles', parseInt(e.target.value) || 20)}
                        placeholder="20"
                        min="1"
                        max="100"
                      />
                    </div>
                    <label className="toggle-field">
                      <input
                        type="checkbox"
                        checked={source.extract_full_content}
                        onChange={(e) => updateWebScrapeSource(idx, 'extract_full_content', e.target.checked)}
                      />
                      <span>Extract Full Content</span>
                    </label>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="form-section">
            <h3>Gmail Press Release Monitoring</h3>

            <div className="gmail-connection-status">
              {gmailStatus.loading ? (
                <p>Loading Gmail status...</p>
              ) : gmailStatus.connected ? (
                <div className="gmail-connected">
                  <div className="gmail-status-header">
                    <span className="status-indicator status-connected">● Connected</span>
                    <span className="gmail-email">{gmailStatus.email}</span>
                  </div>
                  <button
                    type="button"
                    onClick={handleDisconnectGmail}
                    className="btn-disconnect"
                  >
                    Disconnect Gmail
                  </button>
                </div>
              ) : (
                <div className="gmail-not-connected">
                  <p className="option-help">
                    Connect your Gmail account to monitor press release digests from services like PR Newswire and Business Wire.
                  </p>
                  <button
                    type="button"
                    onClick={handleConnectGmail}
                    className="btn-connect-gmail"
                  >
                    Connect Gmail Account
                  </button>
                </div>
              )}
            </div>

            {gmailStatus.connected && (
              <div className="gmail-config">
                <div className="form-field">
                  <label className="toggle-field">
                    <input
                      type="checkbox"
                      checked={formData.config.collection_config.gmail_config.use_sender_whitelist}
                      onChange={(e) => setFormData({
                        ...formData,
                        config: {
                          ...formData.config,
                          collection_config: {
                            ...formData.config.collection_config,
                            gmail_config: {
                              ...formData.config.collection_config.gmail_config,
                              use_sender_whitelist: e.target.checked
                            }
                          }
                        }
                      })}
                    />
                    <span>Filter by sender whitelist</span>
                  </label>
                  <small style={{ display: 'block', marginTop: '6px', color: '#6b7280' }}>
                    Only process emails from specific senders. Leave unchecked to process all emails.
                  </small>
                </div>

                {formData.config.collection_config.gmail_config.use_sender_whitelist && (
                  <div className="form-field">
                    <label>Allowed Sender Domains</label>
                    <textarea
                      value={formData.config.collection_config.gmail_config.sender_whitelist.join('\n')}
                      onChange={(e) => setFormData({
                        ...formData,
                        config: {
                          ...formData.config,
                          collection_config: {
                            ...formData.config.collection_config,
                            gmail_config: {
                              ...formData.config.collection_config.gmail_config,
                              sender_whitelist: e.target.value.split('\n').filter(s => s.trim())
                            }
                          }
                        }
                      })}
                      placeholder="prnewswire.com&#10;businesswire.com&#10;ir@company.com"
                      rows="4"
                    />
                    <small style={{ display: 'block', marginTop: '6px', color: '#6b7280' }}>
                      One sender domain or email per line (e.g., prnewswire.com or news@businesswire.com)
                    </small>
                  </div>
                )}

                <div className="form-field">
                  <label className="toggle-field">
                    <input
                      type="checkbox"
                      checked={formData.config.collection_config.gmail_config.label_config.mark_as_read}
                      onChange={(e) => setFormData({
                        ...formData,
                        config: {
                          ...formData.config,
                          collection_config: {
                            ...formData.config.collection_config,
                            gmail_config: {
                              ...formData.config.collection_config.gmail_config,
                              label_config: {
                                ...formData.config.collection_config.gmail_config.label_config,
                                mark_as_read: e.target.checked
                              }
                            }
                          }
                        }
                      })}
                    />
                    <span>Mark emails as read after processing</span>
                  </label>
                </div>

                <div className="form-field">
                  <label>Gmail Label (optional)</label>
                  <input
                    type="text"
                    value={formData.config.collection_config.gmail_config.label_config.apply_label}
                    onChange={(e) => setFormData({
                      ...formData,
                      config: {
                        ...formData.config,
                        collection_config: {
                          ...formData.config.collection_config,
                          gmail_config: {
                            ...formData.config.collection_config.gmail_config,
                            label_config: {
                              ...formData.config.collection_config.gmail_config.label_config,
                              apply_label: e.target.value
                            }
                          }
                        }
                      }
                    })}
                    placeholder="Intelligence/Processed"
                  />
                  <small style={{ display: 'block', marginTop: '6px', color: '#6b7280' }}>
                    Apply this label to processed emails. Leave empty to skip labeling.
                  </small>
                </div>
              </div>
            )}
          </div>

          <div className="form-section">
            <h3>Mailsac Newsletter Monitoring</h3>
            <p className="option-help" style={{ marginBottom: '16px' }}>
              Use Mailsac disposable email addresses to subscribe to newsletters without exposing your personal email.
              Requires MAILSAC_API_KEY to be set in backend environment.
            </p>

            <div className="form-field">
              <label>Email Addresses to Monitor</label>
              <textarea
                value={formData.config.collection_config.mailsac_config.email_addresses.join('\n')}
                onChange={(e) => setFormData({
                  ...formData,
                  config: {
                    ...formData.config,
                    collection_config: {
                      ...formData.config.collection_config,
                      mailsac_config: {
                        ...formData.config.collection_config.mailsac_config,
                        email_addresses: e.target.value.split('\n').filter(s => s.trim())
                      }
                    }
                  }
                })}
                placeholder="newsletters-companyname@mailsac.com&#10;alerts-companyname@mailsac.com"
                rows="3"
              />
              <small style={{ display: 'block', marginTop: '6px', color: '#6b7280' }}>
                One Mailsac email address per line. Create addresses at mailsac.com and subscribe them to newsletters.
              </small>
            </div>

            <div className="form-field">
              <label className="toggle-field">
                <input
                  type="checkbox"
                  checked={formData.config.collection_config.mailsac_config.extract_links}
                  onChange={(e) => setFormData({
                    ...formData,
                    config: {
                      ...formData.config,
                      collection_config: {
                        ...formData.config.collection_config,
                        mailsac_config: {
                          ...formData.config.collection_config.mailsac_config,
                          extract_links: e.target.checked
                        }
                      }
                    }
                  })}
                />
                <span>Extract and fetch linked articles</span>
              </label>
              <small style={{ display: 'block', marginLeft: '24px', marginTop: '4px', color: '#6b7280' }}>
                Follow links in newsletters to fetch full article content. Disable to use email content directly.
              </small>
            </div>

            <div className="form-field">
              <label className="toggle-field">
                <input
                  type="checkbox"
                  checked={formData.config.collection_config.mailsac_config.delete_after_processing}
                  onChange={(e) => setFormData({
                    ...formData,
                    config: {
                      ...formData.config,
                      collection_config: {
                        ...formData.config.collection_config,
                        mailsac_config: {
                          ...formData.config.collection_config.mailsac_config,
                          delete_after_processing: e.target.checked
                        }
                      }
                    }
                  })}
                />
                <span>Delete emails after processing</span>
              </label>
              <small style={{ display: 'block', marginLeft: '24px', marginTop: '4px', color: '#6b7280' }}>
                Recommended to stay within Mailsac storage limits (50 messages on free tier).
              </small>
            </div>

            <div className="form-field">
              <label>Max Age (days)</label>
              <input
                type="number"
                value={formData.config.collection_config.mailsac_config.max_age_days}
                onChange={(e) => setFormData({
                  ...formData,
                  config: {
                    ...formData.config,
                    collection_config: {
                      ...formData.config.collection_config,
                      mailsac_config: {
                        ...formData.config.collection_config.mailsac_config,
                        max_age_days: parseInt(e.target.value) || 7
                      }
                    }
                  }
                })}
                min="1"
                max="30"
                style={{ width: '100px' }}
              />
              <small style={{ display: 'block', marginTop: '6px', color: '#6b7280' }}>
                Ignore emails older than this many days.
              </small>
            </div>
          </div>

          <div className="modal-footer">
            <button
              type="button"
              onClick={() => setShowDeleteConfirm(true)}
              className="btn-delete-modal"
              disabled={loading}
            >
              Delete Customer
            </button>
            <div className="modal-footer-right">
              <button type="button" onClick={onClose} className="btn-cancel" disabled={loading}>
                Cancel
              </button>
              <button type="submit" className="btn-save" disabled={loading}>
                {loading ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </form>

        {/* Delete Confirmation Overlay */}
        {showDeleteConfirm && (
          <div className="delete-confirm-overlay">
            <div className="delete-confirm-box">
              <h3>Delete Customer?</h3>
              <p>Are you sure you want to delete <strong>{customer.name}</strong>?</p>
              <p className="warning-text">This will permanently delete all intelligence data for this customer. This action cannot be undone.</p>
              <div className="confirm-actions">
                <button onClick={() => setShowDeleteConfirm(false)} className="btn-cancel">
                  Cancel
                </button>
                <button onClick={onDelete} className="btn-delete-confirm">
                  Delete Customer
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
