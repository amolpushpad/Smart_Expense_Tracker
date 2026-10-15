import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';
import Login from './pages/Login';
import Register from './pages/Register';
import Expenses from './pages/Expenses';
import Income from './pages/Income';
import Budgets from './pages/Budgets';
import Profile from './pages/Profile';

const Dashboard = lazy(() => import('./pages/Dashboard'));
const Analytics = lazy(() => import('./pages/Analytics'));
const Reports = lazy(() => import('./pages/Reports'));

function PageLoader() {
  return <div className="auth-page" role="status">Loading page...</div>;
}

function ProtectedLayout() {
  const { user, loading } = useAuth();
  if (loading) return <div className="auth-page" role="status">Checking your session...</div>;
  if (!user) return <Navigate to="/login" replace />;
  return <div className="app-shell"><Sidebar /><div className="main-area"><Navbar /><main className="page-content"><Routes><Route path="/dashboard" element={<Suspense fallback={<PageLoader />}><Dashboard /></Suspense>} /><Route path="/expenses" element={<Expenses />} /><Route path="/income" element={<Income />} /><Route path="/budgets" element={<Budgets />} /><Route path="/analytics" element={<Suspense fallback={<PageLoader />}><Analytics /></Suspense>} /><Route path="/reports" element={<Suspense fallback={<PageLoader />}><Reports /></Suspense>} /><Route path="/profile" element={<Profile />} /><Route path="*" element={<Navigate to="/dashboard" replace />} /></Routes></main></div></div>;
}

export default function App() {
  const { user, loading } = useAuth();
  if (loading) return <div className="auth-page" role="status">Checking your session...</div>;
  return <Routes><Route path="/login" element={user ? <Navigate to="/dashboard" replace /> : <Login />} /><Route path="/register" element={user ? <Navigate to="/dashboard" replace /> : <Register />} /><Route path="/*" element={<ProtectedLayout />} /></Routes>;
}
