<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart as EBarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, TitleComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import type { EChartsOption } from 'echarts'

use([CanvasRenderer, EBarChart, GridComponent, TooltipComponent, LegendComponent, TitleComponent])

interface SeriesData {
  name: string
  data: number[]
  color?: string
}

interface Props {
  title?: string
  xAxisData: string[]
  series: SeriesData[]
  height?: string
  showLegend?: boolean
  horizontal?: boolean
  stack?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  height: '300px',
  showLegend: true,
  horizontal: false,
  stack: false
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
      type: props.horizontal ? 'shadow' : 'shadow',
      shadowStyle: {
        color: 'rgba(255, 255, 255, 0.05)'
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
    itemHeight: 12
  } : undefined,
  grid: {
    left: 0,
    right: 10,
    top: props.title ? 70 : 40,
    bottom: 0,
    containLabel: true
  },
  xAxis: props.horizontal ? {
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
  } : {
    type: 'category',
    data: props.xAxisData,
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
      fontSize: 11,
      rotate: props.xAxisData.length > 6 ? 45 : 0
    }
  },
  yAxis: props.horizontal ? {
    type: 'category',
    data: props.xAxisData,
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
  } : {
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
    type: 'bar',
    data: s.data,
    stack: props.stack ? 'total' : undefined,
    barWidth: '60%',
    itemStyle: {
      color: s.color || defaultColors[idx % defaultColors.length],
      borderRadius: props.stack && idx < props.series.length - 1 ? 0 : props.horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0]
    },
    emphasis: {
      focus: 'series',
      itemStyle: {
        shadowBlur: 10,
        shadowColor: 'rgba(0, 0, 0, 0.3)'
      }
    }
  }))
}))
</script>

<template>
  <div class="bg-slate-800/50 backdrop-blur-sm rounded-xl border border-slate-700/50 p-4">
    <VChart :option="chartOption" autoresize :style="{ height }" />
  </div>
</template>
