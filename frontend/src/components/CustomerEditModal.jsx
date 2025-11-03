import { useState, useEffect } from 'react';
import axios from 'axios';
import './CustomerEditModal.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function CustomerEditModal({ customer, onClose, onSave, onDelete }) {
  const [formData, setFormData] = useState({
    name: '',
    domain: '',
    keywords: [],
    competitors: [],
    stock_symbol: '',
    config: {
      description: '',
      notes: '',
      twitter_handle: '',
      linkedin_company_url: '',
      linkedin_company_id: '',
      github_org: '',
      github_repos: [],
      rss_feeds: [],
      linkedin_user_profiles: [],
      collection_config: {
        news_enabled: true,
        yahoo_finance_news_enabled: false,
        rss_enabled: true,
        australian_news_enabled: true,
        google_news_enabled: true,
        reddit_enabled: false,
        hackernews_enabled: false,
        github_enabled: false,
        twitter_enabled: false,
        linkedin_enabled: false,
        linkedin_user_enabled: false,
        pressrelease_enabled: false,
        reddit_subreddits: [],
        priority_keywords: [],
        web_scrape_sources: []
      }
    }
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

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
        config: {
          description: config.description || '',
          notes: config.notes || '',
          twitter_handle: config.twitter_handle || '',
          linkedin_company_url: config.linkedin_company_url || '',
          linkedin_company_id: config.linkedin_company_id || '',
          github_org: config.github_org || '',
          github_repos: config.github_repos || [],
          rss_feeds: config.rss_feeds || [],
          linkedin_user_profiles: config.linkedin_user_profiles || [],
          collection_config: {
            news_enabled: collectionConfig.news_enabled !== undefined ? collectionConfig.news_enabled : true,
            yahoo_finance_news_enabled: collectionConfig.yahoo_finance_news_enabled || collectionConfig.stock_enabled || false,
            rss_enabled: collectionConfig.rss_enabled !== undefined ? collectionConfig.rss_enabled : true,
            australian_news_enabled: collectionConfig.australian_news_enabled !== undefined ? collectionConfig.australian_news_enabled : true,
            google_news_enabled: collectionConfig.google_news_enabled !== undefined ? collectionConfig.google_news_enabled : true,
            reddit_enabled: collectionConfig.reddit_enabled || false,
            hackernews_enabled: collectionConfig.hackernews_enabled || false,
            github_enabled: collectionConfig.github_enabled || false,
            twitter_enabled: collectionConfig.twitter_enabled || false,
            linkedin_enabled: collectionConfig.linkedin_enabled || false,
            linkedin_user_enabled: collectionConfig.linkedin_user_enabled || false,
            pressrelease_enabled: collectionConfig.pressrelease_enabled || false,
            reddit_subreddits: collectionConfig.reddit_subreddits || [],
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
            }))
          }
        }
      });
    }
  }, [customer]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

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
        config: flatConfig
      };

      await axios.put(`${API_URL}/api/customers/${customer.id}`, payload);
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

  // GitHub Repo management
  const addGithubRepo = () => {
    const newRepos = [...formData.config.github_repos, ''];
    setFormData({
      ...formData,
      config: { ...formData.config, github_repos: newRepos }
    });
  };

  const updateGithubRepo = (index, value) => {
    const newRepos = [...formData.config.github_repos];
    newRepos[index] = value;
    setFormData({
      ...formData,
      config: { ...formData.config, github_repos: newRepos }
    });
  };

  const removeGithubRepo = (index) => {
    const newRepos = formData.config.github_repos.filter((_, i) => i !== index);
    setFormData({
      ...formData,
      config: { ...formData.config, github_repos: newRepos }
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

            <div className="form-field">
              <label>GitHub Organization</label>
              <input
                type="text"
                value={formData.config.github_org}
                onChange={(e) => setFormData({
                  ...formData,
                  config: { ...formData.config, github_org: e.target.value }
                })}
                placeholder="github-org"
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
                  checked={formData.config.collection_config.hackernews_enabled}
                  onChange={(e) => setFormData({
                    ...formData,
                    config: {
                      ...formData.config,
                      collection_config: {
                        ...formData.config.collection_config,
                        hackernews_enabled: e.target.checked
                      }
                    }
                  })}
                />
                <span>Hacker News</span>
              </label>
              <label className="toggle-field">
                <input
                  type="checkbox"
                  checked={formData.config.collection_config.github_enabled}
                  onChange={(e) => setFormData({
                    ...formData,
                    config: {
                      ...formData.config,
                      collection_config: {
                        ...formData.config.collection_config,
                        github_enabled: e.target.checked
                      }
                    }
                  })}
                />
                <span>GitHub</span>
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
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="form-section">
            <div className="section-header">
              <h3>GitHub Repositories</h3>
              <button type="button" onClick={addGithubRepo} className="btn-add-small">
                + Add
              </button>
            </div>
            <div className="tag-list">
              {formData.config.github_repos.map((repo, idx) => (
                <div key={idx} className="tag-item">
                  <input
                    type="text"
                    value={repo}
                    onChange={(e) => updateGithubRepo(idx, e.target.value)}
                    placeholder="owner/repo-name"
                  />
                  <button
                    type="button"
                    onClick={() => removeGithubRepo(idx)}
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
                      <label>Source Name</label>
                      <input
                        type="text"
                        value={source.name}
                        onChange={(e) => updateWebScrapeSource(idx, 'name', e.target.value)}
                        placeholder="e.g., Company Newsroom"
                      />
                    </div>
                    <div className="form-field">
                      <label>URL</label>
                      <input
                        type="text"
                        value={source.url}
                        onChange={(e) => updateWebScrapeSource(idx, 'url', e.target.value)}
                        placeholder="https://example.com/news"
                      />
                    </div>
                    <div className="form-field">
                      <label>Article List Selector</label>
                      <input
                        type="text"
                        value={source.selectors.article_list}
                        onChange={(e) => updateWebScrapeSource(idx, 'selectors.article_list', e.target.value)}
                        placeholder="CSS selector (e.g., div.article)"
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
