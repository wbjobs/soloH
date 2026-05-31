import { ADDRESS_TYPES, type AddressType } from './constants'

export function isValidBTCAddress(address: string): boolean {
  if (!address || typeof address !== 'string') {
    return false
  }

  const trimmed = address.trim()

  for (const type of Object.values(ADDRESS_TYPES)) {
    if (type.regex.test(trimmed)) {
      return true
    }
  }

  return false
}

export function getAddressType(address: string): AddressType | null {
  if (!isValidBTCAddress(address)) {
    return null
  }

  const trimmed = address.trim()

  for (const [key, type] of Object.entries(ADDRESS_TYPES)) {
    if (type.regex.test(trimmed)) {
      return key as AddressType
    }
  }

  return null
}

export function isValidTxid(txid: string): boolean {
  if (!txid || typeof txid !== 'string') {
    return false
  }

  const trimmed = txid.trim()

  const txidRegex = /^[a-fA-F0-9]{64}$/

  return txidRegex.test(trimmed)
}

export function isValidBlockHash(hash: string): boolean {
  if (!hash || typeof hash !== 'string') {
    return false
  }

  const trimmed = hash.trim()

  const blockHashRegex = /^[a-fA-F0-9]{64}$/

  return blockHashRegex.test(trimmed)
}

export function isValidBlockHeight(height: number | string): boolean {
  let num: number
  if (typeof height === 'string') {
    num = parseInt(height, 10)
    if (isNaN(num)) {
      return false
    }
  } else {
    num = height
  }

  return Number.isInteger(num) && num >= 0
}

export function isValidBTCAmount(amount: number | string): boolean {
  let num: number
  if (typeof amount === 'string') {
    num = parseFloat(amount)
    if (isNaN(num)) {
      return false
    }
  } else {
    num = amount
  }

  return !isNaN(num) && num >= 0
}

export function isValidSatoshiAmount(amount: number | string): boolean {
  let num: number
  if (typeof amount === 'string') {
    num = parseInt(amount, 10)
    if (isNaN(num)) {
      return false
    }
  } else {
    num = amount
  }

  return Number.isInteger(num) && num >= 0
}

export function isValidURL(url: string): boolean {
  if (!url || typeof url !== 'string') {
    return false
  }

  try {
    new URL(url)
    return true
  } catch {
    return false
  }
}

export function isValidEmail(email: string): boolean {
  if (!email || typeof email !== 'string') {
    return false
  }

  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return emailRegex.test(email.trim())
}

export function isValidDate(date: string | number | Date): boolean {
  let d: Date
  if (date instanceof Date) {
    d = date
  } else if (typeof date === 'string' || typeof date === 'number') {
    d = new Date(date)
  } else {
    return false
  }

  return !isNaN(d.getTime())
}

export function isValidIPFS(cid: string): boolean {
  if (!cid || typeof cid !== 'string') {
    return false
  }

  const trimmed = cid.trim()

  const cidv0Regex = /^Qm[a-zA-Z0-9]{44}$/
  const cidv1Regex = /^b[a-zA-Z0-9]{58}$/

  return cidv0Regex.test(trimmed) || cidv1Regex.test(trimmed)
}

export function validateAddress(address: string): {
  valid: boolean
  type: AddressType | null
  error?: string
} {
  if (!address) {
    return { valid: false, type: null, error: '地址不能为空' }
  }

  const trimmed = address.trim()

  if (trimmed.length < 26 || trimmed.length > 90) {
    return { valid: false, type: null, error: '地址长度不正确' }
  }

  const type = getAddressType(trimmed)

  if (!type) {
    return { valid: false, type: null, error: '无效的比特币地址格式' }
  }

  return { valid: true, type }
}

export function validateTxid(txid: string): {
  valid: boolean
  error?: string
} {
  if (!txid) {
    return { valid: false, error: '交易ID不能为空' }
  }

  const trimmed = txid.trim()

  if (trimmed.length !== 64) {
    return { valid: false, error: '交易ID长度必须为64个字符' }
  }

  if (!isValidTxid(trimmed)) {
    return { valid: false, error: '无效的交易ID格式' }
  }

  return { valid: true }
}

export function sanitizeInput(input: string): string {
  if (!input || typeof input !== 'string') {
    return ''
  }

  return input
    .trim()
    .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
    .replace(/javascript:/gi, '')
    .replace(/on\w+=/gi, '')
}

export function isEmpty(value: unknown): boolean {
  if (value === null || value === undefined) {
    return true
  }

  if (typeof value === 'string') {
    return value.trim() === ''
  }

  if (Array.isArray(value)) {
    return value.length === 0
  }

  if (typeof value === 'object') {
    return Object.keys(value as Record<string, unknown>).length === 0
  }

  return false
}

export function isDuplicate(items: unknown[], key?: string): boolean {
  if (!Array.isArray(items) || items.length < 2) {
    return false
  }

  if (key) {
    const seen = new Set()
    for (const item of items) {
      if (item && typeof item === 'object' && key in item) {
        const value = (item as Record<string, unknown>)[key]
        if (seen.has(value)) {
          return true
        }
        seen.add(value)
      }
    }
  } else {
    const seen = new Set(items)
    return seen.size !== items.length
  }

  return false
}
