import React, { useState, useEffect } from 'react';

const COMMON_CURRENCIES = [
  { code: 'AED', name: 'UAE Dirham' },
  { code: 'AUD', name: 'Australian Dollar' },
  { code: 'BDT', name: 'Bangladeshi Taka' },
  { code: 'BHD', name: 'Bahraini Dinar' },
  { code: 'CAD', name: 'Canadian Dollar' },
  { code: 'CHF', name: 'Swiss Franc' },
  { code: 'CNY', name: 'Chinese Yuan' },
  { code: 'DKK', name: 'Danish Krone' },
  { code: 'EUR', name: 'Euro' },
  { code: 'GBP', name: 'British Pound' },
  { code: 'HKD', name: 'Hong Kong Dollar' },
  { code: 'IDR', name: 'Indonesian Rupiah' },
  { code: 'INR', name: 'Indian Rupee' },
  { code: 'JPY', name: 'Japanese Yen' },
  { code: 'KES', name: 'Kenyan Shilling' },
  { code: 'KWD', name: 'Kuwaiti Dinar' },
  { code: 'LKR', name: 'Sri Lankan Rupee' },
  { code: 'MYR', name: 'Malaysian Ringgit' },
  { code: 'NOK', name: 'Norwegian Krone' },
  { code: 'NPR', name: 'Nepalese Rupee' },
  { code: 'NZD', name: 'New Zealand Dollar' },
  { code: 'OMR', name: 'Omani Rial' },
  { code: 'PHP', name: 'Philippine Peso' },
  { code: 'PKR', name: 'Pakistani Rupee' },
  { code: 'QAR', name: 'Qatari Riyal' },
  { code: 'SAR', name: 'Saudi Riyal' },
  { code: 'SEK', name: 'Swedish Krona' },
  { code: 'SGD', name: 'Singapore Dollar' },
  { code: 'THB', name: 'Thai Baht' },
  { code: 'USD', name: 'US Dollar' },
  { code: 'ZAR', name: 'South African Rand' },
];
import { useQueryClient } from '@tanstack/react-query';
import settingsAPI from '../../services/settingsAPI';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { queryKeys } from '../../utils/queryKeys';

const FamilySettings = () => {
  const user = useAuthStore((state) => state.user);
  const isAdmin = user?.role === 'ADMIN';
  const queryClient = useQueryClient();

  const [familyProfile, setFamilyProfile] = useState(null);
  const [preferences, setPreferences] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  // Form states
  const [profileForm, setProfileForm] = useState({
    name: '',
    base_currency: 'USD',
    fiscal_month_start: '01',
    privacy_level: 'FAMILY',
  });

  const [prefForm, setPrefForm] = useState({
    theme: 'light',
    language: 'en',
    show_budget_alerts: true,
    show_net_worth_by_country: true,
    show_member_spending: true,
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [profileRes, prefRes] = await Promise.all([
        settingsAPI.getFamilyProfile(),
        settingsAPI.getPreferences(),
      ]);

      setFamilyProfile(profileRes.data);
      setPreferences(prefRes.data);

      setProfileForm({
        name: profileRes.data.name,
        base_currency: profileRes.data.base_currency,
        fiscal_month_start: profileRes.data.fiscal_month_start,
        privacy_level: profileRes.data.privacy_level,
      });

      setPrefForm(prevForm => ({
        ...prevForm,
        ...prefRes.data,
      }));
      
      // Sync theme from API response to store
      const setTheme = useThemeStore.getState().setTheme;
      setTheme(prefRes.data.theme || 'light');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load settings');
    } finally {
      setLoading(false);
    }
  };

  const handleProfileSubmit = async (e) => {
    e.preventDefault();
    try {
      setError(null);
      const formData = {};
      // Only include changed fields
      if (profileForm.name !== familyProfile.name) formData.name = profileForm.name;
      if (profileForm.base_currency !== familyProfile.base_currency) formData.base_currency = profileForm.base_currency;
      if (profileForm.fiscal_month_start !== familyProfile.fiscal_month_start) formData.fiscal_month_start = profileForm.fiscal_month_start;
      if (profileForm.privacy_level !== familyProfile.privacy_level) formData.privacy_level = profileForm.privacy_level;

      if (Object.keys(formData).length === 0) {
        setSuccessMessage('No changes to save');
        return;
      }

      const response = await settingsAPI.updateFamilyProfile(formData);
      setFamilyProfile(response.data);
      
      // Invalidate dashboard query if base_currency changed
      if (formData.base_currency) {
        queryClient.invalidateQueries({ queryKey: queryKeys.dashboardAll() });
      }
      
      setSuccessMessage('Family profile updated successfully!');
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update family profile');
    }
  };

  const handlePrefSubmit = async (e) => {
    e.preventDefault();
    try {
      setError(null);
      const response = await settingsAPI.updatePreferences(prefForm);
      setPreferences(response.data);
      
      // Sync theme to store
      const setTheme = useThemeStore.getState().setTheme;
      setTheme(prefForm.theme);
      
      setSuccessMessage('Preferences updated successfully!');
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update preferences');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  return (
    <div className="p-6">
      {error && (
        <div className="mb-4 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-400">
          {error}
        </div>
      )}

      {successMessage && (
        <div className="mb-4 p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg text-green-700 dark:text-green-400">
          {successMessage}
        </div>
      )}

      {/* Family Profile Section */}
      {isAdmin && (
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mb-4">Family Profile</h2>
          <form onSubmit={handleProfileSubmit} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Family Name
                </label>
                <input
                  type="text"
                  value={profileForm.name}
                  onChange={(e) => setProfileForm({ ...profileForm, name: e.target.value })}
                  className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg focus:outline-none focus:border-indigo-500 dark:bg-slate-700 dark:text-slate-100"
                  disabled={!isAdmin}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Base Currency
                </label>
                <select
                  value={profileForm.base_currency}
                  onChange={(e) => setProfileForm({ ...profileForm, base_currency: e.target.value })}
                  className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg focus:outline-none focus:border-indigo-500 dark:bg-slate-700 dark:text-slate-100"
                  disabled={!isAdmin}
                >
                  {COMMON_CURRENCIES.map(c => (
                    <option key={c.code} value={c.code}>{c.code} — {c.name}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Fiscal Year Start Month
                </label>
                <select
                  value={profileForm.fiscal_month_start}
                  onChange={(e) => setProfileForm({ ...profileForm, fiscal_month_start: e.target.value })}
                  className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg focus:outline-none focus:border-indigo-500 dark:bg-slate-700 dark:text-slate-100"
                  disabled={!isAdmin}
                >
                  {Array.from({ length: 12 }, (_, i) => {
                    const month = String(i + 1).padStart(2, '0');
                    const monthName = new Date(2024, i).toLocaleString('en-US', { month: 'long' });
                    return (
                      <option key={month} value={month}>
                        {monthName} ({month})
                      </option>
                    );
                  })}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Privacy Level
                </label>
                <select
                  value={profileForm.privacy_level}
                  onChange={(e) => setProfileForm({ ...profileForm, privacy_level: e.target.value })}
                  className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg focus:outline-none focus:border-indigo-500 dark:bg-slate-700 dark:text-slate-100"
                  disabled={!isAdmin}
                >
                  <option value="FAMILY">Family (All members see everything)</option>
                  <option value="PRIVATE">Private (Members see only their data)</option>
                  <option value="SHARED">Shared (Members see shared accounts + their own)</option>
                </select>
              </div>
            </div>

            {isAdmin && (
              <button
                type="submit"
                className="mt-4 px-6 py-2 bg-indigo-600 dark:bg-indigo-700 text-white rounded-lg hover:bg-indigo-700 dark:hover:bg-indigo-600 transition-colors font-medium"
              >
                Save Family Profile
              </button>
            )}
          </form>
        </div>
      )}

      {/* Preferences Section */}
      <div>
        <h2 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mb-4">Preferences</h2>
        <form onSubmit={handlePrefSubmit} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                Theme
              </label>
              <select
                value={prefForm.theme}
                onChange={(e) => {
                  setPrefForm({ ...prefForm, theme: e.target.value });
                  // Apply theme immediately on selection
                  const setTheme = useThemeStore.getState().setTheme;
                  setTheme(e.target.value);
                }}
                className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg focus:outline-none focus:border-indigo-500 dark:bg-slate-700 dark:text-slate-100"
              >
                <option value="light">Light</option>
                <option value="dark">Dark</option>
                <option value="auto">Auto</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                Language
              </label>
              <select
                value={prefForm.language}
                onChange={(e) => setPrefForm({ ...prefForm, language: e.target.value })}
                className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg focus:outline-none focus:border-indigo-500 dark:bg-slate-700 dark:text-slate-100"
              >
                <option value="en">English</option>
                <option value="hi">Hindi</option>
                <option value="es">Spanish</option>
              </select>
            </div>
          </div>

          <div className="space-y-3 mt-4">
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={prefForm.show_budget_alerts}
                onChange={(e) => setPrefForm({ ...prefForm, show_budget_alerts: e.target.checked })}
                className="w-4 h-4 rounded dark:bg-slate-700 dark:border-slate-600"
              />
              <span className="text-slate-700 dark:text-slate-300">Show budget alerts</span>
            </label>

            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={prefForm.show_net_worth_by_country}
                onChange={(e) => setPrefForm({ ...prefForm, show_net_worth_by_country: e.target.checked })}
                className="w-4 h-4 rounded dark:bg-slate-700 dark:border-slate-600"
              />
              <span className="text-slate-700 dark:text-slate-300">Show Net Worth by Country on Dashboard</span>
            </label>

            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={prefForm.show_member_spending}
                onChange={(e) => setPrefForm({ ...prefForm, show_member_spending: e.target.checked })}
                className="w-4 h-4 rounded dark:bg-slate-700 dark:border-slate-600"
              />
              <span className="text-slate-700 dark:text-slate-300">Show Member Spending on Dashboard</span>
            </label>
          </div>

          <button
            type="submit"
            className="mt-4 px-6 py-2 bg-indigo-600 dark:bg-indigo-700 text-white rounded-lg hover:bg-indigo-700 dark:hover:bg-indigo-600 transition-colors font-medium"
          >
            Save Preferences
          </button>
        </form>
      </div>
    </div>
  );
};

export default FamilySettings;
