<script setup lang="ts">
import { ref } from 'vue'
import { ArrowDownLeft, ArrowUpRight, Clock, ChevronDown, ChevronRight, ExternalLink } from 'lucide-vue-next'
import type { Transaction } from '../types'
import { formatBTC, formatTimestamp, formatHash } from '../utils/format'

interface Props {
  transactions: Transaction[]
  maxItems?: number
}

const props = withDefaults(defineProps<Props>(), {
  maxItems: 10
})

const emit = defineEmits<{
  (e: 'transaction-click', tx: Transaction): void
}>()

const expandedId = ref<string | null>(null)

const displayTransactions = () => {
  return props.transactions.slice(0, props.maxItems)
}

const toggleExpand = (id: string) => {
  expandedId.value = expandedId.value === id ? null : id
}

const isIncome = (tx: Transaction): boolean => {
  return tx.inputs.some(input => input.prevAddress) || false
}

const getAmount = (tx: Transaction): number => {
  return isIncome(tx) ? (tx.outputValue || tx.totalOutput) : (tx.inputValue || tx.totalInput)
}
</script>

<template>
  <div class="bg-slate-800/50 backdrop-blur-sm rounded-xl border border-slate-700/50 overflow-hidden">
    <div class="px-4 py-3 border-b border-slate-700/50">
      <h3 class="text-lg font-semibold text-white">交易历史</h3>
      <p class="text-sm text-slate-400 mt-0.5">最近 {{ Math.min(transactions.length, maxItems) }} 笔交易</p>
    </div>

    <div class="divide-y divide-slate-700/50 max-h-[500px] overflow-y-auto">
      <div
        v-for="(tx, index) in displayTransactions()"
        :key="tx.txid"
        class="relative group"
      >
        <div class="absolute left-6 top-0 bottom-0 w-0.5 bg-slate-700/50"></div>

        <div
          class="relative px-4 py-3 hover:bg-slate-700/30 transition-colors cursor-pointer"
          @click="toggleExpand(tx.txid)"
        >
          <div class="flex items-start gap-4">
            <div class="relative z-10">
              <div
                class="w-8 h-8 rounded-full flex items-center justify-center"
                :class="[
                  isIncome(tx)
                    ? 'bg-green-500/20 text-green-400'
                    : 'bg-red-500/20 text-red-400'
                ]"
              >
                <ArrowDownLeft v-if="isIncome(tx)" class="w-4 h-4" />
                <ArrowUpRight v-else class="w-4 h-4" />
              </div>
            </div>

            <div class="flex-1 min-w-0">
              <div class="flex items-center justify-between gap-2">
                <div class="flex items-center gap-2">
                  <span class="text-sm font-medium text-white truncate">
                    {{ formatHash(tx.txid, 12) }}
                  </span>
                  <span
                    class="px-2 py-0.5 rounded text-xs font-medium"
                    :class="[
                      isIncome(tx)
                        ? 'bg-green-500/10 text-green-400'
                        : 'bg-red-500/10 text-red-400'
                    ]"
                  >
                    {{ isIncome(tx) ? '收入' : '支出' }}
                  </span>
                </div>
                <span
                  class="text-sm font-mono font-semibold flex-shrink-0"
                  :class="[
                    isIncome(tx) ? 'text-green-400' : 'text-red-400'
                  ]"
                >
                  {{ isIncome(tx) ? '+' : '-' }}{{ formatBTC(getAmount(tx)) }}
                </span>
              </div>

              <div class="flex items-center justify-between mt-1">
                <div class="flex items-center gap-1.5 text-xs text-slate-500">
                  <Clock class="w-3 h-3" />
                  <span>{{ formatTimestamp(tx.blockTime, 'relative') }}</span>
                </div>
                <div class="flex items-center gap-1">
                  <span v-if="tx.suspiciousScore !== undefined && tx.suspiciousScore > 50" class="px-1.5 py-0.5 rounded bg-red-500/10 text-red-400 text-xs">
                    风险 {{ tx.suspiciousScore.toFixed(0) }}
                  </span>
                  <ChevronDown
                    v-if="expandedId === tx.txid"
                    class="w-4 h-4 text-slate-500 transition-transform duration-200"
                  />
                  <ChevronRight
                    v-else
                    class="w-4 h-4 text-slate-500 transition-transform duration-200"
                  />
                </div>
              </div>

              <Transition name="expand">
                <div v-if="expandedId === tx.txid" class="mt-3 pt-3 border-t border-slate-700/50">
                  <div class="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <p class="text-slate-500 text-xs mb-1">区块高度</p>
                      <p class="text-slate-300 font-mono">{{ tx.blockHeight || '-' }}</p>
                    </div>
                    <div>
                      <p class="text-slate-500 text-xs mb-1">确认数</p>
                      <p class="text-slate-300">{{ tx.confirmations || '-' }}</p>
                    </div>
                    <div>
                      <p class="text-slate-500 text-xs mb-1">矿工费</p>
                      <p class="text-slate-300 font-mono">{{ tx.fee ? formatBTC(tx.fee) : '-' }}</p>
                    </div>
                    <div>
                      <p class="text-slate-500 text-xs mb-1">输入/输出</p>
                      <p class="text-slate-300">{{ tx.inputCount }} / {{ tx.outputCount }}</p>
                    </div>
                  </div>

                  <div class="mt-3 flex items-center justify-end">
                    <button
                      class="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-cyan-500/10 text-cyan-400 text-xs font-medium hover:bg-cyan-500/20 transition-colors"
                      @click.stop="emit('transaction-click', tx)"
                    >
                      <ExternalLink class="w-3 h-3" />
                      查看详情
                    </button>
                  </div>
                </div>
              </Transition>
            </div>
          </div>
        </div>
      </div>

      <div
        v-if="transactions.length === 0"
        class="px-4 py-12 text-center"
      >
        <p class="text-slate-500">暂无交易记录</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.expand-enter-active,
.expand-leave-active {
  transition: all 0.3s ease;
  overflow: hidden;
}

.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
}

.expand-enter-to,
.expand-leave-from {
  opacity: 1;
  max-height: 200px;
}
</style>
