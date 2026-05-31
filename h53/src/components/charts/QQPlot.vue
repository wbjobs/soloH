<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue';
import * as echarts from 'echarts';
import type { QQPoint } from '@/types';
import { DataLine } from '@element-plus/icons-vue';

interface Props {
  data: QQPoint[];
  inflationFactor?: number;
  height?: string;
  loading?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  height: '500px',
  loading: false,
});

const chartRef = ref<HTMLDivElement | null>(null);
let chartInstance: echarts.ECharts | null = null;

const maxValue = computed(() => {
  if (!props.data || props.data.length === 0) return 10;
  const maxExp = Math.max(...props.data.map(d => d.expected));
  const maxObs = Math.max(...props.data.map(d => d.observed));
  return Math.ceil(Math.max(maxExp, maxObs) * 1.1);
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
  if (!chartInstance || !props.data || props.data.length === 0) return;
  
  const data = props.data;
  
  const observedData = data.map(d => [d.expected, d.observed]);
  
  const n = data.length;
  const confidence = 0.95;
  
  const lowerBand: [number, number][] = [];
  const upperBand: [number, number][] = [];
  const lineData: [number, number][] = [[0, 0], [maxValue.value, maxValue.value]];
  
  for (let i = 0; i < n; i++) {
    const p = (i + 1) / (n + 1);
    const expected = -Math.log10(p);
    
    const alphaLow = (1 - confidence) / 2;
    const alphaHigh = 1 - (1 - confidence) / 2;
    
    const lowerP = betaInv(alphaLow, i + 1, n - i);
    const upperP = betaInv(alphaHigh, i + 1, n - i);
    
    lowerBand.push([expected, -Math.log10(Math.max(lowerP, 1e-300))]);
    upperBand.push([expected, -Math.log10(Math.min(upperP, 1 - 1e-10))]);
  }
  
  const bandData = [...lowerBand, ...upperBand.reverse()];
  
  const option: echarts.EChartsOption = {
    backgroundColor: '#0F172A',
    title: {
      text: 'QQ图 (Quantile-Quantile Plot)',
      left: 'center',
      top: 10,
      textStyle: {
        color: '#FFFFFF',
        fontSize: 18,
        fontWeight: 'bold',
      },
      subtext: props.inflationFactor !== undefined 
        ? `Inflation factor (λ) = ${props.inflationFactor.toFixed(3)}`
        : undefined,
      subtextStyle: {
        color: '#FF7D00',
        fontSize: 14,
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
        if (params.seriesName === 'QQ Points') {
          return `
            <div style="font-weight: bold; margin-bottom: 8px; color: #165DFF;">SNP</div>
            <div><strong>期望 -log10(P):</strong> ${params.data[0].toFixed(4)}</div>
            <div><strong>观测 -log10(P):</strong> ${params.data[1].toFixed(4)}</div>
          `;
        }
        return '';
      },
    },
    grid: {
      left: '12%',
      right: '8%',
      bottom: '10%',
      top: '18%',
    },
    xAxis: {
      type: 'value',
      name: 'Expected -log10(P)',
      nameLocation: 'middle',
      nameGap: 40,
      nameTextStyle: {
        color: '#FFFFFF',
        fontSize: 14,
        fontWeight: 'bold',
      },
      min: 0,
      max: maxValue.value,
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
    yAxis: {
      type: 'value',
      name: 'Observed -log10(P)',
      nameLocation: 'middle',
      nameGap: 50,
      nameTextStyle: {
        color: '#FFFFFF',
        fontSize: 14,
        fontWeight: 'bold',
      },
      min: 0,
      max: maxValue.value,
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
        name: '95% Confidence Band',
        type: 'line',
        data: bandData,
        lineStyle: {
          width: 0,
        },
        areaStyle: {
          color: 'rgba(255, 255, 255, 0.1)',
        },
        silent: true,
        z: 1,
      },
      {
        name: 'Expected under null',
        type: 'line',
        data: lineData,
        lineStyle: {
          color: '#FFFFFF',
          width: 2,
          type: 'dashed',
        },
        silent: true,
        z: 2,
      },
      {
        name: 'QQ Points',
        type: 'scatter',
        data: observedData,
        symbolSize: 8,
        itemStyle: {
          color: '#165DFF',
          opacity: 0.8,
          borderColor: 'rgba(255, 255, 255, 0.3)',
          borderWidth: 1,
        },
        emphasis: {
          itemStyle: {
            color: '#00B42A',
            borderColor: '#FFFFFF',
            borderWidth: 2,
            shadowBlur: 10,
            shadowColor: 'rgba(0, 180, 42, 0.5)',
          } as any,
          scale: true,
        },
        z: 3,
      },
    ] as any,
  };
  
  chartInstance.setOption(option);
};

function betaInv(p: number, a: number, b: number): number {
  if (p <= 0) return 0;
  if (p >= 1) return 1;
  
  let x = a / (a + b);
  for (let i = 0; i < 100; i++) {
    const f = betaCdf(x, a, b) - p;
    if (Math.abs(f) < 1e-10) break;
    const df = betaPdf(x, a, b);
    x = x - f / df;
    x = Math.max(1e-10, Math.min(1 - 1e-10, x));
  }
  return x;
}

function lgamma(z: number): number {
  const g = 7;
  const c = [
    0.99999999999980993,
    676.5203681218851,
    -1259.1392167224028,
    771.32342877765313,
    -176.61502916214059,
    12.507343278686905,
    -0.13857109526572012,
    9.9843695780195716e-6,
    1.5056327351493116e-7
  ];
  
  if (z < 0.5) {
    return Math.log(Math.PI / Math.sin(Math.PI * z)) - lgamma(1 - z);
  }
  
  z -= 1;
  let x = c[0];
  for (let i = 1; i < g + 2; i++) {
    x += c[i] / (z + i);
  }
  const t = z + g + 0.5;
  return 0.5 * Math.log(2 * Math.PI) + (z + 0.5) * Math.log(t) - t + Math.log(x);
}

function betaPdf(x: number, a: number, b: number): number {
  if (x <= 0 || x >= 1) return 0;
  const lnbeta = lgamma(a) + lgamma(b) - lgamma(a + b);
  return Math.exp((a - 1) * Math.log(x) + (b - 1) * Math.log(1 - x) - lnbeta);
}

function betaCdf(x: number, a: number, b: number): number {
  if (x <= 0) return 0;
  if (x >= 1) return 1;
  
  const bt = Math.exp(lgamma(a + b) - lgamma(a) - lgamma(b) +
    a * Math.log(x) + b * Math.log(1 - x));
  
  if (x < (a + 1) / (a + b + 2)) {
    return bt * betacf(x, a, b) / a;
  } else {
    return 1 - bt * betacf(1 - x, b, a) / b;
  }
}

function betacf(x: number, a: number, b: number): number {
  const maxIter = 200;
  const eps = 3e-7;
  
  let m = 1;
  let qab = a + b;
  let qap = a + 1;
  let qam = a - 1;
  let c = 1;
  let d = 1 - qab * x / qap;
  if (Math.abs(d) < 1e-30) d = 1e-30;
  d = 1 / d;
  let h = d;
  
  for (let i = 1; i <= maxIter; i++) {
    let m2 = 2 * m;
    let aa = m * (b - m) * x / ((qam + m2) * (a + m2));
    d = 1 + aa * d;
    if (Math.abs(d) < 1e-30) d = 1e-30;
    c = 1 + aa / c;
    if (Math.abs(c) < 1e-30) c = 1e-30;
    d = 1 / d;
    h *= d * c;
    aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2));
    d = 1 + aa * d;
    if (Math.abs(d) < 1e-30) d = 1e-30;
    c = 1 + aa / c;
    if (Math.abs(c) < 1e-30) c = 1e-30;
    d = 1 / d;
    let del = d * c;
    h *= del;
    if (Math.abs(del - 1) < eps) break;
    m++;
  }
  
  return h;
}

onMounted(() => {
  initChart();
  renderChart();
});

watch(
  () => [props.data, props.inflationFactor],
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
  <div class="qq-plot-wrapper">
    <div ref="chartRef" class="chart-container" :style="{ height }"></div>
    <div v-if="!data || data.length === 0" class="empty-state">
      <el-empty description="暂无QQ图数据" :image-size="80">
        <template #image>
          <el-icon :size="60" color="#475569"><DataLine /></el-icon>
        </template>
      </el-empty>
    </div>
  </div>
</template>

<style scoped>
.qq-plot-wrapper {
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
