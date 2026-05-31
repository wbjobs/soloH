import { CloudRain, Wind, Waves, Mountain } from 'lucide-react';
import { useAudioStore } from '../../store/useAudioStore';
import type { BackgroundSoundId } from '../../types/audio';

const SOUND_CONFIGS: { id: BackgroundSoundId; label: string; icon: typeof CloudRain }[] = [
  { id: 'rain', label: '雨声', icon: CloudRain },
  { id: 'whiteNoise', label: '白噪音', icon: Wind },
  { id: 'pinkNoise', label: '粉红噪音', icon: Waves },
  { id: 'brownNoise', label: '棕噪音', icon: Mountain }
];

export const BackgroundSounds = () => {
  const { backgroundSounds, currentBand, toggleBackgroundSound, setBackgroundVolume } = useAudioStore();

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-white/80 tracking-wider">背景声音</h3>
      <div className="space-y-2">
        {SOUND_CONFIGS.map(({ id, label, icon: Icon }) => {
          const sound = backgroundSounds[id];
          const isActive = sound.enabled;

          return (
            <div
              key={id}
              className={`
                p-3 rounded-xl transition-all duration-300
                ${isActive ? 'bg-white/10' : 'bg-white/5'}
              `}
              style={{
                border: `1px solid ${isActive ? currentBand.color + '60' : 'rgba(255,255,255,0.1)'}`
              }}
            >
              <div className="flex items-center justify-between mb-2">
                <button
                  onClick={() => toggleBackgroundSound(id)}
                  className={`
                    flex items-center gap-2 transition-all duration-300
                    ${isActive ? 'text-white' : 'text-white/60 hover:text-white/80'}
                  `}
                >
                  <div
                    className={`
                      w-8 h-8 rounded-lg flex items-center justify-center
                      transition-all duration-300
                      ${isActive ? 'scale-105' : ''}
                    `}
                    style={{
                      backgroundColor: isActive ? currentBand.color + '30' : 'rgba(255,255,255,0.05)',
                      boxShadow: isActive ? `0 0 15px ${currentBand.glowColor}` : 'none'
                    }}
                  >
                    <Icon size={16} style={{ color: isActive ? currentBand.color : 'inherit' }} />
                  </div>
                  <span className="text-sm font-medium">{label}</span>
                </button>
                <div
                  className={`
                    w-10 h-6 rounded-full relative transition-all duration-300
                    ${isActive ? '' : 'bg-white/10'}
                  `}
                  style={{
                    backgroundColor: isActive ? currentBand.color : undefined
                  }}
                >
                  <div
                    className={`
                      absolute top-0.5 w-5 h-5 rounded-full bg-white
                      transition-all duration-300 shadow-md
                    `}
                    style={{
                      left: isActive ? '18px' : '2px'
                    }}
                  />
                </div>
              </div>
              {isActive && (
                <div className="px-2">
                  <div className="relative h-1.5 bg-white/10 rounded-full overflow-hidden">
                    <div
                      className="absolute left-0 top-0 h-full rounded-full transition-all duration-150"
                      style={{
                        width: `${sound.volume * 100}%`,
                        backgroundColor: currentBand.color
                      }}
                    />
                    <input
                      type="range"
                      min={0}
                      max={1}
                      step={0.01}
                      value={sound.volume}
                      onChange={(e) => setBackgroundVolume(id, parseFloat(e.target.value))}
                      className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                    />
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
