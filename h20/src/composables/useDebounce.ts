import { ref, watch, type Ref, type WatchSource } from 'vue'

export interface UseDebounceOptions<T> {
  delay?: number
  immediate?: boolean
  maxWait?: number
  leading?: boolean
  trailing?: boolean
}

export function useDebounce<T>(
  source: WatchSource<T>,
  options: UseDebounceOptions<T> = {}
): Ref<T> {
  const { delay = 300, immediate = false, maxWait, leading = false, trailing = true } = options

  const debounced = ref<T>() as Ref<T>
  let timer: ReturnType<typeof setTimeout> | null = null
  let maxTimer: ReturnType<typeof setTimeout> | null = null
  let lastInvokeTime = 0
  let leadingValue: T | undefined

  function invoke(value: T) {
    lastInvokeTime = Date.now()
    debounced.value = value
  }

  function clearTimers() {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
    if (maxTimer) {
      clearTimeout(maxTimer)
      maxTimer = null
    }
  }

  watch(
    source,
    (newValue, oldValue) => {
      if (immediate && oldValue === undefined) {
        invoke(newValue)
        return
      }

      const now = Date.now()
      const isLeading = leading && !timer

      if (isLeading) {
        leadingValue = newValue
        invoke(newValue)
      }

      if (timer) {
        clearTimeout(timer)
      }

      if (maxWait && !maxTimer) {
        maxTimer = setTimeout(() => {
          if (trailing) {
            invoke(newValue)
          }
          clearTimers()
        }, maxWait)
      }

      timer = setTimeout(() => {
        if (trailing && !isLeading) {
          invoke(newValue)
        }
        clearTimers()
      }, delay)
    },
    { immediate }
  )

  return debounced
}

export function useDebounceFn<T extends (...args: unknown[]) => unknown>(
  fn: T,
  delay: number = 300
): {
  run: T
  cancel: () => void
  flush: () => void
  pending: Ref<boolean>
} {
  let timer: ReturnType<typeof setTimeout> | null = null
  let lastArgs: unknown[] | null = null
  let lastThis: unknown = null
  const pending = ref(false)

  function invoke() {
    if (lastArgs && lastThis) {
      pending.value = false
      fn.apply(lastThis, lastArgs)
      lastArgs = null
      lastThis = null
    }
  }

  function cancel() {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
    pending.value = false
    lastArgs = null
    lastThis = null
  }

  function flush() {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
    invoke()
  }

  function run(this: unknown, ...args: unknown[]) {
    lastArgs = args
    lastThis = this
    pending.value = true

    if (timer) {
      clearTimeout(timer)
    }

    timer = setTimeout(() => {
      timer = null
      invoke()
    }, delay)
  }

  return {
    run: run as T,
    cancel,
    flush,
    pending
  }
}
