import { useMemo } from 'react';
import type { ModalityResult, Modality } from '@/types';
import { MODALITY_LABELS, MODALITY_COLORS, EMOTION_LABELS } from '@/types';
import { formatPercent, getDominantEmotion } from '@/utils';

interface ModalityContributionProps {
  modalities: {
    audio: ModalityResult;
    video: ModalityResult;
    text: ModalityResult;
  };
}

export function ModalityContribution({ modalities }: ModalityContributionProps) {
  const modalityList = useMemo(() => {
    return (Object.entries(modalities) as [Modality, ModalityResult][])
      .map(([key, value]) => ({
        key,
        ...value,
        label: MODALITY_LABELS[key],
        color: MODALITY_COLORS[key],
        dominantEmotion: getDominantEmotion(value.emotionProbabilities),
      }))
      .sort((a, b) => b.contribution - a.contribution);
  }, [modalities]);

  const totalContribution = useMemo(() => {
    return modalityList.reduce((sum, m) => sum + m.contribution, 0);
  }, [modalityList]);

  const maxContribution = Math.max(...modalityList.map(m => m.contribution), 0.01);

  return (
    <div className="w-full space-y-6">
      <div className="space-y-4">
        {modalityList.map((modality, index) => (
          <div
            key={modality.key}
            className="p-4 rounded-xl bg-white/5 border border-white/10 hover:border-white/20 transition-all animate-slide-up"
            style={{ animationDelay: `${index * 100}ms` }}
          >
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-3">
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center"
                  style={{ backgroundColor: modality.color + '30' }}
                >
                  {modality.key === 'audio' && (
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24" style={{ color: modality.color }}>
                      <path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z" />
                    </svg>
                  )}
                  {modality.key === 'video' && (
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24" style={{ color: modality.color }}>
                      <path d="M18 10.48V6c0-1.1-.9-2-2-2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2v-4.48l4 3.98v-11l-4 3.98z" />
                    </svg>
                  )}
                  {modality.key === 'text' && (
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24" style={{ color: modality.color }}>
                      <path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z" />
                    </svg>
                  )}
                </div>
                <div>
                  <h4 className="font-medium" style={{ color: modality.color }}>
                    {modality.label}
                  </h4>
                  <p className="text-xs text-muted-foreground">
                    主导情感: {EMOTION_LABELS[modality.dominantEmotion.category]}
                  </p>
                </div>
              </div>

              <div className="text-right">
                <p className="text-2xl font-bold font-mono" style={{ color: modality.color }}>
                  {formatPercent(modality.contribution / Math.max(totalContribution, 0.01), 0)}
                </p>
                <p className="text-xs text-muted-foreground">贡献度</p>
              </div>
            </div>

            <div className="relative h-3 bg-white/10 rounded-full overflow-hidden">
              <div
                className="absolute inset-y-0 left-0 rounded-full transition-all duration-1000 ease-out"
                style={{
                  width: `${(modality.contribution / maxContribution) * 100}%`,
                  backgroundColor: modality.color,
                  boxShadow: `0 0 20px ${modality.color}40`,
                }}
              />
            </div>

            <div className="mt-4 grid grid-cols-7 gap-1">
              {(Object.entries(modality.emotionProbabilities) as [string, number][]).map(([emotion, prob]) => (
                <div key={emotion} className="text-center">
                  <div
                    className="h-16 rounded-lg mb-1 flex items-end justify-center p-1"
                    style={{
                      backgroundColor: `var(--emotion-${emotion})20`,
                      border: `1px solid var(--emotion-${emotion})30`,
                    }}
                  >
                    <div
                      className="w-full rounded transition-all duration-500"
                      style={{
                        height: `${prob * 100}%`,
                        backgroundColor: `var(--emotion-${emotion})`,
                      }}
                    />
                  </div>
                  <p className="text-[10px] text-muted-foreground truncate">
                    {EMOTION_LABELS[emotion as keyof typeof EMOTION_LABELS]}
                  </p>
                  <p className="text-[10px] font-mono" style={{ color: `var(--emotion-${emotion})` }}>
                    {formatPercent(prob, 0)}
                  </p>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="p-4 rounded-xl bg-gradient-to-br from-primary/20 to-secondary/20 border border-primary/30">
        <h4 className="text-sm font-medium mb-3">模态融合决策</h4>
        <div className="flex items-center justify-around">
          {modalityList.map((modality, index) => (
            <div key={modality.key} className="flex flex-col items-center">
              <div
                className="w-16 h-16 rounded-full flex items-center justify-center text-2xl font-bold mb-2"
                style={{
                  backgroundColor: modality.color + '30',
                  border: `3px solid ${modality.color}`,
                  transform: `scale(${0.8 + (modality.contribution / maxContribution) * 0.4})`,
                }}
              >
                {index + 1}
              </div>
              <span className="text-xs text-muted-foreground">{modality.label}</span>
            </div>
          ))}
          <div className="text-3xl text-muted-foreground">→</div>
          <div className="flex flex-col items-center">
            <div className="w-16 h-16 rounded-full bg-gradient-primary flex items-center justify-center text-2xl font-bold mb-2 animate-glow">
              {modalityList.length > 0 ? '✓' : '?'}
            </div>
            <span className="text-xs text-muted-foreground">融合结果</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ModalityContribution;
