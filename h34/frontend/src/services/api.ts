import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'
import type {
  ApiResponse,
  PaginatedResponse,
  User,
  UserConfig,
  WeatherStation,
  WeatherData,
  SporeSensor,
  SporeData,
  GridCell,
  RiskGrid,
  ForecastData,
  Alert,
  NotificationLog,
  HealthCheckResponse,
  LoginRequest,
  LoginResponse,
  PaginationParams,
  RiskGridQueryParams,
  WeatherDataQueryParams,
  CropType,
} from '@/types'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

const api: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

api.interceptors.response.use(
  (response: AxiosResponse) => {
    return response.data
  },
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export const authApi = {
  login: (data: LoginRequest): Promise<ApiResponse<LoginResponse>> =>
    api.post('/auth/login', data),

  logout: (): Promise<ApiResponse<void>> =>
    api.post('/auth/logout'),

  getCurrentUser: (): Promise<ApiResponse<User>> =>
    api.get('/auth/me'),
}

export const healthApi = {
  check: (): Promise<ApiResponse<HealthCheckResponse>> =>
    api.get('/health'),
}

export const userConfigApi = {
  list: (params?: PaginationParams): Promise<ApiResponse<PaginatedResponse<UserConfig>>> =>
    api.get('/user-configs', { params }),

  get: (id: number): Promise<ApiResponse<UserConfig>> =>
    api.get(`/user-configs/${id}`),

  create: (data: Omit<UserConfig, 'id' | 'user_id' | 'created_at' | 'updated_at'>): Promise<ApiResponse<UserConfig>> =>
    api.post('/user-configs', data),

  update: (id: number, data: Partial<Omit<UserConfig, 'id' | 'user_id' | 'created_at' | 'updated_at'>>): Promise<ApiResponse<UserConfig>> =>
    api.put(`/user-configs/${id}`, data),

  delete: (id: number): Promise<ApiResponse<void>> =>
    api.delete(`/user-configs/${id}`),
}

export const weatherStationApi = {
  list: (params?: PaginationParams): Promise<ApiResponse<PaginatedResponse<WeatherStation>>> =>
    api.get('/weather-stations', { params }),

  get: (id: number): Promise<ApiResponse<WeatherStation>> =>
    api.get(`/weather-stations/${id}`),

  getByLocation: (lat: number, lng: number, radius: number = 50): Promise<ApiResponse<WeatherStation[]>> =>
    api.get('/weather-stations/nearby', { params: { lat, lng, radius } }),
}

export const weatherDataApi = {
  list: (params?: WeatherDataQueryParams): Promise<ApiResponse<PaginatedResponse<WeatherData>>> =>
    api.get('/weather-data', { params }),

  getLatest: (stationId: number): Promise<ApiResponse<WeatherData>> =>
    api.get(`/weather-data/latest/${stationId}`),

  getTimeSeries: (stationId: number, startDate: string, endDate: string): Promise<ApiResponse<WeatherData[]>> =>
    api.get(`/weather-data/station/${stationId}/timeseries`, { params: { startDate, endDate } }),
}

export const sporeSensorApi = {
  list: (params?: PaginationParams & { crop_type?: CropType }): Promise<ApiResponse<PaginatedResponse<SporeSensor>>> =>
    api.get('/spore-sensors', { params }),

  get: (id: number): Promise<ApiResponse<SporeSensor>> =>
    api.get(`/spore-sensors/${id}`),
}

export const sporeDataApi = {
  list: (params?: PaginationParams & { sensor_id?: number }): Promise<ApiResponse<PaginatedResponse<SporeData>>> =>
    api.get('/spore-data', { params }),

  getLatest: (sensorId: number): Promise<ApiResponse<SporeData>> =>
    api.get(`/spore-data/latest/${sensorId}`),
}

export const riskGridApi = {
  list: (params?: RiskGridQueryParams): Promise<ApiResponse<PaginatedResponse<RiskGrid>>> =>
    api.get('/risk-grids', { params }),

  getLatest: (cropType: CropType): Promise<ApiResponse<RiskGrid[]>> =>
    api.get('/risk-grids/latest', { params: { crop_type: cropType } }),

  getHeatmap: (cropType: CropType, date?: string): Promise<ApiResponse<RiskGrid[]>> =>
    api.get('/risk-grids/heatmap', { params: { crop_type: cropType, date } }),

  getByGrid: (gridId: number, params?: { crop_type?: CropType; start_date?: string; end_date?: string }): Promise<ApiResponse<RiskGrid[]>> =>
    api.get(`/risk-grids/grid/${gridId}`, { params }),
}

export const forecastApi = {
  list: (params?: PaginationParams & { grid_id?: number; start_date?: string; end_date?: string }): Promise<ApiResponse<PaginatedResponse<ForecastData>>> =>
    api.get('/forecast-data', { params }),

  getByGrid: (gridId: number, startDate: string, endDate: string): Promise<ApiResponse<ForecastData[]>> =>
    api.get(`/forecast-data/grid/${gridId}`, { params: { startDate, endDate } }),
}

export const alertApi = {
  list: (params?: PaginationParams & { is_read?: boolean; user_id?: number }): Promise<ApiResponse<PaginatedResponse<Alert>>> =>
    api.get('/alerts', { params }),

  get: (id: number): Promise<ApiResponse<Alert>> =>
    api.get(`/alerts/${id}`),

  markAsRead: (id: number): Promise<ApiResponse<Alert>> =>
    api.patch(`/alerts/${id}/read`),

  markAllAsRead: (): Promise<ApiResponse<{ updated: number }>> =>
    api.patch('/alerts/read-all'),

  getUnreadCount: (): Promise<ApiResponse<{ count: number }>> =>
    api.get('/alerts/unread-count'),
}

export const gridCellApi = {
  list: (params?: PaginationParams): Promise<ApiResponse<PaginatedResponse<GridCell>>> =>
    api.get('/grid-cells', { params }),

  get: (id: number): Promise<ApiResponse<GridCell>> =>
    api.get(`/grid-cells/${id}`),

  getByLocation: (lat: number, lng: number): Promise<ApiResponse<GridCell>> =>
    api.get('/grid-cells/by-location', { params: { lat, lng } }),
}

export default api
