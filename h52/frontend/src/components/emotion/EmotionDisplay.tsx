import { useMemo } from 'react';
import type { EmotionCategory, EmotionProbabilities } from '@/types';
import { EMOTION_LABELS, EMOTION_COLORS } from '@/types';
import { formatPercent, getDominantEmotion } from '@/utils';
import { cn } from '@/utils';

interface EmotionDisplayProps {
  probabilities: EmotionProbabilities;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  showConfidence?: boolean;
  className?: string;
}

export function EmotionDisplay({
  probabilities,
  size = 'md',
  showLabel = true,
  showConfidence = true,
  className,
}: EmotionDisplayProps) {
  const dominant = useMemo(() => getDominantEmotion(probabilities), [probabilities]);

  const sizeClasses = {
    sm: 'text-3xl w-20 h-20',
    md: 'text-5xl w-32 h-32',
    lg: 'text-7xl w-48 h-48',
  };

  const emotionEmojis: Record<EmotionCategory, string> = {
    anger: '😠',
    joy: '😊',
    sadness: '😢',
    surprise: '😮',
    disgust: '🤢',
    fear: '😨',
    neutral: '😐',
  };

  const sortedEmotions = useMemo(() => {
    return (Object.entries(probabilities) as [EmotionCategory, number][])
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3);
  }, [probabilities]);

  return (
    <div className={cn('flex flex-col items-center', className)}>
      <div
        className={cn(
          'relative rounded-full flex items-center justify-center transition-all duration-500',
          sizeClasses[size],
          'animate-breathe'
        )}
        style={{
          background: `radial-gradient(circle, ${EMOTION_COLORS[dominant.category]}40 0%, transparent 70%)`,
          boxShadow: `0 0 60px ${EMOTION_COLORS[dominant.category]}40`,
        }}
      >
        <span className={cn('select-none', size === 'sm' ? 'text-3xl' : size === 'md' ? 'text-5xl' : 'text-7xl')}>
          {emotionEmojis[dominant.category]}
        </span>

        <div
          className="absolute inset-0 rounded-full border-4 animate-spin-slow"
          style={{
            borderColor: `${EMOTION_COLORS[dominant.category]} transparent ${EMOTION_COLORS[dominant.category]} transparent`,
            opacity: 0.5,
          }}
        />
      </div>

      {showLabel && (
        <div className="mt-4 text-center">
          <h3
            className={cn(
              'font-display font-bold transition-all duration-300',
              size === 'sm' ? 'text-lg' : size === 'md' ? 'text-2xl' : 'text-4xl'
            )}
            style={{ color: EMOTION_COLORS[dominant.category] }}
          >
            {EMOTION_LABELS[dominant.category]}
          </h3>

          {showConfidence && (
            <p className="text-muted-foreground mt-1 font-mono">
              置信度: {formatPercent(dominant.confidence)}
            </p>
          )}
        </div>
      )}

      {showLabel && (
        <div className="mt-4 w-full space-y-2">
          {sortedEmotions.map(([emotion, prob], index) => (
            <div key={emotion} className="flex items-center gap-3">
              <span className="text-lg w-8">{emotionEmojis[emotion]}</span>
              <div className="flex-1">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm text-muted-foreground">
                    {EMOTION_LABELS[emotion]}
                  </span>
                  <span
                    className="text-sm font-mono font-medium"
                    style={{ color: EMOTION_COLORS[emotion] }}
                  >
                    {formatPercent(prob, 1)}
                  </span>
                </div>
                <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-1000 ease-out"
                    style={{
                      width: `${prob * 100}%`,
                      backgroundColor: EMOTION_COLORS[emotion],
                      opacity: index === 0 ? 1 : 0.7 - index * 0.2,
                    }}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function EmotionBadge({ emotion, probability }: { emotion: EmotionCategory; probability: number }) {
  const emotionEmojis: Record<EmotionCategory, string> = {
    anger: '😠',
    joy: '😊',
    sadness: '😢',
    surprise: '😮',
    disgust: '🤢',
    fear: '😨',
    neutral: '😐',
  };

  return (
    <span
      className="emotion-badge"
      style={{
        backgroundColor: `${EMOTION_COLORS[emotion]}20`,
        color: EMOTION_COLORS[emotion],
        borderColor: `${EMOTION_COLORS[emotion]}40`,
      }}
    >
      <span className="mr-1">{emotionEmojis[emotion]}</span>
      {EMOTION_LABELS[emotion]}
      <span className="ml-1 font-mono text-xs">
        {formatPercent(probability, 0)}
      </span>
    </span>
  );
}

export default EmotionDisplay;
