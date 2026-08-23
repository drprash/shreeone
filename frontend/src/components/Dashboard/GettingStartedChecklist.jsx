import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { CheckCircle2, Circle, ChevronRight, X } from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import { goalsAPI } from '../../services/goalsAPI';
import api from '../../services/api';
import { OPEN_QUICK_ADD_EVENT } from '../Transactions/FloatingAddTransactionButton';

/**
 * Admin-only "Getting started" checklist. Progress is derived from live data
 * (accounts, transactions, members, goals) — there is no step state to keep
 * in sync. The card hides itself once every item is done, or when dismissed
 * (persisted server-side via /auth/checklist-dismiss).
 */
const GettingStartedChecklist = ({ accounts, dashboardData, familyMembers }) => {
  const navigate = useNavigate();
  const { user, updateUser } = useAuthStore();
  const isAdmin = user?.role === 'ADMIN';
  const dismissed = user?.setup_checklist_dismissed === true;

  const { data: goals, isSuccess: goalsLoaded } = useQuery({
    queryKey: ['goals', 'checklist-count'],
    queryFn: () => goalsAPI.list(false),
    enabled: isAdmin && !dismissed,
    staleTime: 60 * 1000,
  });

  if (!isAdmin || dismissed) return null;
  // Wait until every source has loaded so items don't flash unchecked
  if (!accounts || !dashboardData || !familyMembers || !goalsLoaded) return null;

  const hasAccount = accounts.length > 0;
  const items = [
    {
      label: 'Add your first account',
      hint: 'Bank, credit card, cash or investment',
      done: hasAccount,
      action: () => navigate('/accounts', { state: { openCreate: true } }),
    },
    {
      label: 'Log your first transaction',
      hint: hasAccount ? 'Use the floating + button' : 'Add an account first',
      done: (dashboardData.recent_transactions?.length ?? 0) > 0,
      disabled: !hasAccount,
      action: () => window.dispatchEvent(new Event(OPEN_QUICK_ADD_EVENT)),
    },
    {
      label: 'Invite a family member',
      hint: 'Share an activation link from Settings',
      done: familyMembers.length > 1,
      action: () => navigate('/settings?tab=members'),
    },
    {
      label: 'Set a savings goal',
      hint: 'A vacation fund, emergency buffer, or down-payment',
      done: goals.length > 0,
      action: () => navigate('/goals'),
    },
  ];

  const doneCount = items.filter((i) => i.done).length;
  if (doneCount === items.length) return null;

  const handleDismiss = () => {
    updateUser({ setup_checklist_dismissed: true });
    api.post('/auth/checklist-dismiss').catch(() => {});
  };

  return (
    <div className="relative bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700 p-5 sm:p-6 mb-6">
      <button
        type="button"
        onClick={handleDismiss}
        aria-label="Dismiss getting started checklist"
        className="absolute top-4 right-4 p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
      >
        <X className="w-4 h-4" />
      </button>

      <div className="flex items-center gap-3 mb-1 pr-10">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-slate-100">
          Getting started
        </h2>
        <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
          {doneCount} of {items.length}
        </span>
      </div>
      <div className="h-1.5 rounded-full bg-slate-100 dark:bg-slate-700 mb-4 overflow-hidden">
        <div
          className="h-full rounded-full bg-blue-600 dark:bg-blue-400 transition-all duration-300"
          style={{ width: `${(doneCount / items.length) * 100}%` }}
        />
      </div>

      <ul className="space-y-1">
        {items.map((item) => (
          <li key={item.label}>
            {item.done ? (
              <div className="flex items-center gap-3 px-2 py-2">
                <CheckCircle2 className="w-5 h-5 text-green-500 shrink-0" />
                <span className="text-sm text-slate-400 dark:text-slate-500 line-through">
                  {item.label}
                </span>
              </div>
            ) : (
              <button
                type="button"
                onClick={item.action}
                disabled={item.disabled}
                className="w-full flex items-center gap-3 px-2 py-2 rounded-lg text-left hover:bg-slate-50 dark:hover:bg-slate-700/60 disabled:opacity-50 disabled:cursor-not-allowed transition-colors group"
              >
                <Circle className="w-5 h-5 text-slate-300 dark:text-slate-600 shrink-0" />
                <span className="flex-1 min-w-0">
                  <span className="block text-sm font-medium text-gray-800 dark:text-slate-200">
                    {item.label}
                  </span>
                  <span className="block text-xs text-slate-500 dark:text-slate-400">
                    {item.hint}
                  </span>
                </span>
                <ChevronRight className="w-4 h-4 text-slate-300 dark:text-slate-600 group-hover:text-blue-500 shrink-0" />
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
};

export default GettingStartedChecklist;
