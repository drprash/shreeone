import { useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import api from '../services/api';
import { addPendingOp } from '../lib/offlineDb';
import { useOfflineQueue } from '../context/OfflineQueueContext';
import { queryKeys } from '../utils/queryKeys';

/**
 * Offline-aware transaction creation hook.
 * When online  → POST to server immediately.
 * When offline → save to IndexedDB; auto-syncs on reconnect.
 *
 * If navigator.onLine reports true but the network is actually unreachable
 * (common on Android), the POST will fail with a network error and the hook
 * falls back to the IndexedDB offline path automatically.
 *
 * @param {object} options
 * @param {() => void} [options.onSuccess]  Called after successful save (online or offline)
 */
export function useCreateTransaction({ onSuccess } = {}) {
  const { isOnline } = useOfflineQueue();
  const queryClient = useQueryClient();

  const saveOffline = async (payload) => {
    const op = {
      id: crypto.randomUUID(),
      type: 'CREATE_TRANSACTION',
      payload,
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
    mutationFn: (payload) => api.post('/transactions/', payload),
    onSuccess: () => {
      toast.success('Transaction added');
      queryClient.invalidateQueries({ queryKey: queryKeys.transactionsAll() });
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts() });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboardAll() });
      onSuccess?.();
    },
    onError: async (error, payload) => {
      // Network error (no server response) — save to IndexedDB instead
      if (!error.response) {
        await saveOffline(payload);
        return;
      }
      toast.error(error.response.data?.detail || 'Failed to add transaction');
    },
  });

  const mutate = async (payload) => {
    if (isOnline) {
      onlineMutation.mutate(payload);
      return;
    }

    // Fast path: navigator says we're offline
    await saveOffline(payload);
  };

  return {
    mutate,
    isPending: onlineMutation.isPending,
    isOnline,
  };
}
