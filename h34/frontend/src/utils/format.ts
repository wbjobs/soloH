import { format, formatDistanceToNow, parseISO, formatRelative } from 'date-fns'
import { zhCN } from 'date-fns/locale'
import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import type { CropType, RiskLevel } from '@/types'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export const formatDate = (
  date: string | Date,
  formatStr: string = 'yyyy-MM-dd'
): string => {
  const d = typeof date === 'string' ? parseISO(date) : date
  return format(d, formatStr, { locale: zhCN })
}

export const formatDateTime = (
  date: string | Date,
  formatStr: string = 'yyyy-MM-dd HH:mm:ss'
): string => {
  const d = typeof date === 'string' ? parseISO(date) : date
  return format(d, formatStr, { locale: zhCN })
}

export const formatRelativeTime = (date: string | Date): string => {
  const d = typeof date === 'string' ? parseISO(date) : date
  return formatRelative(d, new Date(), { locale: zhCN })
}

export const formatTimeAgo = (date: string | Date): string => {
  const d = typeof date === 'string' ? parseISO(date) : date
  return formatDistanceToNow(d, { addSuffix: true, locale: zhCN })
}

export const formatNumber = (
  num: number,
  decimals: number = 2,
  locale: string = 'zh-CN'
): string => {
  return new Intl.NumberFormat(locale, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(num)
}

export const formatTemperature = (temp?: number): string => {
  if (temp === undefined || temp === null) return '--'
  return `${formatNumber(temp, 1)}°C`
}

export const formatHumidity = (humidity?: number): string => {
  if (humidity === undefined || humidity === null) return '--'
  return `${formatNumber(humidity, 1)}%`
}

export const formatRainfall = (rainfall?: number): string => {
  if (rainfall === undefined || rainfall === null) return '--'
  return `${formatNumber(rainfall, 1)} mm`
}

export const formatWindSpeed = (speed?: number): string => {
  if (speed === undefined || speed === null) return '--'
  return `${formatNumber(speed, 1)} m/s`
}

export const formatPercentage = (
  value?: number,
  decimals: number = 1
): string => {
  if (value === undefined || value === null) return '--'
  return `${formatNumber(value, decimals)}%`
}

export const formatRiskIndex = (riskIndex: number): string => {
  return `${formatNumber(riskIndex, 0)} / 100`
}

export const formatConcentration = (concentration?: number): string => {
  if (concentration === undefined || concentration === null) return '--'
  return `${formatNumber(concentration, 2)} 孢子/m³`
}

export const formatCoordinates = (lat: number, lng: number): string => {
  return `${formatNumber(lat, 4)}, ${formatNumber(lng, 4)}`
}

export const formatDistance = (distance: number, unit: string = 'km'): string => {
  return `${formatNumber(distance, 2)} ${unit}`
}

export const getCropTypeLabel = (cropType: CropType): string => {
  const labels: Record<CropType, string> = {
    wheat: '小麦',
    potato: '马铃薯',
    corn: '玉米',
    rice: '水稻',
  }
  return labels[cropType] || cropType
}

export const getCropTypeColor = (cropType: CropType): string => {
  const colors: Record<CropType, string> = {
    wheat: '#f59e0b',
    potato: '#8b5cf6',
    corn: '#eab308',
    rice: '#06b6d4',
  }
  return colors[cropType] || '#6b7280'
}

export const getRiskLevelLabel = (level: RiskLevel | 'all'): string => {
  const labels: Record<RiskLevel | 'all', string> = {
    all: '全部',
    low: '低风险',
    medium: '中风险',
    high: '高风险',
    extreme: '极高风险',
  }
  return labels[level] || level
}

export const getRiskLevelColor = (level: RiskLevel): string => {
  const colors: Record<RiskLevel, string> = {
    low: '#22c55e',
    medium: '#eab308',
    high: '#f97316',
    extreme: '#ef4444',
  }
  return colors[level] || '#6b7280'
}

export const getSeverityBadgeClass = (severity: string): string => {
  const lower = severity.toLowerCase()
  if (lower.includes('高') || lower.includes('extreme') || lower.includes('high')) {
    return 'risk-extreme'
  }
  if (lower.includes('中') || lower.includes('medium')) {
    return 'risk-medium'
  }
  if (lower.includes('低') || lower.includes('low')) {
    return 'risk-low'
  }
  return 'risk-high'
}

export const truncateText = (text: string, maxLength: number): string => {
  if (text.length <= maxLength) return text
  return `${text.substring(0, maxLength)}...`
}

export const capitalizeFirstLetter = (str: string): string => {
  return str.charAt(0).toUpperCase() + str.slice(1)
}

export const getInitials = (name: string): string => {
  return name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .substring(0, 2)
}

export const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${formatNumber(bytes / Math.pow(k, i), 2)} ${sizes[i]}`
}

export const formatDuration = (minutes: number): string => {
  const hours = Math.floor(minutes / 60)
  const mins = minutes % 60
  if (hours > 0) {
    return `${hours}小时${mins > 0 ? ` ${mins}分钟` : ''}`
  }
  return `${mins}分钟`
}

export const generateId = (): string => {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
}

export const debounce = <T extends (...args: any[]) => any>(
  func: T,
  wait: number
): ((...args: Parameters<T>) => void) => {
  let timeout: ReturnType<typeof setTimeout>
  return (...args: Parameters<T>) => {
    clearTimeout(timeout)
    timeout = setTimeout(() => func(...args), wait)
  }
}

export const throttle = <T extends (...args: any[]) => any>(
  func: T,
  limit: number
): ((...args: Parameters<T>) => void) => {
  let inThrottle = false
  return (...args: Parameters<T>) => {
    if (!inThrottle) {
      func(...args)
      inThrottle = true
      setTimeout(() => {
        inThrottle = false
      }, limit)
    }
  }
}
