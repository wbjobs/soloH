import axios, { type AxiosInstance, type AxiosProgressEvent } from 'axios';
import type { 
  Task, 
  TaskResult, 
  UploadResponse, 
  TaskListResponse,
  UpdateBoxRequest,
  UpdateBoxResponse
} from '../types';

const baseURL = '/api';

const api: AxiosInstance = axios.create({
  baseURL,
  timeout: 300000,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token');
    }
    return Promise.reject(error);
  }
);

export const uploadFile = (
  file: File,
  onProgress?: (progress: number, loaded: number, total: number) => void
): Promise<UploadResponse> => {
  const formData = new FormData();
  formData.append('file', file);

  return api.post('/files/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    onUploadProgress: (progressEvent: AxiosProgressEvent) => {
      if (onProgress && progressEvent.total) {
        const progress = Math.round((progressEvent.loaded / progressEvent.total) * 100);
        onProgress(progress, progressEvent.loaded, progressEvent.total);
      }
    },
  });
};

export const getTasks = (
  page: number = 1,
  perPage: number = 10,
  status?: string
): Promise<TaskListResponse> => {
  const params: Record<string, any> = { page, perPage };
  if (status) {
    params.status = status;
  }
  return api.get('/tasks', { params });
};

export const getTask = (taskId: string): Promise<Task> => {
  return api.get(`/tasks/${taskId}`);
};

export const getTaskResult = (taskId: string): Promise<TaskResult> => {
  return api.get(`/tasks/${taskId}/result`);
};

export const updateTaskResult = (
  taskId: string,
  data: UpdateBoxRequest
): Promise<UpdateBoxResponse> => {
  return api.put(`/tasks/${taskId}/result`, data);
};

export const rerunTask = (taskId: string): Promise<Task> => {
  return api.post(`/tasks/${taskId}/rerun`);
};

export const exportTask = (
  taskId: string,
  format: 'markdown' | 'tei' | 'txt' | 'json' = 'txt'
): Promise<Blob> => {
  return api.get(`/tasks/${taskId}/export`, {
    params: { format },
    responseType: 'blob',
  });
};

export const deleteTask = (taskId: string): Promise<{ success: boolean }> => {
  return api.delete(`/tasks/${taskId}`);
};

export const getImageUrl = (imagePath: string): string => {
  if (imagePath.startsWith('http')) {
    return imagePath;
  }
  if (imagePath.startsWith('/')) {
    return `/api${imagePath}`;
  }
  return `/api/${imagePath}`;
};

export default api;
