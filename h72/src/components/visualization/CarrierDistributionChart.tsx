import ReactECharts from 'echarts-for-react';
import type { CarrierDistribution } from '../../types';

interface CarrierDistributionChartProps {
  data: CarrierDistribution;
}

export function CarrierDistributionChart({ data }: CarrierDistributionChartProps) {
  const option = {
    backgroundColor: 'transparent',
    title: {
      text: '载流子浓度分布',
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
      axisPointer: {
        type: 'cross',
        crossStyle: {
          color: 'rgba(100, 255, 218, 0.5)',
        },
      },
      formatter: (params: any) => {
        let html = `<div style="font-family: monospace; padding: 4px 0;">`;
        html += `<div style="color: #8892B0; margin-bottom: 4px;">深度: <span style="color: #64FFDA;">${params[0].value[0].toFixed(1)} nm</span></div>`;
        params.forEach((p: any) => {
          let color = '#8892B0';
          if (p.seriesName === '电子浓度') color = '#64FFDA';
          else if (p.seriesName === '空穴浓度') color = '#FF6B35';
          else if (p.seriesName === '复合速率') color = '#FFD700';
          else if (p.seriesName === '电场') color = '#9C27B0';
          
          const value = p.value[1];
          const displayValue = Math.abs(value) > 1000 || Math.abs(value) < 0.01 
            ? value.toExponential(2) 
            : value.toFixed(2);
          
          html += `<div style="color: #8892B0;">${p.seriesName}: <span style="color: ${color};">${displayValue}</span></div>`;
        });
        html += '</div>';
        return html;
      },
    },
    legend: {
      data: ['电子浓度', '空穴浓度', '复合速率'],
      textStyle: {
        color: '#8892B0',
        fontSize: 12,
      },
      top: 10,
      right: 20,
      icon: 'roundRect',
    },
    grid: {
      left: 80,
      right: 80,
      top: 60,
      bottom: 50,
    },
    xAxis: {
      type: 'value',
      name: '器件深度 (nm)',
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
    },
    yAxis: [
      {
        type: 'value',
        name: '载流子浓度 (cm⁻³)',
        nameTextStyle: {
          color: '#64FFDA',
          fontSize: 12,
        },
        axisLine: {
          lineStyle: {
            color: 'rgba(100, 255, 218, 0.3)',
          },
        },
        axisLabel: {
          color: '#64FFDA',
          fontSize: 11,
          fontFamily: 'monospace',
          formatter: (value: number) => value.toExponential(0),
        },
        splitLine: {
          lineStyle: {
            color: 'rgba(136, 146, 176, 0.1)',
          },
        },
        logScale: true,
        min: 1e10,
        max: 1e20,
      },
      {
        type: 'value',
        name: '复合速率 (cm⁻³s⁻¹)',
        nameTextStyle: {
          color: '#FFD700',
          fontSize: 12,
        },
        axisLine: {
          lineStyle: {
            color: 'rgba(255, 215, 0, 0.3)',
          },
        },
        axisLabel: {
          color: '#FFD700',
          fontSize: 11,
          fontFamily: 'monospace',
          formatter: (value: number) => value.toExponential(0),
        },
        splitLine: {
          show: false,
        },
        logScale: true,
        min: 1e10,
        max: 1e25,
      },
    ],
    series: [
      {
        name: '电子浓度',
        type: 'line',
        yAxisIndex: 0,
        data: data.depth.map((d, i) => [d, data.electronDensity[i]]),
        smooth: true,
        symbol: 'none',
        lineStyle: {
          width: 3,
          color: '#64FFDA',
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(100, 255, 218, 0.2)' },
              { offset: 1, color: 'rgba(100, 255, 218, 0)' },
            ],
          },
        },
      },
      {
        name: '空穴浓度',
        type: 'line',
        yAxisIndex: 0,
        data: data.depth.map((d, i) => [d, data.holeDensity[i]]),
        smooth: true,
        symbol: 'none',
        lineStyle: {
          width: 3,
          color: '#FF6B35',
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(255, 107, 53, 0.2)' },
              { offset: 1, color: 'rgba(255, 107, 53, 0)' },
            ],
          },
        },
      },
      {
        name: '复合速率',
        type: 'line',
        yAxisIndex: 1,
        data: data.depth.map((d, i) => [d, data.recombinationRate[i]]),
        smooth: true,
        symbol: 'none',
        lineStyle: {
          width: 2.5,
          color: '#FFD700',
          type: 'dashed',
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(255, 215, 0, 0.15)' },
              { offset: 1, color: 'rgba(255, 215, 0, 0)' },
            ],
          },
        },
      },
    ],
  };

  return (
    <div className="glass-card p-4 h-full">
      <ReactECharts option={option} style={{ height: '100%', minHeight: '400px' }} />
    </div>
  );
}
