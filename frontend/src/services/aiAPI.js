import api from './api';

export const getAIStatus = () =>
  api.get('/ai/status').then(r => r.data);

export const testAIConnection = () =>
  api.post('/ai/test-connection').then(r => r.data);

export const categorizeTransaction = (description) =>
  api.post('/ai/categorize', { description }).then(r => r.data);

export const parseReceipt = (imageFile) => {
  const form = new FormData();
  form.append('image', imageFile);
  return api.post('/ai/parse-receipt', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data);
};

export const parseVoiceTranscript = (transcript) =>
  api.post('/ai/parse-voice-text', { transcript }).then(r => r.data);

export const parseStatement = (file, accountId, accountType = 'BANK') => {
  const form = new FormData();
  form.append('file', file);
  if (accountId) form.append('account_id', accountId);
  form.append('account_type', accountType);
  return api.post('/ai/parse-statement', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000, // statements can take up to 2 min for large PDFs
  }).then(r => r.data);
};

export const bulkCreateTransactions = (transactions) =>
  api.post('/transactions/bulk', { transactions }).then(r => r.data);

export const getNarratives = () =>
  api.get('/ai/narratives').then(r => r.data);

export const dismissNarrative = (id) =>
  api.post(`/ai/narratives/${id}/dismiss`);
