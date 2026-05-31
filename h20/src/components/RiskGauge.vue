<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { GaugeChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import type { EChartsOption } from 'echarts'

use([CanvasRenderer, GaugeChart, TitleComponent, TooltipComponent])

interface Props {
  score: number
  title?: string
  showAnimation?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  title: '风险评分',
  showAnimation: true
})

const getRiskLevel = (score: number): { label: string; color: string; bgColor: string } => {
  if (score >= 80) return { label: '严重', color: '#ef4444', bgColor: 'bg-red-500/20' }
  if (score >= 60) return { label: '高', color: '#f97316', bgColor: 'bg-orange-500/20' }
  if (score >= 40) return { label: '中', color: '#eab308', bgColor: 'bg-yellow-500/20' }
  return { label: '低', color: '#22c55e', bgColor: 'bg-green-500/20' }
}

const riskLevel = computed(() => getRiskLevel(props.score))

const chartOption = computed<EChartsOption>(() => ({
  series: [
    {
      type: 'gauge',
      startAngle: 200,
      endAngle: -20,
      min: 0,
      max: 100,
      splitNumber: 10,
      radius: '90%',
      center: ['50%', '60%'],
      axisLine: {
        lineStyle: {
          width: 12,
          color: [
            [0.4, '#22c55e'],
            [0.6, '#eab308'],
            [0.8, '#f97316'],
            [1, '#ef4444']
          ]
        }
      },
      pointer: {
        icon: 'path://M12.8,0.7l12,40.1H0.7L12.8,0.7z',
        length: '60%',
        width: 10,
        offsetCenter: [0, '-10%'],
        itemStyle: {
          color: riskLevel.value.color
        }
      },
      axisTick: {
        length: 8,
        lineStyle: {
          color: 'rgba(255,255,255,0.3)',
          width: 1
        }
      },
      splitLine: {
        length: 14,
        lineStyle: {
          color: 'rgba(255,255,255,0.5)',
          width: 2
        }
      },
      axisLabel: {
        color: '#94a3b8',
        fontSize: 11,
        distance: -30,
        formatter: (value: number) => {
          if (value === 0 || value === 20 || value === 40 || value === 60 || value === 80 || value === 100) {
            return value.toString()
          }
          return ''
        }
      },
      title: {
        offsetCenter: [0, '30%'],
        fontSize: 14,
        color: '#94a3b8'
      },
      detail: {
        fontSize: 36,
        fontWeight: 'bold',
        offsetCenter: [0, '5%'],
        formatter: '{value}',
        color: riskLevel.value.color
      },
      data: [
        {
          value: props.score,
          name: props.title
        }
      ],
      animationDuration: props.showAnimation ? 2000 : 0,
      animationEasing: 'cubicOut'
    }
  ]
}))
</script>

<template>
  <div class="bg-slate-800/50 backdrop-blur-sm rounded-xl border border-slate-700/50 p-5">
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-lg font-semibold text-white">{{ title }}</h3>
      <span
        class="px-3 py-1 rounded-full text-xs font-medium"
        :class="[riskLevel.bgColor, 'text-' + riskLevel.color.replace('#', '')]"
        :style="{ color: riskLevel.color }"
      >
        {{ riskLevel.label }}风险
      </span>
    </div>

    <div class="h-56">
      <VChart :option="chartOption" autoresize class="w-full h-full" />
    </div>

    <div class="grid grid-cols-4 gap-2 mt-4">
      <div class="text-center">
        <div class="w-3 h-3 rounded-full bg-green-500 mx-auto mb-1"></div>
        <span class="text-xs text-slate-500">低</span>
        <p class="text-xs text-slate-400">0-39</p>
      </div>
      <div class="text-center">
        <div class="w-3 h-3 rounded-full bg-yellow-500 mx-auto mb-1"></div>
        <span class="text-xs text-slate-500">中</span>
        <p class="text-xs text-slate-400">40-59</p>
      </div>
      <div class="text-center">
        <div class="w-3 h-3 rounded-full bg-orange-500 mx-auto mb-1"></div>
        <span class="text-xs text-slate-500">高</span>
        <p class="text-xs text-slate-400">60-79</p>
      </div>
      <div class="text-center">
        <div class="w-3 h-3 rounded-full bg-red-500 mx-auto mb-1"></div>
        <span class="text-xs text-slate-500">严重</span>
        <p class="text-xs text-slate-400">80-100</p>
      </div>
    </div>
  </div>
</template>
