import ReactECharts from 'echarts-for-react';
import type { AngularDistribution } from '../../types';

interface AngularDistributionChartProps {
  data: AngularDistribution;
}

export function AngularDistributionChart({ data }: AngularDistributionChartProps) {
  const polarData = data.angles.map((angle, i) => ({
    value: [angle, data.intensities[i] * 100],
    name: `${angle.toFixed(0)}°`,
  }));

  const option = {
    backgroundColor: 'transparent',
    title: {
      text: '电致发光角度分布',
      textStyle: {
        color: '#CCD6F6',
        fontSize: 14,
        fontWeight: 600,
      },
      left: 10,
      top: 10,
    },
    legend: {
      data: ['归一化强度'],
      textStyle: { color: '#A8B2D1', fontSize: 12 },
      top: 10,
      right: 10,
    },
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(17, 34, 64, 0.95)',
      borderColor: 'rgba(100, 255, 218, 0.3)',
      textStyle: { color: '#CCD6F6' },
      formatter: (params: any) => {
        const [angle, intensity] = params.value;
        return `角度: ${angle.toFixed(1)}°<br/>强度: ${(intensity / 100).toFixed(3)}`;
      },
    },
    polar: {
      radius: ['15%', '75%'],
      startAngle: 0,
      endAngle: 90,
      center: ['50%', '60%'],
    },
    angleAxis: {
      type: 'value',
      min: 0,
      max: 90,
      interval: 15,
      axisLine: { lineStyle: { color: '#4A5568' } },
      splitLine: { lineStyle: { color: 'rgba(74, 85, 104, 0.3)' } },
      axisLabel: {
        color: '#8892B0',
        fontSize: 11,
        formatter: '{value}°',
      },
    },
    radiusAxis: {
      type: 'value',
      min: 0,
      max: 100,
      interval: 20,
      axisLine: { lineStyle: { color: '#4A5568' } },
      splitLine: { lineStyle: { color: 'rgba(74, 85, 104, 0.3)' } },
      axisLabel: {
        color: '#8892B0',
        fontSize: 10,
        formatter: '{value}%',
      },
    },
    series: [
      {
        name: '归一化强度',
        type: 'line',
        coordinateSystem: 'polar',
        data: polarData,
        smooth: true,
        lineStyle: {
          width: 3,
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 1,
            y2: 1,
            colorStops: [
              { offset: 0, color: '#64FFDA' },
              { offset: 1, color: '#FF6B35' },
            ],
          },
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 1,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(100, 255, 218, 0.4)' },
              { offset: 1, color: 'rgba(255, 107, 53, 0.1)' },
            ],
          },
        },
        symbol: 'circle',
        symbolSize: 6,
        itemStyle: {
          color: '#64FFDA',
          borderColor: '#112240',
          borderWidth: 2,
        },
      },
      {
        name: '朗伯分布',
        type: 'line',
        coordinateSystem: 'polar',
        data: data.angles.map(angle => ({
          value: [angle, Math.cos(angle * Math.PI / 180) * 100],
        })),
        smooth: true,
        lineStyle: {
          width: 2,
          type: 'dashed',
          color: 'rgba(136, 146, 176, 0.5)',
        },
        symbol: 'none',
      },
    ],
  };

  return (
    <div className="glass-card p-5">
      <ReactECharts option={option} style={{ height: '350px' }} />
      <div className="mt-4 grid grid-cols-2 gap-4">
        <div className="p-3 bg-space-800/30 rounded-lg">
          <p className="text-xs text-slate-500 mb-1">峰值强度角度</p>
          <p className="text-lg font-mono text-quantum-400">
            {data.peakIntensityAngle.toFixed(1)}°
          </p>
        </div>
        <div className="p-3 bg-space-800/30 rounded-lg">
          <p className="text-xs text-slate-500 mb-1">半高宽</p>
          <p className="text-lg font-mono text-energy-400">
            {data.fwhmAngle.toFixed(1)}°
          </p>
        </div>
      </div>
    </div>
  );
}
