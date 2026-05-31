import axios from 'axios';
import type { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';
import { ElMessage } from 'element-plus';
import type {
  LoginRequest,
  RegisterRequest,
  AuthResponse,
  UploadFile,
  FilePreview,
  SampleMatchResult,
  GWASRequest,
  GWASResponse,
  AnalysisTask,
  TaskListResponse,
  TaskStats,
  GWASResult,
  SNPListResponse,
  LDHeatmapRequest,
  LDHeatmapResponse,
  ReferenceGenome,
  MaizeInbredLine,
  PCAResult,
  MultiPhenotypeRequest,
  MultiPhenotypeResponse,
  MultiPhenotypeResult,
  EnrichmentRequest,
  EnrichmentResponse,
  EnrichmentResult,
  FineMappingRequest,
  FineMappingResponse,
  FineMappingResult,
} from '@/types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api';

const axiosInstance: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000,
  headers: {
    'Content-Type': 'application/json',
  },
});

axiosInstance.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

axiosInstance.interceptors.response.use(
  (response: AxiosResponse) => {
    return response.data;
  },
  (error) => {
    if (error.response) {
      if (error.response.status === 401) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('user');
        window.location.href = '/login';
        ElMessage.error('登录已过期，请重新登录');
      } else if (error.response.status === 403) {
        ElMessage.error('没有权限执行此操作');
      } else if (error.response.data?.error) {
        ElMessage.error(error.response.data.error);
      } else {
        ElMessage.error('请求失败，请稍后重试');
      }
    } else if (error.request) {
      ElMessage.error('网络错误，请检查网络连接');
    }
    return Promise.reject(error);
  }
);

export const authAPI = {
  login: (data: LoginRequest): Promise<AuthResponse> =>
    axiosInstance.post('/auth/login', data),
  
  register: (data: RegisterRequest): Promise<AuthResponse> =>
    axiosInstance.post('/auth/register', data),
  
  getProfile: (): Promise<any> =>
    axiosInstance.get('/auth/profile'),
};

export const uploadAPI = {
  uploadVCF: (file: File, onProgress?: (progress: number) => void): Promise<UploadFile> => {
    const formData = new FormData();
    formData.append('file', file);
    return axiosInstance.post('/upload/vcf', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          onProgress(Math.round((progressEvent.loaded * 100) / progressEvent.total));
        }
      },
    });
  },
  
  uploadPhenotype: (file: File, onProgress?: (progress: number) => void): Promise<UploadFile> => {
    const formData = new FormData();
    formData.append('file', file);
    return axiosInstance.post('/upload/phenotype', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          onProgress(Math.round((progressEvent.loaded * 100) / progressEvent.total));
        }
      },
    });
  },
  
  uploadCovariate: (file: File, onProgress?: (progress: number) => void): Promise<UploadFile> => {
    const formData = new FormData();
    formData.append('file', file);
    return axiosInstance.post('/upload/covariate', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          onProgress(Math.round((progressEvent.loaded * 100) / progressEvent.total));
        }
      },
    });
  },
  
  getFilePreview: (fileId: string): Promise<FilePreview> =>
    axiosInstance.get(`/upload/preview/${fileId}`),
  
  listFiles: (type?: string): Promise<UploadFile[]> =>
    axiosInstance.get('/upload/files', { params: type ? { type } : {} }),
  
  deleteFile: (fileId: string): Promise<void> =>
    axiosInstance.delete(`/upload/${fileId}`),
};

export const analysisAPI = {
  matchSamples: (vcfFileId: string, phenotypeFileId: string): Promise<SampleMatchResult> =>
    axiosInstance.post('/analysis/match-samples', { vcfFileId, phenotypeFileId }),
  
  runPCA: (vcfFileId: string, nComponents?: number): Promise<any> =>
    axiosInstance.post('/analysis/pca', { vcfFileId, nComponents: nComponents || 10 }),
  
  runGWAS: (data: GWASRequest): Promise<GWASResponse> =>
    axiosInstance.post('/analysis/gwas', data),
  
  calculateLDHeatmap: (data: LDHeatmapRequest): Promise<any> =>
    axiosInstance.post('/analysis/ld-heatmap', data),
};

export const taskAPI = {
  listTasks: (page?: number, pageSize?: number, status?: string, type?: string): Promise<TaskListResponse> =>
    axiosInstance.get('/tasks', {
      params: { page, pageSize, status, type },
    }),
  
  getTask: (taskId: string): Promise<AnalysisTask> =>
    axiosInstance.get(`/tasks/${taskId}`),
  
  cancelTask: (taskId: string): Promise<void> =>
    axiosInstance.delete(`/tasks/${taskId}`),
  
  restartTask: (taskId: string): Promise<any> =>
    axiosInstance.post(`/tasks/${taskId}/restart`),
  
  getStats: (): Promise<TaskStats> =>
    axiosInstance.get('/tasks/stats'),
};

export const resultAPI = {
  getResult: (taskId: string): Promise<GWASResult> =>
    axiosInstance.get(`/results/${taskId}`),
  
  getSNPs: (taskId: string, page?: number, pageSize?: number, chr?: string, minLog10P?: number): Promise<SNPListResponse> =>
    axiosInstance.get(`/results/${taskId}/snps`, {
      params: { page, pageSize, chr, minLog10P },
    }),
  
  downloadManhattan: (taskId: string): string =>
    `${API_BASE_URL}/results/${taskId}/download/manhattan.png`,
  
  downloadQQ: (taskId: string): string =>
    `${API_BASE_URL}/results/${taskId}/download/qq.png`,
  
  downloadLDHeatmap: (taskId: string): string =>
    `${API_BASE_URL}/results/${taskId}/download/ld-heatmap.png`,
  
  downloadSNPsCSV: (taskId: string): string =>
    `${API_BASE_URL}/results/${taskId}/download/snps.csv`,
  
  downloadReport: (taskId: string): string =>
    `${API_BASE_URL}/results/${taskId}/download/report.pdf`,
};

export const referenceAPI = {
  listGenomes: (species?: string): Promise<ReferenceGenome[]> =>
    axiosInstance.get('/reference/genomes', { params: species ? { species } : {} }),
  
  getGenome: (genomeId: string): Promise<ReferenceGenome> =>
    axiosInstance.get(`/reference/genomes/${genomeId}`),
  
  getGenes: (genomeId: string, page?: number, pageSize?: number, chr?: string, start?: number, end?: number): Promise<any> =>
    axiosInstance.get(`/reference/genomes/${genomeId}/genes`, {
      params: { page, pageSize, chr, start, end },
    }),
  
  getMaizeInbredLines: (): Promise<MaizeInbredLine[]> =>
    axiosInstance.get('/reference/maize/inbred-lines'),
};

export const multiphenotypeAPI = {
  runMANOVA: (data: MultiPhenotypeRequest): Promise<MultiPhenotypeResponse> =>
    axiosInstance.post('/analysis/multiphenotype', { ...data, method: 'MANOVA' }),
  
  runCCA: (data: MultiPhenotypeRequest): Promise<MultiPhenotypeResponse> =>
    axiosInstance.post('/analysis/multiphenotype', { ...data, method: 'CCA' }),
  
  getResult: (taskId: string): Promise<MultiPhenotypeResult> =>
    axiosInstance.get(`/results/${taskId}`),
};

export const enrichmentAPI = {
  runGO: (data: EnrichmentRequest): Promise<EnrichmentResponse> =>
    axiosInstance.post('/analysis/enrichment', { ...data, enrichmentType: 'GO' }),
  
  runKEGG: (data: EnrichmentRequest): Promise<EnrichmentResponse> =>
    axiosInstance.post('/analysis/enrichment', { ...data, enrichmentType: 'KEGG' }),
  
  getResult: (taskId: string): Promise<EnrichmentResult> =>
    axiosInstance.get(`/results/${taskId}`),
};

export const finemappingAPI = {
  run: (data: FineMappingRequest): Promise<FineMappingResponse> =>
    axiosInstance.post('/analysis/finemapping', data),
  
  getResult: (taskId: string): Promise<FineMappingResult> =>
    axiosInstance.get(`/results/${taskId}`),
};

export default axiosInstance;
