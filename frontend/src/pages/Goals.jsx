import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Target, Plus, Trash2, TrendingUp, PlusCircle,
  ChevronDown, ChevronUp, Clock, Wallet, ShoppingBag,
  CreditCard, BarChart2, X, Edit,
} from 'lucide-react';
import { goalsAPI } from '../services/goalsAPI';
import api from '../services/api';
import toast from 'react-hot-toast';

const GOAL_TYPES = [
  { value: 'SAVINGS_TARGET',      label: 'Savings Target',      icon: Wallet,      bg: 'bg-blue-100 dark:bg-blue-900/40',   color: 'text-blue-600 dark:text-blue-400' },
  { value: 'PURCHASE',            label: 'Purchase / Big Buy',  icon: ShoppingBag, bg: 'bg-purple-100 dark:bg-purple-900/40', color: 'text-purple-600 dark:text-purple-400' },
  { value: 'DEBT_PAYOFF',         label: 'Debt Payoff',         icon: CreditCard,  bg: 'bg-red-100 dark:bg-red-900/40',     color: 'text-red-600 dark:text-red-400' },
  { value: 'NET_WORTH_MILESTONE', label: 'Net Worth Milestone', icon: BarChart2,   bg: 'bg-green-100 dark:bg-green-900/40', color: 'text-green-600 dark:text-green-400' },
  { value: 'REMITTANCE',          label: 'Remittance Fund',     icon: Target,      bg: 'bg-orange-100 dark:bg-orange-900/40', color: 'text-orange-600 dark:text-orange-400' },
];

function getGoalMeta(type) {
  return GOAL_TYPES.find(t => t.value === type) ?? GOAL_TYPES[0];
}

/** Parse YYYY-MM-DD without timezone shift. */
function parseLocalDate(str) {
  if (!str) return null;
  const [y, m, d] = str.split('-').map(Number);
  return new Date(y, m - 1, d);
}

function formatLocalDate(str) {
  const d = parseLocalDate(str);
  if (!d) return '';
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

function isDatePast(dateStr) {
  if (!dateStr) return false;
  const target = parseLocalDate(dateStr);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return target < today;
}

function ContributeForm({ goalId, currency, onDone }) {
  const qc = useQueryClient();
  const [amount, setAmount] = useState('');
  const [note, setNote] = useState('');
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);

  const mutation = useMutation({
    mutationFn: (data) => goalsAPI.contribute(goalId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['goal-progress', goalId] });
      qc.invalidateQueries({ queryKey: ['goals'] });
      toast.success('Contribution added');
      onDone();
    },
    onError: () => toast.error('Failed to add contribution'),
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!amount || parseFloat(amount) <= 0) return;
    mutation.mutate({ amount: parseFloat(amount), note: note || null, contributed_at: date });
  };

  return (
    <form onSubmit={handleSubmit} className="mt-4 pt-4 border-t border-gray-100 dark:border-slate-700">
      <p className="text-xs font-semibold text-gray-500 dark:text-slate-400 mb-2 uppercase tracking-wide">Add Contribution</p>
      <div className="flex gap-2 items-end">
        <div className="flex-1">
          <label className="block text-xs text-gray-500 dark:text-slate-400 mb-1">Amount ({currency})</label>
          <input
            required
            type="number"
            min="0.01"
            step="0.01"
            value={amount}
            onChange={e => setAmount(e.target.value)}
            className="w-full border dark:border-slate-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-slate-700 text-gray-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500"
            placeholder="0.00"
            autoFocus
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 dark:text-slate-400 mb-1">Date</label>
          <input
            type="date"
            value={date}
            onChange={e => setDate(e.target.value)}
            className="border dark:border-slate-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-slate-700 text-gray-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>
      <input
        type="text"
        value={note}
        onChange={e => setNote(e.target.value)}
        placeholder="Note (optional)"
        className="mt-2 w-full border dark:border-slate-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-slate-700 text-gray-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500"
      />
      <div className="flex gap-2 mt-3">
        <button
          type="submit"
          disabled={mutation.isPending}
          className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg py-2 text-sm font-medium"
        >
          {mutation.isPending ? 'Saving…' : 'Save Contribution'}
        </button>
        <button
          type="button"
          onClick={onDone}
          className="px-4 border dark:border-slate-600 rounded-lg py-2 text-sm text-gray-600 dark:text-slate-300 hover:bg-gray-50 dark:hover:bg-slate-700"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

function ContributionHistory({ goalId, currency }) {
  const { data: contributions = [], isLoading } = useQuery({
    queryKey: ['goal-contributions', goalId],
    queryFn: () => goalsAPI.contributions(goalId),
  });

  if (isLoading) return <p className="text-xs text-gray-400 mt-3">Loading history…</p>;
  if (!contributions.length) return (
    <p className="text-xs text-gray-400 dark:text-slate-500 mt-3 italic">No contributions recorded yet.</p>
  );

  return (
    <ul className="mt-3 space-y-1.5">
      {contributions.slice(0, 5).map(c => (
        <li key={c.id} className="flex items-center justify-between text-xs text-gray-600 dark:text-slate-400 bg-gray-50 dark:bg-slate-700/50 rounded px-2 py-1.5">
          <span className="flex items-center gap-1.5">
            <Clock className="w-3 h-3 opacity-50" />
            {formatLocalDate(c.contributed_at)}
            {c.note && <span className="italic text-gray-400 dark:text-slate-500">— {c.note}</span>}
          </span>
          <span className="font-semibold text-green-600 dark:text-green-400">
            +{Number(c.amount).toLocaleString(undefined, { maximumFractionDigits: 2 })} {currency}
          </span>
        </li>
      ))}
    </ul>
  );
}

function GoalCard({ goal, onArchive, onEdit }) {
  const [showContribute, setShowContribute] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  const { data: progress, isLoading } = useQuery({
    queryKey: ['goal-progress', goal.id],
    queryFn: () => goalsAPI.progress(goal.id),
  });

  const meta = getGoalMeta(goal.type);
  const Icon = meta.icon;
  const pct = progress?.percent ?? 0;
  const monthsLeft = progress?.months_remaining;
  const daysLeft = progress?.days_remaining;
  const monthlyNeeded = progress?.monthly_needed;
  const currentAmount = progress?.current_amount ?? goal.current_amount ?? 0;
  const isLinked = !!goal.linked_account_id;
  const datePast = isDatePast(goal.target_date);
  const done = pct >= 100;

  return (
    <div className="card-hover bg-white dark:bg-slate-800 rounded-lg shadow p-4 sm:p-6 border border-gray-100 dark:border-slate-700">
      {/* Header row */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className={`p-2 sm:p-3 rounded-lg flex-shrink-0 ${meta.bg}`}>
            <Icon className={`w-5 h-5 ${meta.color}`} />
          </div>
          <div className="min-w-0">
            <h3 className="font-semibold text-gray-900 dark:text-slate-100 truncate">{goal.name}</h3>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-xs text-gray-500 dark:text-slate-400">{meta.label}</span>
              {isLinked && (
                <span className="text-xs bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 px-1.5 py-0.5 rounded">auto-tracked</span>
              )}
              {done && (
                <span className="text-xs bg-green-50 dark:bg-green-900/30 text-green-600 dark:text-green-400 px-1.5 py-0.5 rounded font-medium">Reached!</span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          <button
            onClick={() => onEdit(goal)}
            className="p-1 text-gray-400 hover:text-blue-600 dark:hover:text-blue-400"
            title="Edit goal"
          >
            <Edit className="w-4 h-4" />
          </button>
          <button
            onClick={() => {
              if (window.confirm('Archive this goal?')) onArchive(goal.id);
            }}
            className="p-1 text-gray-400 hover:text-red-600 dark:hover:text-red-400"
            title="Archive goal"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Progress bar */}
      <div className="mt-4">
        <div className="flex justify-between items-baseline mb-1">
          <span className="text-xs text-gray-500 dark:text-slate-400">
            {isLoading ? '…' : (
              <>
                {Number(currentAmount).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                {' / '}
                {Number(goal.target_amount).toLocaleString(undefined, { maximumFractionDigits: 0 })} {goal.currency}
              </>
            )}
          </span>
          <span className={`text-sm font-bold ${done ? 'text-green-600 dark:text-green-400' : 'text-blue-600 dark:text-blue-400'}`}>
            {pct.toFixed(1)}%
          </span>
        </div>
        <div className="w-full bg-gray-200 dark:bg-slate-700 rounded-full h-2">
          <div
            className={`h-2 rounded-full transition-all ${done ? 'bg-green-500' : 'bg-blue-500'}`}
            style={{ width: `${Math.min(pct, 100)}%` }}
          />
        </div>
      </div>

      {/* Date & hints */}
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1">
        {goal.target_date && (
          <span className={`text-xs ${datePast && !done ? 'text-red-500 dark:text-red-400 font-medium' : 'text-gray-500 dark:text-slate-400'}`}>
            {datePast && !done ? 'Deadline passed · ' : 'By '}
            {formatLocalDate(goal.target_date)}
          </span>
        )}
        {!datePast && !done && monthsLeft != null && monthsLeft > 0 && monthlyNeeded && (
          <span className="text-xs text-green-600 dark:text-green-400 flex items-center gap-1">
            <TrendingUp className="w-3 h-3" />
            {Number(monthlyNeeded).toLocaleString(undefined, { maximumFractionDigits: 0 })} {goal.currency}/mo for {monthsLeft} mo
          </span>
        )}
        {!datePast && !done && daysLeft != null && daysLeft >= 0 && daysLeft < 30 && (
          <span className="text-xs text-amber-600 dark:text-amber-400">
            {daysLeft === 0 ? 'Due today' : `${daysLeft} day${daysLeft !== 1 ? 's' : ''} left`}
          </span>
        )}
      </div>

      {/* Notes */}
      {goal.notes && (
        <p className="mt-2 text-xs text-gray-400 dark:text-slate-500 italic">{goal.notes}</p>
      )}

      {/* Contribution actions */}
      {!isLinked && !done && (
        <div className="mt-4 pt-3 border-t border-gray-100 dark:border-slate-700 flex items-center gap-4">
          <button
            onClick={() => { setShowContribute(v => !v); setShowHistory(false); }}
            className="flex items-center gap-1.5 text-sm text-blue-600 dark:text-blue-400 hover:text-blue-700"
          >
            <PlusCircle className="w-4 h-4" />
            Add Contribution
          </button>
          <button
            onClick={() => { setShowHistory(v => !v); setShowContribute(false); }}
            className="flex items-center gap-1.5 text-sm text-gray-500 dark:text-slate-400 hover:text-gray-700"
          >
            {showHistory ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            History
          </button>
        </div>
      )}

      {showContribute && (
        <ContributeForm
          goalId={goal.id}
          currency={goal.currency}
          onDone={() => setShowContribute(false)}
        />
      )}
      {showHistory && <ContributionHistory goalId={goal.id} currency={goal.currency} />}
    </div>
  );
}

function GoalModal({ editing, onClose, onSave }) {
  const { data: familyProfile } = useQuery({
    queryKey: ['settings', 'family-profile'],
    queryFn: () => api.get('/settings/family-profile').then(r => r.data),
    staleTime: 1000 * 60 * 5,
  });
  const { data: secondaryCurrencies = [] } = useQuery({
    queryKey: ['settings', 'currencies'],
    queryFn: () => api.get('/settings/currencies').then(r => r.data),
    staleTime: 1000 * 60 * 5,
  });
  const { data: accounts = [] } = useQuery({
    queryKey: ['accounts'],
    queryFn: () => api.get('/accounts/').then(r => r.data),
    staleTime: 1000 * 60 * 5,
  });

  const baseCurrency = familyProfile?.base_currency ?? 'USD';
  const currencyOptions = [
    baseCurrency,
    ...secondaryCurrencies.map(c => c.currency_code).filter(c => c !== baseCurrency),
  ];

  const [form, setForm] = useState({
    name:               editing?.name ?? '',
    type:               editing?.type ?? 'SAVINGS_TARGET',
    target_amount:      editing?.target_amount ?? '',
    currency:           editing?.currency ?? '',
    target_date:        editing?.target_date ?? '',
    linked_account_id:  editing?.linked_account_id ?? '',
    notes:              editing?.notes ?? '',
  });

  const effectiveCurrency = form.currency || baseCurrency;

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave({
      ...form,
      currency:           effectiveCurrency,
      target_amount:      parseFloat(form.target_amount),
      target_date:        form.target_date || null,
      linked_account_id:  form.linked_account_id || null,
      notes:              form.notes || null,
    });
  };

  return (
    <div className="modal-backdrop fixed inset-0 flex items-start sm:items-center justify-center z-50 p-3 sm:p-4 overflow-y-auto">
      <div className="glass-panel bg-white dark:bg-slate-800 rounded-lg shadow-xl w-full max-w-md mx-3 sm:mx-4 p-4 sm:p-6 max-h-[92vh] overflow-y-auto slide-in">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-slate-100">
            {editing ? 'Edit Goal' : 'New Goal'}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-slate-200">
            <X className="w-6 h-6" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">Name *</label>
            <input
              required
              value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              className="w-full px-3 py-2 border dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-blue-500 bg-white dark:bg-slate-700 text-gray-900 dark:text-slate-100"
              placeholder="e.g. Emergency Fund"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">Type *</label>
            <select
              value={form.type}
              onChange={e => setForm(f => ({ ...f, type: e.target.value }))}
              className="w-full px-3 py-2 border dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-blue-500 bg-white dark:bg-slate-700 text-gray-900 dark:text-slate-100"
            >
              {GOAL_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">Target Amount *</label>
              <input
                required
                type="number"
                min="0.01"
                step="0.01"
                value={form.target_amount}
                onChange={e => setForm(f => ({ ...f, target_amount: e.target.value }))}
                className="w-full px-3 py-2 border dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-blue-500 bg-white dark:bg-slate-700 text-gray-900 dark:text-slate-100"
                placeholder="0.00"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">Currency *</label>
              <select
                value={effectiveCurrency}
                onChange={e => setForm(f => ({ ...f, currency: e.target.value }))}
                className="w-full px-3 py-2 border dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-blue-500 bg-white dark:bg-slate-700 text-gray-900 dark:text-slate-100"
              >
                {currencyOptions.map(c => (
                  <option key={c} value={c}>{c}{c === baseCurrency ? ' (primary)' : ''}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">
              Target Date <span className="text-gray-400 font-normal">(optional)</span>
            </label>
            <input
              type="date"
              value={form.target_date}
              onChange={e => setForm(f => ({ ...f, target_date: e.target.value }))}
              className="w-full px-3 py-2 border dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-blue-500 bg-white dark:bg-slate-700 text-gray-900 dark:text-slate-100"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">
              Link to Account <span className="text-gray-400 font-normal">(optional)</span>
            </label>
            <select
              value={form.linked_account_id}
              onChange={e => setForm(f => ({ ...f, linked_account_id: e.target.value }))}
              className="w-full px-3 py-2 border dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-blue-500 bg-white dark:bg-slate-700 text-gray-900 dark:text-slate-100"
            >
              <option value="">None — track manually</option>
              {accounts.map(a => (
                <option key={a.id} value={a.id}>{a.name} ({a.currency})</option>
              ))}
            </select>
            {form.linked_account_id && (
              <p className="mt-1 text-xs text-blue-600 dark:text-blue-400">
                Progress will be auto-tracked from the account's live balance.
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">
              Notes <span className="text-gray-400 font-normal">(optional)</span>
            </label>
            <textarea
              value={form.notes}
              onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
              rows={2}
              className="w-full px-3 py-2 border dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-blue-500 bg-white dark:bg-slate-700 text-gray-900 dark:text-slate-100"
            />
          </div>

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2.5 border dark:border-slate-600 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-700 text-gray-700 dark:text-slate-300"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex-1 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium"
            >
              {editing ? 'Save Changes' : 'Create Goal'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function Goals() {
  const qc = useQueryClient();
  const [showModal, setShowModal]     = useState(false);
  const [editingGoal, setEditingGoal] = useState(null);

  const { data: goals = [], isLoading } = useQuery({
    queryKey: ['goals'],
    queryFn: () => goalsAPI.list(),
  });

  const createMutation = useMutation({
    mutationFn: goalsAPI.create,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['goals'] });
      setShowModal(false);
      toast.success('Goal created');
    },
    onError: () => toast.error('Failed to create goal'),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => goalsAPI.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['goals'] });
      setShowModal(false);
      setEditingGoal(null);
      toast.success('Goal updated');
    },
    onError: () => toast.error('Failed to update goal'),
  });

  const archiveMutation = useMutation({
    mutationFn: goalsAPI.archive,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['goals'] });
      toast.success('Goal archived');
    },
    onError: () => toast.error('Failed to archive goal'),
  });

  const handleSave = (data) => {
    if (editingGoal) {
      updateMutation.mutate({ id: editingGoal.id, data });
    } else {
      createMutation.mutate(data);
    }
  };

  const openEdit = (goal) => {
    setEditingGoal(goal);
    setShowModal(true);
  };

  const openCreate = () => {
    setEditingGoal(null);
    setShowModal(true);
  };

  return (
    <div className="max-w-7xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3 mb-6">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-gray-900 dark:text-slate-100">Financial Goals</h1>
          <p className="text-gray-600 dark:text-slate-400 mt-1">Track savings targets, purchases, and milestones</p>
        </div>
        <button
          onClick={openCreate}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2.5 rounded-lg flex items-center gap-2 self-start sm:self-auto"
        >
          <Plus className="w-5 h-5" />
          New Goal
        </button>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
        </div>
      ) : goals.length === 0 ? (
        <div className="text-center py-16 bg-white dark:bg-slate-800 rounded-lg shadow border border-gray-100 dark:border-slate-700">
          <Target className="w-12 h-12 mx-auto mb-3 text-gray-300 dark:text-slate-600" />
          <p className="text-lg font-medium text-gray-900 dark:text-slate-100">No goals yet</p>
          <p className="text-sm text-gray-500 dark:text-slate-400 mt-1">Create your first financial goal to start tracking progress.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {goals.map(goal => (
            <GoalCard
              key={goal.id}
              goal={goal}
              onArchive={id => archiveMutation.mutate(id)}
              onEdit={openEdit}
            />
          ))}
        </div>
      )}

      {showModal && (
        <GoalModal
          editing={editingGoal}
          onClose={() => { setShowModal(false); setEditingGoal(null); }}
          onSave={handleSave}
        />
      )}
    </div>
  );
}
