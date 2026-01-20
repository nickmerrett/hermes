# Hermes Platform Test Suite

Comprehensive test suite for the Hermes customer intelligence platform, covering backend API endpoints, utility functions, and frontend components.

## Table of Contents

- [Overview](#overview)
- [Backend Tests](#backend-tests)
  - [Setup](#backend-setup)
  - [Running Tests](#running-backend-tests)
  - [Test Structure](#backend-test-structure)
  - [Writing New Tests](#writing-backend-tests)
- [Frontend Tests](#frontend-tests)
  - [Setup](#frontend-setup)
  - [Running Tests](#running-frontend-tests)
  - [Test Structure](#frontend-test-structure)
  - [Writing New Tests](#writing-frontend-tests)
- [Running Tests in Containers](#running-tests-in-containers)
- [Coverage Targets](#coverage-targets)
- [CI/CD Integration](#cicd-integration)

---

## Overview

The test suite is organized into two main sections:

| Component | Framework | Test Types |
|-----------|-----------|------------|
| Backend | pytest | Unit tests, Integration tests |
| Frontend | Vitest + Testing Library | Component tests, Context tests |

**Total Tests:** ~300+ test cases covering:
- 4 utility modules (deduplication, smart feed, encryption, rate limiting)
- 4 API modules (auth, customers, feed, RSS)
- 3 frontend components (AuthContext, ProtectedRoute, LoginPage)

---

## Backend Tests

### Backend Setup

The backend uses **pytest** with async support. Required dependencies are already in `requirements.txt`:

```bash
cd backend
pip install -r requirements.txt
```

Key testing dependencies:
- `pytest>=8.0.0` - Test framework
- `pytest-asyncio` - Async test support
- `pytest-cov` - Coverage reporting

### Running Backend Tests

```bash
cd backend

# Run all tests
pytest

# Run unit tests only (fast, no database)
pytest tests/unit -v

# Run integration tests only (requires database fixtures)
pytest tests/integration -v

# Run specific test file
pytest tests/unit/utils/test_deduplication.py -v

# Run tests matching a pattern
pytest -k "test_login" -v

# Run with coverage report
pytest --cov=app --cov-report=term-missing

# Generate HTML coverage report
pytest --cov=app --cov-report=html
# Open htmlcov/index.html in browser

# Run tests by marker
pytest -m unit          # Only unit tests
pytest -m integration   # Only integration tests
pytest -m "not slow"    # Exclude slow tests
```

### Backend Test Structure

```
backend/
├── pytest.ini                      # pytest configuration
└── tests/
    ├── __init__.py
    ├── conftest.py                 # Shared fixtures
    │
    ├── unit/                       # Pure unit tests (no DB)
    │   ├── __init__.py
    │   └── utils/
    │       ├── __init__.py
    │       ├── test_deduplication.py    # URL normalization, title similarity
    │       ├── test_smart_feed.py       # Feed filtering, diversity control
    │       ├── test_encryption.py       # Fernet encrypt/decrypt
    │       └── test_rate_limiter.py     # Rate limiting, task queue
    │
    ├── integration/                # Tests requiring database
    │   ├── __init__.py
    │   └── api/
    │       ├── __init__.py
    │       ├── test_auth.py            # Login, refresh, user CRUD
    │       ├── test_customers.py       # Customer CRUD
    │       ├── test_feed.py            # Feed retrieval, filtering
    │       └── test_rss.py             # RSS tokens, feed generation
    │
    ├── collectors/                 # Collector tests (mocked APIs)
    │   └── __init__.py
    │
    └── fixtures/                   # Test data files
        └── api_responses/
```

### Available Fixtures (conftest.py)

| Fixture | Description |
|---------|-------------|
| `test_db` | In-memory SQLite database session |
| `client` | FastAPI TestClient with DB override |
| `test_user` | Regular user fixture |
| `admin_user` | Admin user fixture |
| `auth_headers` | JWT auth headers for regular user |
| `admin_auth_headers` | JWT auth headers for admin |
| `sample_customer` | Customer with default settings |
| `sample_customer_with_custom_feed` | Customer with custom smart feed |
| `sample_intelligence_item` | Single intelligence item with processed data |
| `sample_intelligence_items` | Multiple items for feed testing |
| `sample_rss_token` | RSS feed token |

### Writing Backend Tests

**Unit Test Example:**
```python
# tests/unit/utils/test_example.py
import pytest
from app.utils.example import my_function

class TestMyFunction:
    def test_basic_case(self):
        result = my_function("input")
        assert result == "expected"

    def test_edge_case(self):
        with pytest.raises(ValueError):
            my_function(None)
```

**Integration Test Example:**
```python
# tests/integration/api/test_example.py
import pytest
from fastapi import status

class TestMyEndpoint:
    def test_get_resource(self, client, auth_headers, sample_customer):
        response = client.get(
            f"/api/resource/{sample_customer.id}",
            headers=auth_headers
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == sample_customer.id

    def test_unauthorized_access(self, client):
        response = client.get("/api/resource/1")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
```

**Async Test Example:**
```python
# tests/unit/utils/test_async_example.py
import pytest

class TestAsyncFunction:
    @pytest.mark.asyncio
    async def test_async_operation(self):
        result = await async_function()
        assert result is True
```

---

## Frontend Tests

### Frontend Setup

The frontend uses **Vitest** with React Testing Library and MSW for API mocking.

```bash
cd frontend

# Install dependencies (includes test dependencies)
npm install
```

Key testing dependencies (in package.json):
- `vitest` - Test framework
- `@testing-library/react` - React component testing
- `@testing-library/jest-dom` - DOM matchers
- `@testing-library/user-event` - User interaction simulation
- `msw` - API mocking
- `jsdom` - DOM environment

### Running Frontend Tests

```bash
cd frontend

# Run all tests in watch mode
npm run test

# Run tests once (CI mode)
npm run test -- --run

# Run with coverage
npm run test:coverage

# Run with interactive UI
npm run test:ui

# Run specific test file
npm run test -- tests/unit/contexts/AuthContext.test.jsx

# Run tests matching a pattern
npm run test -- --grep "login"
```

### Frontend Test Structure

```
frontend/
├── vitest.config.js               # Vitest configuration
├── package.json                   # Test scripts and dependencies
│
├── src/
│   ├── setupTests.js              # Test setup (MSW, matchers)
│   └── mocks/
│       ├── handlers.js            # MSW request handlers
│       └── server.js              # MSW server setup
│
└── tests/
    └── unit/
        ├── contexts/
        │   └── AuthContext.test.jsx    # Auth state management
        └── components/
            ├── ProtectedRoute.test.jsx # Route protection
            └── LoginPage.test.jsx      # Login UI
```

### MSW Mock Handlers

API mocks are defined in `src/mocks/handlers.js`. Available mock endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login` | POST | Returns tokens for valid credentials |
| `/api/auth/refresh` | POST | Refreshes access token |
| `/api/auth/me` | GET | Returns current user |
| `/api/auth/users` | GET/POST | User management |
| `/api/customers` | GET/POST | Customer CRUD |
| `/api/rss/tokens` | GET/POST | RSS token management |
| `/api/feed` | GET | Intelligence feed |

### Writing Frontend Tests

**Component Test Example:**
```jsx
// tests/unit/components/MyComponent.test.jsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import MyComponent from '../../../src/components/MyComponent'

describe('MyComponent', () => {
  it('should render correctly', () => {
    render(<MyComponent />)
    expect(screen.getByText('Hello')).toBeInTheDocument()
  })

  it('should handle click', async () => {
    const user = userEvent.setup()
    render(<MyComponent />)

    await user.click(screen.getByRole('button'))

    expect(screen.getByText('Clicked')).toBeInTheDocument()
  })
})
```

**Context Test Example:**
```jsx
// tests/unit/contexts/MyContext.test.jsx
import { describe, it, expect } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MyProvider, useMyContext } from '../../../src/contexts/MyContext'

function TestComponent() {
  const { value } = useMyContext()
  return <div data-testid="value">{value}</div>
}

describe('MyContext', () => {
  it('should provide value to children', async () => {
    render(
      <MyProvider>
        <TestComponent />
      </MyProvider>
    )

    await waitFor(() => {
      expect(screen.getByTestId('value')).toHaveTextContent('expected')
    })
  })
})
```

**Testing with Router:**
```jsx
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from '../../../src/contexts/AuthContext'

function renderWithRouter(ui, { initialEntries = ['/'] } = {}) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <AuthProvider>
        <Routes>
          {ui}
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  )
}
```

---

## Running Tests in Containers

For consistent test environments and to avoid local dependency issues, tests can be run in Docker/Podman containers.

### Container Test Files

```
├── docker-compose.test.yml      # Test orchestration
├── backend/
│   └── Dockerfile               # Multi-stage (includes test target)
└── frontend/
    └── Dockerfile.test          # Frontend test image
```

### Quick Start

```bash
# Run backend tests
docker-compose -f docker-compose.test.yml run --rm backend-test

# Run frontend tests
docker-compose -f docker-compose.test.yml run --rm frontend-test

# Run backend tests with coverage
docker-compose -f docker-compose.test.yml run --rm backend-coverage

# Run frontend tests with coverage
docker-compose -f docker-compose.test.yml run --rm frontend-coverage
```

### Podman Users

For Podman on Fedora/RHEL with SELinux, use `podman-compose` and note that the volume mounts include `:Z` labels for SELinux compatibility:

```bash
podman-compose -f docker-compose.test.yml run --rm backend-test
podman-compose -f docker-compose.test.yml run --rm frontend-test
```

### Available Test Services

| Service | Description | Output |
|---------|-------------|--------|
| `backend-test` | Runs pytest on backend unit + integration tests | Console output |
| `backend-coverage` | Runs pytest with coverage report | `backend/htmlcov/` |
| `frontend-test` | Runs Vitest on frontend tests | Console output |
| `frontend-coverage` | Runs Vitest with coverage | `frontend/coverage/` |

### Backend Dockerfile Test Stage

The backend Dockerfile uses a multi-stage build with a dedicated test stage:

```dockerfile
# Build test stage
FROM base AS test
WORKDIR /app
COPY app/ ./app/
COPY tests/ ./tests/
COPY pytest.ini ./
ENV TESTING=true
CMD ["pytest", "tests/", "-v", "--tb=short"]
```

Build and run manually:

```bash
cd backend

# Build the test image
docker build -t hermes-backend-test --target test .

# Run tests
docker run --rm hermes-backend-test

# Run specific tests
docker run --rm hermes-backend-test pytest tests/unit -v
```

### Frontend Dockerfile.test

```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
CMD ["npm", "run", "test", "--", "--run"]
```

Build and run manually:

```bash
cd frontend

# Build the test image
docker build -t hermes-frontend-test -f Dockerfile.test .

# Run tests
docker run --rm hermes-frontend-test
```

### Environment Variables

The test containers set these environment variables automatically:

| Variable | Value | Purpose |
|----------|-------|---------|
| `TESTING` | `true` | Enables test mode |
| `JWT_SECRET_KEY` | `test-secret-key` | JWT signing for tests |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `PYTHONDONTWRITEBYTECODE` | `1` | Prevents .pyc files |

### Viewing Coverage Reports

After running coverage tests, reports are available on your host:

```bash
# Backend HTML coverage
open backend/htmlcov/index.html

# Frontend coverage
open frontend/coverage/index.html
```

---

## Coverage Targets

| Module Type | Target Coverage |
|-------------|-----------------|
| Security (auth, encryption) | 90% |
| Business logic (smart_feed, dedup) | 85% |
| API endpoints | 80% |
| Collectors | 70% |
| UI components | 70% |

**Overall Target:** 75%+ coverage

---

## CI/CD Integration

### GitHub Actions Example

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt

      - name: Run tests
        run: |
          cd backend
          pytest --cov=app --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: backend/coverage.xml

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install dependencies
        run: |
          cd frontend
          npm ci

      - name: Run tests
        run: |
          cd frontend
          npm run test -- --run --coverage

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: frontend/coverage/coverage-final.json
```

### Pre-commit Hook

Add to `.git/hooks/pre-commit`:

```bash
#!/bin/bash

# Run backend unit tests
cd backend
pytest tests/unit -q --tb=no
if [ $? -ne 0 ]; then
  echo "Backend tests failed"
  exit 1
fi

# Run frontend tests
cd ../frontend
npm run test -- --run --reporter=dot
if [ $? -ne 0 ]; then
  echo "Frontend tests failed"
  exit 1
fi

echo "All tests passed"
```

---

## Test Markers

Backend tests use pytest markers for categorization:

```ini
# pytest.ini markers
markers =
    unit: Pure unit tests (no database or external dependencies)
    integration: Tests requiring database
    slow: Tests that take longer than 1 second
    auth: Authentication-related tests
    api: API endpoint tests
    collector: Data collector tests
```

Usage:
```bash
pytest -m unit                    # Run only unit tests
pytest -m "integration and auth"  # Run auth integration tests
pytest -m "not slow"              # Skip slow tests
```

---

## Troubleshooting

### Backend Tests

**Issue:** `ModuleNotFoundError: No module named 'app'`
```bash
# Run from backend directory or set PYTHONPATH
cd backend
export PYTHONPATH=$PYTHONPATH:$(pwd)
pytest
```

**Issue:** Database tests failing
```bash
# Ensure test environment variables are set
export TESTING=true
export JWT_SECRET_KEY=test-secret
```

### Frontend Tests

**Issue:** MSW handlers not working
```javascript
// Check that server is started in setupTests.js
beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
```

**Issue:** `act(...)` warnings
```javascript
// Wrap state updates in waitFor
await waitFor(() => {
  expect(screen.getByText('Updated')).toBeInTheDocument()
})
```

---

## Adding New Tests

1. **Identify the test type:**
   - Unit test: Pure function, no external dependencies
   - Integration test: Requires database or external services

2. **Create the test file** in the appropriate directory

3. **Use existing fixtures** from `conftest.py` (backend) or create mock handlers (frontend)

4. **Follow naming conventions:**
   - Files: `test_<module>.py` or `<Component>.test.jsx`
   - Classes: `Test<FeatureName>`
   - Functions: `test_<behavior>`

5. **Run tests locally** before committing

6. **Check coverage** to ensure new code is tested
