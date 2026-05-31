export type CropType = 'wheat' | 'potato' | 'corn' | 'rice'

export type AlertType = 'risk' | 'warning'

export type NotificationChannel = 'email' | 'webhook'

export type RiskLevel = 'low' | 'medium' | 'high' | 'extreme'

export interface Coordinate {
  lat: number
  lng: number
}

export interface GeoPoint {
  type: 'Point'
  coordinates: [number, number]
}

export interface GeoPolygon {
  type: 'Polygon'
  coordinates: [number, number][][]
}

export interface User {
  id: number
  email: string
  full_name?: string
  is_active: boolean
  created_at: string
}

export interface UserConfig {
  id: number
  user_id: number
  crop_type: CropType
  variety_name: string
  resistance_level: number
  risk_threshold: number
  notification_email?: string
  webhook_url?: string
  created_at: string
  updated_at: string
}

export interface WeatherStation {
  id: number
  name: string
  code: string
  location: GeoPoint
  latitude: number
  longitude: number
  elevation?: number
  is_active: boolean
  created_at: string
}

export interface WeatherData {
  id: number
  station_id: number
  timestamp: string
  temperature?: number
  relative_humidity?: number
  rainfall?: number
  leaf_wetness_duration?: number
  wind_speed?: number
  solar_radiation?: number
}

export interface SporeSensor {
  id: number
  name: string
  code: string
  location: GeoPoint
  latitude: number
  longitude: number
  crop_type: CropType
  spore_type: string
  is_active: boolean
  created_at: string
}

export interface SporeData {
  id: number
  sensor_id: number
  timestamp: string
  concentration: number
  created_at: string
}

export interface GridCell {
  id: number
  grid_x: number
  grid_y: number
  centroid: GeoPoint
  bounds: GeoPolygon
  lat: number
  lon: number
  resolution_km: number
  created_at: string
}

export interface RiskGrid {
  id: number
  grid_id: number
  forecast_date: string
  crop_type: CropType
  risk_index: number
  infection_probability?: number
  model_version?: string
  calculated_at: string
  grid_cell?: GridCell
}

export interface ForecastData {
  id: number
  grid_id: number
  forecast_date: string
  lead_time_hours: number
  temperature?: number
  humidity?: number
  rainfall?: number
  wind_speed?: number
  created_at: string
}

export interface Alert {
  id: number
  user_id: number
  grid_id: number
  alert_type: AlertType
  severity: string
  threshold_exceeded?: number
  message: string
  triggered_at: string
  notified_at?: string
  is_read: boolean
  grid_cell?: GridCell
}

export interface NotificationLog {
  id: number
  alert_id: number
  channel: NotificationChannel
  recipient: string
  status: string
  error_message?: string
  sent_at: string
}

export interface ApiResponse<T = any> {
  code: number
  message: string
  data?: T
}

export interface PaginatedResponse<T> {
  items: T[]
  page: number
  page_size: number
  total: number
  total_pages: number
}

export interface PaginationParams {
  page?: number
  page_size?: number
}

export interface HealthCheckResponse {
  status: string
  timestamp: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: User
}

export interface RiskGridQueryParams extends PaginationParams {
  crop_type?: CropType
  start_date?: string
  end_date?: string
  min_risk?: number
  max_risk?: number
}

export interface WeatherDataQueryParams extends PaginationParams {
  station_id?: number
  start_date?: string
  end_date?: string
}
