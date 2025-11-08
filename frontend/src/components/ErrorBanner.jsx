import React from 'react'
import '../styles/ErrorBanner.css'

const ErrorBanner = ({ errors, onDismiss }) => {
  if (!errors || errors.length === 0) {
    return null
  }

  const getErrorIcon = (status) => {
    if (status === 'auth_required') {
      return '🔐'
    }
    return '⚠️'
  }

  const getErrorTitle = (status, sourceType) => {
    const sourceNames = {
      'reddit': 'Reddit',
      'linkedin_user': 'LinkedIn',
      'linkedin': 'LinkedIn',
      'twitter': 'Twitter'
    }

    const sourceName = sourceNames[sourceType] || sourceType

    if (status === 'auth_required') {
      return `${sourceName} - Authentication Required`
    }
    return `${sourceName} Collection Error`
  }

  return (
    <div className="error-banner-container">
      {errors.map((error, index) => (
        <div
          key={`${error.customer_id}-${error.source_type}`}
          className={`error-banner ${error.status === 'auth_required' ? 'auth-error' : 'general-error'}`}
        >
          <div className="error-banner-content">
            <span className="error-icon">{getErrorIcon(error.status)}</span>
            <div className="error-details">
              <strong>{getErrorTitle(error.status, error.source_type)}</strong>
              {error.error_message && (
                <p className="error-message">{error.error_message}</p>
              )}
              {error.error_count > 1 && (
                <small className="error-count">
                  Failed {error.error_count} times in a row
                </small>
              )}
            </div>
          </div>
          {onDismiss && (
            <button
              className="error-dismiss"
              onClick={() => onDismiss(error)}
              title="Dismiss"
            >
              ×
            </button>
          )}
        </div>
      ))}
    </div>
  )
}

export default ErrorBanner
