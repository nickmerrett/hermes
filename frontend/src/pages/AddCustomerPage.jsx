import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../api/auth';
import './AddCustomerPage.css';

export default function AddCustomerPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Step 1: Company name input
  const [companyName, setCompanyName] = useState('');

  // Step 2: Research results (editable)
  const [researchData, setResearchData] = useState(null);

  const handleResearch = async () => {
    if (!companyName.trim()) {
      setError('Please enter a company name');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await apiClient.post(`/customer-research/research`, {
        company_name: companyName
      });

      setResearchData(response.data);
      setStep(2);
    } catch (err) {
      console.error('Research error:', err);
      setError(err.response?.data?.detail || 'Failed to research company');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveCustomer = async () => {
    setLoading(true);
    setError(null);

    try {
      // Map researchData to Customer schema
      const customerData = {
        name: researchData.company_name,
        domain: researchData.domain || null,
        keywords: researchData.keywords || [],
        competitors: researchData.competitors || [],
        stock_symbol: researchData.stock_symbol || null,
        config: {
          industry: researchData.industry || null,
          description: researchData.description || null,
          executives: researchData.executives || [],
          priority_keywords: researchData.priority_keywords || []
        }
      };

      await apiClient.post(`/customers`, customerData);

      setStep(3);
    } catch (err) {
      console.error('Save customer error:', err);
      setError(err.response?.data?.detail || 'Failed to save customer');
    } finally {
      setLoading(false);
    }
  };

  const updateResearchField = (field, value) => {
    setResearchData({ ...researchData, [field]: value });
  };

  const updateArrayField = (field, index, value) => {
    const newArray = [...researchData[field]];
    newArray[index] = value;
    setResearchData({ ...researchData, [field]: newArray });
  };

  const addArrayItem = (field, defaultValue = '') => {
    setResearchData({
      ...researchData,
      [field]: [...researchData[field], defaultValue]
    });
  };

  const removeArrayItem = (field, index) => {
    const newArray = researchData[field].filter((_, i) => i !== index);
    setResearchData({ ...researchData, [field]: newArray });
  };

  const updateExecutive = (index, field, value) => {
    const newExecs = [...researchData.executives];
    newExecs[index] = { ...newExecs[index], [field]: value };
    setResearchData({ ...researchData, executives: newExecs });
  };

  const addExecutive = () => {
    setResearchData({
      ...researchData,
      executives: [...researchData.executives, { name: '', role: '', linkedin_url: '', notes: '' }]
    });
  };

  const removeExecutive = (index) => {
    const newExecs = researchData.executives.filter((_, i) => i !== index);
    setResearchData({ ...researchData, executives: newExecs });
  };

  return (
    <div className="add-customer-page">
      <div className="page-container">
        <div className="page-header">
          <h1>Add New Customer</h1>
          <p>AI-powered configuration wizard</p>
          <button onClick={() => navigate('/')} className="btn-back">
            ← Back to Dashboard
          </button>
        </div>

        <div className="progress-bar">
          <div className={`progress-step ${step >= 1 ? 'active' : ''} ${step > 1 ? 'completed' : ''}`}>
            <div className="step-number">1</div>
            <div className="step-label">Company Name</div>
          </div>
          <div className="progress-line"></div>
          <div className={`progress-step ${step >= 2 ? 'active' : ''} ${step > 2 ? 'completed' : ''}`}>
            <div className="step-number">2</div>
            <div className="step-label">Review & Edit</div>
          </div>
          <div className="progress-line"></div>
          <div className={`progress-step ${step >= 3 ? 'active' : ''}`}>
            <div className="step-number">3</div>
            <div className="step-label">Save Customer</div>
          </div>
        </div>

        {error && (
          <div className="error-banner">
            <span>⚠️</span> {error}
          </div>
        )}

        <div className="step-content">
          {/* Step 1: Company Name */}
          {step === 1 && (
            <div className="step-panel">
              <h2>Enter Company Name</h2>
              <p className="step-description">
                We'll use AI to automatically research and discover:
              </p>
              <ul className="feature-list">
                <li>✓ Company information (domain, description, stock symbol)</li>
                <li>✓ Executive team and LinkedIn profiles</li>
                <li>✓ Main competitors in the industry</li>
                <li>✓ Relevant keywords and monitoring sources</li>
              </ul>

              <div className="input-group">
                <input
                  type="text"
                  className="company-input"
                  placeholder="e.g., Atlassian, Tesla, Commonwealth Bank"
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleResearch()}
                  autoFocus
                />
              </div>

              <div className="button-group">
                <button
                  onClick={handleResearch}
                  className="btn-primary btn-large"
                  disabled={loading || !companyName.trim()}
                >
                  {loading ? '🔍 Researching...' : '🔍 Research Company →'}
                </button>
              </div>
            </div>
          )}

          {/* Step 2: Review & Edit */}
          {step === 2 && researchData && (
            <div className="step-panel">
              <h2>Review & Edit Research Results</h2>
              <p className="step-description">
                Review the discovered information and make any necessary edits:
              </p>

              <div className="form-sections">
                {/* Basic Info Section */}
                <section className="form-section">
                  <h3>Basic Information</h3>
                  <div className="form-grid">
                    <div className="form-field">
                      <label>Company Name</label>
                      <input
                        type="text"
                        value={researchData.company_name}
                        onChange={(e) => updateResearchField('company_name', e.target.value)}
                      />
                    </div>
                    <div className="form-field">
                      <label>Domain</label>
                      <input
                        type="text"
                        value={researchData.domain || ''}
                        onChange={(e) => updateResearchField('domain', e.target.value)}
                        placeholder="example.com"
                      />
                    </div>
                    <div className="form-field">
                      <label>Stock Symbol</label>
                      <input
                        type="text"
                        value={researchData.stock_symbol || ''}
                        onChange={(e) => updateResearchField('stock_symbol', e.target.value)}
                        placeholder="AAPL, TEAM, CBA.AX"
                      />
                    </div>
                    <div className="form-field">
                      <label>Industry</label>
                      <input
                        type="text"
                        value={researchData.industry || ''}
                        onChange={(e) => updateResearchField('industry', e.target.value)}
                      />
                    </div>
                    <div className="form-field full-width">
                      <label>Description</label>
                      <textarea
                        value={researchData.description || ''}
                        onChange={(e) => updateResearchField('description', e.target.value)}
                        rows="3"
                      />
                    </div>
                  </div>
                </section>

                {/* Executives Section */}
                <section className="form-section">
                  <div className="section-header">
                    <h3>Executives to Monitor</h3>
                    <button onClick={addExecutive} className="btn-add">+ Add Executive</button>
                  </div>
                  <div className="warning-box">
                    <span className="warning-icon">⚠️</span>
                    <div className="warning-text">
                      <strong>Please verify executive information:</strong> AI-suggested executives may be outdated.
                      Check LinkedIn or company website to confirm current roles and remove anyone who has left the company.
                    </div>
                  </div>
                  <div className="executives-list">
                    {researchData.executives.map((exec, idx) => (
                      <div key={idx} className="executive-card">
                        <div className="executive-grid">
                          <input
                            type="text"
                            placeholder="Full Name"
                            value={exec.name}
                            onChange={(e) => updateExecutive(idx, 'name', e.target.value)}
                          />
                          <input
                            type="text"
                            placeholder="Role (e.g., CEO, CTO)"
                            value={exec.role}
                            onChange={(e) => updateExecutive(idx, 'role', e.target.value)}
                          />
                        </div>
                        <input
                          type="text"
                          placeholder="LinkedIn Profile URL"
                          value={exec.linkedin_url}
                          onChange={(e) => updateExecutive(idx, 'linkedin_url', e.target.value)}
                          className="exec-url"
                        />
                        <input
                          type="text"
                          placeholder="Notes (why monitor this person?)"
                          value={exec.notes}
                          onChange={(e) => updateExecutive(idx, 'notes', e.target.value)}
                          className="exec-notes"
                        />
                        <button
                          onClick={() => removeExecutive(idx)}
                          className="btn-remove"
                        >
                          ✕ Remove
                        </button>
                      </div>
                    ))}
                  </div>
                </section>

                {/* Competitors Section */}
                <section className="form-section">
                  <div className="section-header">
                    <h3>Competitors</h3>
                    <button onClick={() => addArrayItem('competitors', '')} className="btn-add">+ Add Competitor</button>
                  </div>
                  <div className="tag-list">
                    {researchData.competitors.map((competitor, idx) => (
                      <div key={idx} className="tag-item">
                        <input
                          type="text"
                          value={competitor}
                          onChange={(e) => updateArrayField('competitors', idx, e.target.value)}
                        />
                        <button
                          onClick={() => removeArrayItem('competitors', idx)}
                          className="tag-remove"
                        >
                          ✕
                        </button>
                      </div>
                    ))}
                  </div>
                </section>

                {/* Keywords Section */}
                <section className="form-section">
                  <div className="section-header">
                    <h3>Keywords to Monitor</h3>
                    <button onClick={() => addArrayItem('keywords', '')} className="btn-add">+ Add Keyword</button>
                  </div>
                  <div className="tag-list">
                    {researchData.keywords.map((keyword, idx) => (
                      <div key={idx} className="tag-item">
                        <input
                          type="text"
                          value={keyword}
                          onChange={(e) => updateArrayField('keywords', idx, e.target.value)}
                        />
                        <button
                          onClick={() => removeArrayItem('keywords', idx)}
                          className="tag-remove"
                        >
                          ✕
                        </button>
                      </div>
                    ))}
                  </div>
                </section>

                {/* Priority Keywords Section */}
                <section className="form-section">
                  <div className="section-header">
                    <h3>Priority Keywords (High-Impact Terms)</h3>
                    <button onClick={() => addArrayItem('priority_keywords', '')} className="btn-add">+ Add Priority Keyword</button>
                  </div>
                  <div className="tag-list">
                    {researchData.priority_keywords.map((keyword, idx) => (
                      <div key={idx} className="tag-item">
                        <input
                          type="text"
                          value={keyword}
                          onChange={(e) => updateArrayField('priority_keywords', idx, e.target.value)}
                        />
                        <button
                          onClick={() => removeArrayItem('priority_keywords', idx)}
                          className="tag-remove"
                        >
                          ✕
                        </button>
                      </div>
                    ))}
                  </div>
                </section>
              </div>

              <div className="button-group">
                <button onClick={() => setStep(1)} className="btn-secondary">
                  ← Back
                </button>
                <button
                  onClick={handleSaveCustomer}
                  className="btn-primary btn-large"
                  disabled={loading}
                >
                  {loading ? 'Saving...' : 'Save Customer →'}
                </button>
              </div>
            </div>
          )}

          {/* Step 3: Success */}
          {step === 3 && (
            <div className="step-panel">
              <h2>✅ Customer Saved Successfully!</h2>
              <p className="step-description">
                {researchData.company_name} has been added to your intelligence platform.
              </p>

              <div className="success-box">
                <div className="success-icon">🎉</div>
                <h3>What's Next?</h3>
                <ul className="next-steps">
                  <li>✓ Customer profile is now in the database</li>
                  <li>✓ You can now trigger a collection to start gathering intelligence</li>
                  <li>✓ The customer will appear in your dashboard tabs</li>
                </ul>
              </div>

              <div className="button-group">
                <button onClick={() => setStep(2)} className="btn-secondary">
                  ← Edit Configuration
                </button>
                <button onClick={() => navigate('/')} className="btn-success btn-large">
                  ✓ Back to Dashboard
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
