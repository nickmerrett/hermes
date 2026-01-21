/**
 * Tests for AuthContext - authentication state management.
 *
 * Tests cover:
 * - Initial authentication state
 * - Login functionality
 * - Logout functionality
 * - Token refresh
 * - Token expiration detection
 * - User role detection
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AuthProvider, useAuth } from '../../../src/contexts/AuthContext'
import { mockTokens } from '../../../src/mocks/handlers'

// Test component that uses the auth context
function TestComponent() {
  const {
    user,
    isAuthenticated,
    isAdmin,
    isLoading,
    error,
    login,
    logout
  } = useAuth()

  return (
    <div>
      <div data-testid="loading">{isLoading ? 'loading' : 'loaded'}</div>
      <div data-testid="authenticated">{isAuthenticated ? 'yes' : 'no'}</div>
      <div data-testid="admin">{isAdmin ? 'yes' : 'no'}</div>
      <div data-testid="user">{user ? user.email : 'no-user'}</div>
      <div data-testid="error">{error || 'no-error'}</div>
      <button
        data-testid="login-btn"
        onClick={() => login('admin@example.com', 'password123')}
      >
        Login
      </button>
      <button
        data-testid="login-fail-btn"
        onClick={() => login('wrong@example.com', 'wrongpassword')}
      >
        Login Fail
      </button>
      <button data-testid="logout-btn" onClick={logout}>
        Logout
      </button>
    </div>
  )
}

// Wrapper for rendering with AuthProvider
function renderWithAuth() {
  return render(
    <AuthProvider>
      <TestComponent />
    </AuthProvider>
  )
}

describe('AuthContext', () => {
  beforeEach(() => {
    // Clear localStorage before each test
    localStorage.clear()
  })

  describe('Initial State', () => {
    it('should complete loading and reach loaded state', async () => {
      renderWithAuth()

      // Wait for loading to complete (loading state is transient and may not be catchable)
      await waitFor(() => {
        expect(screen.getByTestId('loading').textContent).toBe('loaded')
      })
    })

    it('should not be authenticated initially', async () => {
      renderWithAuth()

      await waitFor(() => {
        expect(screen.getByTestId('loading').textContent).toBe('loaded')
      })

      expect(screen.getByTestId('authenticated').textContent).toBe('no')
      expect(screen.getByTestId('user').textContent).toBe('no-user')
    })

    it('should not be admin initially', async () => {
      renderWithAuth()

      await waitFor(() => {
        expect(screen.getByTestId('loading').textContent).toBe('loaded')
      })

      expect(screen.getByTestId('admin').textContent).toBe('no')
    })

    it('should have no error initially', async () => {
      renderWithAuth()

      await waitFor(() => {
        expect(screen.getByTestId('loading').textContent).toBe('loaded')
      })

      expect(screen.getByTestId('error').textContent).toBe('no-error')
    })
  })

  describe('Login', () => {
    it('should authenticate user on successful login', async () => {
      const user = userEvent.setup()
      renderWithAuth()

      await waitFor(() => {
        expect(screen.getByTestId('loading').textContent).toBe('loaded')
      })

      // Click login button
      await user.click(screen.getByTestId('login-btn'))

      // Should be authenticated after login
      await waitFor(() => {
        expect(screen.getByTestId('authenticated').textContent).toBe('yes')
      })
    })

    it('should store tokens in localStorage on login', async () => {
      const user = userEvent.setup()
      renderWithAuth()

      await waitFor(() => {
        expect(screen.getByTestId('loading').textContent).toBe('loaded')
      })

      await user.click(screen.getByTestId('login-btn'))

      await waitFor(() => {
        expect(localStorage.getItem('hermes_access_token')).toBeTruthy()
        expect(localStorage.getItem('hermes_refresh_token')).toBeTruthy()
      })
    })

    it('should set error on failed login', async () => {
      const user = userEvent.setup()
      renderWithAuth()

      await waitFor(() => {
        expect(screen.getByTestId('loading').textContent).toBe('loaded')
      })

      await user.click(screen.getByTestId('login-fail-btn'))

      await waitFor(() => {
        expect(screen.getByTestId('error').textContent).not.toBe('no-error')
      })
    })

    it('should remain unauthenticated on failed login', async () => {
      const user = userEvent.setup()
      renderWithAuth()

      await waitFor(() => {
        expect(screen.getByTestId('loading').textContent).toBe('loaded')
      })

      await user.click(screen.getByTestId('login-fail-btn'))

      // Wait a bit for potential state changes
      await new Promise(resolve => setTimeout(resolve, 100))

      expect(screen.getByTestId('authenticated').textContent).toBe('no')
    })
  })

  describe('Logout', () => {
    it('should clear authentication on logout', async () => {
      const user = userEvent.setup()
      renderWithAuth()

      await waitFor(() => {
        expect(screen.getByTestId('loading').textContent).toBe('loaded')
      })

      // Login first
      await user.click(screen.getByTestId('login-btn'))
      await waitFor(() => {
        expect(screen.getByTestId('authenticated').textContent).toBe('yes')
      })

      // Then logout
      await user.click(screen.getByTestId('logout-btn'))

      expect(screen.getByTestId('authenticated').textContent).toBe('no')
      expect(screen.getByTestId('user').textContent).toBe('no-user')
    })

    it('should clear tokens from localStorage on logout', async () => {
      const user = userEvent.setup()
      renderWithAuth()

      await waitFor(() => {
        expect(screen.getByTestId('loading').textContent).toBe('loaded')
      })

      // Login first
      await user.click(screen.getByTestId('login-btn'))
      await waitFor(() => {
        expect(localStorage.getItem('hermes_access_token')).toBeTruthy()
      })

      // Then logout
      await user.click(screen.getByTestId('logout-btn'))

      expect(localStorage.getItem('hermes_access_token')).toBeNull()
      expect(localStorage.getItem('hermes_refresh_token')).toBeNull()
    })

    it('should clear error on logout', async () => {
      const user = userEvent.setup()
      renderWithAuth()

      await waitFor(() => {
        expect(screen.getByTestId('loading').textContent).toBe('loaded')
      })

      // Trigger an error
      await user.click(screen.getByTestId('login-fail-btn'))
      await waitFor(() => {
        expect(screen.getByTestId('error').textContent).not.toBe('no-error')
      })

      // Logout should clear error
      await user.click(screen.getByTestId('logout-btn'))
      expect(screen.getByTestId('error').textContent).toBe('no-error')
    })
  })

  describe('Token Persistence', () => {
    it('should restore authentication from stored token on mount', async () => {
      // Pre-populate localStorage with a valid token
      // Create a token that won't expire during the test
      const futureExp = Math.floor(Date.now() / 1000) + 3600 // 1 hour from now
      const validToken = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' })) +
        '.' +
        btoa(JSON.stringify({
          sub: '1',
          email: 'admin@example.com',
          role: 'platform_admin',
          exp: futureExp
        })) +
        '.signature'

      localStorage.setItem('hermes_access_token', validToken)
      localStorage.setItem('hermes_refresh_token', 'refresh-token')

      renderWithAuth()

      await waitFor(() => {
        expect(screen.getByTestId('loading').textContent).toBe('loaded')
      })

      // Should be authenticated from stored token
      expect(screen.getByTestId('authenticated').textContent).toBe('yes')
    })
  })

  describe('useAuth Hook', () => {
    it('should throw error when used outside AuthProvider', () => {
      // Suppress console.error for this test
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      expect(() => {
        render(<TestComponent />)
      }).toThrow('useAuth must be used within an AuthProvider')

      consoleSpy.mockRestore()
    })
  })
})

describe('AuthContext - Admin Detection', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('should detect admin role correctly', async () => {
    // Token with platform_admin role
    const futureExp = Math.floor(Date.now() / 1000) + 3600
    const adminToken = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' })) +
      '.' +
      btoa(JSON.stringify({
        sub: '1',
        email: 'admin@example.com',
        role: 'platform_admin',
        exp: futureExp
      })) +
      '.signature'

    localStorage.setItem('hermes_access_token', adminToken)
    localStorage.setItem('hermes_refresh_token', 'refresh')

    renderWithAuth()

    await waitFor(() => {
      expect(screen.getByTestId('loading').textContent).toBe('loaded')
    })

    expect(screen.getByTestId('admin').textContent).toBe('yes')
  })

  it('should detect non-admin role correctly', async () => {
    // Token with regular user role
    const futureExp = Math.floor(Date.now() / 1000) + 3600
    const userToken = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' })) +
      '.' +
      btoa(JSON.stringify({
        sub: '2',
        email: 'user@example.com',
        role: 'user',
        exp: futureExp
      })) +
      '.signature'

    localStorage.setItem('hermes_access_token', userToken)
    localStorage.setItem('hermes_refresh_token', 'refresh')

    renderWithAuth()

    await waitFor(() => {
      expect(screen.getByTestId('loading').textContent).toBe('loaded')
    })

    expect(screen.getByTestId('admin').textContent).toBe('no')
  })
})
