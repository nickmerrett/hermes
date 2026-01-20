/**
 * Tests for ProtectedRoute component - route access control.
 *
 * Tests cover:
 * - Rendering protected content when authenticated
 * - Redirecting to login when not authenticated
 * - Showing loading state during auth check
 * - Admin route restriction
 * - Access denied display for non-admins
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import ProtectedRoute from '../../../src/components/ProtectedRoute'
import { AuthProvider } from '../../../src/contexts/AuthContext'

// Helper to create valid JWT token
function createMockToken(payload) {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
  const body = btoa(JSON.stringify(payload))
  return `${header}.${body}.signature`
}

// Create tokens for different user types
function createAdminToken() {
  return createMockToken({
    sub: '1',
    email: 'admin@example.com',
    role: 'platform_admin',
    exp: Math.floor(Date.now() / 1000) + 3600
  })
}

function createUserToken() {
  return createMockToken({
    sub: '2',
    email: 'user@example.com',
    role: 'user',
    exp: Math.floor(Date.now() / 1000) + 3600
  })
}

// Test components
function ProtectedContent() {
  return <div data-testid="protected-content">Protected Content</div>
}

function AdminContent() {
  return <div data-testid="admin-content">Admin Content</div>
}

function LoginPage() {
  return <div data-testid="login-page">Login Page</div>
}

// Render helper with router
function renderWithRouter(ui, { initialEntries = ['/'] } = {}) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          {ui}
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  )
}

describe('ProtectedRoute', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  describe('Loading State', () => {
    it('should show loading spinner while checking auth', async () => {
      renderWithRouter(
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <ProtectedContent />
            </ProtectedRoute>
          }
        />
      )

      // Should show loading initially
      expect(screen.getByText(/loading/i)).toBeInTheDocument()
    })
  })

  describe('Unauthenticated Users', () => {
    it('should redirect to login when not authenticated', async () => {
      renderWithRouter(
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <ProtectedContent />
            </ProtectedRoute>
          }
        />
      )

      // Wait for auth check to complete
      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument()
      }, { timeout: 3000 })

      // Should redirect to login
      await waitFor(() => {
        expect(screen.getByTestId('login-page')).toBeInTheDocument()
      })
    })

    it('should not show protected content when not authenticated', async () => {
      renderWithRouter(
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <ProtectedContent />
            </ProtectedRoute>
          }
        />
      )

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument()
      }, { timeout: 3000 })

      expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument()
    })
  })

  describe('Authenticated Users', () => {
    it('should render protected content when authenticated', async () => {
      // Set up authenticated state
      localStorage.setItem('hermes_access_token', createUserToken())
      localStorage.setItem('hermes_refresh_token', 'refresh-token')

      renderWithRouter(
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <ProtectedContent />
            </ProtectedRoute>
          }
        />
      )

      // Wait for content to appear
      await waitFor(() => {
        expect(screen.getByTestId('protected-content')).toBeInTheDocument()
      }, { timeout: 3000 })
    })

    it('should not redirect authenticated users', async () => {
      localStorage.setItem('hermes_access_token', createUserToken())
      localStorage.setItem('hermes_refresh_token', 'refresh-token')

      renderWithRouter(
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <ProtectedContent />
            </ProtectedRoute>
          }
        />
      )

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument()
      }, { timeout: 3000 })

      expect(screen.queryByTestId('login-page')).not.toBeInTheDocument()
    })
  })

  describe('Admin Routes', () => {
    it('should render admin content for admin users', async () => {
      localStorage.setItem('hermes_access_token', createAdminToken())
      localStorage.setItem('hermes_refresh_token', 'refresh-token')

      renderWithRouter(
        <Route
          path="/"
          element={
            <ProtectedRoute requireAdmin>
              <AdminContent />
            </ProtectedRoute>
          }
        />
      )

      await waitFor(() => {
        expect(screen.getByTestId('admin-content')).toBeInTheDocument()
      }, { timeout: 3000 })
    })

    it('should show access denied for non-admin on admin routes', async () => {
      localStorage.setItem('hermes_access_token', createUserToken())
      localStorage.setItem('hermes_refresh_token', 'refresh-token')

      renderWithRouter(
        <Route
          path="/"
          element={
            <ProtectedRoute requireAdmin>
              <AdminContent />
            </ProtectedRoute>
          }
        />
      )

      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument()
      }, { timeout: 3000 })

      // Should show access denied
      expect(screen.getByText(/access denied/i)).toBeInTheDocument()
      expect(screen.queryByTestId('admin-content')).not.toBeInTheDocument()
    })

    it('should show link to return to dashboard on access denied', async () => {
      localStorage.setItem('hermes_access_token', createUserToken())
      localStorage.setItem('hermes_refresh_token', 'refresh-token')

      renderWithRouter(
        <Route
          path="/"
          element={
            <ProtectedRoute requireAdmin>
              <AdminContent />
            </ProtectedRoute>
          }
        />
      )

      await waitFor(() => {
        expect(screen.getByText(/access denied/i)).toBeInTheDocument()
      }, { timeout: 3000 })

      // Should have link to return
      expect(screen.getByText(/return to dashboard/i)).toBeInTheDocument()
    })
  })

  describe('Props', () => {
    it('should pass children through when authorized', async () => {
      localStorage.setItem('hermes_access_token', createUserToken())
      localStorage.setItem('hermes_refresh_token', 'refresh-token')

      renderWithRouter(
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <div data-testid="custom-child">Custom Child Content</div>
            </ProtectedRoute>
          }
        />
      )

      await waitFor(() => {
        expect(screen.getByTestId('custom-child')).toBeInTheDocument()
      }, { timeout: 3000 })

      expect(screen.getByText('Custom Child Content')).toBeInTheDocument()
    })

    it('should default requireAdmin to false', async () => {
      localStorage.setItem('hermes_access_token', createUserToken())
      localStorage.setItem('hermes_refresh_token', 'refresh-token')

      renderWithRouter(
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <ProtectedContent />
            </ProtectedRoute>
          }
        />
      )

      await waitFor(() => {
        expect(screen.getByTestId('protected-content')).toBeInTheDocument()
      }, { timeout: 3000 })

      // Regular user should access non-admin protected route
      expect(screen.queryByText(/access denied/i)).not.toBeInTheDocument()
    })
  })
})
