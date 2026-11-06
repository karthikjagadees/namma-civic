import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import CitizenDashboard from './pages/CitizenDashboard'
import ReportComplaintPage from './pages/ReportComplaintPage'
import ComplaintDetailPage from './pages/ComplaintDetailPage'
import { OfficerDashboard } from './pages/OfficerDashboard'
import { AnalyticsPage } from './pages/AnalyticsPage'
import { AdminPage } from './pages/AdminPage'
import { DuplicateReviewPage } from './pages/DuplicateReviewPage'
import { AgentsPage, DepartmentsPage, InsightsPage, ServicesPage, TrackPage } from './pages/PublicPages'
import { ProtectedRoute } from './components/AppShell'

export default function App() {
  return (
    <Router>
      <Routes>
        {/* Public Routes */}
        <Route path="/" element={<LandingPage />} />
        <Route path="/services" element={<ServicesPage />} />
        <Route path="/track" element={<TrackPage />} />
        <Route path="/insights" element={<InsightsPage />} />
        <Route path="/departments" element={<DepartmentsPage />} />
        <Route path="/agents" element={<AgentsPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/analytics" element={<AnalyticsPage />} />

        {/* Protected Citizen & General Routes */}
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <CitizenDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/report"
          element={
            <ProtectedRoute>
              <ReportComplaintPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/complaints/:id"
          element={
            <ProtectedRoute>
              <ComplaintDetailPage />
            </ProtectedRoute>
          }
        />

        {/* Protected Officer Routes */}
        <Route
          path="/officer"
          element={
            <ProtectedRoute roles={['officer', 'admin']}>
              <OfficerDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/officer/duplicate-reviews"
          element={
            <ProtectedRoute roles={['officer', 'admin']}>
              <DuplicateReviewPage />
            </ProtectedRoute>
          }
        />

        {/* Protected Admin Routes */}
        <Route
          path="/admin"
          element={
            <ProtectedRoute roles={['admin']}>
              <AdminPage />
            </ProtectedRoute>
          }
        />

        {/* Catch-all fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  )
}
