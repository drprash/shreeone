import React from 'react';
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import OfflineBanner from '../components/OfflineBanner';
import CacheWarmer from '../components/CacheWarmer';
import OnboardingTour from '../components/Onboarding/OnboardingTour';
import { LayoutDashboard, Wallet, List, Tags, Settings, LogOut, Menu, X, Target, BarChart2 } from 'lucide-react';

const MainLayout = () => {
  const { user, clearAuth } = useAuthStore();
  const location = useLocation();
  const navigate = useNavigate();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = React.useState(false);

  const navigation = [
    { name: 'Dashboard', href: '/', icon: LayoutDashboard },
    { name: 'Stats', href: '/stats', icon: BarChart2 },
    { name: 'Goals', href: '/goals', icon: Target },
    { name: 'Accounts', href: '/accounts', icon: Wallet },
    { name: 'Transactions', href: '/transactions', icon: List },
    { name: 'Categories', href: '/categories', icon: Tags },
    { name: 'Settings', href: '/settings', icon: Settings },
  ];

  const handleLogout = () => {
    clearAuth();
    navigate('/login', { replace: true });
  };

  React.useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [location.pathname]);

  return (
    <div className="min-h-screen bg-gray-100 dark:bg-[#0d1117]">
      <header className="md:hidden fixed top-0 left-0 right-0 z-30 bg-white dark:bg-[#161b22] border-b border-gray-200 dark:border-[#2a3142] px-4 py-3">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold text-blue-600 dark:text-blue-400">ShreeOne</h1>
            <p className="text-xs text-gray-500 dark:text-gray-400">Family Finance</p>
          </div>
          <button
            type="button"
            aria-label="Open menu"
            onClick={() => setIsMobileMenuOpen(true)}
            className="p-2 rounded-lg text-gray-700 dark:text-slate-300 hover:bg-gray-100 dark:hover:bg-[#1e293b]"
          >
            <Menu className="w-6 h-6" />
          </button>
        </div>
      </header>

      {isMobileMenuOpen && (
        <button
          type="button"
          aria-label="Close menu"
          onClick={() => setIsMobileMenuOpen(false)}
          className="md:hidden fixed inset-0 z-30 bg-black/40"
        />
      )}

      <div className={`fixed inset-y-0 left-0 z-40 w-64 bg-white dark:bg-[#161b22] border-r border-gray-200 dark:border-[#2a3142] shadow-lg dark:shadow-black/40 transform transition-transform duration-200 md:translate-x-0 ${isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="flex flex-col h-full">
          <div className="p-6 flex items-start justify-between">
            <h1 className="text-2xl font-bold text-blue-600 dark:text-blue-400">ShreeOne</h1>
            <button
              type="button"
              aria-label="Close menu"
              onClick={() => setIsMobileMenuOpen(false)}
              className="md:hidden p-1 rounded text-gray-600 dark:text-slate-400 hover:bg-gray-100 dark:hover:bg-[#1e293b]"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
          <p className="text-sm text-gray-500 dark:text-slate-500 -mt-5 px-6 mb-4">Family Finance</p>

          <nav className="flex-1 px-4 space-y-2">
            {navigation.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.href;
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  className={`flex items-center px-4 py-3 rounded-lg transition-colors ${
                    isActive
                      ? 'bg-blue-50 dark:bg-blue-500/20 text-blue-600 dark:text-blue-300 font-medium'
                      : 'text-gray-600 dark:text-slate-300 hover:bg-gray-50 dark:hover:bg-[#1e293b] hover:text-gray-900 dark:hover:text-slate-100'
                  }`}
                >
                  <Icon className="w-5 h-5 mr-3" />
                  {item.name}
                </Link>
              );
            })}
          </nav>

          <div className="p-4 border-t border-gray-200 dark:border-[#2a3142]">
            <div className="flex items-center justify-between mb-4">
              <div>
                <p className="font-medium text-gray-900 dark:text-slate-200">{user?.first_name}</p>
                <p className="text-sm text-gray-500 dark:text-slate-500 capitalize">{user?.role?.toLowerCase()}</p>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="flex items-center w-full px-4 py-2 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/40 rounded-lg transition-colors"
            >
              <LogOut className="w-5 h-5 mr-3" />
              Logout
            </button>
          </div>
        </div>
      </div>

      <CacheWarmer />
      <OnboardingTour />
      <div className="md:ml-64 pt-16 md:pt-0">
        <OfflineBanner />
        <div className="p-4 md:p-8">
          <Outlet />
        </div>
      </div>
    </div>
  );
};

export default MainLayout;
