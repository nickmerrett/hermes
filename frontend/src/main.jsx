import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import App from './App'
import LoginPage from './pages/LoginPage'
import AddCustomerPage from './pages/AddCustomerPage'
import ExecutiveDashboardPage from './pages/ExecutiveDashboard/ExecutiveDashboardPage'
import AnalyticsDashboardPage from './pages/AnalyticsDashboard/AnalyticsDashboardPage'
import AdminPanel from './components/AdminPanel'
import './styles/index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={
            <ProtectedRoute>
              <App />
            </ProtectedRoute>
          } />
          <Route path="/add-customer" element={
            <ProtectedRoute>
              <AddCustomerPage />
            </ProtectedRoute>
          } />
          <Route path="/analytics" element={
            <ProtectedRoute>
              <AnalyticsDashboardPage />
            </ProtectedRoute>
          } />
          <Route path="/executive" element={
            <Navigate to="/analytics" replace />
          } />
          <Route path="/executive/:executiveId" element={
            <ProtectedRoute>
              <ExecutiveDashboardPage />
            </ProtectedRoute>
          } />
          <Route path="/admin" element={
            <ProtectedRoute requireAdmin>
              <AdminPanel />
            </ProtectedRoute>
          } />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
)
