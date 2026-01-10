import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import App from './App'
import AddCustomerPage from './pages/AddCustomerPage'
import ExecutiveDashboardPage from './pages/ExecutiveDashboard/ExecutiveDashboardPage'
import './styles/index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/add-customer" element={<AddCustomerPage />} />
        <Route path="/executive/:executiveId" element={<ExecutiveDashboardPage />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
)
