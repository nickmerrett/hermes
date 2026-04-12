import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || '/api'

// Create axios instance for auth requests
const authAxios = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Create axios instance for authenticated requests
export const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Set auth token for all requests
export function setAuthToken(token) {
  if (token) {
    apiClient.defaults.headers.common['Authorization'] = `Bearer ${token}`
  } else {
    delete apiClient.defaults.headers.common['Authorization']
  }
}

// Request interceptor to add token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('hermes_access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor to handle 401 errors
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    // If 401 and we haven't tried to refresh yet
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true

      const refreshToken = localStorage.getItem('hermes_refresh_token')
      if (refreshToken) {
        try {
          const response = await authAxios.post('/auth/refresh', {
            refresh_token: refreshToken
          })

          const { access_token, refresh_token: newRefreshToken } = response.data

          localStorage.setItem('hermes_access_token', access_token)
          localStorage.setItem('hermes_refresh_token', newRefreshToken)
          setAuthToken(access_token)

          // Retry the original request
          originalRequest.headers.Authorization = `Bearer ${access_token}`
          return apiClient(originalRequest)
        } catch (refreshError) {
          // Refresh failed, clear tokens and redirect to login
          localStorage.removeItem('hermes_access_token')
          localStorage.removeItem('hermes_refresh_token')
          setAuthToken(null)
          window.location.href = '/login'
          return Promise.reject(refreshError)
        }
      } else {
        // No refresh token, redirect to login
        window.location.href = '/login'
      }
    }

    return Promise.reject(error)
  }
)

// Auth API functions
export const authApi = {
  // Login
  login: (email, password) => {
    return authAxios.post('/auth/login', { email, password })
  },

  // Refresh token
  refresh: (refreshToken) => {
    return authAxios.post('/auth/refresh', { refresh_token: refreshToken })
  },

  // Get current user
  getCurrentUser: () => {
    return apiClient.get('/auth/me')
  },

  // Create user (admin only)
  createUser: (userData) => {
    return apiClient.post('/auth/users', userData)
  },

  // List users (admin only)
  listUsers: () => {
    return apiClient.get('/auth/users')
  },

  // Get user (admin only)
  getUser: (userId) => {
    return apiClient.get(`/auth/users/${userId}`)
  },

  // Update user (admin only)
  updateUser: (userId, userData) => {
    return apiClient.put(`/auth/users/${userId}`, userData)
  },

  // Delete user (admin only)
  deleteUser: (userId) => {
    return apiClient.delete(`/auth/users/${userId}`)
  }
}

// RSS Token API functions
export const rssApi = {
  // List user's RSS tokens
  listTokens: () => {
    return apiClient.get('/rss/tokens')
  },

  // Create RSS token
  createToken: (name, customerId) => {
    return apiClient.post('/rss/tokens', { name, customer_id: customerId })
  },

  // Delete RSS token
  deleteToken: (tokenId) => {
    return apiClient.delete(`/rss/tokens/${tokenId}`)
  },

  // Deactivate RSS token
  deactivateToken: (tokenId) => {
    return apiClient.patch(`/rss/tokens/${tokenId}/deactivate`)
  },

  // Activate RSS token
  activateToken: (tokenId) => {
    return apiClient.patch(`/rss/tokens/${tokenId}/activate`)
  },

  // Get customer smart feed settings
  getSettings: (customerId) => {
    return apiClient.get(`/rss/settings/${customerId}`)
  },

  // Update customer smart feed settings
  updateSettings: (customerId, settings) => {
    return apiClient.put(`/rss/settings/${customerId}`, settings)
  }
}

// Customer sharing API
export const sharesApi = {
  list: (customerId) =>
    apiClient.get(`/customers/${customerId}/shares`),

  add: (customerId, email, canAdmin = false, canReshare = false) =>
    apiClient.post(`/customers/${customerId}/shares`, {
      email,
      can_admin: canAdmin,
      can_reshare: canReshare,
    }),

  revoke: (customerId, userId) =>
    apiClient.delete(`/customers/${customerId}/shares/${userId}`),
}

export default apiClient
