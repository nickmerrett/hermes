/**
 * Test setup file - runs before each test file
 *
 * Sets up:
 * - Testing Library matchers
 * - MSW server for API mocking
 * - Global mocks for browser APIs
 */

import { expect, afterEach, beforeAll, afterAll } from 'vitest'
import { cleanup } from '@testing-library/react'
import * as matchers from '@testing-library/jest-dom/matchers'
import { server } from './mocks/server'

// Extend Vitest's expect with Testing Library matchers
expect.extend(matchers)

// Setup MSW server
beforeAll(() => {
  // Start the MSW server before all tests
  server.listen({ onUnhandledRequest: 'warn' })
})

afterEach(() => {
  // Cleanup DOM after each test
  cleanup()

  // Reset MSW handlers after each test
  server.resetHandlers()

  // Clear localStorage
  localStorage.clear()

  // Clear sessionStorage
  sessionStorage.clear()
})

afterAll(() => {
  // Close the MSW server after all tests
  server.close()
})

// Mock window.matchMedia for responsive tests
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => {}
  })
})

// Mock IntersectionObserver
global.IntersectionObserver = class IntersectionObserver {
  constructor() {
    this.root = null
    this.rootMargin = ''
    this.thresholds = []
  }
  observe() {}
  unobserve() {}
  disconnect() {}
}

// Mock ResizeObserver
global.ResizeObserver = class ResizeObserver {
  constructor() {}
  observe() {}
  unobserve() {}
  disconnect() {}
}

// Mock scrollTo
window.scrollTo = () => {}

// Suppress console.error for expected errors in tests
const originalError = console.error
console.error = (...args) => {
  // Suppress React Router warnings in tests
  if (
    typeof args[0] === 'string' &&
    (args[0].includes('React Router') ||
      args[0].includes('act(...)') ||
      args[0].includes('Warning:'))
  ) {
    return
  }
  originalError.call(console, ...args)
}
