import { useAppStore } from '@/store/appStore';
import { Play, Pause, Square, RotateCcw, Save, Gauge } from 'lucide-react';

const ControlPanel = () => {
  const {
    isRecording,
    isPaused,
    recognizedWords,
    grammarResult,
    startSession,
    endSession,
    setPaused,
    clearRecognizedWords,
    saveCurrentError,
    minConfidence,
    setMinConfidence
  } = useAppStore();

  const handleStart = () => {
    startSession();
  };

  const handleStop = async () => {
    await endSession();
  };

  const handlePause = () => {
    setPaused(!isPaused);
  };

  const handleClear = () => {
    clearRecognizedWords();
  };

  const handleSave = async () => {
    await saveCurrentError();
  };

  return (
    <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50">
      <div className="flex flex-wrap items-center gap-3">
        {!isRecording ? (
          <button
            onClick={handleStart}
            className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-teal-500 to-cyan-500 hover:from-teal-600 hover:to-cyan-600 text-white rounded-lg font-medium transition-all duration-200 shadow-lg shadow-teal-500/20 hover:shadow-teal-500/30 hover:scale-[1.02] active:scale-[0.98]"
          >
            <Play className="w-4 h-4" />
            开始录制
          </button>
        ) : (
          <>
            <button
              onClick={handlePause}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-lg font-medium transition-all duration-200 ${
                isPaused
                  ? 'bg-teal-500/20 text-teal-400 border border-teal-500/30 hover:bg-teal-500/30'
                  : 'bg-amber-500/20 text-amber-400 border border-amber-500/30 hover:bg-amber-500/30'
              }`}
            >
              {isPaused ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
              {isPaused ? '继续' : '暂停'}
            </button>
            <button
              onClick={handleStop}
              className="flex items-center gap-2 px-5 py-2.5 bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30 rounded-lg font-medium transition-all duration-200"
            >
              <Square className="w-4 h-4" />
              结束
            </button>
          </>
        )}

        {recognizedWords.length > 0 && (
          <>
            <button
              onClick={handleClear}
              className="flex items-center gap-2 px-4 py-2.5 text-slate-400 hover:text-white hover:bg-slate-700/50 rounded-lg font-medium transition-all duration-200"
            >
              <RotateCcw className="w-4 h-4" />
              清除
            </button>
            {grammarResult && !grammarResult.isCorrect && (
              <button
                onClick={handleSave}
                className="flex items-center gap-2 px-4 py-2.5 text-teal-400 hover:text-teal-300 hover:bg-teal-500/10 rounded-lg font-medium transition-all duration-200"
              >
                <Save className="w-4 h-4" />
                保存错误
              </button>
            )}
          </>
        )}

        <div className="flex-1" />

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-slate-400">
            <Gauge className="w-4 h-4" />
            <span className="text-xs">识别阈值</span>
          </div>
          <input
            type="range"
            min="0.3"
            max="0.9"
            step="0.05"
            value={minConfidence}
            onChange={(e) => setMinConfidence(parseFloat(e.target.value))}
            className="w-24 h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-teal-500"
          />
          <span className="text-xs text-teal-400 font-medium w-8">
            {Math.round(minConfidence * 100)}%
          </span>
        </div>
      </div>

      {grammarResult && (
        <div className="mt-4 pt-4 border-t border-slate-700/50">
          <div className="flex items-center gap-3">
            <div
              className={`px-3 py-1.5 rounded-lg text-sm font-medium flex items-center gap-2 ${
                grammarResult.isCorrect
                  ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                  : 'bg-red-500/20 text-red-400 border border-red-500/30'
              }`}
            >
              {grammarResult.isCorrect ? '✓ 语法正确' : `✗ ${grammarResult.errors.length} 处语法错误`}
            </div>
            {grammarResult.ruleApplied.length > 0 && (
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs text-slate-500">应用规则：</span>
                {grammarResult.ruleApplied.map((rule, i) => (
                  <span
                    key={i}
                    className="px-2 py-0.5 bg-slate-700/50 text-slate-400 text-xs rounded"
                  >
                    {rule}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default ControlPanel;
