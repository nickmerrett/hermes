import { useState } from 'react';
import axios from 'axios';
import './CustomerConfigWizard.css';

const API_URL = import.meta.env.VITE_API_URL || '/api';

export default function CustomerConfigWizard({ onClose }) {
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Step 1: Company name input
  const [companyName, setCompanyName] = useState('');

  // Step 2: Research results (editable)
  const [researchData, setResearchData] = useState(null);

  // Final: Generated YAML
  const [yamlConfig, setYamlConfig] = useState('');

  const handleResearch = async () => {
    if (!companyName.trim()) {
      setError('Please enter a company name');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await axios.post(`${API_URL}/customer-research/research`, {
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

  const handleGenerateConfig = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await axios.post(`${API_URL}/customer-research/generate-config`, {
        research_data: researchData
      });

      setYamlConfig(response.data.yaml_config);
      setStep(3);
    } catch (err) {
      console.error('Generate config error:', err);
      setError(err.response?.data?.detail || 'Failed to generate configuration');
    } finally {
      setLoading(false);
    }
  };

  const handleCopyToClipboard = () => {
    navigator.clipboard.writeText(yamlConfig);
    alert('Configuration copied to clipboard!');
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
    <div className="wizard-overlay">
      <div className="wizard-modal">
        <div className="wizard-header">
          <h2>Add New Customer - Configuration Wizard</h2>
          <button onClick={onClose} className="close-btn">&times;</button>
        </div>

        <div className="wizard-progress">
          <div className={`progress-step ${step >= 1 ? 'active' : ''}`}>1. Company</div>
          <div className={`progress-step ${step >= 2 ? 'active' : ''}`}>2. Review & Edit</div>
          <div className={`progress-step ${step >= 3 ? 'active' : ''}`}>3. Generate</div>
        </div>

        {error && (
          <div className="error-message">
            {error}
          </div>
        )}

        {/* Step 1: Company Name */}
        {step === 1 && (
          <div className="wizard-step">
            <h3>Enter Company Name</h3>
            <p>We'll automatically research this company and discover:</p>
            <ul>
              <li>Company info (domain, description, stock symbol)</li>
              <li>Executive team and LinkedIn profiles</li>
              <li>Competitors</li>
              <li>Keywords and data sources</li>
            </ul>

            <input
              type="text"
              className="company-input"
              placeholder="e.g., Atlassian, Tesla, Commonwealth Bank"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleResearch()}
              autoFocus
            />

            <div className="wizard-actions">
              <button onClick={onClose} className="btn-secondary">Cancel</button>
              <button
                onClick={handleResearch}
                className="btn-primary"
                disabled={loading || !companyName.trim()}
              >
                {loading ? 'Researching...' : 'Research Company →'}
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Review & Edit Research Data */}
        {step === 2 && researchData && (
          <div className="wizard-step review-step">
            <h3>Review & Edit Research Results</h3>
            <p>Review the automatically discovered information and make any necessary edits:</p>

            <div className="research-sections">
              {/* Basic Info */}
              <section className="research-section">
                <h4>Basic Information</h4>
                <div className="form-grid">
                  <div className="form-field">
                    <label>Company Name:</label>
                    <input
                      type="text"
                      value={researchData.company_name}
                      onChange={(e) => updateResearchField('company_name', e.target.value)}
                    />
                  </div>
                  <div className="form-field">
                    <label>Domain:</label>
                    <input
                      type="text"
                      value={researchData.domain || ''}
                      onChange={(e) => updateResearchField('domain', e.target.value)}
                    />
                  </div>
                  <div className="form-field">
                    <label>Stock Symbol:</label>
                    <input
                      type="text"
                      value={researchData.stock_symbol || ''}
                      onChange={(e) => updateResearchField('stock_symbol', e.target.value)}
                      placeholder="e.g., AAPL, TEAM, CBA.AX"
                    />
                  </div>
                  <div className="form-field">
                    <label>Industry:</label>
                    <input
                      type="text"
                      value={researchData.industry || ''}
                      onChange={(e) => updateResearchField('industry', e.target.value)}
                    />
                  </div>
                  <div className="form-field full-width">
                    <label>Description:</label>
                    <textarea
                      value={researchData.description || ''}
                      onChange={(e) => updateResearchField('description', e.target.value)}
                      rows="2"
                    />
                  </div>
                </div>
              </section>

              {/* Executives */}
              <section className="research-section">
                <h4>
                  Executives to Monitor
                  <button onClick={addExecutive} className="btn-add">+ Add</button>
                </h4>
                {researchData.executives.map((exec, idx) => (
                  <div key={idx} className="executive-item">
                    <div className="form-grid">
                      <input
                        type="text"
                        placeholder="Name"
                        value={exec.name}
                        onChange={(e) => updateExecutive(idx, 'name', e.target.value)}
                      />
                      <input
                        type="text"
                        placeholder="Role (e.g., CEO)"
                        value={exec.role}
                        onChange={(e) => updateExecutive(idx, 'role', e.target.value)}
                      />
                      <input
                        type="text"
                        placeholder="LinkedIn URL"
                        value={exec.linkedin_url}
                        onChange={(e) => updateExecutive(idx, 'linkedin_url', e.target.value)}
                        className="full-width"
                      />
                      <input
                        type="text"
                        placeholder="Notes"
                        value={exec.notes}
                        onChange={(e) => updateExecutive(idx, 'notes', e.target.value)}
                        className="full-width"
                      />
                    </div>
                    <button
                      onClick={() => removeExecutive(idx)}
                      className="btn-remove"
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </section>

              {/* Competitors */}
              <section className="research-section">
                <h4>
                  Competitors
                  <button onClick={() => addArrayItem('competitors', '')} className="btn-add">+ Add</button>
                </h4>
                <div className="list-items">
                  {researchData.competitors.map((competitor, idx) => (
                    <div key={idx} className="list-item">
                      <input
                        type="text"
                        value={competitor}
                        onChange={(e) => updateArrayField('competitors', idx, e.target.value)}
                      />
                      <button
                        onClick={() => removeArrayItem('competitors', idx)}
                        className="btn-remove-small"
                      >
                        &times;
                      </button>
                    </div>
                  ))}
                </div>
              </section>

              {/* Keywords */}
              <section className="research-section">
                <h4>
                  Keywords
                  <button onClick={() => addArrayItem('keywords', '')} className="btn-add">+ Add</button>
                </h4>
                <div className="list-items">
                  {researchData.keywords.map((keyword, idx) => (
                    <div key={idx} className="list-item">
                      <input
                        type="text"
                        value={keyword}
                        onChange={(e) => updateArrayField('keywords', idx, e.target.value)}
                      />
                      <button
                        onClick={() => removeArrayItem('keywords', idx)}
                        className="btn-remove-small"
                      >
                        &times;
                      </button>
                    </div>
                  ))}
                </div>
              </section>

              {/* Priority Keywords */}
              <section className="research-section">
                <h4>
                  Priority Keywords
                  <button onClick={() => addArrayItem('priority_keywords', '')} className="btn-add">+ Add</button>
                </h4>
                <div className="list-items">
                  {researchData.priority_keywords.map((keyword, idx) => (
                    <div key={idx} className="list-item">
                      <input
                        type="text"
                        value={keyword}
                        onChange={(e) => updateArrayField('priority_keywords', idx, e.target.value)}
                      />
                      <button
                        onClick={() => removeArrayItem('priority_keywords', idx)}
                        className="btn-remove-small"
                      >
                        &times;
                      </button>
                    </div>
                  ))}
                </div>
              </section>
            </div>

            <div className="wizard-actions">
              <button onClick={() => setStep(1)} className="btn-secondary">← Back</button>
              <button
                onClick={handleGenerateConfig}
                className="btn-primary"
                disabled={loading}
              >
                {loading ? 'Generating...' : 'Generate Configuration →'}
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Generated YAML */}
        {step === 3 && (
          <div className="wizard-step">
            <h3>Configuration Generated!</h3>
            <p>Copy this YAML configuration and paste it into <code>config/customers.yaml</code></p>

            <div className="yaml-output">
              <pre>{yamlConfig}</pre>
            </div>

            <div className="wizard-actions">
              <button onClick={() => setStep(2)} className="btn-secondary">← Edit</button>
              <button onClick={handleCopyToClipboard} className="btn-primary">
                📋 Copy to Clipboard
              </button>
              <button onClick={onClose} className="btn-success">Done</button>
            </div>

            <div className="next-steps">
              <h4>Next Steps:</h4>
              <ol>
                <li>Copy the configuration above</li>
                <li>Open <code>config/customers.yaml</code></li>
                <li>Paste the configuration into the <code>customers:</code> array</li>
                <li>Restart the backend container to apply changes</li>
                <li>Trigger a collection to start gathering intelligence</li>
              </ol>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
