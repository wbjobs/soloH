import React, { useEffect, useRef } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import { SimulationTimeSeries } from '../../types';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

interface RealTimeChartProps {
  timeSeries: SimulationTimeSeries | null;
  targetSize?: number;
  pidEnabled?: boolean;
}

export const RealTimeChart: React.FC<RealTimeChartProps> = ({
  timeSeries,
  targetSize,
  pidEnabled = false
}) => {
  const chartRef = useRef<ChartJS<'line'>>(null);

  const sizeData = {
    labels: timeSeries?.timestamps.map(t => t.toFixed(1)) || [],
    datasets: [
      {
        label: '液滴尺寸 (μm)',
        data: timeSeries?.dropletSizes || [],
        borderColor: '#3B82F6',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        borderWidth: 2,
        fill: true,
        tension: 0.3,
        pointRadius: 0,
        pointHoverRadius: 4,
        yAxisID: 'y'
      },
      ...(pidEnabled && targetSize ? [{
        label: '目标尺寸 (μm)',
        data: timeSeries?.timestamps.map(() => targetSize) || [],
        borderColor: '#10B981',
        borderWidth: 2,
        borderDash: [5, 5],
        fill: false,
        tension: 0,
        pointRadius: 0,
        yAxisID: 'y'
      }] : [])
    ]
  };

  const freqData = {
    labels: timeSeries?.timestamps.map(t => t.toFixed(1)) || [],
    datasets: [
      {
        label: '生成频率 (Hz)',
        data: timeSeries?.frequencies || [],
        borderColor: '#F59E0B',
        backgroundColor: 'rgba(245, 158, 11, 0.1)',
        borderWidth: 2,
        fill: true,
        tension: 0.3,
        pointRadius: 0,
        pointHoverRadius: 4
      }
    ]
  };

  const flowRateData = {
    labels: timeSeries?.timestamps.map(t => t.toFixed(1)) || [],
    datasets: [
      {
        label: '连续相流速 (μL/min)',
        data: timeSeries?.continuousFlowRates || [],
        borderColor: '#06B6D4',
        backgroundColor: 'rgba(6, 182, 212, 0.1)',
        borderWidth: 2,
        fill: false,
        tension: 0.3,
        pointRadius: 0,
        pointHoverRadius: 4
      },
      {
        label: '离散相流速 (μL/min)',
        data: timeSeries?.dispersedFlowRates || [],
        borderColor: '#EC4899',
        backgroundColor: 'rgba(236, 72, 153, 0.1)',
        borderWidth: 2,
        fill: false,
        tension: 0.3,
        pointRadius: 0,
        pointHoverRadius: 4
      }
    ]
  };

  const commonOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: {
      duration: 0
    },
    interaction: {
      mode: 'index' as const,
      intersect: false
    },
    plugins: {
      legend: {
        display: true,
        position: 'top' as const,
        labels: {
          color: '#9CA3AF',
          font: {
            size: 11
          },
          usePointStyle: true,
          pointStyle: 'circle'
        }
      },
      tooltip: {
        backgroundColor: 'rgba(23, 23, 23, 0.95)',
        titleColor: '#E5E7EB',
        bodyColor: '#D1D5DB',
        borderColor: '#374151',
        borderWidth: 1,
        padding: 10,
        displayColors: true
      }
    },
    scales: {
      x: {
        display: true,
        title: {
          display: true,
          text: '时间 (s)',
          color: '#6B7280'
        },
        grid: {
          color: 'rgba(75, 85, 99, 0.3)'
        },
        ticks: {
          color: '#6B7280',
          maxTicksLimit: 8
        }
      },
      y: {
        display: true,
        grid: {
          color: 'rgba(75, 85, 99, 0.3)'
        },
        ticks: {
          color: '#6B7280'
        }
      }
    }
  };

  const sizeOptions = {
    ...commonOptions,
    plugins: {
      ...commonOptions.plugins,
      legend: {
        ...commonOptions.plugins.legend,
        labels: {
          ...commonOptions.plugins.legend.labels,
          filter: (item: any) => item.datasetIndex < 2
        }
      }
    }
  };

  const hasData = timeSeries && timeSeries.timestamps.length > 0;

  return (
    <div className="space-y-4">
      <div className="bg-zinc-900/50 border border-zinc-700/50 rounded-xl p-4">
        <h4 className="text-sm font-semibold text-zinc-200 mb-3">液滴尺寸趋势</h4>
        <div className="h-64">
          {hasData ? (
            <Line ref={chartRef} data={sizeData} options={sizeOptions} />
          ) : (
            <div className="h-full flex items-center justify-center text-zinc-500 text-sm">
              启动仿真以查看数据
            </div>
          )}
        </div>
      </div>

      <div className="bg-zinc-900/50 border border-zinc-700/50 rounded-xl p-4">
        <h4 className="text-sm font-semibold text-zinc-200 mb-3">生成频率趋势</h4>
        <div className="h-48">
          {hasData ? (
            <Line data={freqData} options={commonOptions} />
          ) : (
            <div className="h-full flex items-center justify-center text-zinc-500 text-sm">
              启动仿真以查看数据
            </div>
          )}
        </div>
      </div>

      <div className="bg-zinc-900/50 border border-zinc-700/50 rounded-xl p-4">
        <h4 className="text-sm font-semibold text-zinc-200 mb-3">流速变化</h4>
        <div className="h-48">
          {hasData ? (
            <Line data={flowRateData} options={commonOptions} />
          ) : (
            <div className="h-full flex items-center justify-center text-zinc-500 text-sm">
              启动仿真以查看数据
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
