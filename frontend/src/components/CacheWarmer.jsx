import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import { useAuthStore } from '../store/authStore';
import { queryKeys } from '../utils/queryKeys';

/**
 * Invisible component that prefetches all critical API endpoints
 * immediately after login. This populates both the React Query cache
 * and the Workbox service worker cache, so every page works offline
 * even if the user hasn't manually navigated to it yet.
 *
 * Renders nothing. Mount once inside the authenticated layout.
 */
const DEFAULT_TX_FILTER = { type: 'all', account: 'all', category: 'all' };

export default function CacheWarmer() {
  const queryClient = useQueryClient();
  const { user, isAuthenticated } = useAuthStore();

  useEffect(() => {
    if (!isAuthenticated || !user?.id) return;

    const queries = [
      {
        queryKey: queryKeys.accounts(),
        queryFn: () => api.get('/accounts/').then(r => r.data),
      },
      {
        queryKey: queryKeys.categories(),
        queryFn: () => api.get('/categories/').then(r => r.data),
      },
      {
        queryKey: queryKeys.familySettings(),
        queryFn: () => api.get('/settings/family-profile').then(r => r.data),
      },
      {
        queryKey: queryKeys.dashboard(user.id),
        queryFn: () => api.get('/dashboard/').then(r => r.data),
      },
      {
        queryKey: queryKeys.transactionsList(DEFAULT_TX_FILTER, user.id),
        queryFn: () => api.get('/transactions/').then(r => r.data),
      },
    ];

    // prefetchQuery skips if the data is already fresh (within staleTime).
    // allSettled ensures a single failure doesn't block the rest.
    Promise.allSettled(
      queries.map(q => queryClient.prefetchQuery({ queryKey: q.queryKey, queryFn: q.queryFn }))
    );
  }, [isAuthenticated, user?.id, queryClient]);

  return null;
}
