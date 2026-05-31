<script setup lang="ts">import { ref, computed, watch, onMounted } from 'vue';
import VChart from 'vue-echarts';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { GraphChart } from 'echarts/charts';
import { TooltipComponent, LegendComponent } from 'echarts/components';
import type { EChartsOption, ECharts } from 'echarts';
import type { GraphData, GraphNode, GraphEdge } from '../types';
import { getNodeColor, calculateNodeSize, calculateEdgeWidth } from '../utils/graph';
import { formatBTC } from '../utils/format';
import type { LayoutType } from './GraphFilterPanel.vue';
import { ZoomIn, ZoomOut, Maximize2, RefreshCw, Info } from 'lucide-vue-next';
use([CanvasRenderer, GraphChart, TooltipComponent, LegendComponent]);
const props = defineProps<{
 graphData: GraphData;
 layout?: LayoutType;
 highlightNodeId?: string;
}>();
const emit = defineEmits<{
 (e: 'node-click', node: GraphNode): void;
 (e: 'edge-click', edge: GraphEdge): void;
}>();
const chartRef = ref<InstanceType<typeof VChart> | null>(null);
const isLoading = ref(false);
const showInfo = ref(true);
const getLayoutConfig = (layout: LayoutType) => {
 switch (layout) {
 case 'circular':
 return {
 layout: 'circular' as const,
 circular: {
 rotateLabel: true
 }
 };
 case 'hierarchical':
 return {
 layout: 'force' as const,
 force: {
 repulsion: 800,
 gravity: 0.2,
 edgeLength: [150, 250],
 layoutAnimation: true
 }
 };
 case 'force':
 default:
 return {
 layout: 'force' as const,
 force: {
 repulsion: 600,
 gravity: 0.1,
 edgeLength: [100, 200],
 edgeForce: 0.2
 }
 };
 }
};
const chartOption = computed<any>(() => {
 const nodes = props.graphData?.nodes || [];
 const edges = props.graphData?.edges || [];
 const layoutConfig = getLayoutConfig(props.layout || 'force');
 const processedNodes = nodes.map(node => {
 const baseColor = node.color || getNodeColor(undefined, node.suspiciousScore);
 const isHighlighted = props.highlightNodeId === node.id;
 return {
 id: node.id,
 name: node.label,
 value: node.size,
 symbolSize: calculateNodeSize(node.size || 20),
 itemStyle: {
 color: baseColor,
 borderColor: isHighlighted ? '#fbbf24' : 'rgba(255,255,255,0.3)',
 borderWidth: isHighlighted ? 3 : 1,
 shadowBlur: isHighlighted ? 20 : 0,
 shadowColor: isHighlighted ? '#fbbf24' : 'transparent'
 },
 label: {
 show: nodes.length < 50,
 formatter: (params: {
 name: string;
 }) => {
 const name = params.name;
 return name.length > 10 ? name.substring(0, 10) + '...' : name;
 },
 fontSize: 11,
 color: '#e2e8f0'
 },
 category: node.type,
 ...node
 };
 });
 const processedEdges = edges.map(edge => {
 const isHighlighted = props.highlightNodeId &&
 (edge.source === props.highlightNodeId || edge.target === props.highlightNodeId);
 const opacity = props.highlightNodeId ? (isHighlighted ? 1 : 0.1) : 0.6;
 return {
 source: edge.source,
 target: edge.target,
 value: edge.value,
 lineStyle: {
 width: calculateEdgeWidth(edge.value || 1),
 color: isHighlighted ? '#fbbf24' : '#64748b',
 opacity,
 curveness: 0.1
 },
 emphasis: {
 lineStyle: {
 width: 4,
 color: '#22d3ee',
 opacity: 1
 }
 },
 ...edge
 };
 });
 return {
 backgroundColor: 'transparent',
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
 if (params.dataType === 'node') {
 const node = params.data as GraphNode;
 const score = node.suspiciousScore;
 return `
 <div style="min-width: 200px;">
 <div style="font-weight: 600; font-size: 14px; margin-bottom: 8px; color: #22d3ee;">${params.name}</div>
 <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
 <span style="color: #94a3b8;">类型:</span>
 <span style="color: #e2e8f0;">${node.type === 'address' ? '地址' : '交易'}</span>
 </div>
 ${score !== undefined ? `
 <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
 <span style="color: #94a3b8;">风险评分:</span>
 <span style="color: ${score >= 70 ? '#ef4444' : score >= 40 ? '#f59e0b' : '#22c55e'}; font-weight: 600;">${score.toFixed(1)}</span>
 </div>
 ` : ''}
 <div style="display: flex; justify-content: space-between;">
 <span style="color: #94a3b8;">ID:</span>
 <span style="color: #64748b; font-family: monospace; font-size: 11px;">${node.id.substring(0, 16)}...</span>
 </div>
 </div>
 `;
 }
 else {
 const edge = params.data as GraphEdge;
 const value = edge.value ?? params.value;
 return `
 <div style="min-width: 180px;">
 <div style="font-weight: 600; font-size: 14px; margin-bottom: 8px; color: #22d3ee;">交易详情</div>
 ${value !== undefined && value !== null ? `
 <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
 <span style="color: #94a3b8;">金额:</span>
 <span style="color: #e2e8f0; font-weight: 600;">${formatBTC(value, 'auto')}</span>
 </div>
 ` : ''}
 ${edge.timestamp ? `
 <div style="display: flex; justify-content: space-between;">
 <span style="color: #94a3b8;">时间:</span>
 <span style="color: #e2e8f0;">${new Date(edge.timestamp instanceof Date ? edge.timestamp.getTime() : (typeof edge.timestamp === 'number' && edge.timestamp < 1e12 ? edge.timestamp * 1000 : edge.timestamp)).toLocaleString()}</span>
 </div>
 ` : ''}
 </div>
 `;
 }
 }
 },
 legend: {
 show: true,
 orient: 'horizontal',
 top: 10,
 right: 20,
 textStyle: {
 color: '#94a3b8',
 fontSize: 12
 },
 data: [
 { name: 'address', itemStyle: { color: '#3b82f6' } },
 { name: 'transaction', itemStyle: { color: '#6b7280' } }
 ]
 },
 series: [{
 type: 'graph',
 ...layoutConfig,
 data: processedNodes,
 links: processedEdges,
 categories: [
 { name: 'address', itemStyle: { color: '#3b82f6' } },
 { name: 'transaction', itemStyle: { color: '#6b7280' } }
 ],
 roam: true,
 draggable: true,
 focusNodeAdjacency: true,
 emphasis: {
 focus: 'adjacency',
 label: {
 show: true,
 fontSize: 13,
 fontWeight: 'bold'
 },
 lineStyle: {
 width: 4
 }
 },
 select: {
 itemStyle: {
 borderColor: '#fbbf24',
 borderWidth: 3,
 shadowBlur: 20,
 shadowColor: '#fbbf24'
 }
 },
 animationDuration: 1500,
 animationEasingUpdate: 'quinticInOut'
 }]
 };
});
const handleClick = (params: any) => {
 if (params.dataType === 'node') {
 emit('node-click', params.data as GraphNode);
 }
 else if (params.dataType === 'edge') {
 emit('edge-click', params.data as GraphEdge);
 }
};
const zoomIn = () => {
 const chart = chartRef.value?.chart as unknown as ECharts | undefined;
 if (chart) {
 chart.dispatchAction({
 type: 'dataZoom',
 start: 0,
 end: 100
 });
 }
};
const zoomOut = () => {
 const chart = chartRef.value?.chart as unknown as ECharts | undefined;
 if (chart) {
 chart.dispatchAction({
 type: 'dataZoom',
 start: 0,
 end: 100
 });
 }
};
const resetView = () => {
 const chart = chartRef.value?.chart as unknown as ECharts | undefined;
 if (chart) {
 chart.dispatchAction({
 type: 'restore'
 });
 }
};
const toggleInfo = () => {
 showInfo.value = !showInfo.value;
};
const stats = computed(() => {
 if (!props.graphData)
 return null;
 return {
 nodes: props.graphData.nodes.length,
 edges: props.graphData.edges.length,
 addresses: props.graphData.nodes.filter(n => n.type === 'address').length,
 transactions: props.graphData.nodes.filter(n => n.type === 'transaction').length
 };
});
watch(() => props.graphData, () => {
 isLoading.value = true;
 setTimeout(() => {
 isLoading.value = false;
 }, 500);
}, { deep: true });
onMounted(() => {
 isLoading.value = false;
});
</script>

<template>
  <div class="relative w-full h-full min-h-[500px] bg-slate-900/30 rounded-xl border border-slate-700/50 overflow-hidden">
    <div class="absolute top-4 left-4 z-10 flex items-center gap-2">
      <div
        v-if="showInfo && stats"
        class="bg-slate-800/90 backdrop-blur-sm rounded-lg px-4 py-2 border border-slate-700/50"
      >
        <div class="flex items-center gap-4 text-sm">
          <div class="flex items-center gap-1.5">
            <div class="w-2 h-2 rounded-full bg-blue-500"></div>
            <span class="text-slate-400">地址:</span>
            <span class="text-white font-mono">{{ stats.addresses }}</span>
          </div>
          <div class="flex items-center gap-1.5">
            <div class="w-2 h-2 rounded-full bg-slate-500"></div>
            <span class="text-slate-400">交易:</span>
            <span class="text-white font-mono">{{ stats.transactions }}</span>
          </div>
          <div class="flex items-center gap-1.5">
            <span class="text-slate-400">边:</span>
            <span class="text-white font-mono">{{ stats.edges }}</span>
          </div>
        </div>
      </div>
    </div>

    <div class="absolute top-4 right-4 z-10 flex flex-col gap-2">
      <button
        class="w-9 h-9 bg-slate-800/90 backdrop-blur-sm rounded-lg border border-slate-700/50 flex items-center justify-center text-slate-400 hover:text-cyan-400 hover:border-cyan-500/50 transition-all"
        title="放大"
        @click="zoomIn"
      >
        <ZoomIn class="w-4 h-4" />
      </button>
      <button
        class="w-9 h-9 bg-slate-800/90 backdrop-blur-sm rounded-lg border border-slate-700/50 flex items-center justify-center text-slate-400 hover:text-cyan-400 hover:border-cyan-500/50 transition-all"
        title="缩小"
        @click="zoomOut"
      >
        <ZoomOut class="w-4 h-4" />
      </button>
      <button
        class="w-9 h-9 bg-slate-800/90 backdrop-blur-sm rounded-lg border border-slate-700/50 flex items-center justify-center text-slate-400 hover:text-cyan-400 hover:border-cyan-500/50 transition-all"
        title="重置视图"
        @click="resetView"
      >
        <RefreshCw class="w-4 h-4" />
      </button>
      <button
        class="w-9 h-9 bg-slate-800/90 backdrop-blur-sm rounded-lg border border-slate-700/50 flex items-center justify-center transition-all"
        :class="[showInfo ? 'text-cyan-400 border-cyan-500/50' : 'text-slate-400 hover:text-cyan-400 hover:border-cyan-500/50']"
        title="显示/隐藏信息"
        @click="toggleInfo"
      >
        <Info class="w-4 h-4" />
      </button>
    </div>

    <div
      v-if="isLoading"
      class="absolute inset-0 bg-slate-900/80 backdrop-blur-sm flex items-center justify-center z-20"
    >
      <div class="flex flex-col items-center gap-3">
        <div class="w-10 h-10 border-4 border-cyan-500/30 border-t-cyan-500 rounded-full animate-spin"></div>
        <span class="text-sm text-slate-400">加载图数据...</span>
      </div>
    </div>

    <VChart
      ref="chartRef"
      :option="chartOption"
      autoresize
      class="w-full h-full"
      @click="handleClick"
    />

    <div class="absolute bottom-4 right-4 z-10 bg-slate-800/90 backdrop-blur-sm rounded-lg px-3 py-2 border border-slate-700/50">
      <div class="flex items-center gap-2 text-xs">
        <span class="text-slate-500">风险等级:</span>
        <div class="flex items-center gap-1">
          <span class="w-3 h-3 rounded-full bg-green-500"></span>
          <span class="text-slate-400">低</span>
        </div>
        <div class="flex items-center gap-1">
          <span class="w-3 h-3 rounded-full bg-yellow-500"></span>
          <span class="text-slate-400">中</span>
        </div>
        <div class="flex items-center gap-1">
          <span class="w-3 h-3 rounded-full bg-orange-500"></span>
          <span class="text-slate-400">高</span>
        </div>
        <div class="flex items-center gap-1">
          <span class="w-3 h-3 rounded-full bg-red-500"></span>
          <span class="text-slate-400">严重</span>
        </div>
      </div>
    </div>
  </div>
</template>
