import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import api from '../services/api';
import { getPendingOps, removePendingOp } from '../lib/offlineDb';
import { useOnlineStatus } from '../hooks/useOnlineStatus';
import { useAuthStore } from '../store/authStore';
import { queryKeys } from '../utils/queryKeys';

const OfflineQueueContext = createContext(null);

export function OfflineQueueProvider({ children }) {
  const [pendingOps, setPendingOps] = useState([]);
  const [isSyncing, setIsSyncing] = useState(false);
  const { isOnline, checkNow } = useOnlineStatus();
  const { isAuthenticated } = useAuthStore();
  const queryClient = useQueryClient();
  const wasOfflineRef = useRef(!isOnline);

  const refresh = useCallback(async () => {
    try {
      const ops = await getPendingOps();
      setPendingOps(ops);
    } catch {
      // IndexedDB unavailable (e.g. private browsing on some browsers) — silent fail
    }
  }, []);

  const syncPending = useCallback(async () => {
    const ops = await getPendingOps();
    if (ops.length === 0) return;

    setIsSyncing(true);
    let synced = 0;
    let failed = 0;
    const syncedTypes = new Set();

    const apiCall = {
      CREATE_TRANSACTION: (op) => api.post('/transactions/', op.payload),
      UPDATE_TRANSACTION: (op) => { const { id, ...data } = op.payload; return api.put(`/transactions/${id}`, data); },
      DELETE_TRANSACTION: (op) => api.delete(`/transactions/${op.payload.id}`),
      CREATE_ACCOUNT:     (op) => api.post('/accounts/', op.payload),
      UPDATE_ACCOUNT:     (op) => { const { id, ...data } = op.payload; return api.put(`/accounts/${id}`, data); },
      DELETE_ACCOUNT:     (op) => api.delete(`/accounts/${op.payload.id}`),
      CREATE_CATEGORY:    (op) => api.post('/categories/', op.payload),
      UPDATE_CATEGORY:    (op) => { const { id, ...data } = op.payload; return api.put(`/categories/${id}`, data); },
      DELETE_CATEGORY:    (op) => api.delete(`/categories/${op.payload.id}`),
    };

    for (const op of ops) {
      const fn = apiCall[op.type];
      if (!fn) { failed++; continue; }
      try {
        await fn(op);
        await removePendingOp(op.id);
        synced++;
        syncedTypes.add(op.type);
      } catch {
        failed++;
      }
    }

    await refresh();
    setIsSyncing(false);

    // Invalidate only the caches affected by the synced op types
    const hasTx = [...syncedTypes].some(t => t.endsWith('_TRANSACTION'));
    const hasAccount = [...syncedTypes].some(t => t.endsWith('_ACCOUNT'));
    const hasCategory = [...syncedTypes].some(t => t.endsWith('_CATEGORY'));

    if (hasTx || hasAccount) {
      queryClient.invalidateQueries({ queryKey: queryKeys.transactionsAll() });
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts() });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboardAll() });
    }
    if (hasCategory) {
      queryClient.invalidateQueries({ queryKey: queryKeys.categories() });
    }

    if (synced > 0) {
      toast.success(`${synced} offline change${synced !== 1 ? 's' : ''} synced`);
    }
    if (failed > 0) {
      toast.error(`${failed} change${failed !== 1 ? 's' : ''} failed to sync — will retry when online`);
    }
  }, [queryClient, refresh]);

  // Load pending ops on mount. When a new op is queued, refresh the list
  // and ping the server — if reachable, sync immediately.
  useEffect(() => {
    const handleQueueUpdate = async () => {
      await refresh();
      if (isAuthenticated) {
        const reachable = await checkNow();
        if (reachable) syncPending();
      }
    };

    refresh();
    window.addEventListener('offlineQueueUpdated', handleQueueUpdate);
    return () => window.removeEventListener('offlineQueueUpdated', handleQueueUpdate);
  }, [refresh, syncPending, isAuthenticated, checkNow]);

  // Auto-sync when coming back online (only if authenticated)
  useEffect(() => {
    if (isOnline && wasOfflineRef.current && isAuthenticated) {
      syncPending();
    }
    wasOfflineRef.current = !isOnline;
  }, [isOnline, isAuthenticated, syncPending]);

  return (
    <OfflineQueueContext.Provider value={{ pendingOps, isSyncing, isOnline, syncNow: syncPending, refreshPending: refresh }}>
      {children}
    </OfflineQueueContext.Provider>
  );
}

export function useOfflineQueue() {
  return useContext(OfflineQueueContext);
}
