import { useEffect, useRef, useState } from 'react';
import { Heart, Activity, Mic, MicOff, Link, Unlink } from 'lucide-react';
import { useAudioStore } from '../../store/useAudioStore';
import { HRVDetection } from '../../audio/HRVDetection';

export const HRVPanel = () => {
  const { hrv, setHRV, setBeatFrequency, currentBand, beatFrequency } = useAudioStore();
  const hrvDetectionRef = useRef<HRVDetection | null>(null);
  const [isStarting, setIsStarting] = useState(false);

  useEffect(() => {
    return () => {
      if (hrvDetectionRef.current) {
        hrvDetectionRef.current.stop();
        hrvDetectionRef.current = null;
      }
    };
  }, []);

  const handleToggleHRV = async () => {
    if (hrv.isDetecting) {
      if (hrvDetectionRef.current) {
        hrvDetectionRef.current.stop();
        hrvDetectionRef.current = null;
      }
      setHRV({
        enabled: false,
        isDetecting: false,
        currentHeartRate: 0,
        averageHeartRate: 0,
        hrvValue: 0,
        confidence: 0
      });
    } else {
      setIsStarting(true);
      try {
        const detection = new HRVDetection(
          (hr, hrvValue, confidence) => {
            setHRV({
              currentHeartRate: hr,
              hrvValue,
              confidence,
              averageHeartRate: hrv.averageHeartRate === 0
                ? hr
                : (hrv.averageHeartRate * 0.9 + hr * 0.1)
            });

            if (hrv.followHeartRate) {
              const targetFrequency = Math.max(
                currentBand.frequencyRange[0],
                Math.min(
                  currentBand.frequencyRange[1],
                  hr / 60
                )
              );
              if (Math.abs(targetFrequency - beatFrequency) > 0.1) {
                setBeatFrequency(targetFrequency);
              }
            }
          },
          () => {
            if (useAudioStore.getState().haptic.enabled) {
              useAudioStore.getState().triggerHaptic(80);
            }
          }
        );

        const success = await detection.start();
        if (success) {
          hrvDetectionRef.current = detection;
          setHRV({
            enabled: true,
            isDetecting: true
          });
        }
      } catch (error) {
        console.error('启动HRV检测失败:', error);
      } finally {
        setIsStarting(false);
      }
    }
  };

  const getHRVStatusColor = () => {
    if (hrv.hrvValue > 60) return '#10b981';
    if (hrv.hrvValue > 30) return '#f59e0b';
    return '#ef4444';
  };

  const getHRVStatusText = () => {
    if (hrv.hrvValue > 60) return '优秀';
    if (hrv.hrvValue > 30) return '正常';
    if (hrv.hrvValue > 0) return '偏低';
    return '--';
  };

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-white/80 tracking-wider flex items-center gap-2">
        <Activity size={14} />
        心率变异性 (HRV)
      </h3>
      <div className="p-4 bg-white/5 rounded-2xl backdrop-blur-sm space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div
              className={`
                w-12 h-12 rounded-xl flex items-center justify-center
                transition-all duration-300
                ${hrv.isDetecting ? 'animate-pulse' : ''}
              `}
              style={{
                backgroundColor: hrv.isDetecting
                  ? 'rgba(239, 68, 68, 0.2)'
                  : 'rgba(255, 255, 255, 0.05)',
                boxShadow: hrv.isDetecting
                  ? '0 0 20px rgba(239, 68, 68, 0.4)'
                  : 'none'
              }}
            >
              <Heart
                size={24}
                style={{
                  color: hrv.isDetecting ? '#ef4444' : 'rgba(255, 255, 255, 0.5)'
                }}
                fill={hrv.isDetecting ? '#ef4444' : 'none'}
              />
            </div>
            <div>
              <div className="text-2xl font-bold text-white font-mono">
                {hrv.isDetecting ? hrv.currentHeartRate.toFixed(0) : '--'}
                <span className="text-sm text-white/50 ml-1">BPM</span>
              </div>
              <div className="text-xs text-white/50">
                平均: {hrv.isDetecting ? hrv.averageHeartRate.toFixed(0) : '--'} BPM
              </div>
            </div>
          </div>
          <button
            onClick={handleToggleHRV}
            disabled={isStarting}
            className={`
              flex items-center gap-2 px-4 py-2 rounded-xl
              transition-all duration-300 text-sm font-medium
              disabled:opacity-50
              ${hrv.isDetecting
                ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30 border border-red-500/30'
                : 'bg-white/10 text-white hover:bg-white/20 border border-white/20'
              }
            `}
          >
            {isStarting ? (
              <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
            ) : hrv.isDetecting ? (
              <><MicOff size={16} /> 停止</>
            ) : (
              <><Mic size={16} /> 开始检测</>
            )}
          </button>
        </div>

        {hrv.isDetecting && (
          <>
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-white/5 rounded-xl p-3">
                <div className="text-[10px] text-white/40 mb-1">HRV 值</div>
                <div className="flex items-baseline gap-1">
                  <span
                    className="text-xl font-bold font-mono"
                    style={{ color: getHRVStatusColor() }}
                  >
                    {hrv.hrvValue.toFixed(1)}
                  </span>
                  <span className="text-xs text-white/40">ms</span>
                </div>
                <div
                  className="text-xs mt-1"
                  style={{ color: getHRVStatusColor() }}
                >
                  {getHRVStatusText()}
                </div>
              </div>
              <div className="bg-white/5 rounded-xl p-3">
                <div className="text-[10px] text-white/40 mb-1">检测置信度</div>
                <div className="text-xl font-bold text-white font-mono">
                  {(hrv.confidence * 100).toFixed(0)}%
                </div>
                <div className="w-full h-1.5 bg-white/10 rounded-full mt-2 overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-300"
                    style={{
                      width: `${hrv.confidence * 100}%`,
                      backgroundColor: hrv.confidence > 0.6 ? '#10b981' : hrv.confidence > 0.3 ? '#f59e0b' : '#ef4444'
                    }}
                  />
                </div>
              </div>
            </div>

            <div className="pt-3 border-t border-white/10">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-white/60">追随心率节拍</span>
                <button
                  onClick={() => setHRV({ followHeartRate: !hrv.followHeartRate })}
                  className={`
                    flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs
                    transition-all duration-300
                    ${hrv.followHeartRate
                      ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                      : 'bg-white/5 text-white/50 border border-white/10'
                    }
                  `}
                >
                  {hrv.followHeartRate ? (
                    <><Link size={12} /> 已同步</>
                  ) : (
                    <><Unlink size={12} /> 未同步</>
                  )}
                </button>
              </div>
              {hrv.followHeartRate && (
                <div className="text-[11px] text-white/40">
                  节拍频率将自动调整至心率的 1/60（{currentBand.name} 频段）
                </div>
              )}
            </div>
          </>
        )}

        {!hrv.isDetecting && (
          <div className="text-[11px] text-white/40 text-center py-2">
            💡 将手指轻放在麦克风旁，或使用带麦克风的耳机
          </div>
        )}
      </div>
    </div>
  );
};
