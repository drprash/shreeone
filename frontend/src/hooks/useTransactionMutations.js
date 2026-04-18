import { useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import api from '../services/api';
import { addPendingOp } from '../lib/offlineDb';
import { useOfflineQueue } from '../context/OfflineQueueContext';
import { queryKeys } from '../utils/queryKeys';

function invalidateTx(queryClient) {
  queryClient.invalidateQueries({ queryKey: queryKeys.transactionsAll() });
  queryClient.invalidateQueries({ queryKey: queryKeys.accounts() });
  queryClient.invalidateQueries({ queryKey: queryKeys.dashboardAll() });
}

export function useUpdateTransaction({ onSuccess } = {}) {
  const { isOnline } = useOfflineQueue();
  const queryClient = useQueryClient();

  const saveOffline = async ({ id, data }) => {
    queryClient.setQueriesData(
      { queryKey: queryKeys.transactionsAll() },
      (old) => Array.isArray(old) ? old.map(t => t.id === id ? { ...t, ...data } : t) : old
    );
    const op = {
      id: crypto.randomUUID(),
      type: 'UPDATE_TRANSACTION',
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
    mutationFn: ({ id, data }) => api.put(`/transactions/${id}`, data),
    onSuccess: () => {
      toast.success('Transaction updated');
      invalidateTx(queryClient);
      onSuccess?.();
    },
    onError: async (error, variables) => {
      if (!error.response) {
        await saveOffline(variables);
        return;
      }
      toast.error(error.response.data?.detail || 'Failed to update transaction');
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

export function useDeleteTransaction() {
  const { isOnline } = useOfflineQueue();
  const queryClient = useQueryClient();

  const saveOffline = async (id) => {
    queryClient.setQueriesData(
      { queryKey: queryKeys.transactionsAll() },
      (old) => Array.isArray(old) ? old.filter(t => t.id !== id) : old
    );
    const op = {
      id: crypto.randomUUID(),
      type: 'DELETE_TRANSACTION',
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
    mutationFn: (id) => api.delete(`/transactions/${id}`),
    onSuccess: () => {
      toast.success('Transaction deleted');
      invalidateTx(queryClient);
    },
    onError: async (error, id) => {
      if (!error.response) {
        await saveOffline(id);
        return;
      }
      toast.error(error.response.data?.detail || 'Failed to delete transaction');
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
