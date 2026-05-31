import { useMemo, useRef } from 'react';
import { X, TrendingUp, Gauge, Activity, Zap, Droplets } from 'lucide-react';
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler } from 'chart.js';
import { Line } from 'react-chartjs-2';
import { useSimulationStore } from '../../store/useSimulationStore';
import { vecLength } from '../../types/physics';

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

interface DataMonitorProps {
  isOpen: boolean;
  onClose: () => void;
}

interface StatCardProps {
  icon: any;
  label: string;
  value: string;
  unit: string;
  color: string;
}

function StatCard({ icon: Icon, label, value, unit, color }: StatCardProps) {
  return (
    <div className="bg-slate-800/50 rounded-lg p-3 border border-slate-700">
      <div className="flex items-center gap-2 mb-1">
        <Icon size={14} className={color} />
        <span className="text-xs text-slate-400">{label}</span>
      </div>
      <div className="flex items-baseline gap-1">
        <span className={`text-lg font-bold font-mono ${color}`}>{value}</span>
        <span className="text-xs text-slate-500">{unit}</span>
      </div>
    </div>
  );
}

function ColorLegend() {
  const colors = [
    { color: '#1e3a5f', label: '低速 (0 m/s)' },
    { color: '#4ecdc4', label: '中速 (5 m/s)' },
    { color: '#95e619', label: '较快 (8 m/s)' },
    { color: '#ffe66d', label: '高速 (12 m/s)' },
    { color: '#ff6b35', label: '极快 (15+ m/s)' }
  ];

  return (
    <div className="bg-slate-800/50 rounded-lg p-3 border border-slate-700">
      <h4 className="text-xs font-medium text-slate-400 mb-2">粒子速度颜色图例</h4>
      <div className="space-y-1">
        {colors.map((item, i) => (
          <div key={i} className="flex items-center gap-2">
            <div className="w-4 h-4 rounded" style={{ backgroundColor: item.color }} />
            <span className="text-xs text-slate-300">{item.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function DataMonitor({ isOpen, onClose }: DataMonitorProps) {
  const {
    impactForceHistory,
    currentImpactData,
    peakForce,
    peakPressure,
    simulationTime,
    fps,
    stats
  } = useSimulationStore();

  const chartData = useMemo(() => {
    const labels = impactForceHistory.slice(-100).map(d => d.timestamp.toFixed(2));
    const forceMagnitude = impactForceHistory.slice(-100).map(d => 
      vecLength(d.totalForce)
    );
    const pressure = impactForceHistory.slice(-100).map(d => d.maxPressure / 1000);

    return {
      labels,
      datasets: [
        {
          label: '总冲击力 (N)',
          data: forceMagnitude,
          borderColor: '#4ecdc4',
          backgroundColor: 'rgba(78, 205, 196, 0.1)',
          borderWidth: 2,
          fill: true,
          tension: 0.3,
          yAxisID: 'y'
        },
        {
          label: '最大压强 (kPa)',
          data: pressure,
          borderColor: '#ff6b35',
          backgroundColor: 'rgba(255, 107, 53, 0.1)',
          borderWidth: 2,
          fill: true,
          tension: 0.3,
          yAxisID: 'y1'
        }
      ]
    };
  }, [impactForceHistory]);

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 0 },
    interaction: {
      mode: 'index' as const,
      intersect: false,
    },
    plugins: {
      legend: {
        display: true,
        position: 'top' as const,
        labels: {
          color: '#94a3b8',
          font: { size: 10 },
          boxWidth: 12,
          padding: 8
        }
      },
      tooltip: {
        backgroundColor: 'rgba(15, 23, 42, 0.95)',
        titleColor: '#e2e8f0',
        bodyColor: '#94a3b8',
        borderColor: '#334155',
        borderWidth: 1,
        padding: 8,
        displayColors: true
      }
    },
    scales: {
      x: {
        title: {
          display: true,
          text: '时间 (s)',
          color: '#64748b',
          font: { size: 10 }
        },
        ticks: {
          color: '#64748b',
          font: { size: 8 },
          maxTicksLimit: 6
        },
        grid: {
          color: 'rgba(51, 65, 85, 0.5)'
        }
      },
      y: {
        type: 'linear' as const,
        display: true,
        position: 'left' as const,
        title: {
          display: true,
          text: '冲击力 (N)',
          color: '#4ecdc4',
          font: { size: 10 }
        },
        ticks: {
          color: '#64748b',
          font: { size: 8 }
        },
        grid: {
          color: 'rgba(51, 65, 85, 0.3)'
        }
      },
      y1: {
        type: 'linear' as const,
        display: true,
        position: 'right' as const,
        title: {
          display: true,
          text: '压强 (kPa)',
          color: '#ff6b35',
          font: { size: 10 }
        },
        ticks: {
          color: '#64748b',
          font: { size: 8 }
        },
        grid: {
          drawOnChartArea: false
        }
      }
    }
  };

  const currentForceMagnitude = currentImpactData ? vecLength(currentImpactData.totalForce) : 0;

  if (!isOpen) return null;

  return (
    <div className="absolute right-0 top-16 bottom-12 w-96 bg-slate-900/95 backdrop-blur-sm border-l border-cyan-500/20 overflow-y-auto z-20">
      <div className="p-4">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold text-cyan-400">数据监控面板</h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-700 rounded-md transition-colors"
          >
            <X size={20} className="text-slate-400" />
          </button>
        </div>

        <div className="grid grid-cols-2 gap-3 mb-4">
          <StatCard
            icon={Zap}
            label="当前冲击力"
            value={currentForceMagnitude.toFixed(1)}
            unit="N"
            color="text-cyan-400"
          />
          <StatCard
            icon={Gauge}
            label="峰值冲击力"
            value={peakForce.toFixed(1)}
            unit="N"
            color="text-orange-400"
          />
          <StatCard
            icon={TrendingUp}
            label="当前压强"
            value={currentImpactData ? (currentImpactData.maxPressure / 1000).toFixed(2) : '0.00'}
            unit="kPa"
            color="text-emerald-400"
          />
          <StatCard
            icon={Activity}
            label="峰值压强"
            value={(peakPressure / 1000).toFixed(2)}
            unit="kPa"
            color="text-rose-400"
          />
        </div>

        <div className="grid grid-cols-3 gap-2 mb-4">
          <StatCard
            icon={Droplets}
            label="冲击粒子"
            value={currentImpactData?.particleCount.toString() || '0'}
            unit="个"
            color="text-blue-400"
          />
          <StatCard
            icon={Activity}
            label="模拟时间"
            value={simulationTime.toFixed(1)}
            unit="s"
            color="text-purple-400"
          />
          <StatCard
            icon={Gauge}
            label="帧率"
            value={fps.toString()}
            unit="FPS"
            color="text-amber-400"
          />
        </div>

        <div className="bg-slate-800/50 rounded-lg p-3 mb-4 border border-slate-700">
          <h4 className="text-sm font-medium text-slate-300 mb-2">模拟统计</h4>
          <div className="space-y-1 text-xs">
            <div className="flex justify-between">
              <span className="text-slate-400">平均密度:</span>
              <span className="text-slate-200 font-mono">{stats.avgDensity.toFixed(0)} kg/m³</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">平均速度:</span>
              <span className="text-slate-200 font-mono">{stats.avgSpeed.toFixed(2)} m/s</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">活跃网格数:</span>
              <span className="text-slate-200 font-mono">{stats.activeCells}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">冲击面积:</span>
              <span className="text-slate-200 font-mono">
                {currentImpactData ? currentImpactData.impactArea.toFixed(4) : '0.0000'} m²
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">冲击粒子平均速度:</span>
              <span className="text-slate-200 font-mono">
                {currentImpactData ? currentImpactData.averageVelocity.toFixed(2) : '0.00'} m/s
              </span>
            </div>
          </div>
        </div>

        <div className="bg-slate-800/50 rounded-lg p-3 mb-4 border border-slate-700">
          <h4 className="text-sm font-medium text-slate-300 mb-3">冲击力与压强时序曲线</h4>
          <div className="h-64">
            <Line data={chartData} options={chartOptions} />
          </div>
        </div>

        <ColorLegend />

        <div className="mt-4 bg-slate-800/50 rounded-lg p-3 border border-cyan-500/20">
          <h4 className="text-sm font-medium text-cyan-400 mb-2">物理模型说明</h4>
          <div className="text-xs text-slate-400 space-y-1">
            <p><span className="text-cyan-300">• Bingham模型:</span> τ = τ_y + μ·γ̇</p>
            <p><span className="text-cyan-300">• 屈服应力:</span> 低于此值时流体表现为刚体</p>
            <p><span className="text-cyan-300">• SPH核函数:</span> 三次样条核 (Cubic Spline)</p>
            <p><span className="text-cyan-300">• 状态方程:</span> Tait方程 (弱可压缩)</p>
            <p><span className="text-cyan-300">• 时间积分:</span> 半隐式欧拉法</p>
          </div>
        </div>
      </div>
    </div>
  );
}
