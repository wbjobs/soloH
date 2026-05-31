import ReactECharts from 'echarts-for-react';
import type { AgingResults } from '../../types';

interface AgingCurveChartProps {
  data: AgingResults;
}

export function AgingCurveChart({ data }: AgingCurveChartProps) {
  const brightnessData = data.agingData.map(point => ({
    time: point.time,
    brightness: point.brightness,
  }));

  const voltageData = data.agingData.map(point => ({
    time: point.time,
    voltage: point.voltage,
  }));

  const option = {
    backgroundColor: 'transparent',
    title: {
      text: '亮度衰减与寿命预测',
      textStyle: {
        color: '#CCD6F6',
        fontSize: 14,
        fontWeight: 600,
      },
      left: 10,
      top: 10,
    },
    legend: {
      data: ['相对亮度', '工作电压'],
      textStyle: { color: '#A8B2D1', fontSize: 12 },
      top: 10,
      right: 10,
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(17, 34, 64, 0.95)',
      borderColor: 'rgba(100, 255, 218, 0.3)',
      textStyle: { color: '#CCD6F6' },
      axisPointer: {
        type: 'cross',
        lineStyle: { color: '#4A5568' },
      },
      formatter: (params: any) => {
        let result = `时间: ${params[0].axisValue.toExponential(2)} h<br/>`;
        params.forEach((param: any) => {
          const value = param.seriesName === '相对亮度' 
            ? (param.value * 100).toFixed(1) + '%'
            : param.value.toFixed(2) + ' V';
          result += `${param.marker} ${param.seriesName}: ${value}<br/>`;
        });
        return result;
      },
    },
    xAxis: {
      type: 'log',
      name: '时间 (h)',
      nameTextStyle: { color: '#8892B0', fontSize: 11 },
      axisLine: { lineStyle: { color: '#4A5568' } },
      axisLabel: {
        color: '#8892B0',
        fontSize: 10,
        formatter: (value: number) => {
          if (value >= 1000) return (value / 1000).toFixed(0) + 'k';
          return value.toFixed(0);
        },
      },
      splitLine: { lineStyle: { color: 'rgba(74, 85, 104, 0.3)' } },
    },
    yAxis: [
      {
        type: 'value',
        name: '相对亮度',
        nameTextStyle: { color: '#8892B0', fontSize: 11 },
        min: 0,
        max: 1.1,
        axisLine: { lineStyle: { color: '#4A5568' } },
        axisLabel: {
          color: '#8892B0',
          fontSize: 10,
          formatter: (value: number) => (value * 100).toFixed(0) + '%',
        },
        splitLine: { lineStyle: { color: 'rgba(74, 85, 104, 0.3)' } },
      },
      {
        type: 'value',
        name: '电压 (V)',
        nameTextStyle: { color: '#8892B0', fontSize: 11 },
        position: 'right',
        axisLine: { lineStyle: { color: '#4A5568' } },
        axisLabel: { color: '#8892B0', fontSize: 10 },
        splitLine: { show: false },
      },
    ],
    graphic: [
      {
        type: 'text',
        left: '10%',
        top: '40%',
        silent: true,
        style: {
          text: 'LT50',
          fill: '#FF6B6B',
          fontSize: 12,
          fontWeight: 600,
        },
      },
      {
        type: 'line',
        shape: { x1: 0, y1: 0, x2: 0, y2: 0 },
        style: {
          stroke: '#FF6B6B',
          lineWidth: 2,
          lineDash: [4, 4],
        },
      },
    ],
    series: [
      {
        name: '相对亮度',
        type: 'line',
        data: brightnessData.map(d => [d.time, d.brightness / data.agingData[0].brightness]),
        smooth: true,
        lineStyle: {
          width: 3,
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 1,
            y2: 0,
            colorStops: [
              { offset: 0, color: '#64FFDA' },
              { offset: 0.5, color: '#FFD166' },
              { offset: 1, color: '#FF6B6B' },
            ],
          },
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(100, 255, 218, 0.3)' },
              { offset: 1, color: 'rgba(100, 255, 218, 0)' },
            ],
          },
        },
        symbol: 'circle',
        symbolSize: 5,
        itemStyle: { color: '#64FFDA' },
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: '#FF6B6B', type: 'dashed', width: 2 },
          data: [
            { yAxis: 0.5, label: { formatter: '50%', position: 'end', color: '#FF6B6B' } },
            { yAxis: 0.7, label: { formatter: '70%', position: 'end', color: '#FFD166' } },
            { yAxis: 0.95, label: { formatter: '95%', position: 'end', color: '#64FFDA' } },
          ],
        },
      },
      {
        name: '工作电压',
        type: 'line',
        yAxisIndex: 1,
        data: voltageData.map(d => [d.time, d.voltage]),
        smooth: true,
        lineStyle: {
          width: 2,
          color: '#A8B2D1',
          type: 'dashed',
        },
        symbol: 'none',
      },
    ],
  };

  return (
    <div className="glass-card p-5">
      <ReactECharts option={option} style={{ height: '350px' }} />
      <div className="mt-4 grid grid-cols-4 gap-3">
        <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
          <p className="text-xs text-red-400 mb-1">LT50 (50%)</p>
          <p className="text-base font-mono text-red-400">
            {data.lt50 > 1e6 ? (data.lt50 / 1e6).toFixed(1) + ' Mh' :
             data.lt50 > 1e3 ? (data.lt50 / 1e3).toFixed(1) + ' kh' :
             data.lt50.toFixed(0) + ' h'}
          </p>
        </div>
        <div className="p-3 bg-yellow-500/10 border border-yellow-500/20 rounded-lg">
          <p className="text-xs text-yellow-400 mb-1">LT70 (70%)</p>
          <p className="text-base font-mono text-yellow-400">
            {data.lt70 > 1e6 ? (data.lt70 / 1e6).toFixed(1) + ' Mh' :
             data.lt70 > 1e3 ? (data.lt70 / 1e3).toFixed(1) + ' kh' :
             data.lt70.toFixed(0) + ' h'}
          </p>
        </div>
        <div className="p-3 bg-green-500/10 border border-green-500/20 rounded-lg">
          <p className="text-xs text-green-400 mb-1">LT95 (95%)</p>
          <p className="text-base font-mono text-green-400">
            {data.lt95 > 1e6 ? (data.lt95 / 1e6).toFixed(1) + ' Mh' :
             data.lt95 > 1e3 ? (data.lt95 / 1e3).toFixed(1) + ' kh' :
             data.lt95.toFixed(0) + ' h'}
          </p>
        </div>
        <div className="p-3 bg-space-800/30 rounded-lg">
          <p className="text-xs text-slate-500 mb-1">主导退化模式</p>
          <p className="text-sm font-medium text-slate-300">
            {data.degradationMode}
          </p>
        </div>
      </div>
    </div>
  );
}
