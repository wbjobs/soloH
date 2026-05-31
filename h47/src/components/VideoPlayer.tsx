import { useRef, useState, useEffect } from 'react';
import { FrameData } from '@/types';
import { keypointExtractor } from '@/services/keypointExtractor';
import {
  Play,
  Pause,
  RotateCcw,
  FastForward,
  Gauge,
  Maximize2,
  SkipBack,
  SkipForward
} from 'lucide-react';

interface VideoPlayerProps {
  frames: FrameData[];
  title?: string;
  showOverlay?: boolean;
  onFrameChange?: (frameIndex: number) => void;
}

const SPEED_OPTIONS = [0.25, 0.5, 0.75, 1, 1.5, 2];

const VideoPlayer = ({ frames, title, showOverlay = true, onFrameChange }: VideoPlayerProps) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number>(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentFrameIndex, setCurrentFrameIndex] = useState(0);
  const [speed, setSpeed] = useState(1);
  const lastFrameTime = useRef<number>(0);

  const totalFrames = frames.length;
  const fps = 20;
  const frameInterval = 1000 / (fps * speed);

  useEffect(() => {
    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (frames.length > 0 && currentFrameIndex < frames.length) {
      drawFrame(frames[currentFrameIndex]);
      onFrameChange?.(currentFrameIndex);
    }
  }, [currentFrameIndex, frames]);

  useEffect(() => {
    if (isPlaying && frames.length > 0) {
      const animate = (timestamp: number) => {
        if (timestamp - lastFrameTime.current >= frameInterval) {
          setCurrentFrameIndex(prev => {
            if (prev >= frames.length - 1) {
              setIsPlaying(false);
              return prev;
            }
            return prev + 1;
          });
          lastFrameTime.current = timestamp;
        }
        animationRef.current = requestAnimationFrame(animate);
      };
      animationRef.current = requestAnimationFrame(animate);
    } else {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    }

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [isPlaying, frames, frameInterval]);

  const drawFrame = (frame: FrameData) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    canvas.width = 640;
    canvas.height = 480;

    ctx.fillStyle = '#0f172a';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    if (showOverlay) {
      keypointExtractor.drawOverlay(canvas, frame);
    } else {
      ctx.fillStyle = '#1e293b';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    }
  };

  const handlePlayPause = () => {
    if (currentFrameIndex >= frames.length - 1) {
      setCurrentFrameIndex(0);
    }
    setIsPlaying(!isPlaying);
  };

  const handleReset = () => {
    setIsPlaying(false);
    setCurrentFrameIndex(0);
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseInt(e.target.value);
    setCurrentFrameIndex(value);
    onFrameChange?.(value);
  };

  const handleFrameStep = (direction: 'backward' | 'forward') => {
    setIsPlaying(false);
    setCurrentFrameIndex(prev => {
      if (direction === 'backward') {
        return Math.max(0, prev - 1);
      } else {
        return Math.min(frames.length - 1, prev + 1);
      }
    });
  };

  const handleSpeedChange = (newSpeed: number) => {
    setSpeed(newSpeed);
  };

  const formatTime = (frameIndex: number) => {
    const totalSeconds = frameIndex / fps;
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = Math.floor(totalSeconds % 60);
    const milliseconds = Math.floor((totalSeconds % 1) * 100);
    return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}.${milliseconds.toString().padStart(2, '0')}`;
  };

  if (frames.length === 0) {
    return (
      <div className="bg-slate-800/50 rounded-xl p-8 text-center border border-dashed border-slate-700">
        <div className="w-16 h-16 bg-slate-700/30 rounded-full flex items-center justify-center mx-auto mb-4">
          <Gauge className="w-8 h-8 text-slate-600" />
        </div>
        <p className="text-slate-500 text-sm">暂无录制数据</p>
        <p className="text-slate-600 text-xs mt-1">完成录制后可在此回放</p>
      </div>
    );
  }

  return (
    <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 overflow-hidden">
      {title && (
        <div className="px-4 py-2 border-b border-slate-700/50">
          <h3 className="text-sm font-medium text-slate-300">{title}</h3>
        </div>
      )}

      <div className="relative aspect-video bg-slate-900">
        <canvas
          ref={canvasRef}
          className="w-full h-full object-contain"
        />

        <div className="absolute top-3 left-3 px-2.5 py-1 bg-slate-900/80 rounded text-xs text-slate-300 font-mono">
          {formatTime(currentFrameIndex)} / {formatTime(frames.length)}
        </div>

        <div className="absolute top-3 right-3 px-2.5 py-1 bg-slate-900/80 rounded text-xs text-teal-400 font-mono">
          帧 {currentFrameIndex + 1} / {frames.length}
        </div>
      </div>

      <div className="px-4 py-3 space-y-3">
        <div className="flex items-center gap-2">
          <button
            onClick={() => handleFrameStep('backward')}
            className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-700/50 rounded transition-colors"
            title="上一帧"
          >
            <SkipBack className="w-4 h-4" />
          </button>
          <button
            onClick={handleReset}
            className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-700/50 rounded transition-colors"
            title="重置"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
          <button
            onClick={handlePlayPause}
            className="p-2 bg-teal-500 hover:bg-teal-600 text-white rounded-lg transition-colors"
            title={isPlaying ? '暂停' : '播放'}
          >
            {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
          </button>
          <button
            onClick={() => handleFrameStep('forward')}
            className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-700/50 rounded transition-colors"
            title="下一帧"
          >
            <SkipForward className="w-4 h-4" />
          </button>

          <div className="flex-1 mx-2">
            <input
              type="range"
              min="0"
              max={frames.length - 1}
              value={currentFrameIndex}
              onChange={handleSeek}
              className="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-teal-500"
            />
          </div>

          <div className="flex items-center gap-1">
            {SPEED_OPTIONS.map((s) => (
              <button
                key={s}
                onClick={() => handleSpeedChange(s)}
                className={`px-2 py-1 text-xs rounded transition-colors ${
                  speed === s
                    ? 'bg-teal-500/30 text-teal-400 border border-teal-500/30'
                    : 'text-slate-400 hover:text-white hover:bg-slate-700/50'
                }`}
              >
                {s}x
              </button>
            ))}
          </div>

          <button
            className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-700/50 rounded transition-colors"
            title="全屏"
          >
            <Maximize2 className="w-4 h-4" />
          </button>
        </div>

        <div className="flex items-center justify-between text-xs text-slate-500">
          <span>
            <FastForward className="w-3.5 h-3.5 inline mr-1" />
            支持慢动作回放 (0.25x - 2x)
          </span>
          <span>{fps} FPS</span>
        </div>
      </div>
    </div>
  );
};

export default VideoPlayer;
