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
import { getAIStatus } from '../../services/aiAPI';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { queryKeys } from '../../utils/queryKeys';

const AI_PROVIDERS = [
  { id: 'local',     label: 'Local (Ollama)',         model: 'gemma4:e4b' },
  { id: 'openai',    label: 'OpenAI (GPT-4o-mini)',   model: 'gpt-4o-mini' },
  { id: 'anthropic', label: 'Anthropic (Claude Haiku)', model: 'claude-haiku-4-5-20251001' },
  { id: 'google',    label: 'Google (Gemini Flash)',  model: 'gemini-2.0-flash' },
];

const FamilySettings = () => {
  const user = useAuthStore((state) => state.user);
  const isAdmin = user?.role === 'ADMIN';
  const queryClient = useQueryClient();

  const [familyProfile, setFamilyProfile] = useState(null);
  const [preferences, setPreferences] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);
  const [aiStatus, setAiStatus] = useState(null);

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
    ai_categorization_enabled: false,
    ai_monthly_narrative_enabled: false,
    ai_weekly_digest_enabled: false,
    ai_receipt_ocr_enabled: false,
    ai_voice_entry_enabled: false,
    ai_statement_upload_enabled: false,
    ai_provider: null,
    ai_model_override: '',
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [profileRes, prefRes, aiStatusRes] = await Promise.all([
        settingsAPI.getFamilyProfile(),
        settingsAPI.getPreferences(),
        getAIStatus().then(data => ({ data })).catch(() => ({ data: null })),
      ]);
      if (aiStatusRes.data) setAiStatus(aiStatusRes.data);

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

          <div className="mt-6">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100 mb-1">AI Features</h3>
            {!aiStatus?.ai_service_available ? (
              <div className="mt-2 p-4 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-500 dark:text-slate-400 text-sm">
                AI service is not running. Start the AI Docker service (<code className="font-mono bg-slate-100 dark:bg-slate-700 px-1 rounded">docker compose -f docker-compose.ai.yml up -d</code>) to enable AI features.
              </div>
            ) : (
              <>
                <p className="text-sm text-slate-500 dark:text-slate-400 mb-3">
                  Enable or disable individual AI-powered features.
                </p>
                <div className="space-y-3">
                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={prefForm.ai_categorization_enabled}
                      onChange={(e) => setPrefForm({ ...prefForm, ai_categorization_enabled: e.target.checked })}
                      className="w-4 h-4 rounded dark:bg-slate-700 dark:border-slate-600"
                    />
                    <div>
                      <span className="text-slate-700 dark:text-slate-300 font-medium">Auto-categorisation</span>
                      <p className="text-xs text-slate-500 dark:text-slate-400">Suggest a category when adding transactions</p>
                    </div>
                  </label>

                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={prefForm.ai_voice_entry_enabled}
                      onChange={(e) => setPrefForm({ ...prefForm, ai_voice_entry_enabled: e.target.checked })}
                      className="w-4 h-4 rounded dark:bg-slate-700 dark:border-slate-600"
                    />
                    <div>
                      <span className="text-slate-700 dark:text-slate-300 font-medium">Voice / Smart Entry</span>
                      <p className="text-xs text-slate-500 dark:text-slate-400">Parse natural language into transaction fields</p>
                    </div>
                  </label>

                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={prefForm.ai_receipt_ocr_enabled}
                      onChange={(e) => setPrefForm({ ...prefForm, ai_receipt_ocr_enabled: e.target.checked })}
                      className="w-4 h-4 rounded dark:bg-slate-700 dark:border-slate-600"
                    />
                    <div>
                      <span className="text-slate-700 dark:text-slate-300 font-medium">Receipt Scan (OCR)</span>
                      <p className="text-xs text-slate-500 dark:text-slate-400">Extract transaction details from receipt photos</p>
                    </div>
                  </label>

                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={prefForm.ai_statement_upload_enabled}
                      onChange={(e) => setPrefForm({ ...prefForm, ai_statement_upload_enabled: e.target.checked })}
                      className="w-4 h-4 rounded dark:bg-slate-700 dark:border-slate-600"
                    />
                    <div>
                      <span className="text-slate-700 dark:text-slate-300 font-medium">Bank Statement Upload</span>
                      <p className="text-xs text-slate-500 dark:text-slate-400">Import transactions from PDF or image statements</p>
                    </div>
                  </label>

                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={prefForm.ai_monthly_narrative_enabled}
                      onChange={(e) => setPrefForm({ ...prefForm, ai_monthly_narrative_enabled: e.target.checked })}
                      className="w-4 h-4 rounded dark:bg-slate-700 dark:border-slate-600"
                    />
                    <div>
                      <span className="text-slate-700 dark:text-slate-300 font-medium">Monthly Finance Summary</span>
                      <p className="text-xs text-slate-500 dark:text-slate-400">Generate a plain-English narrative of monthly spending</p>
                    </div>
                  </label>

                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={prefForm.ai_weekly_digest_enabled}
                      onChange={(e) => setPrefForm({ ...prefForm, ai_weekly_digest_enabled: e.target.checked })}
                      className="w-4 h-4 rounded dark:bg-slate-700 dark:border-slate-600"
                    />
                    <div>
                      <span className="text-slate-700 dark:text-slate-300 font-medium">Weekly Spending Digest</span>
                      <p className="text-xs text-slate-500 dark:text-slate-400">Generate a brief weekly summary on the Dashboard</p>
                    </div>
                  </label>
                </div>
              </>
            )}
          </div>

          {aiStatus?.ai_service_available && (
            <div className="mt-6">
              <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100 mb-1">AI Provider</h3>
              <p className="text-sm text-slate-500 dark:text-slate-400 mb-3">
                Choose which AI service processes your data. API keys are configured by your admin.
              </p>
              <div className="space-y-2">
                {AI_PROVIDERS.map((p) => {
                  const configured = aiStatus.configured_providers?.includes(p.id);
                  return (
                    <label
                      key={p.id}
                      className={`flex items-start gap-3 p-3 rounded-lg border transition-colors ${
                        configured
                          ? 'border-slate-200 dark:border-slate-700 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-700/50'
                          : 'border-slate-100 dark:border-slate-800 opacity-50 cursor-not-allowed'
                      }`}
                      title={!configured ? 'API key not configured — contact your admin' : undefined}
                    >
                      <input
                        type="radio"
                        name="ai_provider"
                        value={p.id}
                        checked={(prefForm.ai_provider ?? aiStatus?.ai_provider ?? 'local') === p.id}
                        onChange={() => configured && setPrefForm({ ...prefForm, ai_provider: p.id })}
                        disabled={!configured}
                        className="mt-0.5 w-4 h-4 dark:bg-slate-700 dark:border-slate-600"
                      />
                      <div>
                        <span className="text-slate-700 dark:text-slate-300 font-medium">{p.label}</span>
                        <p className="text-xs text-slate-500 dark:text-slate-400">
                          Default model: {p.model}
                          {!configured && ' — API key not configured'}
                        </p>
                      </div>
                    </label>
                  );
                })}
              </div>

              <div className="mt-3">
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Model override <span className="text-slate-400 font-normal">(optional — leave blank for provider default)</span>
                </label>
                <input
                  type="text"
                  value={prefForm.ai_model_override || ''}
                  onChange={(e) => setPrefForm({ ...prefForm, ai_model_override: e.target.value || null })}
                  placeholder="e.g. gpt-4o, claude-opus-4-6, gemini-2.0-pro"
                  className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg focus:outline-none focus:border-indigo-500 dark:bg-slate-700 dark:text-slate-100 text-sm"
                />
              </div>
            </div>
          )}

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
