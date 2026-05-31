import { useSimulationStore } from '../../store/useSimulationStore';
import { useParameterStore } from '../../store/useParameterStore';
import { Clock, Droplets, Gauge, Activity, Cpu, Thermometer } from 'lucide-react';
import { vecLength } from '../../types/physics';

export function StatusBar() {
  const {
    particles,
    simulationTime,
    fps,
    isRunning,
    isPaused,
    currentImpactData,
    peakForce,
    peakPressure
  } = useSimulationStore();

  const { sphParams } = useParameterStore();

  const currentForce = currentImpactData ? vecLength(currentImpactData.totalForce) : 0;
  const activeParticles = particles.filter(p => p.isActive).length;

  const getStatusColor = () => {
    if (!isRunning) return 'text-slate-400';
    if (isPaused) return 'text-amber-400';
    return 'text-green-400';
  };

  const getStatusText = () => {
    if (!isRunning) return '就绪';
    if (isPaused) return '已暂停';
    return '运行中';
  };

  return (
    <div className="absolute bottom-0 left-0 right-0 h-12 bg-slate-900/90 backdrop-blur-sm border-t border-cyan-500/20 flex items-center justify-between px-4 z-10">
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${getStatusColor()} animate-pulse`} />
          <span className={`text-sm font-medium ${getStatusColor()}`}>
            {getStatusText()}
          </span>
        </div>

        <div className="h-4 w-px bg-slate-700" />

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <Clock size={14} className="text-cyan-400" />
            <span className="text-xs text-slate-400">模拟时间:</span>
            <span className="text-sm font-mono text-white">
              {simulationTime.toFixed(2)}s
            </span>
          </div>

          <div className="flex items-center gap-1.5">
            <Droplets size={14} className="text-blue-400" />
            <span className="text-xs text-slate-400">粒子数:</span>
            <span className="text-sm font-mono text-white">
              {activeParticles} / {sphParams.maxParticles}
            </span>
          </div>

          <div className="flex items-center gap-1.5">
            <Activity size={14} className="text-emerald-400" />
            <span className="text-xs text-slate-400">FPS:</span>
            <span className={`text-sm font-mono ${fps >= 30 ? 'text-green-400' : fps >= 15 ? 'text-amber-400' : 'text-red-400'}`}>
              {fps}
            </span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-6">
        <div className="flex items-center gap-1.5">
          <Gauge size={14} className="text-orange-400" />
          <span className="text-xs text-slate-400">当前冲击力:</span>
          <span className="text-sm font-mono text-white">
            {currentForce.toFixed(1)} N
          </span>
        </div>

        <div className="flex items-center gap-1.5">
          <Thermometer size={14} className="text-rose-400" />
          <span className="text-xs text-slate-400">峰值冲击力:</span>
          <span className="text-sm font-mono text-orange-400">
            {peakForce.toFixed(1)} N
          </span>
        </div>

        <div className="flex items-center gap-1.5">
          <Cpu size={14} className="text-purple-400" />
          <span className="text-xs text-slate-400">峰值压强:</span>
          <span className="text-sm font-mono text-rose-400">
            {(peakPressure / 1000).toFixed(2)} kPa
          </span>
        </div>

        {currentImpactData && currentImpactData.particleCount > 0 && (
          <>
            <div className="h-4 w-px bg-slate-700" />
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-slate-400">冲击粒子:</span>
              <span className="text-sm font-mono text-cyan-400">
                {currentImpactData.particleCount}
              </span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
