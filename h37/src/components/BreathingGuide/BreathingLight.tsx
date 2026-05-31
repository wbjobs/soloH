import { useBreathing } from '../../hooks/useBreathing';
import { useAudioStore } from '../../store/useAudioStore';
import { Wind } from 'lucide-react';

export const BreathingLight = () => {
  const { phase, progress, getPhaseText, isEnabled } = useBreathing();
  const { currentBand, breathing, setBreathing } = useAudioStore();

  if (!isEnabled) {
    return (
      <button
        onClick={() => setBreathing({ enabled: true })}
        className="absolute top-4 right-4 flex items-center gap-2 px-4 py-2 rounded-full
                   bg-white/10 hover:bg-white/20 backdrop-blur-sm
                   text-white/70 hover:text-white text-sm
                   transition-all duration-300 border border-white/10"
      >
        <Wind size={16} />
        开启呼吸引导
      </button>
    );
  }

  const getScale = (): number => {
    switch (phase) {
      case 'inhale':
        return 0.6 + progress * 0.4;
      case 'hold':
        return 1;
      case 'exhale':
        return 1 - progress * 0.4;
      case 'rest':
        return 0.6;
    }
  };

  const scale = getScale();
  const opacity = 0.3 + progress * 0.4;

  return (
    <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
      <button
        onClick={() => setBreathing({ enabled: false })}
        className="absolute top-4 right-4 flex items-center gap-2 px-4 py-2 rounded-full
                   bg-white/10 hover:bg-white/20 backdrop-blur-sm
                   text-white/70 hover:text-white text-sm
                   transition-all duration-300 border border-white/10
                   pointer-events-auto z-10"
      >
        <Wind size={16} />
        关闭呼吸引导
      </button>

      <div
        className="relative flex items-center justify-center"
        style={{ width: '300px', height: '300px' }}
      >
        <div
          className="absolute inset-0 rounded-full transition-all duration-300"
          style={{
            background: `radial-gradient(circle, ${currentBand.color}40 0%, transparent 70%)`,
            transform: `scale(${scale + 0.3})`,
            opacity: opacity * 0.5
          }}
        />

        <div
          className="absolute rounded-full transition-all duration-300"
          style={{
            width: '200px',
            height: '200px',
            background: `radial-gradient(circle, ${currentBand.color}80 0%, ${currentBand.color}20 60%, transparent 100%)`,
            transform: `scale(${scale + 0.1})`,
            opacity: opacity * 0.7,
            boxShadow: `0 0 60px ${currentBand.glowColor}`
          }}
        />

        <div
          className="absolute rounded-full transition-all duration-300"
          style={{
            width: '120px',
            height: '120px',
            background: `radial-gradient(circle, ${currentBand.color} 0%, ${currentBand.color}aa 50%, transparent 100%)`,
            transform: `scale(${scale})`,
            opacity: opacity,
            boxShadow: `0 0 80px ${currentBand.color}, inset 0 0 30px ${currentBand.color}aa`
          }}
        />

        <div className="relative z-10 text-center">
          <div
            className="text-3xl font-bold mb-1 transition-all duration-300"
            style={{
              color: currentBand.color,
              textShadow: `0 0 20px ${currentBand.glowColor}`
            }}
          >
            {getPhaseText()}
          </div>
          <div className="text-xs text-white/50 font-mono">
            {Math.round(progress * 100)}%
          </div>
        </div>

        <div className="absolute -bottom-16 flex gap-3 text-[10px] text-white/40">
          <div className={`transition-all duration-300 ${phase === 'inhale' ? 'text-white scale-110' : ''}`}>
            吸气 {breathing.inhaleTime}s
          </div>
          <div className={`transition-all duration-300 ${phase === 'hold' ? 'text-white scale-110' : ''}`}>
            屏息 {breathing.holdTime}s
          </div>
          <div className={`transition-all duration-300 ${phase === 'exhale' ? 'text-white scale-110' : ''}`}>
            呼气 {breathing.exhaleTime}s
          </div>
          <div className={`transition-all duration-300 ${phase === 'rest' ? 'text-white scale-110' : ''}`}>
            停顿 {breathing.restTime}s
          </div>
        </div>
      </div>
    </div>
  );
};
