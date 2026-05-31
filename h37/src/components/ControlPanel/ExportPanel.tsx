import { useState } from 'react';
import { Download, Loader2 } from 'lucide-react';
import { useAudioStore } from '../../store/useAudioStore';
import { WavExporter } from '../../audio/WavExporter';

export const ExportPanel = () => {
  const [exportDuration, setExportDuration] = useState(5);
  const [isExporting, setIsExporting] = useState(false);
  const { currentBand, beatFrequency, ...audioState } = useAudioStore();

  const handleExport = async () => {
    setIsExporting(true);
    try {
      const exporter = new WavExporter(44100);
      const settings = useAudioStore.getState();
      const filename = `brainwave_${currentBand.name}_${beatFrequency}Hz_${exportDuration}min.wav`;
      await exporter.downloadWAV(settings, exportDuration * 60, filename);
    } catch (error) {
      console.error('导出失败:', error);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-white/80 tracking-wider">导出音频</h3>
      <div className="p-4 bg-white/5 rounded-2xl backdrop-blur-sm space-y-4">
        <div className="space-y-1.5">
          <div className="flex justify-between items-center">
            <span className="text-xs text-white/70">导出时长</span>
            <span className="text-xs font-mono text-white/90">
              {exportDuration} 分钟
            </span>
          </div>
          <div className="flex gap-2">
            {[1, 5, 10, 15, 30].map((duration) => (
              <button
                key={duration}
                onClick={() => setExportDuration(duration)}
                className={`
                  flex-1 py-1.5 text-xs rounded-lg transition-all duration-200
                  ${exportDuration === duration
                    ? 'bg-white/20 text-white'
                    : 'bg-white/5 text-white/60 hover:bg-white/10'
                  }
                `}
              >
                {duration}m
              </button>
            ))}
          </div>
        </div>
        <button
          onClick={handleExport}
          disabled={isExporting}
          className="w-full py-3 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-500
                     text-white font-medium text-sm
                     hover:from-indigo-400 hover:to-purple-400
                     disabled:opacity-50 disabled:cursor-not-allowed
                     transition-all duration-300 flex items-center justify-center gap-2
                     shadow-lg hover:shadow-indigo-500/25"
        >
          {isExporting ? (
            <>
              <Loader2 size={16} className="animate-spin" />
              生成中...
            </>
          ) : (
            <>
              <Download size={16} />
              导出 WAV 文件
            </>
          )}
        </button>
        <p className="text-[11px] text-white/40 text-center">
          16位PCM / 44100Hz / 立体声
        </p>
      </div>
    </div>
  );
};
