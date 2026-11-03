import { lazy, Suspense, useEffect, useState } from 'react';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';
import ThemeSwitcher from './components/ThemeSwitcher';
import Login from './pages/Login';
import Register from './pages/Register';
import Expenses from './pages/Expenses';
import Income from './pages/Income';
import Budgets from './pages/Budgets';
import Profile from './pages/Profile';
import CorporateDashboard from './pages/CorporateDashboard';

const Dashboard = lazy(() => import('./pages/Dashboard'));
const Analytics = lazy(() => import('./pages/Analytics'));
const Reports = lazy(() => import('./pages/Reports'));
const DatasetDemo = lazy(() => import('./pages/DatasetDemo'));

function PageLoader() {
  return <div className="auth-page" role="status">Loading page...</div>;
}

function ProtectedLayout() {
  const { user, loading } = useAuth();
  const [navigationOpen, setNavigationOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    setNavigationOpen(false);
  }, [location.pathname]);

  if (loading) return <div className="auth-page" role="status">Checking your session...</div>;
  if (!user) return <Navigate to="/login" replace />;
  const home = user.workspace_mode === 'corporate' ? '/corporate' : '/dashboard';
  return <div className="app-shell"><Sidebar open={navigationOpen} onClose={() => setNavigationOpen(false)} /><div className="main-area"><Navbar onMenuClick={() => setNavigationOpen(open => !open)} navigationOpen={navigationOpen} /><main className="page-content"><Routes>
    <Route path="/corporate" element={user.workspace_mode === 'corporate' ? <CorporateDashboard user={user} /> : <Navigate to={home} replace />} />
    <Route path="/dashboard" element={user.workspace_mode === 'personal' ? <Suspense fallback={<PageLoader />}><Dashboard /></Suspense> : <Navigate to={home} replace />} />
    <Route path="/expenses" element={user.workspace_mode === 'personal' ? <Expenses /> : <Navigate to={home} replace />} />
    <Route path="/income" element={user.workspace_mode === 'personal' ? <Income /> : <Navigate to={home} replace />} />
    <Route path="/budgets" element={user.workspace_mode === 'personal' ? <Budgets /> : <Navigate to={home} replace />} />
    <Route path="/analytics" element={user.workspace_mode === 'personal' ? <Suspense fallback={<PageLoader />}><Analytics /></Suspense> : <Navigate to={home} replace />} />
    <Route path="/reports" element={user.workspace_mode === 'personal' ? <Suspense fallback={<PageLoader />}><Reports /></Suspense> : <Navigate to={home} replace />} />
    <Route path="/profile" element={user.workspace_mode === 'personal' ? <Profile /> : <Navigate to={home} replace />} />
    <Route path="*" element={<Navigate to={home} replace />} />
  </Routes></main></div></div>;
}

export default function App() {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <div className="auth-page" role="status">Checking your session...</div>;
  const home = user?.workspace_mode === 'corporate' ? '/corporate' : '/dashboard';
  const publicPage = ['/login', '/register', '/demo'].includes(location.pathname);
  return <>{publicPage && <ThemeSwitcher className="theme-switcher-floating" />}<Routes><Route path="/login" element={user ? <Navigate to={home} replace /> : <Login />} /><Route path="/register" element={user ? <Navigate to={home} replace /> : <Register />} /><Route path="/demo" element={<Suspense fallback={<PageLoader />}><DatasetDemo /></Suspense>} /><Route path="/*" element={<ProtectedLayout />} /></Routes></>;
}
