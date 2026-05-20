import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import ProtectedRoute from '../../../src/components/ProtectedRoute'

vi.mock('../../../src/contexts/AuthContext', () => ({
  useAuth: vi.fn()
}))

import { useAuth } from '../../../src/contexts/AuthContext'

function ProtectedContent() {
  return <div data-testid="protected-content">Protected Content</div>
}

function AdminContent() {
  return <div data-testid="admin-content">Admin Content</div>
}

function LoginPage() {
  return <div data-testid="login-page">Login Page</div>
}

function renderWithRouter(ui, { initialEntries = ['/'] } = {}) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        {ui}
      </Routes>
    </MemoryRouter>
  )
}

describe('ProtectedRoute', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Loading State', () => {
    it('should render loading state while auth is resolving', () => {
      useAuth.mockReturnValue({ isAuthenticated: false, isAdmin: false, isLoading: true })

      renderWithRouter(
        <Route path="/" element={<ProtectedRoute><ProtectedContent /></ProtectedRoute>} />
      )

      expect(screen.getByText(/loading/i)).toBeInTheDocument()
      expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument()
    })
  })

  describe('Unauthenticated Users', () => {
    beforeEach(() => {
      useAuth.mockReturnValue({ isAuthenticated: false, isAdmin: false, isLoading: false })
    })

    it('should redirect to login when not authenticated', () => {
      renderWithRouter(
        <Route path="/" element={<ProtectedRoute><ProtectedContent /></ProtectedRoute>} />
      )

      expect(screen.getByTestId('login-page')).toBeInTheDocument()
    })

    it('should not show protected content when not authenticated', () => {
      renderWithRouter(
        <Route path="/" element={<ProtectedRoute><ProtectedContent /></ProtectedRoute>} />
      )

      expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument()
    })
  })

  describe('Authenticated Users', () => {
    beforeEach(() => {
      useAuth.mockReturnValue({ isAuthenticated: true, isAdmin: false, isLoading: false })
    })

    it('should render protected content when authenticated', () => {
      renderWithRouter(
        <Route path="/" element={<ProtectedRoute><ProtectedContent /></ProtectedRoute>} />
      )

      expect(screen.getByTestId('protected-content')).toBeInTheDocument()
    })

    it('should not redirect authenticated users', () => {
      renderWithRouter(
        <Route path="/" element={<ProtectedRoute><ProtectedContent /></ProtectedRoute>} />
      )

      expect(screen.queryByTestId('login-page')).not.toBeInTheDocument()
    })
  })

  describe('Admin Routes', () => {
    it('should render admin content for admin users', () => {
      useAuth.mockReturnValue({ isAuthenticated: true, isAdmin: true, isLoading: false })

      renderWithRouter(
        <Route path="/" element={<ProtectedRoute requireAdmin><AdminContent /></ProtectedRoute>} />
      )

      expect(screen.getByTestId('admin-content')).toBeInTheDocument()
    })

    it('should show access denied for non-admin on admin routes', () => {
      useAuth.mockReturnValue({ isAuthenticated: true, isAdmin: false, isLoading: false })

      renderWithRouter(
        <Route path="/" element={<ProtectedRoute requireAdmin><AdminContent /></ProtectedRoute>} />
      )

      expect(screen.getByText(/access denied/i)).toBeInTheDocument()
      expect(screen.queryByTestId('admin-content')).not.toBeInTheDocument()
    })

    it('should show link to return to dashboard on access denied', () => {
      useAuth.mockReturnValue({ isAuthenticated: true, isAdmin: false, isLoading: false })

      renderWithRouter(
        <Route path="/" element={<ProtectedRoute requireAdmin><AdminContent /></ProtectedRoute>} />
      )

      expect(screen.getByText(/return to dashboard/i)).toBeInTheDocument()
    })
  })

  describe('Props', () => {
    beforeEach(() => {
      useAuth.mockReturnValue({ isAuthenticated: true, isAdmin: false, isLoading: false })
    })

    it('should pass children through when authorized', () => {
      renderWithRouter(
        <Route path="/" element={
          <ProtectedRoute>
            <div data-testid="custom-child">Custom Child Content</div>
          </ProtectedRoute>
        } />
      )

      expect(screen.getByTestId('custom-child')).toBeInTheDocument()
      expect(screen.getByText('Custom Child Content')).toBeInTheDocument()
    })

    it('should default requireAdmin to false', () => {
      renderWithRouter(
        <Route path="/" element={<ProtectedRoute><ProtectedContent /></ProtectedRoute>} />
      )

      expect(screen.getByTestId('protected-content')).toBeInTheDocument()
      expect(screen.queryByText(/access denied/i)).not.toBeInTheDocument()
    })
  })
})
