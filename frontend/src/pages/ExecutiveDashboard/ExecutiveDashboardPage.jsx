import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import './ExecutiveDashboardPage.css';

const API_URL = import.meta.env.VITE_API_URL || '/api';

export default function ExecutiveDashboardPage() {
  const { executiveId } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [profile, setProfile] = useState(null);

  useEffect(() => {
    const fetchExecutiveProfile = async () => {
      try {
        setLoading(true);
        const response = await axios.get(`${API_URL}/executives/${executiveId}/profile`);
        setProfile(response.data);
      } catch (err) {
        console.error('Error fetching executive profile:', err);
        setError(err.response?.data?.detail || 'Failed to load executive profile');
      } finally {
        setLoading(false);
      }
    };

    if (executiveId) {
      fetchExecutiveProfile();
    }
  }, [executiveId]);

  if (loading) {
    return (
      <div className="executive-dashboard">
        <div className="loading-container">
          <div className="spinner"></div>
          <p>Loading executive profile...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="executive-dashboard">
        <div className="error-container">
          <h2>Error Loading Profile</h2>
          <p>{error}</p>
          <button onClick={() => navigate('/')} className="btn-primary">
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="executive-dashboard">
      <div className="dashboard-header">
        <button onClick={() => navigate('/')} className="btn-back">
          ← Back to Dashboard
        </button>
        <h1>Executive Relationship Dashboard</h1>
      </div>

      <div className="dashboard-content">
        {profile ? (
          <div className="profile-section">
            <div className="profile-header">
              <h2>{profile.name || 'Executive Profile'}</h2>
              {profile.title && <p className="profile-title">{profile.title}</p>}
              {profile.company && <p className="profile-company">{profile.company}</p>}
            </div>

            <div className="profile-details">
              <h3>Profile Information</h3>
              <p>Executive ID: {executiveId}</p>
              {profile.background && profile.background.length > 0 && (
                <div className="background-section">
                  <h4>Background</h4>
                  <ul>
                    {profile.background.map((item, idx) => (
                      <li key={idx}>
                        {item.role} at {item.company}
                        {item.start_date && ` (${item.start_date} - ${item.end_date || 'Present'})`}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="no-profile">
            <p>No profile data available for executive ID: {executiveId}</p>
          </div>
        )}
      </div>
    </div>
  );
}
