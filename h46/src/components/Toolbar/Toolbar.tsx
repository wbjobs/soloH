import { useState, useRef, useCallback } from 'react';
import { Play, Pause, RotateCcw, Download, Video, VideoOff, Settings, RefreshCw, BarChart3 } from 'lucide-react';
import { useSimulationStore } from '../../store/useSimulationStore';
import { useParameterStore } from '../../store/useParameterStore';
import { exportImpactForceToCSV, exportProbabilityDistributionToCSV, downloadCSV, generateFileName } from '../../utils/csvExporter';
import { VideoRecorder, generateVideoFileName } from '../../utils/videoRecorder';

interface ToolbarProps {
  canvas: HTMLCanvasElement | null;
  onToggleSettings: () => void;
  onToggleMonitor: () => void;
}

export function Toolbar({ canvas, onToggleSettings, onToggleMonitor }: ToolbarProps) {
  const { start, pause, reset, isRunning, isPaused, getEngine, simulationTime } = useSimulationStore();
  const { sphParams } = useParameterStore();
  const [isRecording, setIsRecording] = useState(false);
  const videoRecorderRef = useRef<VideoRecorder | null>(null);
  const [isExporting, setIsExporting] = useState(false);

  const handleStartPause = useCallback(() => {
    if (!isRunning) {
      start();
    } else {
      pause();
    }
  }, [isRunning, start, pause]);

  const handleReset = useCallback(() => {
    reset();
  }, [reset]);

  const handleExportCSV = useCallback(async () => {
    setIsExporting(true);
    try {
      const engine = getEngine();
      if (engine) {
        const history = engine.getImpactHistory();
        const csv = exportImpactForceToCSV(history);
        const filename = generateFileName('impact_force', 'csv');
        downloadCSV(csv, filename);
      }
    } catch (error) {
      console.error('Export failed:', error);
    } finally {
      setIsExporting(false);
    }
  }, [getEngine]);

  const handleExportProbability = useCallback(async () => {
    setIsExporting(true);
    try {
      const engine = getEngine();
      if (engine) {
        const history = engine.getImpactHistory();
        const latestData = history[history.length - 1];
        if (latestData?.probabilityDistribution) {
          const csv = exportProbabilityDistributionToCSV(latestData.probabilityDistribution);
          const filename = generateFileName('probability_distribution', 'csv');
          downloadCSV(csv, filename);
        }
      }
    } catch (error) {
      console.error('Export failed:', error);
    } finally {
      setIsExporting(false);
    }
  }, [getEngine]);

  const handleToggleRecording = useCallback(async () => {
    if (!canvas) return;

    if (!isRecording) {
      try {
        videoRecorderRef.current = new VideoRecorder(canvas, 30);
        await videoRecorderRef.current.start();
        setIsRecording(true);
      } catch (error) {
        console.error('Recording failed to start:', error);
      }
    } else {
      try {
        if (videoRecorderRef.current) {
          const blob = await videoRecorderRef.current.stop();
          const filename = generateVideoFileName();
          videoRecorderRef.current.download(blob, filename);
          videoRecorderRef.current.destroy();
          videoRecorderRef.current = null;
        }
        setIsRecording(false);
      } catch (error) {
        console.error('Recording failed to stop:', error);
        setIsRecording(false);
      }
    }
  }, [canvas, isRecording]);

  const handleReinitialize = useCallback(() => {
    const engine = getEngine();
    if (engine) {
      engine.initParticles(sphParams.maxParticles > 0 ? 
        Math.min(1000, sphParams.maxParticles) : 1000);
    }
  }, [getEngine, sphParams.maxParticles]);

  return (
    <div className="absolute top-0 left-0 right-0 z-10 flex items-center justify-between px-4 py-3 bg-slate-900/80 backdrop-blur-sm border-b border-cyan-500/20">
      <div className="flex items-center gap-2">
        <h1 className="text-xl font-bold text-cyan-400 tracking-wider" style={{ fontFamily: "'Orbitron', sans-serif" }}>
          SPH 泥石流模拟
        </h1>
        <span className="text-xs text-slate-400 ml-2">
          Bingham 非牛顿流体模型
        </span>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={handleStartPause}
          className={`flex items-center gap-2 px-4 py-2 rounded-md font-medium transition-all duration-200 ${
            isRunning && !isPaused
              ? 'bg-amber-500/80 hover:bg-amber-500 text-white'
              : 'bg-cyan-500/80 hover:bg-cyan-500 text-white'
          } shadow-lg hover:shadow-cyan-500/25`}
        >
          {isRunning && !isPaused ? (
            <>
              <Pause size={18} />
              暂停
            </>
          ) : (
            <>
              <Play size={18} />
              开始
            </>
          )}
        </button>

        <button
          onClick={handleReset}
          className="flex items-center gap-2 px-4 py-2 bg-slate-700/80 hover:bg-slate-600 text-white rounded-md font-medium transition-all duration-200 shadow-lg"
        >
          <RotateCcw size={18} />
          重置
        </button>

        <button
          onClick={handleReinitialize}
          className="flex items-center gap-2 px-4 py-2 bg-slate-700/80 hover:bg-slate-600 text-white rounded-md font-medium transition-all duration-200 shadow-lg"
        >
          <RefreshCw size={18} />
          重新生成粒子
        </button>

        <div className="w-px h-8 bg-slate-600 mx-2" />

        <button
          onClick={handleExportCSV}
          disabled={isExporting}
          className="flex items-center gap-2 px-4 py-2 bg-emerald-600/80 hover:bg-emerald-600 text-white rounded-md font-medium transition-all duration-200 shadow-lg disabled:opacity-50"
        >
          <Download size={18} />
          {isExporting ? '导出中...' : '导出数据'}
        </button>

        <button
          onClick={handleExportProbability}
          disabled={isExporting}
          className="flex items-center gap-2 px-4 py-2 bg-purple-600/80 hover:bg-purple-600 text-white rounded-md font-medium transition-all duration-200 shadow-lg disabled:opacity-50"
        >
          <BarChart3 size={18} />
          概率分布
        </button>

        <button
          onClick={handleToggleRecording}
          className={`flex items-center gap-2 px-4 py-2 rounded-md font-medium transition-all duration-200 shadow-lg ${
            isRecording
              ? 'bg-red-500/80 hover:bg-red-500 text-white animate-pulse'
              : 'bg-slate-700/80 hover:bg-slate-600 text-white'
          }`}
        >
          {isRecording ? <VideoOff size={18} /> : <Video size={18} />}
          {isRecording ? '停止录制' : '录制视频'}
        </button>

        <div className="w-px h-8 bg-slate-600 mx-2" />

        <button
          onClick={onToggleSettings}
          className="flex items-center gap-2 px-4 py-2 bg-slate-700/80 hover:bg-slate-600 text-white rounded-md font-medium transition-all duration-200 shadow-lg"
        >
          <Settings size={18} />
          参数设置
        </button>

        <button
          onClick={onToggleMonitor}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600/80 hover:bg-indigo-600 text-white rounded-md font-medium transition-all duration-200 shadow-lg"
        >
          数据监控
        </button>
      </div>
    </div>
  );
}
