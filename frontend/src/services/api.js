/**
 * API Client for Autonomous AI Genomic Analysis Platform
 * Connects to FastAPI backend (/api/v1) via Vite development proxy.
 */
import axios from 'axios';

const api = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 60000, // 60 seconds timeout for large bioinformatics tasks
});

// Response interceptor for consistent error handling
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const errorData = error.response?.data;
    const detail = errorData?.detail || error.message || 'An unexpected network error occurred';
    const formattedError = new Error(detail);
    formattedError.status = error.response?.status;
    formattedError.errorCode = errorData?.error_code;
    formattedError.raw = errorData;
    return Promise.reject(formattedError);
  }
);

export const datasetsApi = {
  list: () => api.get('/datasets'),
  get: (id) => api.get(`/datasets/${id}`),
  delete: (id) => api.delete(`/datasets/${id}`),
  validateOnly: (formData) =>
    api.post('/datasets/validate-only', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  upload: (formData, onProgress) =>
    api.post('/datasets/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress(percent);
        }
      },
    }),
};

export const analysesApi = {
  create: (data) => api.post('/analyses', data),
  list: (skip = 0, limit = 50) => api.get(`/analyses?skip=${skip}&limit=${limit}`),
  get: (id) => api.get(`/analyses/${id}`),
  getEvents: (id) => api.get(`/analyses/${id}/events`),
  cancel: (id) => api.post(`/analyses/${id}/cancel`),
  getStatistics: (id) => api.get(`/analyses/${id}/statistics`),
  getVariants: (id, params = {}) => {
    const query = new URLSearchParams();
    if (params.chromosome) query.append('chromosome', params.chromosome);
    if (params.gene) query.append('gene', params.gene);
    if (params.consequence) query.append('consequence', params.consequence);
    if (params.priority_category) query.append('priority_category', params.priority_category);
    if (params.has_conflicts !== undefined && params.has_conflicts !== null) {
      query.append('has_conflicts', params.has_conflicts);
    }
    if (params.search) query.append('search', params.search);
    if (params.page) query.append('page', params.page);
    if (params.page_size) query.append('page_size', params.page_size);
    const queryString = query.toString();
    return api.get(`/analyses/${id}/variants${queryString ? `?${queryString}` : ''}`);
  },
  getVariantDetail: (analysisId, variantId) =>
    api.get(`/analyses/${analysisId}/variants/${variantId}`),
  explainVariant: (analysisId, variantId) =>
    api.post(`/analyses/${analysisId}/variants/${variantId}/explain`),
  getVariantExplanation: (analysisId, variantId) =>
    api.get(`/analyses/${analysisId}/variants/${variantId}/explanation`),
  getDashboardSummary: () => api.get('/analyses/dashboard/summary'),
};

export const healthApi = {
  check: () => api.get('/health'),
};

export default api;

