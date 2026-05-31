import axios from 'axios';
import type {
  UploadResponse,
  AnalyzeRequest,
  AnalyzeResponse,
  ResultResponse,
  HistoryItem,
  EmotionResult
} from '@/types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const uploadVideo = async (file: File, onProgress?: (progress: number) => void): Promise<UploadResponse> => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await api.post<UploadResponse>('/api/v1/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    onUploadProgress: (progressEvent) => {
      if (onProgress && progressEvent.total) {
        const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
        onProgress(progress);
      }
    },
  });

  return response.data;
};

export const startAnalysis = async (
  videoId: string,
  request?: AnalyzeRequest
): Promise<AnalyzeResponse> => {
  const response = await api.post<AnalyzeResponse>(
    `/api/v1/analyze/${videoId}`,
    request || {}
  );
  return response.data;
};

export const getAnalysisStatus = async (taskId: string): Promise<AnalyzeResponse> => {
  const response = await api.get<AnalyzeResponse>(`/api/v1/task/${taskId}/status`);
  return response.data;
};

export const getAnalysisResult = async (taskId: string): Promise<ResultResponse> => {
  const response = await api.get<ResultResponse>(`/api/v1/result/${taskId}`);
  return response.data;
};

export const getHistory = async (page = 1, pageSize = 20): Promise<{ items: HistoryItem[]; total: number }> => {
  const response = await api.get<{ items: HistoryItem[]; total: number }>('/api/v1/history', {
    params: { page, page_size: pageSize },
  });
  return response.data;
};

export const getHistoryItem = async (id: string): Promise<EmotionResult> => {
  const response = await api.get<EmotionResult>(`/api/v1/history/${id}`);
  return response.data;
};

export const deleteHistoryItem = async (id: string): Promise<void> => {
  await api.delete(`/api/v1/history/${id}`);
};

export const exportResult = async (taskId: string, format: 'json' | 'csv' = 'json'): Promise<Blob> => {
  const response = await api.get(`/api/v1/result/${taskId}/export`, {
    params: { format },
    responseType: 'blob',
  });
  return response.data;
};

export const checkHealth = async (): Promise<{ status: string; timestamp: string }> => {
  const response = await api.get('/health');
  return response.data;
};

export default api;
