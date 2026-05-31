import React, { useState, useEffect } from 'react';
import { Layers, Zap, AlertTriangle, CheckCircle, XCircle, Activity, Settings } from 'lucide-react';
import { useSimulationStore } from '../../store/useSimulationStore';
import { MultichannelConfig, ChannelResult, FaultDetectionStatus, ChannelFaultStatus, FaultType, OverallStatus } from '../../types';

interface MultichannelPanelProps {
  channelResults: ChannelResult[];
  faultStatus?: FaultDetectionStatus;
  summaryStats?: any;
}

const getFaultTypeLabel = (type: FaultType): string => {
  const labels: Record<FaultType, string> = {
    normal: '正常',
    partial_blockage: '部分堵塞',
    full_blockage: '完全堵塞',
    flow_instability: '流动不稳定',
    pressure_anomaly: '压力异常',
    leakage: '泄漏',
  };
  return labels[type] || type;
};

const getFaultTypeColor = (type: FaultType): string => {
  const colors: Record<FaultType, string> = {
    normal: 'text-green-400',
    partial_blockage: 'text-yellow-400',
    full_blockage: 'text-red-400',
    flow_instability: 'text-orange-400',
    pressure_anomaly: 'text-purple-400',
    leakage: 'text-pink-400',
  };
  return colors[type] || 'text-zinc-400';
};

const getStatusColor = (status: OverallStatus): string => {
  const colors: Record<OverallStatus, string> = {
    normal: 'bg-green-500',
    warning: 'bg-yellow-500',
    critical: 'bg-red-500',
  };
  return colors[status] || 'bg-zinc-500';
};

const getStatusBg = (status: OverallStatus): string => {
  const colors: Record<OverallStatus, string> = {
    normal: 'bg-green-500/10 border-green-500/30',
    warning: 'bg-yellow-500/10 border-yellow-500/30',
    critical: 'bg-red-500/10 border-red-500/30',
  };
  return colors[status] || 'bg-zinc-800 border-zinc-700';
};

export const MultichannelPanel: React.FC<MultichannelPanelProps> = ({
  channelResults,
  faultStatus,
  summaryStats,
}) => {
  const {
    multichannelConfig,
    setChannelBlocked,
    setChannelEnabled,
    updateMultichannelConfig,
  } = useSimulationStore();

  const [localConfig, setLocalConfig] = useState<MultichannelConfig>(multichannelConfig);
  const [showSettings, setShowSettings] = useState(false);

  const enabledChannels = channelResults.filter((c) => c.enabled);

  const handleUpdateConfig = () => {
    updateMultichannelConfig(localConfig);
  };

  return (
    <div className="bg-zinc-900/60 backdrop-blur-sm rounded-2xl border border-zinc-800 p-5 space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-cyan-500 to-blue-500 rounded-xl flex items-center justify-center">
            <Layers className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="font-semibold text-zinc-100">多通道并行仿真</h3>
            <p className="text-xs text-zinc-500">
              {enabledChannels.length}/{channelResults.length} 通道运行中 · 通道间串扰仿真
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {faultStatus && (
            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium border ${getStatusBg(faultStatus.overallStatus)}`}>
              <div className={`w-2 h-2 rounded-full ${getStatusColor(faultStatus.overallStatus)} ${faultStatus.overallStatus !== 'normal' ? 'animate-pulse' : ''}`} />
              {faultStatus.overallStatus === 'normal' ? '系统正常' : faultStatus.overallStatus === 'warning' ? '存在告警' : '严重故障'}
            </div>
          )}
          <button
            onClick={() => setShowSettings(!showSettings)}
            className="p-2 hover:bg-zinc-800 rounded-lg transition-colors"
          >
            <Settings size={16} className="text-zinc-400" />
          </button>
        </div>
      </div>

      {showSettings && (
        <div className="bg-zinc-800/30 rounded-xl p-4 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-zinc-500 block mb-1">通道数量</label>
              <input
                type="number"
                value={localConfig.nChannels}
                onChange={(e) => setLocalConfig({ ...localConfig, nChannels: Number(e.target.value) })}
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-200 focus:border-cyan-500 focus:outline-none transition-colors"
                min={1}
                max={16}
              />
            </div>
            <div>
              <label className="text-xs text-zinc-500 block mb-1">通道间距 (μm)</label>
              <input
                type="number"
                value={localConfig.channelSpacing}
                onChange={(e) => setLocalConfig({ ...localConfig, channelSpacing: Number(e.target.value) })}
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-200 focus:border-cyan-500 focus:outline-none transition-colors"
                min={50}
                max={1000}
                step={10}
              />
            </div>
            <div>
              <label className="text-xs text-zinc-500 block mb-1">串扰强度</label>
              <input
                type="number"
                value={localConfig.crosstalkStrength}
                onChange={(e) => setLocalConfig({ ...localConfig, crosstalkStrength: Number(e.target.value) })}
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-200 focus:border-cyan-500 focus:outline-none transition-colors"
                min={0}
                max={1}
                step={0.05}
              />
            </div>
            <div>
              <label className="text-xs text-zinc-500 block mb-1">衰减长度</label>
              <input
                type="number"
                value={localConfig.crosstalkDecay}
                onChange={(e) => setLocalConfig({ ...localConfig, crosstalkDecay: Number(e.target.value) })}
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-200 focus:border-cyan-500 focus:outline-none transition-colors"
                min={0.1}
                max={10}
                step={0.1}
              />
            </div>
          </div>
          <button
            onClick={handleUpdateConfig}
            className="w-full py-2 bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg text-sm font-medium transition-colors"
          >
            应用配置
          </button>
        </div>
      )}

      {summaryStats && (
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-zinc-800/50 rounded-xl p-3">
            <div className="text-xs text-zinc-500 mb-1">总产出频率</div>
            <div className="text-lg font-bold text-cyan-400">
              {summaryStats.totalThroughputHz?.toFixed(2) || '-'} Hz
            </div>
          </div>
          <div className="bg-zinc-800/50 rounded-xl p-3">
            <div className="text-xs text-zinc-500 mb-1">通道均匀度</div>
            <div className="text-lg font-bold text-emerald-400">
              {summaryStats.channelUniformityScore?.toFixed(1) || '-'}%
            </div>
          </div>
          <div className="bg-zinc-800/50 rounded-xl p-3">
            <div className="text-xs text-zinc-500 mb-1">平均液滴尺寸</div>
            <div className="text-lg font-bold text-blue-400">
              {summaryStats.meanDropletSize?.toFixed(1) || '-'} μm
            </div>
          </div>
          <div className="bg-zinc-800/50 rounded-xl p-3">
            <div className="text-xs text-zinc-500 mb-1">尺寸变异系数</div>
            <div className={`text-lg font-bold ${(summaryStats.sizeCvPercent || 0) < 5 ? 'text-green-400' : 'text-yellow-400'}`}>
              {summaryStats.sizeCvPercent?.toFixed(2) || '-'}%
            </div>
          </div>
        </div>
      )}

      <div className="space-y-3">
        <div className="text-sm font-medium text-zinc-300">通道状态</div>
        <div className="grid grid-cols-2 gap-3">
          {channelResults.map((channel) => {
            const fault = faultStatus?.channelStatuses.find((f) => f.channelId === channel.channelId);
            const isBlocked = channel.blocked;

            return (
              <div
                key={channel.channelId}
                className={`p-3 rounded-xl border transition-all ${
                  isBlocked
                    ? 'bg-red-500/10 border-red-500/30'
                    : fault && fault.faultType !== 'normal'
                    ? 'bg-yellow-500/10 border-yellow-500/30'
                    : 'bg-zinc-800/50 border-zinc-700/50 hover:border-zinc-600'
                }`}
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold ${
                      channel.enabled ? 'bg-cyan-500/20 text-cyan-400' : 'bg-zinc-800 text-zinc-600'
                    }`}>
                      CH{channel.channelId}
                    </div>
                    <div>
                      <div className="text-sm font-medium text-zinc-200">
                        通道 {channel.channelId}
                      </div>
                      <div className={`text-xs ${fault ? getFaultTypeColor(fault.faultType) : 'text-zinc-500'}`}>
                        {fault ? getFaultTypeLabel(fault.faultType) : '加载中...'}
                        {fault && fault.confidence > 0 && (
                          <span className="text-zinc-600"> ({(fault.confidence * 100).toFixed(0)}%)</span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => setChannelEnabled(channel.channelId, !channel.enabled)}
                      className={`p-1.5 rounded-lg transition-colors ${
                        channel.enabled ? 'text-green-400 hover:bg-green-500/20' : 'text-zinc-600 hover:bg-zinc-700'
                      }`}
                      title={channel.enabled ? '禁用通道' : '启用通道'}
                    >
                      {channel.enabled ? <CheckCircle size={14} /> : <XCircle size={14} />}
                    </button>
                  </div>
                </div>

                {channel.enabled && (
                  <>
                    <div className="grid grid-cols-2 gap-2 text-xs mb-2">
                      <div>
                        <span className="text-zinc-500">尺寸: </span>
                        <span className="text-zinc-200 font-mono">{channel.dropletSize.toFixed(1)} μm</span>
                      </div>
                      <div>
                        <span className="text-zinc-500">频率: </span>
                        <span className="text-zinc-200 font-mono">{channel.generationFrequency.toFixed(2)} Hz</span>
                      </div>
                      <div>
                        <span className="text-zinc-500">Qc: </span>
                        <span className="text-zinc-200 font-mono">{channel.continuousFlowRate.toFixed(1)}</span>
                      </div>
                      <div>
                        <span className="text-zinc-500">Qd: </span>
                        <span className="text-zinc-200 font-mono">{channel.dispersedFlowRate.toFixed(1)}</span>
                      </div>
                    </div>

                    {Math.abs(channel.crosstalkDeltaQc || 0) > 0.01 && (
                      <div className="flex items-center gap-1 text-xs text-orange-400">
                        <Zap size={10} />
                        <span>
                          串扰影响: ΔQc={(channel.crosstalkDeltaQc || 0).toFixed(2)}, ΔQd={(channel.crosstalkDeltaQd || 0).toFixed(2)}
                        </span>
                      </div>
                    )}

                    {fault && fault.blockageSeverity > 0 && (
                      <div className="mt-2">
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-zinc-500">堵塞程度</span>
                          <span className="text-red-400">{(fault.blockageSeverity * 100).toFixed(0)}%</span>
                        </div>
                        <div className="h-1.5 bg-zinc-700 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-gradient-to-r from-yellow-500 to-red-500 transition-all"
                            style={{ width: `${fault.blockageSeverity * 100}%` }}
                          />
                        </div>
                      </div>
                    )}
                  </>
                )}

                <div className="mt-2 flex gap-2">
                  {!isBlocked ? (
                    <button
                      onClick={() => setChannelBlocked(channel.channelId, true, 0.6)}
                      className="flex-1 py-1 text-xs bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded-lg transition-colors flex items-center justify-center gap-1"
                    >
                      <AlertTriangle size={10} />
                      模拟堵塞
                    </button>
                  ) : (
                    <button
                      onClick={() => setChannelBlocked(channel.channelId, false)}
                      className="flex-1 py-1 text-xs bg-green-500/10 hover:bg-green-500/20 text-green-400 rounded-lg transition-colors flex items-center justify-center gap-1"
                    >
                      <CheckCircle size={10} />
                      清除堵塞
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {faultStatus && faultStatus.anomalies.length > 0 && (
        <div className="space-y-2">
          <div className="text-sm font-medium text-zinc-300 flex items-center gap-2">
            <Activity size={14} />
            检测到的异常
          </div>
          <div className="space-y-2">
            {faultStatus.anomalies.map((anomaly, idx) => (
              <div
                key={idx}
                className={`p-3 rounded-lg text-sm border ${
                  anomaly.type.includes('full') || anomaly.type.includes('critical')
                    ? 'bg-red-500/10 border-red-500/30'
                    : 'bg-yellow-500/10 border-yellow-500/30'
                }`}
              >
                <div className="flex items-start gap-2">
                  <AlertTriangle size={14} className="text-yellow-400 flex-shrink-0 mt-0.5" />
                  <div>
                    <div className="font-medium text-zinc-200">{anomaly.description}</div>
                    <div className="text-xs text-zinc-500 mt-1">
                      置信度: {(anomaly.confidence * 100).toFixed(0)}%
                      {anomaly.severity !== undefined && ` · 严重程度: ${(anomaly.severity * 100).toFixed(0)}%`}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {faultStatus && faultStatus.recommendations.length > 0 && (
        <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4">
          <div className="text-sm font-medium text-blue-300 mb-2">操作建议</div>
          <ul className="space-y-1">
            {faultStatus.recommendations.map((rec, idx) => (
              <li key={idx} className="text-sm text-blue-400/80 flex items-start gap-2">
                <span className="text-blue-500">•</span>
                {rec}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};
