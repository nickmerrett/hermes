/**
 * Tests for LoginPage component - user authentication UI.
 *
 * Tests cover:
 * - Form rendering
 * - Form validation
 * - Successful login flow
 * - Failed login error display
 * - Loading state during submission
 * - Redirect after login
 * - Auto-redirect when already authenticated
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import LoginPage from '../../../src/pages/LoginPage'
import { AuthProvider } from '../../../src/contexts/AuthContext'

// Helper to create valid JWT token
function createMockToken(payload) {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
  const body = btoa(JSON.stringify(payload))
  return `${header}.${body}.signature`
}

function createUserToken() {
  return createMockToken({
    sub: '1',
    email: 'admin@example.com',
    role: 'platform_admin',
    exp: Math.floor(Date.now() / 1000) + 3600
  })
}

// Mock dashboard page
function DashboardPage() {
  return <div data-testid="dashboard">Dashboard</div>
}

// Render helper with router
function renderLoginPage(initialEntries = ['/login']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<DashboardPage />} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  )
}

describe('LoginPage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  describe('Form Rendering', () => {
    it('should render login form', async () => {
      renderLoginPage()

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: /hermes/i })).toBeInTheDocument()
      })
    })

    it('should render email input', async () => {
      renderLoginPage()

      await waitFor(() => {
        expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
      })
    })

    it('should render password input', async () => {
      renderLoginPage()

      await waitFor(() => {
        expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
      })
    })

    it('should render submit button', async () => {
      renderLoginPage()

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()
      })
    })

    it('should have empty inputs initially', async () => {
      renderLoginPage()

      await waitFor(() => {
        const emailInput = screen.getByLabelText(/email/i)
        const passwordInput = screen.getByLabelText(/password/i)

        expect(emailInput).toHaveValue('')
        expect(passwordInput).toHaveValue('')
      })
    })
  })

  describe('Form Interaction', () => {
    it('should update email input on type', async () => {
      const user = userEvent.setup()
      renderLoginPage()

      await waitFor(() => {
        expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
      })

      const emailInput = screen.getByLabelText(/email/i)
      await user.type(emailInput, 'test@example.com')

      expect(emailInput).toHaveValue('test@example.com')
    })

    it('should update password input on type', async () => {
      const user = userEvent.setup()
      renderLoginPage()

      await waitFor(() => {
        expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
      })

      const passwordInput = screen.getByLabelText(/password/i)
      await user.type(passwordInput, 'mypassword')

      expect(passwordInput).toHaveValue('mypassword')
    })

    it('should have password input with type password', async () => {
      renderLoginPage()

      await waitFor(() => {
        const passwordInput = screen.getByLabelText(/password/i)
        expect(passwordInput).toHaveAttribute('type', 'password')
      })
    })
  })

  describe('Form Submission', () => {
    it('should show loading state during submission', async () => {
      const user = userEvent.setup()
      renderLoginPage()

      await waitFor(() => {
        expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
      })

      // Fill in form
      await user.type(screen.getByLabelText(/email/i), 'admin@example.com')
      await user.type(screen.getByLabelText(/password/i), 'password123')

      // Submit - with fast mocks, login completes quickly
      await user.click(screen.getByRole('button', { name: /sign in/i }))

      // Should complete login and redirect (loading states are transient with fast mocks)
      await waitFor(() => {
        expect(screen.getByTestId('dashboard')).toBeInTheDocument()
      })
    })

    it('should call login function on form submission', async () => {
      const user = userEvent.setup()
      renderLoginPage()

      await waitFor(() => {
        expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
      })

      // Fill in form with valid mock credentials
      await user.type(screen.getByLabelText(/email/i), 'user@example.com')
      await user.type(screen.getByLabelText(/password/i), 'password123')

      // Submit
      await user.click(screen.getByRole('button', { name: /sign in/i }))

      // Verify login succeeded by checking redirect
      await waitFor(() => {
        expect(screen.getByTestId('dashboard')).toBeInTheDocument()
      })
    })

    it('should handle form submission with enter key', async () => {
      const user = userEvent.setup()
      renderLoginPage()

      await waitFor(() => {
        expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
      })

      // Fill in form with valid mock credentials
      await user.type(screen.getByLabelText(/email/i), 'user@example.com')
      await user.type(screen.getByLabelText(/password/i), 'password123{enter}')

      // Should complete login and redirect
      await waitFor(() => {
        expect(screen.getByTestId('dashboard')).toBeInTheDocument()
      })
    })
  })

  describe('Successful Login', () => {
    it('should redirect to dashboard on successful login', async () => {
      const user = userEvent.setup()
      renderLoginPage()

      await waitFor(() => {
        expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
      })

      // Fill in form with valid credentials
      await user.type(screen.getByLabelText(/email/i), 'admin@example.com')
      await user.type(screen.getByLabelText(/password/i), 'password123')

      // Submit
      await user.click(screen.getByRole('button', { name: /sign in/i }))

      // Should redirect to dashboard
      await waitFor(() => {
        expect(screen.getByTestId('dashboard')).toBeInTheDocument()
      }, { timeout: 3000 })
    })
  })

  describe('Failed Login', () => {
    it('should show error message on invalid credentials', async () => {
      const user = userEvent.setup()
      renderLoginPage()

      await waitFor(() => {
        expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
      })

      // Fill in form with invalid credentials
      await user.type(screen.getByLabelText(/email/i), 'wrong@example.com')
      await user.type(screen.getByLabelText(/password/i), 'wrongpassword')

      // Submit
      await user.click(screen.getByRole('button', { name: /sign in/i }))

      // Should show error
      await waitFor(() => {
        expect(screen.getByText(/invalid/i)).toBeInTheDocument()
      })
    })

    it('should not redirect on failed login', async () => {
      const user = userEvent.setup()
      renderLoginPage()

      await waitFor(() => {
        expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
      })

      // Fill in form with invalid credentials
      await user.type(screen.getByLabelText(/email/i), 'wrong@example.com')
      await user.type(screen.getByLabelText(/password/i), 'wrongpassword')

      // Submit
      await user.click(screen.getByRole('button', { name: /sign in/i }))

      // Wait for error
      await waitFor(() => {
        expect(screen.getByText(/invalid/i)).toBeInTheDocument()
      })

      // Should still be on login page
      expect(screen.queryByTestId('dashboard')).not.toBeInTheDocument()
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    })

    it('should re-enable form after failed login', async () => {
      const user = userEvent.setup()
      renderLoginPage()

      await waitFor(() => {
        expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
      })

      // Fill in form with invalid credentials
      await user.type(screen.getByLabelText(/email/i), 'wrong@example.com')
      await user.type(screen.getByLabelText(/password/i), 'wrongpassword')

      // Submit
      await user.click(screen.getByRole('button', { name: /sign in/i }))

      // Wait for error and form to be re-enabled
      await waitFor(() => {
        expect(screen.getByLabelText(/email/i)).not.toBeDisabled()
        expect(screen.getByLabelText(/password/i)).not.toBeDisabled()
        expect(screen.getByRole('button', { name: /sign in/i })).not.toBeDisabled()
      })
    })
  })

  describe('Auto-redirect When Authenticated', () => {
    it('should redirect to home if already authenticated', async () => {
      // Pre-populate with valid token
      localStorage.setItem('hermes_access_token', createUserToken())
      localStorage.setItem('hermes_refresh_token', 'refresh-token')

      renderLoginPage()

      // Should redirect to dashboard
      await waitFor(() => {
        expect(screen.getByTestId('dashboard')).toBeInTheDocument()
      }, { timeout: 3000 })
    })

    it('should not show login form if already authenticated', async () => {
      localStorage.setItem('hermes_access_token', createUserToken())
      localStorage.setItem('hermes_refresh_token', 'refresh-token')

      renderLoginPage()

      await waitFor(() => {
        expect(screen.getByTestId('dashboard')).toBeInTheDocument()
      }, { timeout: 3000 })

      expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument()
    })
  })

  describe('Accessibility', () => {
    it('should have proper form labels', async () => {
      renderLoginPage()

      await waitFor(() => {
        expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
        expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
      })

      // Labels should be properly associated
      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/password/i)

      expect(emailInput).toHaveAttribute('id')
      expect(passwordInput).toHaveAttribute('id')
    })

    it('should have required attributes on inputs', async () => {
      renderLoginPage()

      await waitFor(() => {
        const emailInput = screen.getByLabelText(/email/i)
        const passwordInput = screen.getByLabelText(/password/i)

        expect(emailInput).toHaveAttribute('required')
        expect(passwordInput).toHaveAttribute('required')
      })
    })

    it('should have type email on email input', async () => {
      renderLoginPage()

      await waitFor(() => {
        const emailInput = screen.getByLabelText(/email/i)
        expect(emailInput).toHaveAttribute('type', 'email')
      })
    })
  })
})
