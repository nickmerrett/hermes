import React from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

function ProtectedRoute({ children, requireAdmin = false }) {
  const { isAuthenticated, isAdmin, isLoading } = useAuth()
  const location = useLocation()

  // Show loading state while checking auth
  if (isLoading) {
    return (
      <div className="auth-loading">
        <div className="auth-loading-spinner"></div>
        <p>Loading...</p>
      </div>
    )
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  // Check admin requirement
  if (requireAdmin && !isAdmin) {
    return (
      <div className="auth-forbidden">
        <h2>Access Denied</h2>
        <p>You do not have permission to access this page.</p>
        <a href="/">Return to Dashboard</a>
      </div>
    )
  }

  return children
}

export default ProtectedRoute
