import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './hooks/useAuth'
import LoginPage from './pages/LoginPage'
import ManagerDashboard from './pages/ManagerDashboard'
import ContractorRegister from './pages/ContractorRegister'
import ContractorTimesheet from './pages/ContractorTimesheet'

function PrivateRoute({ children }) {
  const { isLoggedIn } = useAuth()
  return isLoggedIn ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/manager" element={<PrivateRoute><ManagerDashboard /></PrivateRoute>} />
          <Route path="/register/:token" element={<ContractorRegister />} />
          <Route path="/timesheet/:token" element={<ContractorTimesheet />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
