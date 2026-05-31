import type { RiskLevel, CropType, RiskGrid, WeatherStation, SporeSensor } from './index'

export type LayerType = 'heatmap' | 'grid' | 'stations' | 'roads'

export interface MapLayerState {
  heatmap: boolean
  grid: boolean
  stations: boolean
  roads: boolean
}

export interface MapboxConfig {
  accessToken: string
  style: string
  center: [number, number]
  zoom: number
  minZoom: number
  maxZoom: number
  pitch: number
  bearing: number
}

export interface HeatmapLayerConfig {
  radius: number
  weight: number
  opacity: number
  intensity: number
}

export interface GridLayerConfig {
  opacity: number
  strokeWidth: number
  strokeColor: string
  highlightOpacity: number
}

export interface RiskThresholds {
  low: number
  medium: number
  high: number
  extreme: number
}

export const RISK_THRESHOLDS: RiskThresholds = {
  low: 15,
  medium: 40,
  high: 70,
  extreme: 100,
}

export interface RiskLegendItem {
  level: RiskLevel
  color: string
  label: string
  min: number
  max: number
}

export interface PopupData {
  type: 'grid' | 'station' | 'sensor'
  coordinates: [number, number]
  data: RiskGrid | WeatherStation | SporeSensor
  riskIndex?: number
}

export interface MapMouseEvent {
  lngLat: {
    lng: number
    lat: number
  }
  point: {
    x: number
    y: number
  }
  features?: Array<{
    id: string | number
    properties: Record<string, any>
    geometry: any
  }>
}

export interface HoveredFeature {
  id: string | number
  layerId: string
  properties: Record<string, any>
}

export interface MapState {
  isLoaded: boolean
  isStyleLoaded: boolean
  error: Error | null
}

export interface DateRangeOption {
  date: string
  label: string
  isForecast: boolean
}

export const RISK_COLORS: Record<RiskLevel, string> = {
  low: '#22c55e',
  medium: '#eab308',
  high: '#f97316',
  extreme: '#ef4444',
}

export const RISK_GRADIENT = [
  0, '#22c55e',
  0.15, '#22c55e',
  0.4, '#eab308',
  0.7, '#f97316',
  1, '#ef4444',
]

export const getRiskLevel = (riskIndex: number): RiskLevel => {
  if (riskIndex < RISK_THRESHOLDS.low) return 'low'
  if (riskIndex < RISK_THRESHOLDS.medium) return 'medium'
  if (riskIndex < RISK_THRESHOLDS.high) return 'high'
  return 'extreme'
}

export const getRiskColor = (riskIndex: number): string => {
  return RISK_COLORS[getRiskLevel(riskIndex)]
}

export const getRiskLegendItems = (): RiskLegendItem[] => {
  return [
    { level: 'low', color: RISK_COLORS.low, label: '低风险', min: 0, max: RISK_THRESHOLDS.low - 1 },
    { level: 'medium', color: RISK_COLORS.medium, label: '中风险', min: RISK_THRESHOLDS.low, max: RISK_THRESHOLDS.medium - 1 },
    { level: 'high', color: RISK_COLORS.high, label: '高风险', min: RISK_THRESHOLDS.medium, max: RISK_THRESHOLDS.high - 1 },
    { level: 'extreme', color: RISK_COLORS.extreme, label: '极高风险', min: RISK_THRESHOLDS.high, max: RISK_THRESHOLDS.extreme },
  ]
}

export const generateDateOptions = (days: number = 7): DateRangeOption[] => {
  const options: DateRangeOption[] = []
  const today = new Date()

  for (let i = 0; i < days; i++) {
    const date = new Date(today)
    date.setDate(today.getDate() + i)
    const dateStr = date.toISOString().split('T')[0]
    
    let label: string
    if (i === 0) {
      label = '今天'
    } else if (i === 1) {
      label = '明天'
    } else {
      label = `${date.getMonth() + 1}/${date.getDate()}`
    }

    options.push({
      date: dateStr,
      label,
      isForecast: i > 0,
    })
  }

  return options
}

export const CROP_TYPE_LABELS: Record<CropType, string> = {
  wheat: '小麦',
  potato: '马铃薯',
  corn: '玉米',
  rice: '水稻',
}
