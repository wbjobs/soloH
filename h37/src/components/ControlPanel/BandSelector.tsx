import { BRAINWAVE_BANDS } from '../../data/brainwaveBands';
import { useAudioStore } from '../../store/useAudioStore';
import type { BrainwaveBand } from '../../types/audio';

export const BandSelector = () => {
  const { currentBand, setBand } = useAudioStore();

  const handleBandClick = (band: BrainwaveBand) => {
    setBand(band);
  };

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-white/80 tracking-wider">脑波频段</h3>
      <div className="grid grid-cols-5 gap-2">
        {BRAINWAVE_BANDS.map((band) => {
          const isActive = currentBand.id === band.id;
          return (
            <button
              key={band.id}
              onClick={() => handleBandClick(band)}
              className={`
                relative aspect-square rounded-full flex flex-col items-center justify-center
                transition-all duration-300 ease-out
                ${isActive
                  ? 'scale-110 shadow-lg'
                  : 'hover:scale-105 opacity-70 hover:opacity-100'
                }
              `}
              style={{
                background: isActive
                  ? `radial-gradient(circle, ${band.color}40 0%, ${band.color}10 70%, transparent 100%)`
                  : 'rgba(255,255,255,0.05)',
                boxShadow: isActive ? `0 0 30px ${band.glowColor}` : 'none',
                border: `2px solid ${isActive ? band.color : 'rgba(255,255,255,0.2)'}`
              }}
            >
              <span
                className="text-lg font-bold"
                style={{ color: band.color }}
              >
                {band.name}
              </span>
              <span className="text-[10px] text-white/50 mt-0.5">
                {band.frequencyRange[0]}-{band.frequencyRange[1]}Hz
              </span>
              {isActive && (
                <div
                  className="absolute inset-0 rounded-full animate-ping opacity-20"
                  style={{ backgroundColor: band.color }}
                />
              )}
            </button>
          );
        })}
      </div>
      <div className="text-xs text-white/60 text-center py-2 px-3 bg-white/5 rounded-lg">
        {currentBand.description}
      </div>
    </div>
  );
};
