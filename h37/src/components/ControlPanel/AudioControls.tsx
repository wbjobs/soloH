import { Headphones, Volume2, Radio, Waves } from 'lucide-react';
import { useAudioStore } from '../../store/useAudioStore';
import type { AudioMode } from '../../types/audio';

interface SliderProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  unit?: string;
  onChange: (value: number) => void;
  color?: string;
}

const Slider = ({ label, value, min, max, step, unit = '', onChange, color = '#3b82f6' }: SliderProps) => {
  const percentage = ((value - min) / (max - min)) * 100;

  return (
    <div className="space-y-1.5">
      <div className="flex justify-between items-center">
        <span className="text-xs text-white/70">{label}</span>
        <span className="text-xs font-mono text-white/90" style={{ color }}>
          {value.toFixed(step < 1 ? 1 : 0)}{unit}
        </span>
      </div>
      <div className="relative h-2 bg-white/10 rounded-full overflow-hidden">
        <div
          className="absolute left-0 top-0 h-full rounded-full transition-all duration-150"
          style={{
            width: `${percentage}%`,
            background: `linear-gradient(90deg, ${color}80, ${color})`
          }}
        />
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
        />
      </div>
    </div>
  );
};

export const AudioControls = () => {
  const {
    beatFrequency,
    carrierFrequency,
    modulationDepth,
    masterVolume,
    channelBalance,
    audioMode,
    currentBand,
    setBeatFrequency,
    setCarrierFrequency,
    setModulationDepth,
    setMasterVolume,
    setChannelBalance,
    setAudioMode
  } = useAudioStore();

  const modes: { id: AudioMode; label: string; icon: typeof Headphones }[] = [
    { id: 'binaural', label: '双耳节拍', icon: Headphones },
    { id: 'isochronic', label: '等时音', icon: Radio }
  ];

  return (
    <div className="space-y-5">
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-white/80 tracking-wider flex items-center gap-2">
          <Waves size={14} />
          音频模式
        </h3>
        <div className="grid grid-cols-2 gap-2">
          {modes.map(({ id, label, icon: Icon }) => {
            const isActive = audioMode === id;
            return (
              <button
                key={id}
                onClick={() => setAudioMode(id)}
                className={`
                  flex items-center justify-center gap-2 py-2.5 px-3 rounded-xl
                  transition-all duration-300 text-sm font-medium
                  ${isActive
                    ? 'bg-white/15 text-white shadow-lg'
                    : 'bg-white/5 text-white/60 hover:bg-white/10 hover:text-white/80'
                  }
                `}
                style={{
                  boxShadow: isActive ? `0 0 20px ${currentBand.glowColor}` : 'none',
                  border: `1px solid ${isActive ? currentBand.color : 'rgba(255,255,255,0.1)'}`
                }}
              >
                <Icon size={16} />
                {label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-white/80 tracking-wider">频率参数</h3>
        <div className="space-y-4 p-4 bg-white/5 rounded-2xl backdrop-blur-sm">
          <Slider
            label="差频 (脑波频率)"
            value={beatFrequency}
            min={currentBand.frequencyRange[0]}
            max={currentBand.frequencyRange[1]}
            step={0.1}
            unit="Hz"
            onChange={setBeatFrequency}
            color={currentBand.color}
          />
          <Slider
            label="载波频率"
            value={carrierFrequency}
            min={100}
            max={800}
            step={10}
            unit="Hz"
            onChange={setCarrierFrequency}
            color={currentBand.color}
          />
          {audioMode === 'isochronic' && (
            <Slider
              label="调制深度"
              value={modulationDepth}
              min={0}
              max={1}
              step={0.05}
              onChange={setModulationDepth}
              color={currentBand.color}
            />
          )}
        </div>
      </div>

      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-white/80 tracking-wider flex items-center gap-2">
          <Volume2 size={14} />
          音量控制
        </h3>
        <div className="space-y-4 p-4 bg-white/5 rounded-2xl backdrop-blur-sm">
          <Slider
            label="主音量"
            value={masterVolume}
            min={0}
            max={1}
            step={0.01}
            onChange={setMasterVolume}
            color={currentBand.color}
          />
          <Slider
            label="声道平衡"
            value={channelBalance}
            min={-1}
            max={1}
            step={0.01}
            onChange={setChannelBalance}
            color={currentBand.color}
          />
        </div>
      </div>
    </div>
  );
};
