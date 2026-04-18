import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';
import { useAuthStore } from './store/authStore';
import { useThemeStore } from './store/themeStore';
import { OfflineQueueProvider } from './context/OfflineQueueContext';
import { useOnlineStatus } from './hooks/useOnlineStatus';
import { WifiOff } from 'lucide-react';

// Layouts
const MainLayout = React.lazy(() => import('./layouts/MainLayout'));
const AuthLayout = React.lazy(() => import('./layouts/AuthLayout'));

// Pages
const Dashboard = React.lazy(() => import('./pages/Dashboard'));
const Accounts = React.lazy(() => import('./pages/Accounts'));
const AccountDetail = React.lazy(() => import('./pages/AccountDetail'));
const Transactions = React.lazy(() => import('./pages/Transactions'));
const Categories = React.lazy(() => import('./pages/Categories'));
const Settings = React.lazy(() => import('./pages/Settings'));
const Login = React.lazy(() => import('./pages/Login'));
const Register = React.lazy(() => import('./pages/Register'));
const SetPassword = React.lazy(() => import('./pages/SetPassword'));
const ForgotPassword = React.lazy(() => import('./pages/ForgotPassword'));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 60 * 1000,
      gcTime: 30 * 60 * 1000
    }
  }
});

const PrivateRoute = ({ children, adminOnly = false }) => {
  const { isAuthenticated, isSessionExpired, user } = useAuthStore();

  // Session expired while offline — let the overlay handle it, don't redirect yet
  if (!isAuthenticated && !isSessionExpired) {
    return <Navigate to="/login" replace />;
  }

  if (adminOnly && user?.role !== 'ADMIN') {
    return <Navigate to="/" replace />;
  }

  return children;
};

const SessionExpiredOverlay = () => {
  const { isSessionExpired, hasPasskey, user, clearAuth, setSessionExpired } = useAuthStore();
  const { isOnline } = useOnlineStatus();

  React.useEffect(() => {
    if (isOnline && isSessionExpired) {
      // Back online — clear the session and let the user reauthenticate
      clearAuth();
      window.history.pushState({}, '', '/login');
      window.dispatchEvent(new PopStateEvent('popstate'));
    }
  }, [isOnline, isSessionExpired, clearAuth]);

  if (!isSessionExpired) return null;

  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-slate-900/80 backdrop-blur-sm px-6">
      <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl p-8 max-w-sm w-full text-center space-y-4">
        <div className="flex justify-center">
          <div className="bg-amber-100 dark:bg-amber-900/40 rounded-full p-4">
            <WifiOff className="w-8 h-8 text-amber-600 dark:text-amber-400" />
          </div>
        </div>
        <h2 className="text-xl font-semibold text-slate-800 dark:text-slate-100">
          Session expired
        </h2>
        {user?.first_name && (
          <p className="text-slate-500 dark:text-slate-400 text-sm">
            Hi {user.first_name}, your session expired while you were offline.
          </p>
        )}
        <p className="text-slate-500 dark:text-slate-400 text-sm">
          Reconnect to the internet to sign in again.
          {hasPasskey ? ' You can use biometrics once you\'re back online.' : ''}
        </p>
        <div className="flex items-center justify-center gap-2 text-amber-600 dark:text-amber-400 text-sm font-medium">
          <div className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
          Waiting for connection…
        </div>
      </div>
    </div>
  );
};

// Theme Initializer Component
const ThemeInitializer = ({ children }) => {
  const [isReady, setIsReady] = React.useState(false);

  React.useEffect(() => {
    // Wait a tick for Zustand to hydrate from localStorage
    const timer = setTimeout(() => {
      const { initializeTheme } = useThemeStore.getState();
      initializeTheme();
      setIsReady(true);
    }, 0);
    
    return () => clearTimeout(timer);
  }, []);
  
  // Don't render until theme is initialized to avoid flash
  if (!isReady) {
    return null;
  }
  
  return children;
};

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <OfflineQueueProvider>
      <Toaster position="top-right" />
      <SessionExpiredOverlay />
      <ThemeInitializer>
        <React.Suspense
          fallback={
            <div className="min-h-screen flex items-center justify-center bg-gray-100 dark:bg-slate-900">
              <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600"></div>
            </div>
          }
        >
          <Router>
            <Routes>
              <Route element={<AuthLayout />}>
                <Route path="/login" element={<Login />} />
                <Route path="/register" element={<Register />} />
                <Route path="/set-password" element={<SetPassword />} />
                <Route path="/forgot-password" element={<ForgotPassword />} />
              </Route>

              <Route element={<MainLayout />}>
                <Route path="/" element={
                  <PrivateRoute>
                    <Dashboard />
                  </PrivateRoute>
                } />
                <Route path="/accounts" element={
                  <PrivateRoute>
                    <Accounts />
                  </PrivateRoute>
                } />
                <Route path="/accounts/:accountId" element={
                  <PrivateRoute>
                    <AccountDetail />
                  </PrivateRoute>
                } />
                <Route path="/transactions" element={
                  <PrivateRoute>
                    <Transactions />
                  </PrivateRoute>
                } />
                <Route path="/categories" element={
                  <PrivateRoute>
                    <Categories />
                  </PrivateRoute>
                } />
                <Route path="/settings" element={
                  <PrivateRoute>
                    <Settings />
                  </PrivateRoute>
                } />
              </Route>
            </Routes>
          </Router>
        </React.Suspense>
      </ThemeInitializer>
      </OfflineQueueProvider>
    </QueryClientProvider>
  );
}

export default App;
