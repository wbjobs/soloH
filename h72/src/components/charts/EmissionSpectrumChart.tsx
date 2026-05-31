import ReactECharts from 'echarts-for-react';
import type { EmissionSpectrum } from '../../types';

interface EmissionSpectrumChartProps {
  data: EmissionSpectrum;
}

export function EmissionSpectrumChart({ data }: EmissionSpectrumChartProps) {
  const option = {
    backgroundColor: 'transparent',
    title: {
      text: '发射光谱',
      textStyle: {
        color: '#CCD6F6',
        fontSize: 14,
        fontWeight: 600,
      },
      left: 10,
      top: 10,
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(17, 34, 64, 0.95)',
      borderColor: 'rgba(100, 255, 218, 0.3)',
      textStyle: {
        color: '#CCD6F6',
      },
      formatter: (params: any) => {
        const point = params[0];
        return `<div style="font-family: monospace;">
          <div style="color: #8892B0; margin-bottom: 4px;">波长: <span style="color: #64FFDA;">${point.value[0].toFixed(1)} nm</span></div>
          <div style="color: #8892B0;">强度: <span style="color: #FF6B35;">${(point.value[1] * 100).toFixed(1)}%</span></div>
        </div>`;
      },
    },
    grid: {
      left: 60,
      right: 20,
      top: 50,
      bottom: 40,
    },
    xAxis: {
      type: 'value',
      name: '波长 (nm)',
      nameTextStyle: {
        color: '#8892B0',
        fontSize: 12,
      },
      axisLine: {
        lineStyle: {
          color: 'rgba(136, 146, 176, 0.3)',
        },
      },
      axisLabel: {
        color: '#8892B0',
        fontSize: 11,
        fontFamily: 'monospace',
      },
      splitLine: {
        lineStyle: {
          color: 'rgba(136, 146, 176, 0.1)',
        },
      },
      min: Math.min(...data.spectrumData.map(d => d.wavelength)) - 20,
      max: Math.max(...data.spectrumData.map(d => d.wavelength)) + 20,
    },
    yAxis: {
      type: 'value',
      name: '归一化强度',
      nameTextStyle: {
        color: '#8892B0',
        fontSize: 12,
      },
      axisLine: {
        lineStyle: {
          color: 'rgba(136, 146, 176, 0.3)',
        },
      },
      axisLabel: {
        color: '#8892B0',
        fontSize: 11,
        fontFamily: 'monospace',
        formatter: (value: number) => (value * 100).toFixed(0) + '%',
      },
      splitLine: {
        lineStyle: {
          color: 'rgba(136, 146, 176, 0.1)',
        },
      },
      min: 0,
      max: 1.1,
    },
    series: [
      {
        type: 'line',
        data: data.spectrumData.map(d => [d.wavelength, d.intensity]),
        smooth: true,
        symbol: 'none',
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
              { offset: 0.5, color: '#FF6B35' },
              { offset: 1, color: '#FFD700' },
            ],
          },
          shadowColor: 'rgba(255, 107, 53, 0.3)',
          shadowBlur: 10,
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(255, 107, 53, 0.3)' },
              { offset: 1, color: 'rgba(255, 107, 53, 0)' },
            ],
          },
        },
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: {
            type: 'dashed',
            color: '#64FFDA',
            width: 1,
          },
          data: [
            {
              xAxis: data.peakWavelength,
              label: {
                formatter: `峰值: ${data.peakWavelength.toFixed(1)} nm`,
                position: 'insideEndTop',
                color: '#64FFDA',
                fontSize: 11,
                fontFamily: 'monospace',
              },
            },
          ],
        },
      },
      {
        type: 'scatter',
        data: [[data.peakWavelength, 1]],
        symbolSize: 10,
        itemStyle: {
          color: '#FF6B35',
          shadowColor: 'rgba(255, 107, 53, 0.5)',
          shadowBlur: 15,
        },
      },
    ],
    graphic: [
      {
        type: 'text',
        right: 20,
        top: 20,
        style: {
          text: `FWHM: ${data.fwhm.toFixed(1)} nm`,
          fill: '#8892B0',
          fontSize: 12,
          fontFamily: 'monospace',
        },
      },
    ],
  };

  return (
    <div className="glass-card p-4 h-full">
      <ReactECharts option={option} style={{ height: '100%', minHeight: '300px' }} />
    </div>
  );
}
