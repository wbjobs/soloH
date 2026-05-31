import React from 'react';
import { Play, Pause, RotateCcw, Wifi, WifiOff, Clock } from 'lucide-react';

interface ControlButtonsProps {
  isRunning: boolean;
  isConnected: boolean;
  time: number;
  onStart: () => void;
  onPause: () => void;
  onReset: () => void;
  isLoading?: boolean;
}

export const ControlButtons: React.FC<ControlButtonsProps> = ({
  isRunning,
  isConnected,
  time,
  onStart,
  onPause,
  onReset,
  isLoading = false
}) => {
  const formatTime = (t: number): string => {
    const minutes = Math.floor(t / 60);
    const seconds = (t % 60).toFixed(1);
    return `${minutes}:${seconds.padStart(4, '0')}`;
  };

  return (
    <div className="border border-zinc-700/50 rounded-xl bg-zinc-900/50 backdrop-blur-sm p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-zinc-200">仿真控制</h3>
        <div className="flex items-center gap-2">
          {isConnected ? (
            <div className="flex items-center gap-1 text-green-400">
              <Wifi size={14} />
              <span className="text-xs">已连接</span>
            </div>
          ) : (
            <div className="flex items-center gap-1 text-red-400">
              <WifiOff size={14} />
              <span className="text-xs">未连接</span>
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center justify-center gap-3 bg-zinc-800/50 rounded-lg p-3">
        <Clock size={18} className="text-zinc-400" />
        <span className="text-3xl font-mono font-bold text-blue-400 tracking-wider">
          {formatTime(time)}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-2">
        {!isRunning ? (
          <button
            onClick={onStart}
            disabled={isLoading || !isConnected}
            className="flex items-center justify-center gap-2 bg-green-600 hover:bg-green-500 disabled:bg-zinc-700 disabled:cursor-not-allowed text-white font-medium py-3 px-4 rounded-lg transition-all duration-200 hover:scale-105 active:scale-95"
          >
            <Play size={18} />
            <span>启动</span>
          </button>
        ) : (
          <button
            onClick={onPause}
            disabled={isLoading}
            className="flex items-center justify-center gap-2 bg-amber-600 hover:bg-amber-500 disabled:bg-zinc-700 disabled:cursor-not-allowed text-white font-medium py-3 px-4 rounded-lg transition-all duration-200 hover:scale-105 active:scale-95"
          >
            <Pause size={18} />
            <span>暂停</span>
          </button>
        )}

        <button
          onClick={onReset}
          disabled={isLoading}
          className="flex items-center justify-center gap-2 bg-zinc-700 hover:bg-zinc-600 disabled:bg-zinc-800 disabled:cursor-not-allowed text-white font-medium py-3 px-4 rounded-lg transition-all duration-200 hover:scale-105 active:scale-95 col-span-2"
        >
          <RotateCcw size={18} />
          <span>重置仿真</span>
        </button>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center gap-2 text-zinc-400 text-sm">
          <div className="w-4 h-4 border-2 border-zinc-600 border-t-blue-400 rounded-full animate-spin"></div>
          <span>处理中...</span>
        </div>
      )}
    </div>
  );
};
