<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart as ELineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, TitleComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import type { EChartsOption } from 'echarts'

use([CanvasRenderer, ELineChart, GridComponent, TooltipComponent, LegendComponent, TitleComponent])

interface SeriesData {
  name: string
  data: number[]
  color?: string
  areaStyle?: boolean
}

interface Props {
  title?: string
  xAxisData: string[]
  series: SeriesData[]
  height?: string
  showLegend?: boolean
  smooth?: boolean
  showArea?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  height: '300px',
  showLegend: true,
  smooth: true,
  showArea: false
})

const defaultColors = ['#22d3ee', '#818cf8', '#f472b6', '#34d399', '#fbbf24']

const chartOption = computed<EChartsOption>(() => ({
  backgroundColor: 'transparent',
  title: props.title ? {
    text: props.title,
    textStyle: {
      color: '#e2e8f0',
      fontSize: 14,
      fontWeight: 600
    },
    left: 0,
    top: 0
  } : undefined,
  tooltip: {
    trigger: 'axis',
    backgroundColor: 'rgba(30, 41, 59, 0.95)',
    borderColor: '#475569',
    borderWidth: 1,
    padding: [12, 16],
    textStyle: {
      color: '#e2e8f0',
      fontSize: 12
    },
    axisPointer: {
      type: 'cross',
      lineStyle: {
        color: '#475569',
        type: 'dashed'
      },
      crossStyle: {
        color: '#475569'
      }
    }
  },
  legend: props.showLegend ? {
    show: true,
    top: props.title ? 30 : 0,
    right: 0,
    textStyle: {
      color: '#94a3b8',
      fontSize: 12
    },
    icon: 'roundRect',
    itemWidth: 12,
    itemHeight: 4
  } : undefined,
  grid: {
    left: 0,
    right: 10,
    top: props.title ? 70 : 40,
    bottom: 0,
    containLabel: true
  },
  xAxis: {
    type: 'category',
    data: props.xAxisData,
    boundaryGap: false,
    axisLine: {
      lineStyle: {
        color: '#334155'
      }
    },
    axisTick: {
      show: false
    },
    axisLabel: {
      color: '#64748b',
      fontSize: 11
    }
  },
  yAxis: {
    type: 'value',
    splitLine: {
      lineStyle: {
        color: '#334155',
        type: 'dashed'
      }
    },
    axisLine: {
      show: false
    },
    axisTick: {
      show: false
    },
    axisLabel: {
      color: '#64748b',
      fontSize: 11
    }
  },
  series: props.series.map((s, idx) => ({
    name: s.name,
    type: 'line',
    data: s.data,
    smooth: props.smooth,
    symbol: 'circle',
    symbolSize: 6,
    showSymbol: false,
    lineStyle: {
      width: 2,
      color: s.color || defaultColors[idx % defaultColors.length]
    },
    itemStyle: {
      color: s.color || defaultColors[idx % defaultColors.length],
      borderWidth: 2,
      borderColor: '#1e293b'
    },
    emphasis: {
      focus: 'series',
      itemStyle: {
        symbolSize: 8,
        borderWidth: 3
      }
    },
    areaStyle: (props.showArea || s.areaStyle) ? {
      color: {
        type: 'linear',
        x: 0,
        y: 0,
        x2: 0,
        y2: 1,
        colorStops: [
          { offset: 0, color: `${s.color || defaultColors[idx % defaultColors.length]}40` },
          { offset: 1, color: `${s.color || defaultColors[idx % defaultColors.length]}00` }
        ]
      }
    } : undefined
  }))
}))
</script>

<template>
  <div class="bg-slate-800/50 backdrop-blur-sm rounded-xl border border-slate-700/50 p-4">
    <VChart :option="chartOption" autoresize :style="{ height }" />
  </div>
</template>
