<script setup lang="ts">
import { computed } from 'vue'
import { TrendingUp, TrendingDown, type LucideIcon } from 'lucide-vue-next'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart as ELineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import type { EChartsOption } from 'echarts'

use([CanvasRenderer, ELineChart, GridComponent, TooltipComponent])

interface Props {
  title: string
  value: number | string
  icon: LucideIcon
  trend?: number
  trendLabel?: string
  gradientFrom?: string
  gradientTo?: string
  chartData?: number[]
  format?: 'number' | 'currency' | 'percentage' | 'btc'
}

const props = withDefaults(defineProps<Props>(), {
  gradientFrom: 'from-cyan-500',
  gradientTo: 'to-blue-600',
  format: 'number'
})

const formatValue = (val: number | string): string => {
  if (typeof val === 'string') return val
  switch (props.format) {
    case 'currency':
      return new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' }).format(val)
    case 'percentage':
      return `${val.toFixed(2)}%`
    case 'btc':
      return `${(val / 100000000).toFixed(4)} BTC`
    default:
      return val.toLocaleString('zh-CN')
  }
}

const displayValue = computed(() => formatValue(props.value))

const isPositiveTrend = computed(() => (props.trend ?? 0) >= 0)

const chartOption = computed<EChartsOption | null>(() => {
  if (!props.chartData || props.chartData.length === 0) return null
  return {
    grid: {
      left: 0,
      right: 0,
      top: 0,
      bottom: 0
    },
    xAxis: {
      type: 'category',
      show: false,
      data: props.chartData.map((_, i) => i)
    },
    yAxis: {
      type: 'value',
      show: false
    },
    series: [{
      type: 'line',
      data: props.chartData,
      smooth: true,
      symbol: 'none',
      lineStyle: {
        color: 'rgba(255, 255, 255, 0.6)',
        width: 2
      },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0,
          y: 0,
          x2: 0,
          y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(255, 255, 255, 0.3)' },
            { offset: 1, color: 'rgba(255, 255, 255, 0)' }
          ]
        }
      }
    }],
    tooltip: {
      show: false
    }
  }
})
</script>

<template>
  <div
    class="relative overflow-hidden rounded-xl p-5 transition-all duration-300 hover:scale-[1.02] hover:shadow-xl group"
    :class="[
      'bg-gradient-to-br',
      gradientFrom,
      gradientTo
    ]"
  >
    <div class="absolute top-0 right-0 w-32 h-32 bg-white/5 rounded-full -translate-y-1/2 translate-x-1/2 group-hover:scale-150 transition-transform duration-500"></div>
    <div class="absolute bottom-0 left-0 w-24 h-24 bg-white/5 rounded-full translate-y-1/2 -translate-x-1/2 group-hover:scale-150 transition-transform duration-500"></div>

    <div class="relative z-10">
      <div class="flex items-start justify-between mb-4">
        <div
          class="w-12 h-12 rounded-xl bg-white/15 backdrop-blur-sm flex items-center justify-center"
        >
          <component :is="icon" class="w-6 h-6 text-white" />
        </div>
        <div
          v-if="trend !== undefined"
          class="flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium"
          :class="[
            isPositiveTrend
              ? 'bg-green-500/20 text-green-100'
              : 'bg-red-500/20 text-red-100'
          ]"
        >
          <TrendingUp v-if="isPositiveTrend" class="w-3.5 h-3.5" />
          <TrendingDown v-else class="w-3.5 h-3.5" />
          <span>{{ Math.abs(trend).toFixed(1) }}%</span>
        </div>
      </div>

      <div class="mb-1">
        <p class="text-sm text-white/70 font-medium">{{ title }}</p>
      </div>

      <div class="flex items-baseline gap-2 mb-3">
        <h3 class="text-3xl font-bold text-white tracking-tight">{{ displayValue }}</h3>
        <span v-if="trendLabel" class="text-xs text-white/60">{{ trendLabel }}</span>
      </div>

      <div v-if="chartOption" class="h-16 -mx-2 -mb-2">
        <VChart :option="chartOption" autoresize class="w-full h-full" />
      </div>
    </div>
  </div>
</template>
