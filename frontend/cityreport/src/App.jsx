import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';

// Auth Pages
import Welcome from './pages/auth/Welcome';
import Login from './pages/auth/Login';
import Signup from './pages/auth/Signup';
import AuthCallback from './pages/auth/AuthCallback';

// Citizen Pages
import CitizenDashboard from './pages/citizen/Dashboard';
import NewReport from './pages/citizen/NewReport';
import MapView from './pages/citizen/MapView';
import ReportDetail from './pages/citizen/ReportDetail';
import MyReports from './pages/citizen/MyReports';

// Officer Pages
import OfficerDashboard from './pages/officer/Dashboard';

// Admin Pages
import AdminDashboard from './pages/admin/Dashboard';
import AdminReports from './pages/admin/AdminReports';

// Protected Route Component
const ProtectedRoute = ({ children, allowedRoles }) => {
  const { user, loading } = useAuth();

  if (loading) return <div>Loading...</div>;

  if (!user) {
    return <Navigate to="/login" />;
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to={`/${user.role}/dashboard`} />;
  }

  return children;
};

function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          {/* Public Routes */}
          <Route path="/" element={<Welcome />} />
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/auth/callback" element={<AuthCallback />} />

          {/* Citizen Routes */}
          <Route
            path="/citizen/*"
            element={
              <ProtectedRoute allowedRoles={['citizen']}>
                <Routes>
                  <Route path="dashboard" element={<CitizenDashboard />} />
                  <Route path="report/new" element={<NewReport />} />
                  <Route path="report/:id" element={<ReportDetail />} />
                  <Route path="map" element={<MapView />} />
                  <Route path="reports" element={<MyReports />} />
                </Routes>
              </ProtectedRoute>
            }
          />

          {/* Officer Routes */}
          <Route
            path="/officer/*"
            element={
              <ProtectedRoute allowedRoles={['officer']}>
                <Routes>
                  <Route path="dashboard" element={<OfficerDashboard />} />
                  <Route path="report/:id" element={<ReportDetail />} />
                </Routes>
              </ProtectedRoute>
            }
          />

          {/* Admin Routes */}
          <Route
            path="/admin/*"
            element={
              <ProtectedRoute allowedRoles={['admin']}>
                <Routes>
                  <Route path="dashboard" element={<AdminDashboard />} />
                  <Route path="reports" element={<AdminReports />} />
                  <Route path="reports/:id" element={<ReportDetail />} />
                </Routes>
              </ProtectedRoute>
            }
          />
        </Routes>
      </Router>
    </AuthProvider>
  );
}

export default App;
