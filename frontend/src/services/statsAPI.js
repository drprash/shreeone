import api from './api';

export const getStats = (startDate, endDate) =>
  api.get('/stats', { params: { start_date: startDate, end_date: endDate } })
     .then(r => r.data);
