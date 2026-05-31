import axios from 'axios';
import type {
  UploadResponse,
  DetectionResult,
  PreprocessOptions,
  AudioSynthesisRequest,
  AudioSynthesisResponse,
  Jianzi,
  Dictionary,
  ScoreListItem,
  SerializedScore,
  DifficultyReport,
  GuqinStyle,
  StyleComparisonResult,
} from '@/types/index';

const api = axios.create({
  baseURL: 'http://localhost:5000/api',
  timeout: 30000,
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const message = error.response?.data?.error || error.message;
    console.error('API Error:', message);
    return Promise.reject(new Error(message));
  }
);

export const uploadImage = async (file: File): Promise<UploadResponse> => {
  const formData = new FormData();
  formData.append('image', file);
  const { data } = await api.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return {
    imageId: data.imageId,
    imageUrl: data.url,
    width: data.width,
    height: data.height,
  };
};

export const preprocessImage = async (
  imageId: string,
  options: PreprocessOptions = {}
): Promise<{ imageId: string; processedUrl: string; width: number; height: number }> => {
  const { data } = await api.post('/preprocess', {
    imageId,
    ...options,
  });
  return data;
};

export const detectJianzi = async (imageId: string): Promise<DetectionResult> => {
  const { data } = await api.post('/detect', { imageId });
  return data;
};

export const recognizeComponent = async (
  imageId: string,
  jianziId: string,
  jianzi: Jianzi
): Promise<Jianzi> => {
  const { data } = await api.post('/recognize', {
    imageId,
    jianziId,
    jianzi,
  });
  return data;
};

export const updateJianzi = async (
  jianziId: string,
  data: Partial<Jianzi>
): Promise<Jianzi> => {
  const { data: result } = await api.put(`/jianzi/${jianziId}`, data);
  return result;
};

export const synthesizeAudio = async (
  jianziList: Jianzi[],
  tempo: number,
  technique?: string
): Promise<AudioSynthesisResponse> => {
  const { data } = await api.post('/synthesize', {
    jianziList,
    tempo,
    technique,
  } as AudioSynthesisRequest);
  return data;
};

export const downloadFile = async (type: 'midi' | 'audio' | 'text', id: string): Promise<Blob> => {
  const { data } = await api.get(`/download/${type}/${id}`, {
    responseType: 'blob',
  });
  return data;
};

export const getGongche = async (
  jianziId?: string,
  jianziList?: Jianzi[]
): Promise<unknown> => {
  const params: Record<string, string> = {};
  if (jianziId) {
    params.jianziId = jianziId;
  }
  if (jianziList) {
    params.jianziList = JSON.stringify(jianziList);
  }
  const { data } = await api.get('/gongche', { params });
  return data;
};

export const getDictionary = async (): Promise<Dictionary> => {
  const { data } = await api.get('/dictionary');
  return data;
};

export const createScore = async (
  title: string,
  pages: File[],
  jianziData?: any[][],
  metadata?: Record<string, any>
): Promise<{ success: boolean; score_id: string; metadata: any }> => {
  const formData = new FormData();
  formData.append('title', title);
  pages.forEach((file) => formData.append('pages', file));
  if (jianziData) {
    formData.append('jianzi_data', JSON.stringify(jianziData));
  }
  if (metadata) {
    formData.append('metadata', JSON.stringify(metadata));
  }
  const { data } = await api.post('/score/create', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
};

export const listScores = async (): Promise<ScoreListItem[]> => {
  const { data } = await api.get('/score/list');
  return data.scores || [];
};

export const getScore = async (scoreId: string): Promise<SerializedScore> => {
  const { data } = await api.get(`/score/${scoreId}`);
  return data.score;
};

export const updateScore = async (
  scoreId: string,
  updates: {
    jianzi_updates?: any[];
    audio_synthesis_params?: any;
  }
): Promise<{ success: boolean }> => {
  const { data } = await api.post(`/score/${scoreId}/update`, updates);
  return data;
};

export const deleteScore = async (scoreId: string): Promise<{ success: boolean }> => {
  const { data } = await api.delete(`/score/${scoreId}`);
  return data;
};

export const stitchPages = async (
  pages: File[],
  pageOrder?: number[]
): Promise<{
  success: boolean;
  stitched_url: string;
  page_bounds: number[][];
  columns: number[][];
  column_count: number;
}> => {
  const formData = new FormData();
  pages.forEach((file) => formData.append('pages', file));
  if (pageOrder) {
    formData.append('page_order', JSON.stringify(pageOrder));
  }
  const { data } = await api.post('/score/stitch', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
};

export const evaluateDifficulty = async (
  scoreId: string
): Promise<{
  success: boolean;
  score_id: string;
  report: DifficultyReport;
  visualization: string;
}> => {
  const { data } = await api.get(`/difficulty/evaluate/${scoreId}`);
  return data;
};

export const analyzeAudioDifficulty = async (
  audioFile: File,
  jianziInfo: any
): Promise<{
  success: boolean;
  features: any;
  difficulty: any;
}> => {
  const formData = new FormData();
  formData.append('audio', audioFile);
  formData.append('jianzi_info', JSON.stringify(jianziInfo));
  const { data } = await api.post('/difficulty/analyze', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
};

export const getStyles = async (): Promise<GuqinStyle[]> => {
  const { data } = await api.get('/styles');
  return data.styles || [];
};

export const getStyleDetail = async (styleId: string): Promise<GuqinStyle> => {
  const { data } = await api.get(`/styles/${styleId}`);
  return data.style;
};

export const compareStyles = async (
  jianziList: Jianzi[],
  styleIds: string[],
  tempo: number = 60
): Promise<StyleComparisonResult[]> => {
  const { data } = await api.post('/styles/compare', {
    jianzi_list: jianziList,
    style_ids: styleIds,
    tempo,
  });
  return data.results || [];
};

export const synthesizeScore = async (
  scoreId: string,
  style?: string,
  tempo?: number
): Promise<{
  success: boolean;
  audio_url: string;
  style: string;
  tempo: number;
  duration: number;
}> => {
  const { data } = await api.post(`/score/${scoreId}/synthesize`, {
    style,
    tempo,
  });
  return data;
};

export default api;
