import ReactECharts from 'echarts-for-react';
import type { BandDiagram as BandDiagramType } from '../../types';

interface BandDiagramProps {
  data: BandDiagramType;
}

export function BandDiagram({ data }: BandDiagramProps) {
  const minEnergy = Math.min(...data.valenceBand) - 0.5;
  const maxEnergy = Math.max(...data.conductionBand) + 0.5;

  const option = {
    backgroundColor: 'transparent',
    title: {
      text: '能带图',
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
          const color = p.seriesName === '导带' ? '#64FFDA' : p.seriesName === '价带' ? '#FF6B35' : '#FFD700';
          html += `<div style="color: #8892B0;">${p.seriesName}: <span style="color: ${color};">${p.value[1].toFixed(3)} eV</span></div>`;
        });
        html += '</div>';
        return html;
      },
    },
    legend: {
      data: ['导带 (E_c)', '价带 (E_v)', '费米能级 (E_f)'],
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
      right: 30,
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
    yAxis: {
      type: 'value',
      name: '能量 (eV)',
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
      min: minEnergy,
      max: maxEnergy,
    },
    series: [
      {
        name: '导带 (E_c)',
        type: 'line',
        data: data.depth.map((d, i) => [d, data.conductionBand[i]]),
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
              { offset: 0, color: 'rgba(100, 255, 218, 0.1)' },
              { offset: 1, color: 'rgba(100, 255, 218, 0)' },
            ],
          },
        },
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: {
            type: 'dashed',
            color: 'rgba(136, 146, 176, 0.3)',
            width: 1,
          },
          data: data.layerBoundaries.slice(1, -1).map(lb => ({
            xAxis: lb.position,
            label: {
              formatter: lb.name,
              position: 'insideEndTop',
              color: '#8892B0',
              fontSize: 10,
            },
          })),
        },
      },
      {
        name: '价带 (E_v)',
        type: 'line',
        data: data.depth.map((d, i) => [d, data.valenceBand[i]]),
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
              { offset: 0, color: 'rgba(255, 107, 53, 0.15)' },
              { offset: 1, color: 'rgba(255, 107, 53, 0)' },
            ],
          },
        },
      },
      {
        name: '费米能级 (E_f)',
        type: 'line',
        data: data.depth.map((d, i) => [d, data.fermiLevel[i]]),
        smooth: true,
        symbol: 'none',
        lineStyle: {
          width: 2,
          color: '#FFD700',
          type: 'dashed',
        },
      },
    ],
    graphic: data.layerBoundaries.slice(0, -1).map((lb, index) => ({
      type: 'rect',
      left: 70 + (lb.position / data.depth[data.depth.length - 1]) * (window.innerWidth - 100),
      top: 60,
      shape: {
        width: ((data.layerBoundaries[index + 1].position - lb.position) / data.depth[data.depth.length - 1]) * (window.innerWidth - 100),
        height: window.innerHeight - 200,
      },
      style: {
        fill: index % 2 === 0 ? 'rgba(100, 255, 218, 0.03)' : 'rgba(255, 107, 53, 0.03)',
        stroke: 'none',
      },
      silent: true,
    })),
  };

  return (
    <div className="glass-card p-4 h-full">
      <ReactECharts option={option} style={{ height: '100%', minHeight: '400px' }} />
    </div>
  );
}
