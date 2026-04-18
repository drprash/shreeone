import axios from 'axios';
import { useAuthStore } from '../store/authStore';
import toast from 'react-hot-toast';

const extractErrorMessage = (error, fallback = 'Request failed') => {
  const detail = error?.response?.data?.detail;

  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }

  if (Array.isArray(detail) && detail.length > 0) {
    const firstItem = detail[0];
    if (typeof firstItem === 'string' && firstItem.trim()) {
      return firstItem;
    }
    if (firstItem && typeof firstItem === 'object') {
      const firstItemMessage = firstItem.msg || firstItem.message;
      if (typeof firstItemMessage === 'string' && firstItemMessage.trim()) {
        return firstItemMessage;
      }
    }
  }

  if (detail && typeof detail === 'object') {
    const objectMessage = detail.message || detail.error;
    if (typeof objectMessage === 'string' && objectMessage.trim()) {
      return objectMessage;
    }
  }

  return fallback;
};

// Determine API URL dynamically based on current location
const getApiUrl = () => {
  return `${window.location.origin}/api`;
};

const API_URL = import.meta.env.VITE_API_URL || getApiUrl();

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json'
  }
});

// Request interceptor
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor for token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    const requestUrl = originalRequest?.url || '';
    const isAuthFlowRequest = requestUrl.includes('/auth/login') || requestUrl.includes('/auth/register') || requestUrl.includes('/auth/refresh');
    const refreshToken = useAuthStore.getState().refreshToken;
    
    if (error.response?.status === 401 && !originalRequest?._retry && !isAuthFlowRequest && refreshToken) {
      originalRequest._retry = true;
      
      try {
        const response = await axios.post(`${API_URL}/auth/refresh`, {
          refresh_token: refreshToken
        });

        useAuthStore.getState().setAuth(response.data);
        originalRequest.headers.Authorization = `Bearer ${response.data.access_token}`;

        return api(originalRequest);
      } catch (refreshError) {
        const { isAuthenticated, setSessionExpired, clearAuth } = useAuthStore.getState();
        // No server response = server unreachable (more accurate than navigator.onLine,
        // which only indicates a network interface exists and lies on Android / home-LAN).
        const isServerUnreachable = !refreshError.response;

        if (isServerUnreachable && isAuthenticated) {
          // Preserve auth state — show reconnect overlay instead of redirecting
          setSessionExpired(true);
          return Promise.reject(refreshError);
        }

        clearAuth();
        if (window.location.pathname !== '/login') {
          window.history.pushState({}, '', '/login');
          window.dispatchEvent(new PopStateEvent('popstate'));
        }
        return Promise.reject(refreshError);
      }
    }
    
    // Show error toast only for mutations (POST/PUT/PATCH/DELETE) that received
    // a server response. Network errors on mutations are suppressed here because
    // the calling mutation hook handles the fallback (e.g. saving to IndexedDB).
    // Background GET query failures are handled silently — React Query retries
    // automatically, and the UI shows stale/empty state instead of a popup.
    const isGetRequest = originalRequest?.method?.toLowerCase() === 'get';
    const isNetworkError = !error.response;
    const shouldShowGlobalToast = !requestUrl.includes('/auth/login') && !isGetRequest && !isNetworkError;
    if (shouldShowGlobalToast) {
      toast.error(extractErrorMessage(error));
    }
    
    return Promise.reject(error);
  }
);

export default api;
