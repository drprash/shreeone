import api from './api';

export const goalsAPI = {
  list: (includeArchived = false) =>
    api.get('/goals', { params: { include_archived: includeArchived } }).then(r => r.data),

  get: (id) => api.get(`/goals/${id}`).then(r => r.data),

  create: (data) => api.post('/goals', data).then(r => r.data),

  update: (id, data) => api.put(`/goals/${id}`, data).then(r => r.data),

  archive: (id) => api.delete(`/goals/${id}`),

  progress: (id) => api.get(`/goals/${id}/progress`).then(r => r.data),

  contribute: (id, data) => api.post(`/goals/${id}/contribute`, data).then(r => r.data),

  contributions: (id) => api.get(`/goals/${id}/contributions`).then(r => r.data),
};
