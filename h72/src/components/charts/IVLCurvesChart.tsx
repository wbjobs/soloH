import ReactECharts from 'echarts-for-react';
import type { IVLCharacteristics } from '../../types';

interface IVLCurvesChartProps {
  data: IVLCharacteristics;
}

export function IVLCurvesChart({ data }: IVLCurvesChartProps) {
  const option = {
    backgroundColor: 'transparent',
    title: {
      text: '电流-电压-亮度 (IVL) 特性',
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
    },
    legend: {
      data: ['电流密度', '亮度'],
      textStyle: {
        color: '#8892B0',
        fontSize: 12,
      },
      top: 10,
      right: 20,
      icon: 'roundRect',
    },
    grid: {
      left: 70,
      right: 70,
      top: 60,
      bottom: 50,
    },
    xAxis: {
      type: 'value',
      name: '偏置电压 (V)',
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
        name: '电流密度 (mA/cm²)',
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
        },
        splitLine: {
          lineStyle: {
            color: 'rgba(136, 146, 176, 0.1)',
          },
        },
        logScale: true,
      },
      {
        type: 'value',
        name: '亮度 (cd/m²)',
        nameTextStyle: {
          color: '#FF6B35',
          fontSize: 12,
        },
        axisLine: {
          lineStyle: {
            color: 'rgba(255, 107, 53, 0.3)',
          },
        },
        axisLabel: {
          color: '#FF6B35',
          fontSize: 11,
          fontFamily: 'monospace',
        },
        splitLine: {
          show: false,
        },
        logScale: true,
      },
    ],
    series: [
      {
        name: '电流密度',
        type: 'line',
        yAxisIndex: 0,
        data: data.jvData.map(d => [d.voltage, Math.max(d.currentDensity, 1e-5)]),
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: {
          width: 2.5,
          color: '#64FFDA',
        },
        itemStyle: {
          color: '#64FFDA',
          borderColor: '#0A192F',
          borderWidth: 2,
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
        name: '亮度',
        type: 'line',
        yAxisIndex: 1,
        data: data.lvData.map(d => [d.voltage, Math.max(d.brightness, 1e-3)]),
        smooth: true,
        symbol: 'diamond',
        symbolSize: 6,
        lineStyle: {
          width: 2.5,
          color: '#FF6B35',
          type: 'solid',
        },
        itemStyle: {
          color: '#FF6B35',
          borderColor: '#0A192F',
          borderWidth: 2,
        },
      },
    ],
    graphic: [
      {
        type: 'text',
        right: 20,
        bottom: 20,
        style: {
          text: [
            `开启电压: ${data.turnOnVoltage.toFixed(2)} V`,
            `最大EQE: ${data.maxEQE.toFixed(2)} %`,
          ].join('\n'),
          fill: '#8892B0',
          fontSize: 12,
          fontFamily: 'monospace',
          lineHeight: 20,
        },
      },
    ],
  };

  return (
    <div className="glass-card p-4 h-full">
      <ReactECharts option={option} style={{ height: '100%', minHeight: '350px' }} />
    </div>
  );
}
