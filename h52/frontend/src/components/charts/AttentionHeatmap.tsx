import { useMemo, useState } from 'react';
import type { AttentionMatrix, Modality } from '@/types';
import { MODALITY_LABELS, MODALITY_COLORS } from '@/types';
import { getHeatmapColor, formatNumber } from '@/utils';

interface AttentionHeatmapProps {
  data: AttentionMatrix;
  height?: number;
  showLegend?: boolean;
}

export function AttentionHeatmap({
  data,
  height = 200,
  showLegend = true,
}: AttentionHeatmapProps) {
  const [hoveredCell, setHoveredCell] = useState<{ timeStep: number; modality: number } | null>(null);
  const [selectedTimeStep, setSelectedTimeStep] = useState<number | null>(null);

  const { weights, modalities, timeSteps } = data;

  const flattenedWeights = useMemo(() => {
    return weights.flat();
  }, [weights]);

  const minWeight = useMemo(() => Math.min(...flattenedWeights, 0), [flattenedWeights]);
  const maxWeight = useMemo(() => Math.max(...flattenedWeights, 1), [flattenedWeights]);

  const modalityContributions = useMemo(() => {
    return modalities.map((modality, modIndex) => {
      const total = weights.reduce((sum, timeStep) => sum + timeStep[modIndex], 0);
      const avg = total / timeSteps;
      return { modality, contribution: avg };
    });
  }, [weights, modalities, timeSteps]);

  const timeStepLabels = useMemo(() => {
    if (timeSteps <= 10) {
      return Array.from({ length: timeSteps }, (_, i) => i);
    }
    const step = Math.ceil(timeSteps / 10);
    return Array.from({ length: timeSteps }, (_, i) => (i % step === 0 ? i : -1)).filter((i) => i >= 0);
  }, [timeSteps]);

  const cellWidth = 100 / Math.max(timeSteps, 1);
  const cellHeight = 100 / modalities.length;

  const handleCellClick = (timeStep: number) => {
    setSelectedTimeStep(selectedTimeStep === timeStep ? null : timeStep);
  };

  return (
    <div className="w-full">
      {showLegend && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            {modalityContributions.map(({ modality, contribution }) => (
              <div key={modality} className="flex items-center gap-2">
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: MODALITY_COLORS[modality] }}
                />
                <span className="text-sm text-muted-foreground">
                  {MODALITY_LABELS[modality]}:
                </span>
                <span className="text-sm font-mono font-medium" style={{ color: MODALITY_COLORS[modality] }}>
                  {formatNumber(contribution, 3)}
                </span>
              </div>
            ))}
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">低</span>
            <div className="h-3 w-32 rounded-full" style={{
              background: 'linear-gradient(90deg, #440154, #482878, #3e4989, #31688e, #21918c, #35b779, #fde725)'
            }} />
            <span className="text-xs text-muted-foreground">高</span>
          </div>
        </div>
      )}

      <div className="relative" style={{ height }}>
        <div className="absolute left-0 top-0 h-full flex flex-col justify-around" style={{ width: '80px' }}>
          {modalities.map((modality) => (
            <div
              key={modality}
              className="text-xs text-right pr-2 font-medium"
              style={{ color: MODALITY_COLORS[modality] }}
            >
              {MODALITY_LABELS[modality]}
            </div>
          ))}
        </div>

        <div
          className="absolute right-0 top-0 h-full rounded-xl overflow-hidden border border-white/10"
          style={{ width: 'calc(100% - 90px)' }}
        >
          <div className="relative w-full h-full">
            {weights.map((timeStepWeights, timeIndex) => (
              timeStepWeights.map((weight, modIndex) => {
                const isHovered = hoveredCell?.timeStep === timeIndex && hoveredCell?.modality === modIndex;
                const isSelected = selectedTimeStep === timeIndex;

                return (
                  <div
                    key={`${timeIndex}-${modIndex}`}
                    className="absolute cursor-pointer transition-all duration-200 group"
                    style={{
                      left: `${timeIndex * cellWidth}%`,
                      top: `${modIndex * cellHeight}%`,
                      width: `${cellWidth}%`,
                      height: `${cellHeight}%`,
                      backgroundColor: getHeatmapColor(weight, minWeight, maxWeight),
                      opacity: isSelected || selectedTimeStep === null ? 1 : 0.3,
                      boxShadow: isHovered ? 'inset 0 0 0 2px rgba(255,255,255,0.8)' : 'inset 0 0 0 1px rgba(255,255,255,0.1)',
                      zIndex: isHovered ? 10 : 1,
                    }}
                    onMouseEnter={() => setHoveredCell({ timeStep: timeIndex, modality: modIndex })}
                    onMouseLeave={() => setHoveredCell(null)}
                    onClick={() => handleCellClick(timeIndex)}
                  >
                    {isHovered && (
                      <div className="absolute z-20 bg-card border border-white/20 rounded-lg px-3 py-2 text-xs whitespace-nowrap animate-fade-in"
                        style={{
                          bottom: '100%',
                          left: '50%',
                          transform: 'translateX(-50%)',
                          marginBottom: '8px',
                        }}
                      >
                        <p className="text-muted-foreground">时间: {timeIndex}s</p>
                        <p className="text-muted-foreground">模态: {MODALITY_LABELS[modalities[modIndex]]}</p>
                        <p className="font-mono font-medium" style={{ color: getHeatmapColor(weight, minWeight, maxWeight) }}>
                          权重: {formatNumber(weight, 4)}
                        </p>
                      </div>
                    )}

                    {timeStepWeights.length > 1 && weight > (maxWeight - minWeight) * 0.7 + minWeight && (
                      <span className="absolute inset-0 flex items-center justify-center text-[10px] font-mono text-white/80">
                        {formatNumber(weight, 2)}
                      </span>
                    )}
                  </div>
                );
              })
            ))}
          </div>
        </div>
      </div>

      {timeSteps > 1 && (
        <div className="mt-2 ml-[90px]">
          <div className="relative h-6">
            {timeStepLabels.map((label) => (
              <div
                key={label}
                className="absolute text-[10px] text-muted-foreground transform -translate-x-1/2"
                style={{ left: `${(label / (timeSteps - 1)) * 100}%` }}
              >
                {label}s
              </div>
            ))}
          </div>
          <p className="text-xs text-muted-foreground text-center mt-1">时间步</p>
        </div>
      )}

      {selectedTimeStep !== null && (
        <div className="mt-4 p-4 rounded-xl bg-white/5 animate-slide-up">
          <h4 className="text-sm font-medium mb-2">第 {selectedTimeStep} 秒注意力权重</h4>
          <div className="grid grid-cols-3 gap-4">
            {modalities.map((modality, modIndex) => (
              <div key={modality} className="text-center">
                <p className="text-xs text-muted-foreground mb-1">{MODALITY_LABELS[modality]}</p>
                <p className="text-lg font-mono font-bold" style={{ color: MODALITY_COLORS[modality] }}>
                  {formatNumber(weights[selectedTimeStep]?.[modIndex] || 0, 4)}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default AttentionHeatmap;
