import { useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import api from '../services/api';
import { addPendingOp } from '../lib/offlineDb';
import { useOfflineQueue } from '../context/OfflineQueueContext';
import { queryKeys } from '../utils/queryKeys';

function invalidateAccounts(queryClient) {
  queryClient.invalidateQueries({ queryKey: queryKeys.accounts() });
  queryClient.invalidateQueries({ queryKey: queryKeys.dashboardAll() });
}

export function useCreateAccount({ onSuccess } = {}) {
  const { isOnline } = useOfflineQueue();
  const queryClient = useQueryClient();

  const saveOffline = async (data) => {
    const tempAccount = {
      id: 'temp_' + crypto.randomUUID(),
      ...data,
      opening_balance: parseFloat(data.opening_balance) || 0,
      current_balance: parseFloat(data.opening_balance) || 0,
      sort_order: 9999,
    };
    queryClient.setQueriesData(
      { queryKey: queryKeys.accounts() },
      (old) => Array.isArray(old) ? [...old, tempAccount] : [tempAccount]
    );
    const op = {
      id: crypto.randomUUID(),
      type: 'CREATE_ACCOUNT',
      payload: data,
      createdAt: new Date().toISOString(),
    };
    try {
      await addPendingOp(op);
      window.dispatchEvent(new CustomEvent('offlineQueueUpdated'));
      toast.success("Saved offline — will sync when you're back online");
      onSuccess?.();
    } catch {
      toast.error('Failed to save offline. Please try again.');
    }
  };

  const onlineMutation = useMutation({
    mutationFn: (data) => api.post('/accounts/', data),
    onSuccess: () => {
      toast.success('Account created successfully');
      invalidateAccounts(queryClient);
      onSuccess?.();
    },
    onError: async (error, data) => {
      if (!error.response) { await saveOffline(data); return; }
      toast.error(error.response.data?.detail || 'Failed to create account');
    },
  });

  const mutate = async (data) => {
    if (isOnline) {
      onlineMutation.mutate(data);
      return;
    }
    await saveOffline(data);
  };

  return { mutate, isPending: onlineMutation.isPending };
}

export function useUpdateAccount({ onSuccess } = {}) {
  const { isOnline } = useOfflineQueue();
  const queryClient = useQueryClient();

  const saveOffline = async ({ id, data }) => {
    queryClient.setQueriesData(
      { queryKey: queryKeys.accounts() },
      (old) => Array.isArray(old) ? old.map(a => a.id === id ? { ...a, ...data } : a) : old
    );
    const op = {
      id: crypto.randomUUID(),
      type: 'UPDATE_ACCOUNT',
      payload: { id, ...data },
      createdAt: new Date().toISOString(),
    };
    try {
      await addPendingOp(op);
      window.dispatchEvent(new CustomEvent('offlineQueueUpdated'));
      toast.success("Saved offline — will sync when you're back online");
      onSuccess?.();
    } catch {
      toast.error('Failed to save offline. Please try again.');
    }
  };

  const onlineMutation = useMutation({
    mutationFn: ({ id, data }) => api.put(`/accounts/${id}`, data),
    onSuccess: () => {
      toast.success('Account updated successfully');
      invalidateAccounts(queryClient);
      onSuccess?.();
    },
    onError: async (error, variables) => {
      if (!error.response) { await saveOffline(variables); return; }
      toast.error(error.response.data?.detail || 'Failed to update account');
    },
  });

  const mutate = async ({ id, data }) => {
    if (isOnline) {
      onlineMutation.mutate({ id, data });
      return;
    }
    await saveOffline({ id, data });
  };

  return { mutate, isPending: onlineMutation.isPending };
}

export function useDeleteAccount() {
  const { isOnline } = useOfflineQueue();
  const queryClient = useQueryClient();

  const saveOffline = async (id) => {
    queryClient.setQueriesData(
      { queryKey: queryKeys.accounts() },
      (old) => Array.isArray(old) ? old.filter(a => a.id !== id) : old
    );
    const op = {
      id: crypto.randomUUID(),
      type: 'DELETE_ACCOUNT',
      payload: { id },
      createdAt: new Date().toISOString(),
    };
    try {
      await addPendingOp(op);
      window.dispatchEvent(new CustomEvent('offlineQueueUpdated'));
      toast.success("Deleted offline — will sync when you're back online");
    } catch {
      toast.error('Failed to save offline. Please try again.');
    }
  };

  const onlineMutation = useMutation({
    mutationFn: (id) => api.delete(`/accounts/${id}`),
    onSuccess: () => {
      toast.success('Account deleted');
      invalidateAccounts(queryClient);
    },
    onError: async (error, id) => {
      if (!error.response) { await saveOffline(id); return; }
      toast.error(error.response.data?.detail || 'Failed to delete account');
    },
  });

  const mutate = async (id) => {
    if (isOnline) {
      onlineMutation.mutate(id);
      return;
    }
    await saveOffline(id);
  };

  return { mutate, isPending: onlineMutation.isPending };
}
