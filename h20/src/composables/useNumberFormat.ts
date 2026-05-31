import { ref, computed, type Ref, type ComputedRef } from 'vue'
import { BTC_DECIMALS } from '../utils/constants'

export type NumberFormatStyle = 'decimal' | 'currency' | 'percent'

export interface UseNumberFormatOptions {
  locale?: string
  style?: NumberFormatStyle
  currency?: string
  minimumFractionDigits?: number
  maximumFractionDigits?: number
  useGrouping?: boolean
}

const DEFAULT_OPTIONS: UseNumberFormatOptions = {
  locale: 'zh-CN',
  style: 'decimal',
  currency: 'CNY',
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
  useGrouping: true
}

export function useNumberFormat(
  value: Ref<number | string | null | undefined>,
  options: UseNumberFormatOptions = {}
): {
  formatted: ComputedRef<string>
  formatNumber: (num: number | string, opts?: UseNumberFormatOptions) => string
  formatBTC: (satoshis: number | string) => string
  formatUSD: (value: number | string, btcPrice?: number) => string
  parseNumber: (str: string) => number | null
} {
  const mergedOptions = { ...DEFAULT_OPTIONS, ...options }

  function formatNumberFn(num: number | string, opts?: UseNumberFormatOptions): string {
    const currentOptions = { ...mergedOptions, ...opts }
    let parsedNum: number

    if (typeof num === 'string') {
      parsedNum = parseFloat(num)
    } else {
      parsedNum = num
    }

    if (isNaN(parsedNum)) {
      return '-'
    }

    const formatter = new Intl.NumberFormat(currentOptions.locale, {
      style: currentOptions.style,
      currency: currentOptions.currency,
      minimumFractionDigits: currentOptions.minimumFractionDigits,
      maximumFractionDigits: currentOptions.maximumFractionDigits,
      useGrouping: currentOptions.useGrouping
    })

    return formatter.format(parsedNum)
  }

  function formatBTC(satoshis: number | string): string {
    let sat: number
    if (typeof satoshis === 'string') {
      sat = parseFloat(satoshis)
    } else {
      sat = satoshis
    }

    if (isNaN(sat)) {
      return '-'
    }

    const btc = sat / Math.pow(10, BTC_DECIMALS)

    if (Math.abs(btc) >= 1) {
      return `${btc.toFixed(4)} BTC`
    } else if (Math.abs(btc) >= 0.001) {
      return `${btc.toFixed(6)} BTC`
    } else {
      return `${sat.toLocaleString()} sats`
    }
  }

  function formatUSD(val: number | string, btcPrice?: number): string {
    let num: number
    if (typeof val === 'string') {
      num = parseFloat(val)
    } else {
      num = val
    }

    if (isNaN(num)) {
      return '-'
    }

    if (btcPrice !== undefined) {
      num = num * btcPrice
    }

    return formatNumberFn(num, {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    })
  }

  function parseNumber(str: string): number | null {
    const cleaned = str.replace(/[^0-9.-]/g, '')
    const parsed = parseFloat(cleaned)
    return isNaN(parsed) ? null : parsed
  }

  const formatted = computed(() => {
    if (value.value === null || value.value === undefined) {
      return '-'
    }
    return formatNumberFn(value.value)
  })

  return {
    formatted,
    formatNumber: formatNumberFn,
    formatBTC,
    formatUSD,
    parseNumber
  }
}

export function useBTCFormat(
  value: Ref<number | string | null | undefined>
): {
  formattedBTC: ComputedRef<string>
  formattedSats: ComputedRef<string>
  toBTC: (satoshis: number) => number
  toSats: (btc: number) => number
} {
  function toBTC(satoshis: number): number {
    return satoshis / Math.pow(10, BTC_DECIMALS)
  }

  function toSats(btc: number): number {
    return Math.round(btc * Math.pow(10, BTC_DECIMALS))
  }

  const formattedBTC = computed(() => {
    if (value.value === null || value.value === undefined) {
      return '-'
    }
    let sat: number
    if (typeof value.value === 'string') {
      sat = parseFloat(value.value)
    } else {
      sat = value.value
    }
    if (isNaN(sat)) {
      return '-'
    }
    const btc = toBTC(sat)
    return `${btc.toFixed(8)} BTC`
  })

  const formattedSats = computed(() => {
    if (value.value === null || value.value === undefined) {
      return '-'
    }
    let sat: number
    if (typeof value.value === 'string') {
      sat = parseFloat(value.value)
    } else {
      sat = value.value
    }
    if (isNaN(sat)) {
      return '-'
    }
    return `${sat.toLocaleString()} sats`
  })

  return {
    formattedBTC,
    formattedSats,
    toBTC,
    toSats
  }
}
