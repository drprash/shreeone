import { useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import api from '../services/api';
import { addPendingOp } from '../lib/offlineDb';
import { useOfflineQueue } from '../context/OfflineQueueContext';
import { queryKeys } from '../utils/queryKeys';

function invalidateCategories(queryClient) {
  queryClient.invalidateQueries({ queryKey: queryKeys.categories() });
}

export function useCreateCategory({ onSuccess } = {}) {
  const { isOnline } = useOfflineQueue();
  const queryClient = useQueryClient();

  const saveOffline = async (data) => {
    const tempCategory = {
      id: 'temp_' + crypto.randomUUID(),
      ...data,
      sort_order: 9999,
    };
    queryClient.setQueriesData(
      { queryKey: queryKeys.categories() },
      (old) => Array.isArray(old) ? [...old, tempCategory] : [tempCategory]
    );
    const op = {
      id: crypto.randomUUID(),
      type: 'CREATE_CATEGORY',
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
    mutationFn: (data) => api.post('/categories/', data),
    onSuccess: () => {
      toast.success('Category created');
      invalidateCategories(queryClient);
      onSuccess?.();
    },
    onError: async (error, data) => {
      if (!error.response) { await saveOffline(data); return; }
      toast.error(error.response.data?.detail || 'Failed to create category');
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

export function useUpdateCategory({ onSuccess } = {}) {
  const { isOnline } = useOfflineQueue();
  const queryClient = useQueryClient();

  const saveOffline = async ({ id, data }) => {
    queryClient.setQueriesData(
      { queryKey: queryKeys.categories() },
      (old) => Array.isArray(old) ? old.map(c => c.id === id ? { ...c, ...data } : c) : old
    );
    const op = {
      id: crypto.randomUUID(),
      type: 'UPDATE_CATEGORY',
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
    mutationFn: ({ id, data }) => api.put(`/categories/${id}`, data),
    onSuccess: () => {
      toast.success('Category updated');
      invalidateCategories(queryClient);
      onSuccess?.();
    },
    onError: async (error, variables) => {
      if (!error.response) { await saveOffline(variables); return; }
      toast.error(error.response.data?.detail || 'Failed to update category');
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

export function useDeleteCategory() {
  const { isOnline } = useOfflineQueue();
  const queryClient = useQueryClient();

  const saveOffline = async (id) => {
    queryClient.setQueriesData(
      { queryKey: queryKeys.categories() },
      (old) => Array.isArray(old) ? old.filter(c => c.id !== id) : old
    );
    const op = {
      id: crypto.randomUUID(),
      type: 'DELETE_CATEGORY',
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
    mutationFn: (id) => api.delete(`/categories/${id}`),
    onSuccess: () => {
      toast.success('Category deleted');
      invalidateCategories(queryClient);
    },
    onError: async (error, id) => {
      if (!error.response) { await saveOffline(id); return; }
      toast.error(error.response.data?.detail || 'Failed to delete category');
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
