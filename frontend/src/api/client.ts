import axios, { InternalAxiosRequestConfig, AxiosResponse } from 'axios';

const rawBaseUrl = (import.meta as any).env?.VITE_API_URL || 'http://127.0.0.1:8000';
const apiPrefix = String(rawBaseUrl).endsWith('/api/v1') ? '' : '/api/v1';
const baseURL = `${String(rawBaseUrl).replace(/\/+$/, '')}${apiPrefix}`;

const api = axios.create({
  baseURL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Attach JWT token to every request if available
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem('locallift_token');
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let isNotifyingExpiration = false;

// Response interceptor to handle 401 session expirations gracefully
api.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: any) => {
    if (error.response?.status === 401) {
      const url = error.config?.url || '';
      const isAuthAttempt = url.includes('/auth/login') || url.includes('/auth/register');

      // Only expire session if 401 was on an authenticated resource (not failed login credentials)
      if (!isAuthAttempt && localStorage.getItem('locallift_token')) {
        localStorage.removeItem('locallift_token');

        if (!isNotifyingExpiration) {
          isNotifyingExpiration = true;
          if (typeof window !== 'undefined') {
            window.dispatchEvent(new CustomEvent('auth:expired', { detail: { url } }));
          }
          setTimeout(() => {
            isNotifyingExpiration = false;
          }, 1000);
        }
      }
    }
    return Promise.reject(error);
  }
);

export default api;
