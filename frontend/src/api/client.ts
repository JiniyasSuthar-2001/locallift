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

// Response interceptor to handle 401 session expirations gracefully
api.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: any) => {
    if (error.response?.status === 401) {
      // If unauthorized, do not crash; AuthContext will handle redirect
    }
    return Promise.reject(error);
  }
);

export default api;
