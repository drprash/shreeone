import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import MemberManagement from '../components/Settings/MemberManagement';
import BudgetSettings from '../components/Settings/BudgetSettings';
import RecurringPayments from '../components/Settings/RecurringPayments';
import FamilySettings from '../components/Settings/FamilySettings';
import SecuritySettings from '../components/Settings/SecuritySettings';
import CurrencySettings from '../components/Settings/CurrencySettings';
import BackupRestore from '../components/Settings/BackupRestore';
import { useAuthStore } from '../store/authStore';
import settingsAPI from '../services/settingsAPI';

const Settings = () => {
  const [activeTab, setActiveTab] = useState('family');
  const user = useAuthStore((state) => state.user);
  const isAdmin = user?.role === 'ADMIN';

  const { data: familyProfile } = useQuery({
    queryKey: ['settings', 'family-profile'],
    queryFn: () => settingsAPI.getFamilyProfile().then(r => r.data),
  });

  const tabs = [
    { id: 'family', label: 'Family Settings', icon: '⚙️' },
    ...(isAdmin ? [{ id: 'members', label: 'Member Management', icon: '👥' }] : []),
    ...(isAdmin ? [{ id: 'backup', label: 'Backup & Restore', icon: '💾' }] : []),
    { id: 'currencies', label: 'Currencies', icon: '💱' },
    { id: 'budget', label: 'Budget & Alerts', icon: '💰' },
    { id: 'recurring', label: 'Recurring Payments', icon: '🔄' },
    { id: 'security', label: 'Security', icon: '🔐' },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 py-8">
        <div className="max-w-6xl mx-auto px-4">
          {/* Header */}
          <div className="mb-8">
            <h1 className="text-4xl font-bold text-slate-900 dark:text-slate-100 mb-2">Settings</h1>
            <p className="text-slate-600 dark:text-slate-400">Manage your family finances and preferences</p>
          </div>

          {/* Tabs Navigation */}
          <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700 mb-6">
            <div className="flex flex-wrap gap-4 p-4">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`px-4 py-2 rounded-lg font-medium transition-all flex items-center gap-2 ${
                    activeTab === tab.id
                      ? 'bg-indigo-100 dark:bg-indigo-900 text-indigo-700 dark:text-indigo-300 border border-indigo-300 dark:border-indigo-700'
                      : 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-600 border border-transparent'
                  }`}
                >
                  <span>{tab.icon}</span>
                  <span>{tab.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Content Area */}
          <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700 p-6">
            {activeTab === 'family' && <FamilySettings />}
            {activeTab === 'members' && isAdmin && <MemberManagement />}
            {activeTab === 'currencies' && (
              <CurrencySettings user={user} familyProfile={familyProfile} />
            )}
            {activeTab === 'budget' && <BudgetSettings />}
            {activeTab === 'recurring' && <RecurringPayments />}
            {activeTab === 'security' && <SecuritySettings />}
            {activeTab === 'backup' && isAdmin && <BackupRestore />}
          </div>
        </div>
      </div>
  );
};

export default Settings;
