import { Moon, Brain, Flower2 } from 'lucide-react';
import { PRESETS } from '../../data/presets';
import { useAudioStore } from '../../store/useAudioStore';
import { getBandById } from '../../data/brainwaveBands';
import type { Preset } from '../../types/audio';

const ICONS: Record<string, typeof Moon> = {
  moon: Moon,
  brain: Brain,
  'flower-2': Flower2
};

export const Presets = () => {
  const { loadPreset, setBand, currentBand } = useAudioStore();

  const handlePresetClick = (preset: Preset) => {
    loadPreset(preset);
    if (preset.bandProgression && preset.bandProgression.length > 0) {
      const firstBand = getBandById(preset.bandProgression[0].band);
      if (firstBand) {
        setBand(firstBand);
      }
    }
  };

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-white/80 tracking-wider">预置疗程</h3>
      <div className="space-y-2">
        {PRESETS.map((preset) => {
          const Icon = ICONS[preset.icon] || Moon;
          const band = preset.bandProgression?.[0]?.band
            ? getBandById(preset.bandProgression[0].band)
            : currentBand;
          const color = band?.color || currentBand.color;

          return (
            <button
              key={preset.id}
              onClick={() => handlePresetClick(preset)}
              className="w-full text-left p-4 rounded-xl bg-white/5 hover:bg-white/10 
                         transition-all duration-300 group
                         border border-white/10 hover:border-white/20"
              style={{
                boxShadow: '0 4px 30px rgba(0,0,0,0.1)'
              }}
            >
              <div className="flex items-start gap-3">
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0
                             transition-all duration-300 group-hover:scale-110"
                  style={{
                    background: `linear-gradient(135deg, ${color}40, ${color}10)`,
                    boxShadow: `0 0 20px ${color}30`
                  }}
                >
                  <Icon size={20} style={{ color }} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-1">
                    <h4 className="font-semibold text-white group-hover:text-white/90">
                      {preset.name}
                    </h4>
                    <span className="text-xs text-white/50 font-mono">
                      {preset.duration}分钟
                    </span>
                  </div>
                  <p className="text-xs text-white/60 leading-relaxed">
                    {preset.description}
                  </p>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};
