import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { jwtDecode } from 'jwt-decode'
import { authApi, setAuthToken } from '../api/auth'

const AuthContext = createContext(null)

const TOKEN_KEY = 'hermes_access_token'
const REFRESH_TOKEN_KEY = 'hermes_refresh_token'

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)

  // Check if token is expired
  const isTokenExpired = useCallback((token) => {
    if (!token) return true
    try {
      const decoded = jwtDecode(token)
      // Add 30 second buffer before expiry
      return decoded.exp * 1000 < Date.now() + 30000
    } catch {
      return true
    }
  }, [])

  // Get user info from token
  const getUserFromToken = useCallback((token) => {
    try {
      const decoded = jwtDecode(token)
      return {
        id: decoded.sub,
        email: decoded.email,
        role: decoded.role
      }
    } catch {
      return null
    }
  }, [])

  // Refresh the access token
  const refreshToken = useCallback(async () => {
    const storedRefreshToken = localStorage.getItem(REFRESH_TOKEN_KEY)
    if (!storedRefreshToken) {
      return false
    }

    try {
      const response = await authApi.refresh(storedRefreshToken)
      const { access_token, refresh_token } = response.data

      localStorage.setItem(TOKEN_KEY, access_token)
      localStorage.setItem(REFRESH_TOKEN_KEY, refresh_token)
      setAuthToken(access_token)

      const userInfo = getUserFromToken(access_token)
      setUser(userInfo)

      return true
    } catch (err) {
      console.error('Token refresh failed:', err)
      // Clear tokens on refresh failure
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(REFRESH_TOKEN_KEY)
      setAuthToken(null)
      setUser(null)
      return false
    }
  }, [getUserFromToken])

  // Initialize auth state on mount
  useEffect(() => {
    const initAuth = async () => {
      const storedToken = localStorage.getItem(TOKEN_KEY)

      if (!storedToken) {
        setIsLoading(false)
        return
      }

      if (isTokenExpired(storedToken)) {
        // Try to refresh
        const refreshed = await refreshToken()
        if (!refreshed) {
          setIsLoading(false)
          return
        }
      } else {
        // Token is valid
        setAuthToken(storedToken)
        const userInfo = getUserFromToken(storedToken)
        setUser(userInfo)
      }

      setIsLoading(false)
    }

    initAuth()
  }, [isTokenExpired, refreshToken, getUserFromToken])

  // Set up token refresh interval
  useEffect(() => {
    if (!user) return

    // Check token every minute and refresh if needed
    const interval = setInterval(async () => {
      const storedToken = localStorage.getItem(TOKEN_KEY)
      if (storedToken && isTokenExpired(storedToken)) {
        await refreshToken()
      }
    }, 60000) // Check every minute

    return () => clearInterval(interval)
  }, [user, isTokenExpired, refreshToken])

  // Login function
  const login = async (email, password) => {
    setError(null)
    try {
      const response = await authApi.login(email, password)
      const { access_token, refresh_token } = response.data

      localStorage.setItem(TOKEN_KEY, access_token)
      localStorage.setItem(REFRESH_TOKEN_KEY, refresh_token)
      setAuthToken(access_token)

      const userInfo = getUserFromToken(access_token)
      setUser(userInfo)

      return { success: true }
    } catch (err) {
      const message = err.response?.data?.detail || 'Login failed'
      setError(message)
      return { success: false, error: message }
    }
  }

  // Logout function
  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(REFRESH_TOKEN_KEY)
    setAuthToken(null)
    setUser(null)
    setError(null)
  }, [])

  // Check if user is authenticated
  const isAuthenticated = !!user

  // Check if user is admin
  const isAdmin = user?.role === 'platform_admin'

  const value = {
    user,
    isAuthenticated,
    isAdmin,
    isLoading,
    error,
    login,
    logout,
    refreshToken
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

export default AuthContext
