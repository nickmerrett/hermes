/**
 * MSW request handlers for API mocking in tests.
 *
 * These handlers intercept API requests during tests and return
 * controlled responses for predictable test behavior.
 */

import { http, HttpResponse } from 'msw'

const API_URL = '/api'

// Mock data
export const mockUsers = {
  admin: {
    id: 1,
    email: 'admin@example.com',
    role: 'platform_admin',
    is_active: true,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z'
  },
  user: {
    id: 2,
    email: 'user@example.com',
    role: 'user',
    is_active: true,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z'
  }
}

export const mockCustomers = [
  {
    id: 1,
    name: 'Acme Corp',
    domain: 'acme.com',
    keywords: ['acme', 'widgets'],
    competitors: ['GlobalCorp'],
    stock_symbol: 'ACME',
    tab_color: '#3498db',
    sort_order: 0,
    config: {},
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z'
  },
  {
    id: 2,
    name: 'Beta Inc',
    domain: 'beta.com',
    keywords: ['beta'],
    competitors: [],
    stock_symbol: 'BETA',
    tab_color: '#e74c3c',
    sort_order: 1,
    config: {},
    created_at: '2024-01-02T00:00:00Z',
    updated_at: '2024-01-02T00:00:00Z'
  },
  {
    id: 3,
    name: 'Gamma LLC',
    domain: 'gamma.com',
    keywords: ['gamma'],
    competitors: [],
    stock_symbol: 'GAMA',
    tab_color: '#2ecc71',
    sort_order: 2,
    config: {},
    created_at: '2024-01-03T00:00:00Z',
    updated_at: '2024-01-03T00:00:00Z'
  }
]

export const mockTokens = {
  // Valid tokens - these are mock JWTs with predictable structure
  // In tests, we'll use these or generate proper ones
  validAccessToken: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZW1haWwiOiJhZG1pbkBleGFtcGxlLmNvbSIsInJvbGUiOiJwbGF0Zm9ybV9hZG1pbiIsImV4cCI6OTk5OTk5OTk5OX0.mock',
  validRefreshToken: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZW1haWwiOiJhZG1pbkBleGFtcGxlLmNvbSIsInJvbGUiOiJwbGF0Zm9ybV9hZG1pbiIsInR5cGUiOiJyZWZyZXNoIiwiZXhwIjo5OTk5OTk5OTk5fQ.mock',
  expiredToken: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZW1haWwiOiJhZG1pbkBleGFtcGxlLmNvbSIsInJvbGUiOiJwbGF0Zm9ybV9hZG1pbiIsImV4cCI6MX0.mock'
}

// Auth handlers
const authHandlers = [
  // Login
  http.post(`${API_URL}/auth/login`, async ({ request }) => {
    const body = await request.json()
    const { email, password } = body

    // Mock successful login
    if (email === 'admin@example.com' && password === 'password123') {
      return HttpResponse.json({
        access_token: mockTokens.validAccessToken,
        refresh_token: mockTokens.validRefreshToken,
        token_type: 'bearer',
        expires_in: 1800
      })
    }

    if (email === 'user@example.com' && password === 'password123') {
      return HttpResponse.json({
        access_token: 'user-access-token',
        refresh_token: 'user-refresh-token',
        token_type: 'bearer',
        expires_in: 1800
      })
    }

    // Mock invalid credentials
    return HttpResponse.json(
      { detail: 'Invalid email or password' },
      { status: 401 }
    )
  }),

  // Refresh token
  http.post(`${API_URL}/auth/refresh`, async ({ request }) => {
    const body = await request.json()
    const { refresh_token } = body

    if (refresh_token === mockTokens.validRefreshToken) {
      return HttpResponse.json({
        access_token: 'new-access-token',
        refresh_token: 'new-refresh-token',
        token_type: 'bearer',
        expires_in: 1800
      })
    }

    return HttpResponse.json(
      { detail: 'Invalid or expired refresh token' },
      { status: 401 }
    )
  }),

  // Get current user
  http.get(`${API_URL}/auth/me`, ({ request }) => {
    const authHeader = request.headers.get('Authorization')

    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return HttpResponse.json(
        { detail: 'Not authenticated' },
        { status: 401 }
      )
    }

    // Return admin user for valid token
    return HttpResponse.json(mockUsers.admin)
  }),

  // List users
  http.get(`${API_URL}/auth/users`, ({ request }) => {
    const authHeader = request.headers.get('Authorization')

    if (!authHeader) {
      return HttpResponse.json({ detail: 'Not authenticated' }, { status: 401 })
    }

    return HttpResponse.json({
      users: [mockUsers.admin, mockUsers.user],
      total: 2
    })
  }),

  // Create user
  http.post(`${API_URL}/auth/users`, async ({ request }) => {
    const authHeader = request.headers.get('Authorization')

    if (!authHeader) {
      return HttpResponse.json({ detail: 'Not authenticated' }, { status: 401 })
    }

    const body = await request.json()

    return HttpResponse.json({
      id: 3,
      email: body.email,
      role: body.role || 'user',
      is_active: true,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    }, { status: 201 })
  }),

  // Delete user
  http.delete(`${API_URL}/auth/users/:userId`, ({ params }) => {
    const { userId } = params

    if (userId === '1') {
      return HttpResponse.json(
        { detail: 'Cannot delete your own account' },
        { status: 400 }
      )
    }

    return new HttpResponse(null, { status: 204 })
  })
]

// Customer handlers
const customerHandlers = [
  // List customers
  http.get(`${API_URL}/customers`, () => {
    return HttpResponse.json(mockCustomers)
  }),

  // Get customer
  http.get(`${API_URL}/customers/:customerId`, ({ params }) => {
    const customer = mockCustomers.find(c => c.id === Number(params.customerId))

    if (!customer) {
      return HttpResponse.json({ detail: 'Customer not found' }, { status: 404 })
    }

    return HttpResponse.json(customer)
  }),

  // Create customer
  http.post(`${API_URL}/customers`, async ({ request }) => {
    const body = await request.json()

    return HttpResponse.json({
      id: mockCustomers.length + 1,
      ...body,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    }, { status: 201 })
  }),

  // Reorder customers
  http.patch(`${API_URL}/customers/reorder`, async () => {
    return HttpResponse.json({ status: 'ok' })
  }),

  // Delete customer
  http.delete(`${API_URL}/customers/:customerId`, () => {
    return new HttpResponse(null, { status: 204 })
  })
]

// RSS handlers
const rssHandlers = [
  // List tokens
  http.get(`${API_URL}/rss/tokens`, () => {
    return HttpResponse.json({
      tokens: [],
      total: 0
    })
  }),

  // Create token
  http.post(`${API_URL}/rss/tokens`, async ({ request }) => {
    const body = await request.json()

    return HttpResponse.json({
      id: 1,
      token: 'new-rss-token',
      name: body.name,
      customer_id: body.customer_id,
      customer_name: 'Acme Corp',
      user_id: 1,
      is_active: true,
      created_at: new Date().toISOString(),
      last_used: null,
      rss_url: `http://localhost/api/rss/feed?token=new-rss-token`
    }, { status: 201 })
  }),

  // Get settings
  http.get(`${API_URL}/rss/settings/:customerId`, ({ params }) => {
    return HttpResponse.json({
      customer_id: Number(params.customerId),
      customer_name: 'Acme Corp',
      use_custom: false,
      customer_settings: {},
      effective_settings: {
        enabled: true,
        min_priority: 0.3,
        max_items: 50
      },
      global_settings: {
        enabled: true,
        min_priority: 0.3
      },
      defaults: {
        enabled: true,
        min_priority: 0.3
      }
    })
  })
]

// Feed handlers
const feedHandlers = [
  // Get feed
  http.get(`${API_URL}/feed`, () => {
    return HttpResponse.json({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
      clustered: true
    })
  }),

  // Get collection errors
  http.get(`${API_URL}/feed/collection-errors`, () => {
    return HttpResponse.json({ errors: [] })
  })
]

// Combine all handlers
export const handlers = [
  ...authHandlers,
  ...customerHandlers,
  ...rssHandlers,
  ...feedHandlers
]
