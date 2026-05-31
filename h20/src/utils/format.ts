import { BTC_DECIMALS } from './constants'

export function formatBTC(value: number | string | null | undefined, unit: 'auto' | 'btc' | 'sats' = 'auto'): string {
  if (value === null || value === undefined) {
    return '-'
  }

  let num: number
  if (typeof value === 'string') {
    num = parseFloat(value)
  } else {
    num = value
  }

  if (isNaN(num)) {
    return '-'
  }

  let btc: number
  let sats: number

  if (unit === 'btc') {
    btc = num
    sats = num * Math.pow(10, BTC_DECIMALS)
  } else if (unit === 'sats') {
    btc = num / Math.pow(10, BTC_DECIMALS)
    sats = num
  } else {
    if (Math.abs(num) >= 1e6) {
      btc = num / Math.pow(10, BTC_DECIMALS)
      sats = num
    } else {
      btc = num
      sats = num * Math.pow(10, BTC_DECIMALS)
    }
  }

  if (Math.abs(btc) >= 1) {
    return `${btc.toLocaleString('zh-CN', { minimumFractionDigits: 4, maximumFractionDigits: 4 })} BTC`
  } else if (Math.abs(btc) >= 0.001) {
    return `${btc.toLocaleString('zh-CN', { minimumFractionDigits: 6, maximumFractionDigits: 6 })} BTC`
  } else if (Math.abs(btc) >= 0.00000001) {
    return `${Math.round(sats).toLocaleString('zh-CN')} sats`
  } else if (Math.abs(btc) > 0) {
    return `${btc.toLocaleString('zh-CN', { minimumFractionDigits: 8, maximumFractionDigits: 8 })} BTC`
  } else {
    return '0 BTC'
  }
}

export function formatUSD(
  value: number | string | null | undefined,
  btcPrice?: number
): string {
  if (value === null || value === undefined) {
    return '-'
  }

  let num: number
  if (typeof value === 'string') {
    num = parseFloat(value)
  } else {
    num = value
  }

  if (isNaN(num)) {
    return '-'
  }

  if (btcPrice !== undefined) {
    const btc = num / Math.pow(10, BTC_DECIMALS)
    num = btc * btcPrice
  }

  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(num)
}

export function formatHash(
  hash: string | null | undefined,
  length: number = 8
): string {
  if (!hash) {
    return '-'
  }

  if (hash.length <= length * 2) {
    return hash
  }

  const prefix = hash.slice(0, length)
  const suffix = hash.slice(-length)
  return `${prefix}...${suffix}`
}

export function formatTimestamp(
  timestamp: Date | string | number | null | undefined,
  format: 'full' | 'date' | 'time' | 'relative' = 'full'
): string {
  if (timestamp === null || timestamp === undefined) {
    return '-'
  }

  let date: Date
  if (timestamp instanceof Date) {
    date = timestamp
  } else if (typeof timestamp === 'string') {
    date = new Date(timestamp)
  } else if (typeof timestamp === 'number') {
    date = new Date(timestamp)
  } else {
    return '-'
  }

  if (isNaN(date.getTime())) {
    return '-'
  }

  if (format === 'relative') {
    return formatRelativeTime(date)
  }

  const pad = (n: number) => n.toString().padStart(2, '0')

  const year = date.getFullYear()
  const month = pad(date.getMonth() + 1)
  const day = pad(date.getDate())
  const hours = pad(date.getHours())
  const minutes = pad(date.getMinutes())
  const seconds = pad(date.getSeconds())

  switch (format) {
    case 'date':
      return `${year}-${month}-${day}`
    case 'time':
      return `${hours}:${minutes}:${seconds}`
    case 'full':
    default:
      return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
  }
}

function formatRelativeTime(date: Date): string {
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const absDiff = Math.abs(diff)
  const isPast = diff > 0

  const rtf = new Intl.RelativeTimeFormat('zh-CN', { numeric: 'auto' })

  const seconds = Math.floor(absDiff / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)
  const weeks = Math.floor(days / 7)
  const months = Math.floor(days / 30)
  const years = Math.floor(days / 365)

  const value = isPast ? -1 : 1

  if (seconds < 60) {
    return isPast ? '刚刚' : '即将'
  } else if (minutes < 60) {
    return rtf.format(minutes * value, 'minute')
  } else if (hours < 24) {
    return rtf.format(hours * value, 'hour')
  } else if (days < 7) {
    return rtf.format(days * value, 'day')
  } else if (weeks < 4) {
    return rtf.format(weeks * value, 'week')
  } else if (months < 12) {
    return rtf.format(months * value, 'month')
  } else {
    return rtf.format(years * value, 'year')
  }
}

export function formatBytes(
  bytes: number | null | undefined,
  decimals: number = 2
): string {
  if (bytes === null || bytes === undefined || bytes === 0) {
    return '0 B'
  }

  const k = 1024
  const dm = decimals < 0 ? 0 : decimals
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']

  const i = Math.floor(Math.log(bytes) / Math.log(k))

  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`
}

export function formatPercentage(
  value: number | null | undefined,
  decimals: number = 2
): string {
  if (value === null || value === undefined) {
    return '-'
  }

  if (isNaN(value)) {
    return '-'
  }

  return `${value.toFixed(decimals)}%`
}

export function formatNumber(
  value: number | string | null | undefined,
  decimals: number = 0
): string {
  if (value === null || value === undefined) {
    return '-'
  }

  let num: number
  if (typeof value === 'string') {
    num = parseFloat(value)
  } else {
    num = value
  }

  if (isNaN(num)) {
    return '-'
  }

  return num.toLocaleString('zh-CN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  })
}

export function formatDate(
  date: Date | string | number | null | undefined,
  format: 'full' | 'date' | 'time' | 'relative' = 'date'
): string {
  return formatTimestamp(date, format)
}

export function truncateText(
  text: string | null | undefined,
  maxLength: number = 50,
  suffix: string = '...'
): string {
  if (!text) {
    return '-'
  }

  if (text.length <= maxLength) {
    return text
  }

  return text.slice(0, maxLength - suffix.length) + suffix
}
