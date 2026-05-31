import { Play, Pause, Clock } from 'lucide-react';
import { useAudioStore } from '../../store/useAudioStore';
import { useAudioEngine } from '../../hooks/useAudioEngine';
import { useEffect, useState } from 'react';

export const PlayControls = () => {
  const { isPlaying, currentBand, beatFrequency, audioMode, togglePlay } = useAudioStore();
  const { initAudioContext } = useAudioEngine();
  const [elapsedTime, setElapsedTime] = useState(0);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;
    if (isPlaying) {
      interval = setInterval(() => {
        setElapsedTime((prev) => prev + 1);
      }, 1000);
    } else {
      setElapsedTime(0);
    }
    return () => clearInterval(interval);
  }, [isPlaying]);

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const handlePlayClick = () => {
    initAudioContext();
    togglePlay();
  };

  return (
    <div className="bg-white/5 backdrop-blur-xl rounded-2xl p-4 border border-white/10">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div
            className={`w-3 h-3 rounded-full transition-all duration-300 ${isPlaying ? 'animate-pulse' : ''}`}
            style={{
              backgroundColor: isPlaying ? '#10b981' : '#6b7280',
              boxShadow: isPlaying ? '0 0 10px #10b981' : 'none'
            }}
          />
          <div>
            <div className="text-xs text-white/50">当前状态</div>
            <div className="text-sm font-medium text-white">
              {isPlaying ? '播放中' : '已暂停'}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 text-white/60">
          <Clock size={14} />
          <span className="text-sm font-mono">{formatTime(elapsedTime)}</span>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 mb-4 text-center">
        <div className="bg-white/5 rounded-lg py-2">
          <div className="text-[10px] text-white/40 mb-0.5">频段</div>
          <div className="text-sm font-bold" style={{ color: currentBand.color }}>
            {currentBand.name}
          </div>
        </div>
        <div className="bg-white/5 rounded-lg py-2">
          <div className="text-[10px] text-white/40 mb-0.5">差频</div>
          <div className="text-sm font-bold text-white font-mono">
            {beatFrequency.toFixed(1)}Hz
          </div>
        </div>
        <div className="bg-white/5 rounded-lg py-2">
          <div className="text-[10px] text-white/40 mb-0.5">模式</div>
          <div className="text-sm font-bold text-white">
            {audioMode === 'binaural' ? '双耳' : '等时'}
          </div>
        </div>
      </div>

      <button
        onClick={handlePlayClick}
        className={`
          w-full py-4 rounded-xl font-semibold text-white
          flex items-center justify-center gap-3
          transition-all duration-300 transform hover:scale-[1.02] active:scale-[0.98]
        `}
        style={{
          background: isPlaying
            ? 'linear-gradient(135deg, #ef4444, #dc2626)'
            : `linear-gradient(135deg, ${currentBand.color}, ${currentBand.color}dd)`,
          boxShadow: isPlaying
            ? '0 4px 20px rgba(239, 68, 68, 0.4)'
            : `0 4px 20px ${currentBand.glowColor}`
        }}
      >
        {isPlaying ? (
          <>
            <Pause size={20} />
            暂停播放
          </>
        ) : (
          <>
            <Play size={20} />
            开始播放
          </>
        )}
      </button>
    </div>
  );
};
