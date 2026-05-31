<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue';
import * as echarts from 'echarts';
import type { EChartsOption } from 'echarts';
import type { HaplotypeBlock } from '@/types';

interface Props {
  snpNames: string[];
  positions: number[];
  ldMatrix: number[][];
  hapBlocks?: HaplotypeBlock[];
  height?: string;
  loading?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  height: '600px',
  loading: false,
});

const chartRef = ref<HTMLDivElement | null>(null);
let chartInstance: echarts.ECharts | null = null;

const nSNPs = computed(() => props.snpNames.length);

const tickIndices = computed(() => {
  if (nSNPs.value <= 10) {
    return Array.from({ length: nSNPs.value }, (_, i) => i);
  }
  const step = Math.ceil(nSNPs.value / 10);
  return Array.from({ length: Math.ceil(nSNPs.value / step) }, (_, i) => i * step);
});

const initChart = () => {
  if (!chartRef.value) return;
  
  if (chartInstance) {
    chartInstance.dispose();
  }
  
  chartInstance = echarts.init(chartRef.value);
  
  window.addEventListener('resize', handleResize);
};

const handleResize = () => {
  chartInstance?.resize();
};

const renderChart = () => {
  if (!chartInstance || !props.ldMatrix || props.ldMatrix.length === 0) return;
  
  const data: [number, number, number][] = [];
  
  for (let i = 0; i < nSNPs.value; i++) {
    for (let j = 0; j <= i; j++) {
      const r2 = props.ldMatrix[i]?.[j] ?? 0;
      data.push([j, i, r2]);
    }
  }
  
  const markLineData: echarts.SeriesOption['markLine'] = undefined;
  const markAreas: any[] = [];
  
  if (props.hapBlocks && props.hapBlocks.length > 0) {
    props.hapBlocks.forEach((block) => {
      const startIdx = block.startIdx;
      const endIdx = block.endIdx;
      if (startIdx !== undefined && endIdx !== undefined) {
        markAreas.push({
          silent: true,
          itemStyle: {
            color: 'transparent',
            borderColor: '#FF7D00',
            borderWidth: 2,
            borderType: 'dashed',
          },
          xAxis: [startIdx - 0.5, endIdx + 0.5],
          yAxis: [startIdx - 0.5, endIdx + 0.5],
        });
      }
    });
  }
  
  const option: echarts.EChartsOption = {
    backgroundColor: '#0F172A',
    title: {
      text: '连锁不平衡热图 (LD Heatmap)',
      subtext: `r² 值 | ${nSNPs.value} SNPs`,
      left: 'center',
      top: 10,
      textStyle: {
        color: '#FFFFFF',
        fontSize: 18,
        fontWeight: 'bold',
      },
      subtextStyle: {
        color: '#94A3B8',
        fontSize: 12,
      },
    },
    tooltip: {
      position: 'top',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: '#334155',
      textStyle: {
        color: '#FFFFFF',
      },
      formatter: (params: any) => {
        const i = params.data[1];
        const j = params.data[0];
        const r2 = params.data[2];
        const snp1 = props.snpNames[i];
        const snp2 = props.snpNames[j];
        const pos1 = props.positions[i]?.toLocaleString();
        const pos2 = props.positions[j]?.toLocaleString();
        
        return `
          <div style="font-weight: bold; margin-bottom: 8px; color: #165DFF;">LD r²</div>
          <div style="margin-bottom: 4px;"><strong>${snp1}</strong> (${pos1})</div>
          <div style="margin-bottom: 8px;"><strong>${snp2}</strong> (${pos2})</div>
          <div><strong>r²:</strong> ${r2.toFixed(4)}</div>
        `;
      },
    },
    grid: {
      left: '12%',
      right: '15%',
      bottom: '12%',
      top: '18%',
    },
    xAxis: {
      type: 'category',
      data: tickIndices.value.map(i => props.snpNames[i] || ''),
      splitArea: {
        show: true,
      },
      axisLabel: {
        rotate: 45,
        color: '#94A3B8',
        fontSize: 10,
        interval: 0,
      },
      axisLine: {
        lineStyle: {
          color: '#334155',
        },
      },
    },
    yAxis: {
      type: 'category',
      data: tickIndices.value.map(i => props.snpNames[i] || ''),
      splitArea: {
        show: true,
      },
      axisLabel: {
        color: '#94A3B8',
        fontSize: 10,
        interval: 0,
      },
      axisLine: {
        lineStyle: {
          color: '#334155',
        },
      },
    },
    visualMap: {
      min: 0,
      max: 1,
      calculable: true,
      orient: 'vertical',
      right: '2%',
      top: 'center',
      text: ['High', 'Low'],
      textStyle: {
        color: '#94A3B8',
      },
      inRange: {
        color: ['#1E293B', '#1E3A5F', '#165DFF', '#4C9AFF', '#00B42A', '#86EFAC', '#FF7D00'],
      },
    } as any,
    series: [
      {
        name: 'LD r²',
        type: 'heatmap',
        data: data,
        label: {
          show: false,
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowColor: 'rgba(0, 0, 0, 0.5)',
            borderColor: '#FFFFFF',
            borderWidth: 1,
          },
        },
        markArea: markAreas.length > 0 ? {
          silent: true,
          data: markAreas,
        } : undefined,
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
  () => [props.ldMatrix, props.snpNames, props.positions, props.hapBlocks],
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
  <div class="ld-heatmap-wrapper">
    <div ref="chartRef" class="chart-container" :style="{ height }"></div>
    <div v-if="!ldMatrix || ldMatrix.length === 0" class="empty-state">
      <el-empty description="暂无LD热图数据" :image-size="80">
        <template #image>
          <el-icon :size="60" color="#475569"><HeatMap /></el-icon>
        </template>
      </el-empty>
    </div>
    
    <div v-if="hapBlocks && hapBlocks.length > 0" class="hap-blocks-info">
      <h4 class="title">单倍型块 (Haplotype Blocks)</h4>
      <div class="blocks-list">
        <div v-for="(block, index) in hapBlocks" :key="index" class="block-item">
          <span class="block-index">Block {{ index + 1 }}</span>
          <span class="block-range">{{ block.start.toLocaleString() }} - {{ block.end.toLocaleString() }} bp</span>
          <span class="block-snps">{{ block.snps?.length || 0 }} SNPs</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ld-heatmap-wrapper {
  position: relative;
  width: 100%;
  background: #0F172A;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3);
  padding-bottom: 20px;
}

.chart-container {
  width: 100%;
}

.empty-state {
  position: absolute;
  top: 40%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 10;
}

:deep(.el-empty__description) {
  color: #94A3B8;
}

.hap-blocks-info {
  padding: 16px 24px;
  background: rgba(30, 41, 59, 0.5);
  margin: 0 20px;
  border-radius: 8px;
  border: 1px solid #334155;
}

.title {
  color: #FFFFFF;
  font-size: 14px;
  font-weight: bold;
  margin: 0 0 12px 0;
}

.blocks-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.block-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: rgba(255, 125, 0, 0.1);
  border: 1px solid rgba(255, 125, 0, 0.3);
  border-radius: 6px;
  font-size: 12px;
}

.block-index {
  color: #FF7D00;
  font-weight: bold;
}

.block-range {
  color: #94A3B8;
}

.block-snps {
  color: #00B42A;
}
</style>
