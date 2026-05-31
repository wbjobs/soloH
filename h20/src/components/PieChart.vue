<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart as EPieChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent, TitleComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import type { EChartsOption } from 'echarts'

use([CanvasRenderer, EPieChart, TooltipComponent, LegendComponent, TitleComponent])

interface PieData {
  name: string
  value: number
  color?: string
}

interface Props {
  title?: string
  data: PieData[]
  height?: string
  showLegend?: boolean
  donut?: boolean
  donutSize?: [string, string]
  showLabel?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  height: '300px',
  showLegend: true,
  donut: false,
  donutSize: () => ['40%', '70%'],
  showLabel: true
})

const emit = defineEmits<{
  (e: 'click', item: PieData): void
}>()

const defaultColors = ['#22d3ee', '#818cf8', '#f472b6', '#34d399', '#fbbf24', '#f87171', '#a78bfa', '#fb923c']

const chartOption = computed<EChartsOption>(() => ({
  backgroundColor: 'transparent',
  title: props.title ? {
    text: props.title,
    textStyle: {
      color: '#e2e8f0',
      fontSize: 14,
      fontWeight: 600
    },
    left: 'center',
    top: 0
  } : undefined,
  tooltip: {
    trigger: 'item',
    backgroundColor: 'rgba(30, 41, 59, 0.95)',
    borderColor: '#475569',
    borderWidth: 1,
    padding: [12, 16],
    textStyle: {
      color: '#e2e8f0',
      fontSize: 12
    },
    formatter: (params: any) => {
      return `
        <div style="min-width: 120px;">
          <div style="font-weight: 600; margin-bottom: 4px;">${params.name}</div>
          <div style="display: flex; justify-content: space-between;">
            <span style="color: #94a3b8;">数值:</span>
            <span style="font-weight: 600;">${params.value.toLocaleString()}</span>
          </div>
          <div style="display: flex; justify-content: space-between;">
            <span style="color: #94a3b8;">占比:</span>
            <span style="font-weight: 600; color: #22d3ee;">${params.percent}%</span>
          </div>
        </div>
      `
    }
  },
  legend: props.showLegend ? {
    show: true,
    orient: 'vertical',
    right: 10,
    top: props.title ? 40 : 'center',
    textStyle: {
      color: '#94a3b8',
      fontSize: 12
    },
    icon: 'circle',
    itemWidth: 10,
    itemHeight: 10,
    itemGap: 12,
    formatter: (name: string) => {
      const item = props.data.find(d => d.name === name)
      if (!item) return name
      const total = props.data.reduce((sum, d) => sum + d.value, 0)
      const percent = ((item.value / total) * 100).toFixed(1)
      return `${name}  ${percent}%`
    }
  } : undefined,
  series: [
    {
      name: props.title || '数据分布',
      type: 'pie',
      radius: props.donut ? props.donutSize : '70%',
      center: props.showLegend ? ['35%', '55%'] : ['50%', '55%'],
      avoidLabelOverlap: true,
      itemStyle: {
        borderRadius: 6,
        borderColor: '#1e293b',
        borderWidth: 2
      },
      label: {
        show: props.showLabel,
        position: 'outside',
        color: '#e2e8f0',
        fontSize: 11,
        formatter: '{b}: {d}%'
      },
      labelLine: {
        show: props.showLabel,
        length: 10,
        length2: 10,
        lineStyle: {
          color: '#475569'
        }
      },
      emphasis: {
        label: {
          show: true,
          fontSize: 12,
          fontWeight: 'bold'
        },
        itemStyle: {
          shadowBlur: 20,
          shadowOffsetX: 0,
          shadowColor: 'rgba(0, 0, 0, 0.5)'
        },
        scale: true,
        scaleSize: 8
      },
      data: props.data.map((d, idx) => ({
        value: d.value,
        name: d.name,
        itemStyle: {
          color: d.color || defaultColors[idx % defaultColors.length]
        }
      }))
    }
  ]
}))

const handleClick = (params: { name: string }) => {
  const item = props.data.find(d => d.name === params.name)
  if (item) {
    emit('click', item)
  }
}
</script>

<template>
  <div class="bg-slate-800/50 backdrop-blur-sm rounded-xl border border-slate-700/50 p-4">
    <VChart
      :option="chartOption"
      autoresize
      :style="{ height }"
      @click="handleClick"
    />
  </div>
</template>
