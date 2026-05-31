import { useEffect, useRef } from 'react';
import { Brain, Sparkles, ThumbsUp, ThumbsDown, Minus, TrendingUp, History } from 'lucide-react';
import { useAudioStore } from '../../store/useAudioStore';
import { AdaptiveAITherapy } from '../../audio/AdaptiveAITherapy';
import { getBandById } from '../../data/brainwaveBands';
import type { AIFeedback } from '../../types/audio';

export const AdaptiveAIPanel = () => {
  const {
    adaptiveAI,
    setAdaptiveAI,
    addAIFeedback,
    setModulationDepth,
    setBeatFrequency,
    setBand,
    currentBand,
    modulationDepth,
    beatFrequency
  } = useAudioStore();

  const aiTherapyRef = useRef<AdaptiveAITherapy | null>(null);

  useEffect(() => {
    if (adaptiveAI.enabled && !aiTherapyRef.current) {
      aiTherapyRef.current = new AdaptiveAITherapy(
        adaptiveAI,
        () => useAudioStore.getState(),
        (param, oldValue, newValue, reason) => {
          console.log(`AI自适应: ${param} ${oldValue} → ${newValue} - ${reason}`);

          if (param === 'modulationDepth') {
            setModulationDepth(newValue);
          } else if (param === 'beatFrequency') {
            setBeatFrequency(newValue);
          } else if (param === 'band') {
            const bands = ['delta', 'theta', 'alpha', 'beta', 'gamma'];
            const targetBand = getBandById(bands[Math.round(newValue)]);
            if (targetBand) {
              setBand(targetBand);
            }
          } else if (param === 'phase') {
            const phases = ['warmup', 'active', 'cooldown', 'complete'] as const;
            setAdaptiveAI({ currentPhase: phases[Math.round(newValue)] });
          }

          setAdaptiveAI({
            adaptationLog: [
              ...adaptiveAI.adaptationLog,
              { time: Date.now(), param, oldValue, newValue, reason }
            ]
          });
        },
        (band, frequency) => {
          setAdaptiveAI({
            recommendedBand: band,
            recommendedFrequency: frequency
          });
        }
      );

      aiTherapyRef.current.start();
    } else if (!adaptiveAI.enabled && aiTherapyRef.current) {
      aiTherapyRef.current.destroy();
      aiTherapyRef.current = null;
    }

    return () => {
      if (aiTherapyRef.current) {
        aiTherapyRef.current.destroy();
        aiTherapyRef.current = null;
      }
    };
  }, [adaptiveAI.enabled]);

  const handleFeedback = (feedback: AIFeedback) => {
    addAIFeedback(feedback);
    if (aiTherapyRef.current) {
      aiTherapyRef.current.addFeedback(feedback);
    }
  };

  const handleAcceptRecommendation = () => {
    if (adaptiveAI.recommendedBand) {
      const band = getBandById(adaptiveAI.recommendedBand);
      if (band) {
        setBand(band);
      }
    }
    if (adaptiveAI.recommendedFrequency) {
      setBeatFrequency(adaptiveAI.recommendedFrequency);
    }
    setAdaptiveAI({
      recommendedBand: null,
      recommendedFrequency: null
    });
  };

  const getMoodEmoji = () => {
    if (adaptiveAI.userMood > 0.8) return '😊';
    if (adaptiveAI.userMood > 0.6) return '🙂';
    if (adaptiveAI.userMood > 0.4) return '😐';
    if (adaptiveAI.userMood > 0.2) return '😕';
    return '😟';
  };

  const getPhaseColor = () => {
    switch (adaptiveAI.currentPhase) {
      case 'warmup': return '#3b82f6';
      case 'active': return '#10b981';
      case 'cooldown': return '#8b5cf6';
      case 'complete': return '#f59e0b';
    }
  };

  const getPhaseName = () => {
    switch (adaptiveAI.currentPhase) {
      case 'warmup': return '暖身阶段';
      case 'active': return '主动治疗';
      case 'cooldown': return '放松收尾';
      case 'complete': return '已完成';
    }
  };

  const feedbackButtons: { feedback: AIFeedback; icon: typeof ThumbsUp; label: string; color: string }[] = [
    { feedback: 'much_better', icon: ThumbsUp, label: '好很多', color: '#10b981' },
    { feedback: 'better', icon: ThumbsUp, label: '好一点', color: '#6ee7b7' },
    { feedback: 'same', icon: Minus, label: '没变化', color: '#f59e0b' },
    { feedback: 'worse', icon: ThumbsDown, label: '差一点', color: '#fca5a5' },
    { feedback: 'much_worse', icon: ThumbsDown, label: '差很多', color: '#ef4444' }
  ];

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-white/80 tracking-wider flex items-center gap-2">
        <Brain size={14} />
        AI 自适应疗程
      </h3>
      <div className="p-4 bg-white/5 rounded-2xl backdrop-blur-sm space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div
              className={`
                w-12 h-12 rounded-xl flex items-center justify-center
                transition-all duration-300
                ${adaptiveAI.enabled ? 'animate-pulse' : ''}
              `}
              style={{
                background: adaptiveAI.enabled
                  ? 'linear-gradient(135deg, rgba(139, 92, 246, 0.3), rgba(59, 130, 246, 0.3))'
                  : 'rgba(255, 255, 255, 0.05)',
                boxShadow: adaptiveAI.enabled
                  ? '0 0 20px rgba(139, 92, 246, 0.4)'
                  : 'none'
              }}
            >
              <Sparkles
                size={24}
                style={{
                  color: adaptiveAI.enabled ? '#8b5cf6' : 'rgba(255, 255, 255, 0.5)'
                }}
              />
            </div>
            <div>
              <div className="text-sm font-medium text-white flex items-center gap-2">
                智能自适应
                {adaptiveAI.enabled && (
                  <span className="text-lg">{getMoodEmoji()}</span>
                )}
              </div>
              <div className="text-xs text-white/50">
                根据您的反馈实时调整参数
              </div>
            </div>
          </div>
          <div
            className={`
              w-12 h-6 rounded-full relative transition-all duration-300 cursor-pointer
            `}
            style={{
              backgroundColor: adaptiveAI.enabled ? '#8b5cf6' : 'rgba(255, 255, 255, 0.1)'
            }}
            onClick={() => setAdaptiveAI({ enabled: !adaptiveAI.enabled })}
          >
            <div
              className={`
                absolute top-0.5 w-5 h-5 rounded-full bg-white
                transition-all duration-300 shadow-md
              `}
              style={{
                left: adaptiveAI.enabled ? '26px' : '2px'
              }}
            />
          </div>
        </div>

        {adaptiveAI.enabled && (
          <>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-white/60">当前阶段</span>
                <span
                  className="text-xs font-medium px-2 py-0.5 rounded-full"
                  style={{
                    backgroundColor: getPhaseColor() + '30',
                    color: getPhaseColor()
                  }}
                >
                  {getPhaseName()}
                </span>
              </div>
              <div className="w-full h-2 bg-white/10 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${adaptiveAI.sessionProgress * 100}%`,
                    background: `linear-gradient(90deg, ${getPhaseColor()}80, ${getPhaseColor()})`
                  }}
                />
              </div>
              <div className="flex justify-between text-[10px] text-white/40">
                <span>0%</span>
                <span>{Math.round(adaptiveAI.sessionProgress * 100)}% 完成</span>
                <span>100%</span>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="bg-white/5 rounded-lg p-2">
                <div className="text-[10px] text-white/40 mb-1">频段</div>
                <div className="text-sm font-bold" style={{ color: currentBand.color }}>
                  {currentBand.name}
                </div>
              </div>
              <div className="bg-white/5 rounded-lg p-2">
                <div className="text-[10px] text-white/40 mb-1">频率</div>
                <div className="text-sm font-bold text-white font-mono">
                  {beatFrequency.toFixed(1)}
                </div>
              </div>
              <div className="bg-white/5 rounded-lg p-2">
                <div className="text-[10px] text-white/40 mb-1">深度</div>
                <div className="text-sm font-bold text-white font-mono">
                  {modulationDepth.toFixed(2)}
                </div>
              </div>
            </div>

            {adaptiveAI.recommendedBand && (
              <div className="bg-gradient-to-r from-purple-500/20 to-blue-500/20 rounded-xl p-3 border border-purple-500/30">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <div className="text-xs text-purple-300 font-medium mb-1 flex items-center gap-1">
                      <Sparkles size={12} />
                      AI 推荐调整
                    </div>
                    <div className="text-sm text-white">
                      建议切换到{' '}
                      <span className="font-bold text-purple-300">
                        {getBandById(adaptiveAI.recommendedBand)?.name}
                      </span>
                      {adaptiveAI.recommendedFrequency && (
                        <>
                          {' @ '}
                          <span className="font-mono font-bold text-purple-300">
                            {adaptiveAI.recommendedFrequency.toFixed(1)}Hz
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={handleAcceptRecommendation}
                    className="px-3 py-1.5 rounded-lg bg-purple-500 text-white text-xs font-medium
                               hover:bg-purple-400 transition-colors flex-shrink-0"
                  >
                    应用
                  </button>
                </div>
              </div>
            )}

            <div className="space-y-2">
              <div className="text-xs text-white/60">您现在感觉如何？</div>
              <div className="flex gap-1">
                {feedbackButtons.map(({ feedback, icon: Icon, label, color }) => (
                  <button
                    key={feedback}
                    onClick={() => handleFeedback(feedback)}
                    className={`
                      flex-1 flex flex-col items-center gap-1 py-2 rounded-lg
                      transition-all duration-200 hover:scale-105 active:scale-95
                      bg-white/5 hover:bg-white/10
                    `}
                    title={label}
                  >
                    <Icon size={16} style={{ color }} />
                    <span className="text-[9px] text-white/60">{label}</span>
                  </button>
                ))}
              </div>
            </div>

            {adaptiveAI.adaptationLog.length > 0 && (
              <div className="space-y-2 pt-3 border-t border-white/10">
                <div className="flex items-center gap-1 text-xs text-white/60">
                  <History size={12} />
                  调整历史
                </div>
                <div className="space-y-1 max-h-24 overflow-y-auto">
                  {adaptiveAI.adaptationLog.slice(-5).reverse().map((log, idx) => (
                    <div
                      key={idx}
                      className="text-[10px] text-white/40 flex items-start gap-2"
                    >
                      <TrendingUp size={10} className="flex-shrink-0 mt-0.5 text-emerald-400" />
                      <span>{log.reason}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {!adaptiveAI.enabled && (
          <div className="text-[11px] text-white/40 text-center py-2">
            开启后，AI 将根据您的反馈和生理数据自动优化治疗参数
          </div>
        )}
      </div>
    </div>
  );
};
