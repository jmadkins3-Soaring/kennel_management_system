import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import Login from './pages/Login'
import CalendarPage from './pages/Calendar/CalendarPage'
import ReservationsPage from './pages/Reservations/ReservationsPage'
import DogsPage from './pages/Dogs/DogsPage'
import OwnersPage from './pages/Owners/OwnersPage'
import KennelsPage from './pages/Kennels/KennelsPage'
import ActivitiesPage from './pages/Activities/ActivitiesPage'
import ReportsPage from './pages/Reports/ReportsPage'
import { PortalEntry } from './pages/Portal/PortalApp'

function PrivateRoute({ children }) {
  const { user } = useAuth()
  return user ? children : <Navigate to="/login" replace />
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login"         element={<Login />} />
      <Route path="/portal/:token" element={<PortalEntry />} />
      <Route path="/calendar"      element={<PrivateRoute><CalendarPage /></PrivateRoute>} />
      <Route path="/reservations"  element={<PrivateRoute><ReservationsPage /></PrivateRoute>} />
      <Route path="/dogs"          element={<PrivateRoute><DogsPage /></PrivateRoute>} />
      <Route path="/owners"        element={<PrivateRoute><OwnersPage /></PrivateRoute>} />
      <Route path="/kennels"       element={<PrivateRoute><KennelsPage /></PrivateRoute>} />
      <Route path="/activities"    element={<PrivateRoute><ActivitiesPage /></PrivateRoute>} />
      <Route path="/reports"       element={<PrivateRoute><ReportsPage /></PrivateRoute>} />
      <Route path="*"              element={<Navigate to="/calendar" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  )
}
