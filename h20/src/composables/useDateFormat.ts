import { ref, computed, type Ref, type ComputedRef } from 'vue'

export type DateFormat =
  | 'YYYY-MM-DD'
  | 'YYYY-MM-DD HH:mm:ss'
  | 'YYYY-MM-DD HH:mm'
  | 'MM/DD/YYYY'
  | 'DD/MM/YYYY'
  | 'relative'
  | 'timestamp'

export interface UseDateFormatOptions {
  format?: DateFormat
  locale?: string
  timezone?: string
}

const DEFAULT_OPTIONS: UseDateFormatOptions = {
  format: 'YYYY-MM-DD HH:mm:ss',
  locale: 'zh-CN',
  timezone: 'Asia/Shanghai'
}

function padZero(num: number, length: number = 2): string {
  return num.toString().padStart(length, '0')
}

function formatDate(date: Date, format: DateFormat): string {
  const year = date.getFullYear()
  const month = padZero(date.getMonth() + 1)
  const day = padZero(date.getDate())
  const hours = padZero(date.getHours())
  const minutes = padZero(date.getMinutes())
  const seconds = padZero(date.getSeconds())

  switch (format) {
    case 'YYYY-MM-DD':
      return `${year}-${month}-${day}`
    case 'YYYY-MM-DD HH:mm:ss':
      return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
    case 'YYYY-MM-DD HH:mm':
      return `${year}-${month}-${day} ${hours}:${minutes}`
    case 'MM/DD/YYYY':
      return `${month}/${day}/${year}`
    case 'DD/MM/YYYY':
      return `${day}/${month}/${year}`
    case 'timestamp':
      return date.getTime().toString()
    default:
      return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
  }
}

function formatRelative(date: Date, locale: string = 'zh-CN'): string {
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const absDiff = Math.abs(diff)
  const isPast = diff > 0

  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' })

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

export function useDateFormat(
  date: Ref<Date | string | number | null | undefined>,
  options: UseDateFormatOptions = {}
): {
  formatted: ComputedRef<string>
  formatDate: (date: Date | string | number, fmt?: DateFormat) => string
  formatRelative: (date: Date | string | number) => string
} {
  const mergedOptions = { ...DEFAULT_OPTIONS, ...options }
  const currentFormat = ref<DateFormat>(mergedOptions.format || 'YYYY-MM-DD HH:mm:ss')

  function parseDate(value: Date | string | number | null | undefined): Date | null {
    if (value === null || value === undefined) {
      return null
    }
    if (value instanceof Date) {
      return value
    }
    if (typeof value === 'string') {
      const parsed = new Date(value)
      return isNaN(parsed.getTime()) ? null : parsed
    }
    if (typeof value === 'number') {
      return new Date(value)
    }
    return null
  }

  const formatted = computed(() => {
    const parsedDate = parseDate(date.value)
    if (!parsedDate) {
      return '-'
    }
    if (currentFormat.value === 'relative') {
      return formatRelative(parsedDate, mergedOptions.locale)
    }
    return formatDate(parsedDate, currentFormat.value)
  })

  function formatDateFn(input: Date | string | number, fmt?: DateFormat): string {
    const parsed = parseDate(input)
    if (!parsed) {
      return '-'
    }
    const formatToUse = fmt || currentFormat.value
    if (formatToUse === 'relative') {
      return formatRelative(parsed, mergedOptions.locale)
    }
    return formatDate(parsed, formatToUse)
  }

  function formatRelativeFn(input: Date | string | number): string {
    const parsed = parseDate(input)
    if (!parsed) {
      return '-'
    }
    return formatRelative(parsed, mergedOptions.locale)
  }

  return {
    formatted,
    formatDate: formatDateFn,
    formatRelative: formatRelativeFn
  }
}

export function useNow(updateInterval: number = 1000): Ref<Date> {
  const now = ref(new Date())

  const timer = setInterval(() => {
    now.value = new Date()
  }, updateInterval)

  return now
}
