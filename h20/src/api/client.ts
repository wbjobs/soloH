import axios, { type AxiosInstance, type AxiosRequestConfig, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { API_BASE_URL, USE_MOCK_API } from '../utils/constants'
import { useAppStore } from '../stores/app'
import mockApi from './mock'

export interface ApiClientConfig {
  baseURL?: string
  timeout?: number
  withCredentials?: boolean
}

const defaultConfig: ApiClientConfig = {
  baseURL: API_BASE_URL,
  timeout: 30000,
  withCredentials: true
}

function createApiClient(config: ApiClientConfig = {}): AxiosInstance {
  const mergedConfig = { ...defaultConfig, ...config }
  const instance = axios.create(mergedConfig)

  instance.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
      const token = localStorage.getItem('auth_token')
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
      
      const appStore = useAppStore()
      appStore.setLoading(true)
      
      return config
    },
    (error) => {
      const appStore = useAppStore()
      appStore.setLoading(false)
      return Promise.reject(error)
    }
  )

  instance.interceptors.response.use(
    (response: AxiosResponse) => {
      const appStore = useAppStore()
      appStore.setLoading(false)
      
      if (response.data?.success === false) {
        const errorMessage = response.data.error?.message || '请求失败'
        appStore.addNotification({
          type: 'error',
          message: errorMessage
        })
        return Promise.reject(new Error(errorMessage))
      }
      
      return response.data
    },
    async (error) => {
      const appStore = useAppStore()
      appStore.setLoading(false)
      
      const originalRequest = error.config
      
      if (error.response?.status === 401 && !originalRequest._retry) {
        originalRequest._retry = true
        
        try {
          const refreshToken = localStorage.getItem('refresh_token')
          if (refreshToken) {
            const refreshResponse = await axios.post(`${defaultConfig.baseURL}/auth/refresh`, {
              refreshToken
            })
            
            if (refreshResponse.data?.success) {
              const { accessToken } = refreshResponse.data.data
              localStorage.setItem('auth_token', accessToken)
              originalRequest.headers.Authorization = `Bearer ${accessToken}`
              return instance(originalRequest)
            }
          }
        } catch (refreshError) {
          localStorage.removeItem('auth_token')
          localStorage.removeItem('refresh_token')
          window.location.href = '/login'
        }
      }
      
      const errorMessage = error.response?.data?.error?.message || error.message || '网络错误'
      
      if (error.response?.status !== 401) {
        appStore.addNotification({
          type: 'error',
          message: errorMessage
        })
      }
      
      return Promise.reject(new Error(errorMessage))
    }
  )

  return instance
}

export const apiClient = createApiClient()

async function tryRealThenMock<T>(
  realApiCall: () => Promise<T>,
  mockApiCall: () => Promise<T>,
  endpointName: string
): Promise<T> {
  if (USE_MOCK_API) {
    console.log(`[Mock] Using mock data for: ${endpointName}`)
    return mockApiCall()
  }
  
  try {
    return await realApiCall()
  } catch (error) {
    console.warn(`[API] ${endpointName} failed, falling back to mock:`, (error as Error).message)
    console.log(`[Mock] Using mock data for: ${endpointName}`)
    return mockApiCall()
  }
}

export async function get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  return apiClient.get(url, config)
}

export async function post<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  return apiClient.post(url, data, config)
}

export async function put<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  return apiClient.put(url, data, config)
}

export async function patch<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  return apiClient.patch(url, data, config)
}

export async function del<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  return apiClient.delete(url, config)
}

export { tryRealThenMock, mockApi }
