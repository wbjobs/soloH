<script setup lang="ts">
import { Layers, Users, Wallet, TrendingUp, Eye, Hash } from 'lucide-vue-next'
import type { AddressCluster } from '../types'
import { formatBTC, formatHash, formatPercentage } from '../utils/format'

interface Props {
  cluster: AddressCluster
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'view-detail', cluster: AddressCluster): void
}>()

const getTagColor = (tag: string) => {
  if (tag.includes('mixer') || tag.includes('混币')) return 'bg-purple-500/20 text-purple-400'
  if (tag.includes('exchange') || tag.includes('交易所')) return 'bg-blue-500/20 text-blue-400'
  if (tag.includes('market') || tag.includes('黑市')) return 'bg-red-500/20 text-red-400'
  if (tag.includes('miner') || tag.includes('矿工')) return 'bg-yellow-500/20 text-yellow-400'
  return 'bg-slate-500/20 text-slate-400'
}
</script>

<template>
  <div
    class="bg-slate-800/50 backdrop-blur-sm rounded-xl border border-slate-700/50 transition-all duration-300 hover:shadow-xl hover:border-purple-500/30 overflow-hidden"
  >
    <div class="p-4">
      <div class="flex items-start justify-between mb-4">
        <div class="flex items-center gap-3">
          <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-purple-500/20 to-pink-500/20 flex items-center justify-center">
            <Layers class="w-6 h-6 text-purple-400" />
          </div>
          <div>
            <div class="flex items-center gap-2">
              <Hash class="w-4 h-4 text-slate-500" />
              <h4 class="font-semibold text-white font-mono">{{ cluster.name || cluster.clusterId }}</h4>
            </div>
            <p class="text-xs text-slate-400 mt-0.5">
              <span v-if="cluster.avgSuspiciousScore !== undefined">
                平均风险: <span :class="[cluster.avgSuspiciousScore > 50 ? 'text-red-400' : 'text-green-400']">{{ cluster.avgSuspiciousScore.toFixed(1) }}</span>
              </span>
            </p>
          </div>
        </div>
        <span class="px-2.5 py-1 rounded-full text-xs font-medium bg-purple-500/20 text-purple-400">
          {{ cluster.size }} 地址
        </span>
      </div>

      <div class="grid grid-cols-3 gap-3 mb-4">
        <div class="bg-slate-900/50 rounded-lg p-3 text-center">
          <Wallet class="w-4 h-4 text-cyan-400 mx-auto mb-1" />
          <p class="text-lg font-bold text-white">{{ formatBTC(cluster.balance) }}</p>
          <p class="text-xs text-slate-500">余额</p>
        </div>
        <div class="bg-slate-900/50 rounded-lg p-3 text-center">
          <TrendingUp class="w-4 h-4 text-green-400 mx-auto mb-1" />
          <p class="text-lg font-bold text-white">{{ formatBTC(cluster.totalReceived) }}</p>
          <p class="text-xs text-slate-500">总收入</p>
        </div>
        <div class="bg-slate-900/50 rounded-lg p-3 text-center">
          <Users class="w-4 h-4 text-orange-400 mx-auto mb-1" />
          <p class="text-lg font-bold text-white">{{ cluster.txCount.toLocaleString() }}</p>
          <p class="text-xs text-slate-500">交易数</p>
        </div>
      </div>

      <div class="flex flex-wrap gap-1.5 mb-4">
        <span
          v-for="tag in cluster.tags.slice(0, 4)"
          :key="tag"
          class="px-2 py-0.5 rounded text-xs font-medium"
          :class="getTagColor(tag)"
        >
          {{ tag }}
        </span>
        <span v-if="cluster.tags.length > 4" class="px-2 py-0.5 rounded text-xs text-slate-500">
          +{{ cluster.tags.length - 4 }}
        </span>
      </div>

      <div class="mb-4">
        <div class="text-xs text-slate-500 mb-2">地址预览</div>
        <div class="space-y-1.5 max-h-24 overflow-y-auto">
          <div
            v-for="(addr, idx) in cluster.addresses.slice(0, 5)"
            :key="idx"
            class="flex items-center gap-2 text-xs font-mono text-slate-400 bg-slate-900/30 px-2 py-1 rounded"
          >
            <div class="w-1.5 h-1.5 rounded-full bg-purple-500"></div>
            <span class="truncate">{{ formatHash(addr, 20) }}</span>
          </div>
          <div v-if="cluster.addresses.length > 5" class="text-xs text-slate-500 pl-3.5">
            还有 {{ cluster.addresses.length - 5 }} 个地址...
          </div>
        </div>
      </div>

      <div class="flex items-center justify-between pt-3 border-t border-slate-700/50">
        <div class="text-xs text-slate-500">
          <span v-if="cluster.firstSeen">首次: {{ formatHash(cluster.firstSeen.toString(), 10) }}</span>
        </div>
        <button
          class="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-purple-500/10 text-purple-400 text-xs font-medium hover:bg-purple-500/20 transition-colors"
          @click="emit('view-detail', cluster)"
        >
          <Eye class="w-3 h-3" />
          查看详情
        </button>
      </div>
    </div>
  </div>
</template>
