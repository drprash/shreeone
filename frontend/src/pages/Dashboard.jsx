import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../services/api';
import SummaryCards from '../components/Dashboard/SummaryCards';
import RecentTransactions from '../components/Dashboard/RecentTransactions';
import QuickAdd from '../components/Transactions/QuickAdd';
import { useAuthStore } from '../store/authStore';
import { queryKeys } from '../utils/queryKeys';
import LoadingSpinner from '../components/LoadingSpinner';

const CategoryChart = React.lazy(() => import('../components/Dashboard/CategoryChart'));
const MemberSpending = React.lazy(() => import('../components/Dashboard/MemberSpending'));
const PrivacyIndicator = React.lazy(() => import('../components/Dashboard/PrivacyIndicator'));
const CountryBreakdownWidget = React.lazy(() => import('../components/Dashboard/CountryBreakdownWidget'));
const NarrativeBanner = React.lazy(() => import('../components/AI/NarrativeBanner'));
const NetWorthChart = React.lazy(() => import('../components/Dashboard/NetWorthChart'));

const Dashboard = () => {
  const { user } = useAuthStore();
  const isAdmin = user?.role === 'ADMIN';
  const [selectedMemberId, setSelectedMemberId] = useState('family');

  // Fetch family settings to get privacy level
  const { data: familySettings } = useQuery({
    queryKey: queryKeys.familySettings(),
    queryFn: () => api.get('/settings/family-profile').then(res => res.data),
    staleTime: 1000 * 60 * 5  // 5 minutes
  });

  // Fetch preferences for dashboard widget visibility
  const { data: preferences } = useQuery({
    queryKey: ['settings', 'preferences'],
    queryFn: () => api.get('/settings/preferences').then(res => res.data),
    staleTime: 1000 * 60 * 5
  });

  const { data: dashboardData, isLoading: dashboardLoading } = useQuery({
    queryKey: queryKeys.dashboard(user?.id),
    queryFn: () => api.get('/dashboard/').then(res => res.data),
    staleTime: 60 * 1000
  });

  const { data: accounts } = useQuery({
    queryKey: queryKeys.accounts(),
    queryFn: () => api.get('/accounts/').then(res => res.data)
  });

  const { data: categories } = useQuery({
    queryKey: queryKeys.categories(),
    queryFn: () => api.get('/categories/').then(res => res.data)
  });

  // Admin-only: fetch all family members for the filter dropdown (complete list regardless of activity)
  const { data: familyMembers } = useQuery({
    queryKey: ['admin-users'],
    queryFn: () => api.get('/admin/users').then(res => res.data),
    enabled: isAdmin,
    staleTime: 1000 * 60 * 5
  });

  // Admin-only: fetch per-member summary when a specific member is selected
  const { data: memberSummary, isLoading: memberSummaryLoading } = useQuery({
    queryKey: queryKeys.dashboardMember(selectedMemberId),
    queryFn: () => api.get(`/dashboard/member/${selectedMemberId}`).then(res => res.data),
    enabled: isAdmin && selectedMemberId !== 'family',
    staleTime: 60 * 1000
  });

  if (dashboardLoading) {
    return <LoadingSpinner className="h-screen" />;
  }

  const privacyLevel = familySettings?.privacy_level || 'FAMILY';
  const summaryData = selectedMemberId === 'family' ? dashboardData?.summary : memberSummary;
  const memberList = familyMembers ?? [];
  const showNetWorthByCountry = preferences?.show_net_worth_by_country ?? true;
  const showMemberSpending = preferences?.show_member_spending ?? true;

  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-6 md:mb-8">
        <h1 className="text-2xl md:text-3xl font-bold text-gray-900 dark:text-slate-100">
          Welcome back, {user?.first_name}
        </h1>
        <p className="text-sm md:text-base text-gray-600 dark:text-slate-400 mt-1">
          Here's your family's financial overview
        </p>
      </div>

      {/* Show privacy level indicator for non-admin members */}
      {user?.role !== 'ADMIN' && (
        <React.Suspense fallback={<div className="h-[74px] mb-6" />}>
          <PrivacyIndicator privacyLevel={privacyLevel} userRole={user?.role} />
        </React.Suspense>
      )}

      <React.Suspense fallback={null}>
        <NarrativeBanner />
      </React.Suspense>

      <QuickAdd accounts={accounts} categories={categories} baseCurrency={dashboardData?.summary?.base_currency} />

      {/* Admin-only summary filter */}
      {isAdmin && memberList.length > 0 && (
        <div className="flex items-center gap-3 mb-4">
          <label className="text-sm text-gray-500 dark:text-slate-400 whitespace-nowrap">View summary for</label>
          <select
            value={selectedMemberId}
            onChange={e => setSelectedMemberId(e.target.value)}
            className="text-sm border border-gray-200 dark:border-slate-600 rounded-lg px-3 py-1.5 bg-white dark:bg-slate-800 text-gray-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="family">Family</option>
            {memberList.map(m => (
              <option key={m.id} value={m.id}>{m.first_name} {m.last_name}</option>
            ))}
          </select>
          {memberSummaryLoading && (
            <span className="text-xs text-gray-400 dark:text-slate-500">Loading…</span>
          )}
        </div>
      )}

      {summaryData && (
        <SummaryCards data={summaryData} />
      )}

      <div className={`grid grid-cols-1 ${showMemberSpending ? 'lg:grid-cols-2' : ''} gap-6 mb-6`}>
        {dashboardData?.category_breakdown && (
          <React.Suspense fallback={<div className="bg-white rounded-xl shadow-sm p-4 sm:p-6 border border-gray-100 dark:bg-slate-800 dark:border-slate-700 h-[348px]" />}>
            <CategoryChart
              data={dashboardData.category_breakdown}
              baseCurrency={dashboardData?.summary?.base_currency}
            />
          </React.Suspense>
        )}
        {showMemberSpending && dashboardData?.member_spending && privacyLevel !== 'PRIVATE' && (
          <React.Suspense fallback={<div className="bg-white rounded-xl shadow-sm p-4 sm:p-6 border border-gray-100 dark:bg-slate-800 dark:border-slate-700 h-[348px]" />}>
            <MemberSpending
              data={dashboardData.member_spending}
              baseCurrency={dashboardData?.summary?.base_currency}
            />
          </React.Suspense>
        )}
      </div>

      {/* Country & Currency Breakdown */}
      {showNetWorthByCountry && (
        <div className="mb-6">
          <React.Suspense fallback={<div className="h-32" />}>
            <CountryBreakdownWidget />
          </React.Suspense>
        </div>
      )}

      {/* Net Worth Timeline — Phase 4 */}
      <div className="mb-6">
        <React.Suspense fallback={<div className="h-48 bg-white dark:bg-slate-800 rounded-xl animate-pulse" />}>
          <NetWorthChart baseCurrency={dashboardData?.summary?.base_currency} />
        </React.Suspense>
      </div>

      {dashboardData?.recent_transactions && (
        <RecentTransactions transactions={dashboardData.recent_transactions} />
      )}
    </div>
  );
};

export default Dashboard;
