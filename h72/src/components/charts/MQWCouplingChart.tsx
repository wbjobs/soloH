import ReactECharts from 'echarts-for-react';
import type { CoupledEnergyLevels, MQWParams } from '../../types';

interface MQWCouplingChartProps {
  data: CoupledEnergyLevels;
  mqwParams: MQWParams;
}

export function MQWCouplingChart({ data, mqwParams }: MQWCouplingChartProps) {
  const levelData = data.splitLevels.map((level, i) => ({
    value: level,
    itemStyle: {
      color: i === 0 ? '#64FFDA' : i % 2 === 0 ? '#4FD1C5' : '#38B2AC',
    },
  }));

  const wavefunctionData = data.wavefunctionOverlaps.map((overlap, i) => ({
    name: `阱${i + 1}-阱${i + 2}`,
    value: overlap * 100,
  }));

  const option = {
    backgroundColor: 'transparent',
    title: {
      text: '多量子阱耦合效应',
      textStyle: {
        color: '#CCD6F6',
        fontSize: 14,
        fontWeight: 600,
      },
      left: 10,
      top: 10,
    },
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(17, 34, 64, 0.95)',
      borderColor: 'rgba(100, 255, 218, 0.3)',
      textStyle: { color: '#CCD6F6' },
    },
    grid: [
      {
        left: '10%',
        right: '55%',
        top: '15%',
        bottom: '55%',
      },
      {
        left: '10%',
        right: '55%',
        top: '60%',
        bottom: '10%',
      },
      {
        left: '55%',
        right: '5%',
        top: '15%',
        bottom: '10%',
      },
    ],
    xAxis: [
      {
        gridIndex: 0,
        type: 'category',
        data: levelData.map((_, i) => `E${i + 1}`),
        axisLine: { lineStyle: { color: '#4A5568' } },
        axisLabel: { color: '#8892B0', fontSize: 10 },
      },
      {
        gridIndex: 1,
        type: 'category',
        data: wavefunctionData.map(d => d.name),
        axisLine: { lineStyle: { color: '#4A5568' } },
        axisLabel: { color: '#8892B0', fontSize: 9, rotate: 45 },
      },
      {
        gridIndex: 2,
        show: false,
        type: 'value',
        min: 0,
        max: 100,
      },
    ],
    yAxis: [
      {
        gridIndex: 0,
        type: 'value',
        name: '能级 (eV)',
        nameTextStyle: { color: '#8892B0', fontSize: 10 },
        axisLine: { lineStyle: { color: '#4A5568' } },
        axisLabel: { color: '#8892B0', fontSize: 10 },
        splitLine: { lineStyle: { color: 'rgba(74, 85, 104, 0.3)' } },
      },
      {
        gridIndex: 1,
        type: 'value',
        name: '波函数重叠 (%)',
        nameTextStyle: { color: '#8892B0', fontSize: 10 },
        axisLine: { lineStyle: { color: '#4A5568' } },
        axisLabel: { color: '#8892B0', fontSize: 10, formatter: '{value}%' },
        splitLine: { lineStyle: { color: 'rgba(74, 85, 104, 0.3)' } },
      },
      {
        gridIndex: 2,
        show: false,
        type: 'category',
      },
    ],
    series: [
      {
        name: '耦合分裂能级',
        type: 'bar',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: levelData,
        barWidth: '60%',
        label: {
          show: true,
          position: 'top',
          color: '#CCD6F6',
          fontSize: 9,
          formatter: (params: any) => params.value.toFixed(3) + ' eV',
        },
      },
      {
        name: '波函数重叠积分',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: wavefunctionData.map(d => ({
          value: d.value,
          itemStyle: {
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(100, 255, 218, 0.8)' },
                { offset: 1, color: 'rgba(100, 255, 218, 0.2)' },
              ],
            },
          },
        })),
        barWidth: '50%',
      },
      {
        name: '耦合参数',
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['78%', '50%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 10,
          borderColor: '#112240',
          borderWidth: 2,
        },
        label: {
          show: true,
          position: 'inside',
          color: '#CCD6F6',
          fontSize: 11,
          formatter: (params: any) => {
            return `${params.name}\n${params.value}`;
          },
        },
        data: [
          {
            value: (data.minibandWidth * 1000).toFixed(2),
            name: '微带宽度\n(meV)',
            itemStyle: { color: '#64FFDA' },
          },
          {
            value: (data.couplingStrength * 1000).toFixed(2),
            name: '耦合强度\n(meV)',
            itemStyle: { color: '#FF6B35' },
          },
          {
            value: mqwParams.numWells,
            name: '量子阱\n数量',
            itemStyle: { color: '#FFD166' },
          },
          {
            value: (data.wavefunctionOverlaps.length > 0 ? 
              (Math.max(...data.wavefunctionOverlaps) * 100).toFixed(1) : '0'),
            name: '最大重叠\n(%)',
            itemStyle: { color: '#A8B2D1' },
          },
        ],
      },
    ],
  };

  return (
    <div className="glass-card p-5">
      <ReactECharts option={option} style={{ height: '350px' }} />
      <div className="mt-4 grid grid-cols-2 gap-4">
        <div className="p-3 bg-space-800/30 rounded-lg">
          <p className="text-xs text-slate-500 mb-1">微带宽度</p>
          <p className="text-lg font-mono text-quantum-400">
            {(data.minibandWidth * 1000).toFixed(2)} meV
          </p>
        </div>
        <div className="p-3 bg-space-800/30 rounded-lg">
          <p className="text-xs text-slate-500 mb-1">耦合强度</p>
          <p className="text-lg font-mono text-energy-400">
            {(data.couplingStrength * 1000).toFixed(2)} meV
          </p>
        </div>
      </div>
    </div>
  );
}
