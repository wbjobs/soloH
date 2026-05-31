<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue';
import * as echarts from 'echarts';
import type { ManhattanPoint } from '@/types';

interface Props {
  data: ManhattanPoint[];
  threshold?: number;
  height?: string;
  loading?: boolean;
  mode?: 'pvalue' | 'pip';
  title?: string;
}

const props = withDefaults(defineProps<Props>(), {
  threshold: 5e-8,
  height: '500px',
  loading: false,
  mode: 'pvalue',
  title: undefined,
});

const emit = defineEmits<{
  (e: 'snpClick', snp: ManhattanPoint): void;
}>();

const chartRef = ref<HTMLDivElement | null>(null);
let chartInstance: echarts.ECharts | null = null;

const thresholdLog10 = computed(() => {
  if (props.mode === 'pip') {
    return props.threshold;
  }
  return -Math.log10(props.threshold);
});

const isPipMode = computed(() => props.mode === 'pip');

const yAxisName = computed(() => {
  if (props.mode === 'pip') return '后验包含概率 (PIP)';
  return '-log10(P-value)';
});

const chartTitle = computed(() => {
  if (props.title) return props.title;
  if (props.mode === 'pip') return '精细定位 PIP 图';
  return '曼哈顿图 (Manhattan Plot)';
});

const chrColors = [
  '#165DFF', '#00B42A', '#FF7D00', '#86909C', '#722ED1',
  '#F53F3F', '#14C9C9', '#FB7AFC', '#3D7FFF', '#4CAF50'
];

const initChart = () => {
  if (!chartRef.value) return;
  
  if (chartInstance) {
    chartInstance.dispose();
  }
  
  chartInstance = echarts.init(chartRef.value, undefined, { renderer: 'canvas' });
  
  chartInstance.on('click', (params: any) => {
    if (params.data && params.data.raw) {
      emit('snpClick', params.data.raw);
    }
  });
  
  window.addEventListener('resize', handleResize);
};

const handleResize = () => {
  chartInstance?.resize();
};

const renderChart = () => {
  if (!chartInstance || !props.data || props.data.length === 0) return;
  
  const data = props.data;
  
  const chromOrder = Array.from(new Set(data.map(d => d.chr)))
    .sort((a, b) => {
      const numA = parseInt(a);
      const numB = parseInt(b);
      if (!isNaN(numA) && !isNaN(numB)) return numA - numB;
      return a.localeCompare(b);
    });
  
  const chromSpacing = 50000000;
  let cumulativePos = 0;
  const chromOffsets: Record<string, number> = {};
  const chromMidpoints: { chr: string; midpoint: number }[] = [];
  
  for (const chr of chromOrder) {
    chromOffsets[chr] = cumulativePos;
    const chrData = data.filter(d => d.chr === chr);
    const maxPos = Math.max(...chrData.map(d => d.pos));
    chromMidpoints.push({ chr, midpoint: cumulativePos + maxPos / 2 });
    cumulativePos += maxPos + chromSpacing;
  }
  
  const seriesData: any[][] = [];
  const scatterData: any[] = [];
  
  chromOrder.forEach((chr, chrIndex) => {
    const chrData = data.filter(d => d.chr === chr);
    const color = chrColors[chrIndex % chrColors.length];
    
    chrData.forEach(point => {
      const x = chromOffsets[chr] + point.pos;
      const y = isPipMode.value ? (point.pip ?? 0) : point.log10P;
      const isSignificant = y >= thresholdLog10.value;
      
      let pointColor = color;
      if (isPipMode.value) {
        const pip = point.pip ?? 0;
        if (pip >= 0.9) {
          pointColor = '#F53F3F';
        } else if (pip >= 0.5) {
          pointColor = '#00B42A';
        } else if (pip >= 0.1) {
          pointColor = '#FF7D00';
        } else {
          pointColor = '#334155';
        }
      } else {
        pointColor = isSignificant ? '#FF7D00' : color;
      }
      
      scatterData.push({
        value: [x, y],
        raw: point,
        itemStyle: {
          color: pointColor,
          opacity: isSignificant ? 0.9 : 0.8,
          borderColor: isSignificant ? '#FFFFFF' : 'transparent',
          borderWidth: isSignificant ? 1 : 0,
        },
        symbolSize: isSignificant ? 10 : 5,
      });
    });
  });
  
  const maxY = isPipMode.value ? 1.0 : Math.max(thresholdLog10.value * 1.2, ...data.map(d => d.log10P));
  const yAxisMin = isPipMode.value ? 0 : 0;
  
  const option: echarts.EChartsOption = {
    backgroundColor: '#0F172A',
    title: {
      text: chartTitle.value,
      left: 'center',
      top: 10,
      textStyle: {
        color: '#FFFFFF',
        fontSize: 18,
        fontWeight: 'bold',
      },
    },
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: '#334155',
      textStyle: {
        color: '#FFFFFF',
      },
      formatter: (params: any) => {
        const point = params.data.raw;
        if (!point) return '';
        if (isPipMode.value) {
          return `
            <div style="font-weight: bold; margin-bottom: 8px; color: #165DFF;">${point.snp}</div>
            <div><strong>染色体:</strong> ${point.chr}</div>
            <div><strong>位置:</strong> ${point.pos.toLocaleString()}</div>
            <div><strong>PIP:</strong> ${(point.pip ?? 0).toFixed(4)}</div>
            <div><strong>-log10(P):</strong> ${point.log10P.toFixed(2)}</div>
            ${point.pValue !== undefined ? `<div><strong>P值:</strong> ${point.pValue.toExponential(4)}</div>` : ''}
            ${point.maf !== undefined ? `<div><strong>MAF:</strong> ${point.maf.toFixed(4)}</div>` : ''}
          `;
        }
        return `
          <div style="font-weight: bold; margin-bottom: 8px; color: #165DFF;">${point.snp}</div>
          <div><strong>染色体:</strong> ${point.chr}</div>
          <div><strong>位置:</strong> ${point.pos.toLocaleString()}</div>
          <div><strong>P值:</strong> ${point.pValue.toExponential(4)}</div>
          <div><strong>-log10(P):</strong> ${point.log10P.toFixed(2)}</div>
          ${point.maf !== undefined ? `<div><strong>MAF:</strong> ${point.maf.toFixed(4)}</div>` : ''}
          ${point.effectSize !== undefined ? `<div><strong>效应值:</strong> ${point.effectSize.toFixed(4)}</div>` : ''}
        `;
      },
    },
    grid: {
      left: '8%',
      right: '5%',
      bottom: '12%',
      top: '15%',
    },
    xAxis: {
      type: 'category',
      name: 'Chromosome',
      nameLocation: 'middle',
      nameGap: 40,
      nameTextStyle: {
        color: '#FFFFFF',
        fontSize: 14,
        fontWeight: 'bold',
      },
      data: chromMidpoints.map((c: any) => c.chr),
      axisLine: {
        lineStyle: {
          color: '#334155',
        },
      },
      axisTick: {
        show: false,
      },
      axisLabel: {
        interval: 0,
        color: '#94A3B8',
        fontSize: 12,
      },
      splitLine: {
        show: true,
        lineStyle: {
          color: '#1E293B',
          type: 'dashed',
        },
      },
    } as any,
    yAxis: {
      type: 'value',
      name: yAxisName.value,
      nameLocation: 'middle',
      nameGap: 50,
      nameTextStyle: {
        color: '#FFFFFF',
        fontSize: 14,
        fontWeight: 'bold',
      },
      min: yAxisMin,
      max: isPipMode.value ? maxY : Math.ceil(maxY),
      axisLine: {
        lineStyle: {
          color: '#334155',
        },
      },
      axisLabel: {
        color: '#94A3B8',
        fontSize: 12,
      },
      splitLine: {
        show: true,
        lineStyle: {
          color: '#1E293B',
          type: 'dashed',
        },
      },
    },
    series: [
      {
        name: isPipMode.value ? 'SNP (PIP)' : 'SNP',
        type: 'scatter',
        data: scatterData,
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: {
            color: isPipMode.value ? '#00B42A' : '#FF7D00',
            type: 'dashed',
            width: 2,
          },
          label: {
            formatter: isPipMode.value 
              ? `PIP阈值 (${props.threshold})`
              : `显著阈值 (P=${props.threshold.toExponential(0)})`,
            color: isPipMode.value ? '#00B42A' : '#FF7D00',
            fontSize: 11,
            fontWeight: 'bold',
            position: 'insideEndTop',
          },
          data: [
            {
              yAxis: thresholdLog10.value,
            },
          ],
        },
      },
    ],
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: 0,
        start: 0,
        end: 100,
      },
      {
        type: 'slider',
        xAxisIndex: 0,
        start: 0,
        end: 100,
        bottom: 5,
        height: 20,
        borderColor: '#334155',
        backgroundColor: '#1E293B',
        fillerColor: 'rgba(22, 93, 255, 0.2)',
        handleStyle: {
          color: '#165DFF',
        },
        textStyle: {
          color: '#94A3B8',
          fontSize: 10,
        },
      },
    ],
  };
  
  chartInstance.setOption(option);
};

onMounted(() => {
  initChart();
  renderChart();
});

watch(
  () => [props.data, props.threshold],
  () => {
    renderChart();
  },
  { deep: true }
);

watch(
  () => props.loading,
  (loading) => {
    if (chartInstance) {
      if (loading) {
        chartInstance.showLoading('default', {
          maskColor: 'rgba(15, 23, 42, 0.8)',
          text: '加载中...',
          textColor: '#FFFFFF',
          spinnerRadius: 20,
          lineWidth: 3,
        });
      } else {
        chartInstance.hideLoading();
      }
    }
  }
);

defineExpose({
  resize: handleResize,
  getInstance: () => chartInstance,
});
</script>

<template>
  <div class="manhattan-plot-wrapper">
    <div ref="chartRef" class="chart-container" :style="{ height }"></div>
    <div v-if="!data || data.length === 0" class="empty-state">
      <el-empty description="暂无曼哈顿图数据" :image-size="80">
        <template #image>
          <el-icon :size="60" color="#475569"><DataLine /></el-icon>
        </template>
      </el-empty>
    </div>
  </div>
</template>

<style scoped>
.manhattan-plot-wrapper {
  position: relative;
  width: 100%;
  background: #0F172A;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3);
}

.chart-container {
  width: 100%;
}

.empty-state {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 10;
}

:deep(.el-empty__description) {
  color: #94A3B8;
}
</style>
