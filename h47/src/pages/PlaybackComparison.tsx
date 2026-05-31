import { useState, useEffect } from 'react';
import { useAppStore } from '@/store/appStore';
import { storageService } from '@/services/storageService';
import { RecordedSession, RecognizedWord } from '@/types';
import VideoPlayer from '@/components/VideoPlayer';
import WordSequence from '@/components/WordSequence';
import TranslationOutput from '@/components/TranslationOutput';
import { getErrorTypeName } from '@/data/grammarRules';
import {
  ArrowLeftRight,
  Clock,
  ChevronDown,
  Play,
  Calendar,
  AlertTriangle,
  CheckCircle2
} from 'lucide-react';

const PlaybackComparison = () => {
  const { currentSession, recognizedWords, grammarResult, currentFrames } = useAppStore();
  const [sessions, setSessions] = useState<RecordedSession[]>([]);
  const [selectedSession, setSelectedSession] = useState<RecordedSession | null>(null);
  const [showSessionList, setShowSessionList] = useState(false);
  const [leftFrameIndex, setLeftFrameIndex] = useState(0);
  const [rightFrameIndex, setRightFrameIndex] = useState(0);
  const [syncPlayback, setSyncPlayback] = useState(true);

  useEffect(() => {
    loadSessions();
  }, []);

  const loadSessions = async () => {
    try {
      const data = await storageService.getSessions(20);
      setSessions(data);
    } catch (e) {
      console.error('Failed to load sessions:', e);
    }
  };

  const handleSelectSession = (session: RecordedSession) => {
    setSelectedSession(session);
    setShowSessionList(false);
    setLeftFrameIndex(0);
    setRightFrameIndex(0);
  };

  const formatDate = (timestamp: number) => {
    return new Date(timestamp).toLocaleString('zh-CN', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const formatDuration = (ms: number) => {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
  };

  const displayFrames = selectedSession?.frames || currentFrames;
  const displayWords = selectedSession?.recognizedWords || recognizedWords;
  const displayGrammarResult = selectedSession?.grammarResult || grammarResult;
  const hasError = !displayGrammarResult?.isCorrect && displayGrammarResult?.errors && displayGrammarResult.errors.length > 0;

  const originalText = displayWords.map(w => w.word).join(' ');
  const translation = displayGrammarResult?.translation || '';

  const handleLeftFrameChange = (index: number) => {
    setLeftFrameIndex(index);
    if (syncPlayback) {
      setRightFrameIndex(index);
    }
  };

  const handleRightFrameChange = (index: number) => {
    setRightFrameIndex(index);
    if (syncPlayback) {
      setLeftFrameIndex(index);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950">
      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="mb-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold text-white">回放对比</h2>
              <p className="text-sm text-slate-400 mt-1">
                慢动作回放和标准语法对比
              </p>
            </div>

            <div className="relative">
              <button
                onClick={() => setShowSessionList(!showSessionList)}
                className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg border border-slate-700 transition-colors"
              >
                <Calendar className="w-4 h-4" />
                <span className="text-sm">
                  {selectedSession
                    ? formatDate(selectedSession.timestamp)
                    : '选择历史记录'}
                </span>
                <ChevronDown
                  className={`w-4 h-4 transition-transform ${showSessionList ? 'rotate-180' : ''}`}
                />
              </button>

              {showSessionList && (
                <div className="absolute right-0 mt-2 w-80 bg-slate-800 border border-slate-700 rounded-xl shadow-xl z-50 max-h-96 overflow-y-auto">
                  {sessions.length === 0 ? (
                    <div className="p-4 text-center text-slate-500 text-sm">
                      暂无历史记录
                    </div>
                  ) : (
                    sessions.map((session) => (
                      <button
                        key={session.id}
                        onClick={() => handleSelectSession(session)}
                        className={`w-full p-3 text-left hover:bg-slate-700/50 border-b border-slate-700/50 last:border-b-0 transition-colors ${
                          selectedSession?.id === session.id ? 'bg-slate-700/30' : ''
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Play className="w-3.5 h-3.5 text-teal-400" />
                            <span className="text-sm text-white">
                              {formatDate(session.timestamp)}
                            </span>
                          </div>
                          <div className="flex items-center gap-2">
                            {session.grammarResult?.isCorrect ? (
                              <CheckCircle2 className="w-3.5 h-3.5 text-green-400" />
                            ) : (
                              <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
                            )}
                            <span className="text-xs text-slate-500 font-mono">
                              {formatDuration(session.duration)}
                            </span>
                          </div>
                        </div>
                        <div className="mt-1 text-xs text-slate-500">
                          {session.recognizedWords.map(w => w.word).join(' ')}
                        </div>
                      </button>
                    ))
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <VideoPlayer
            frames={displayFrames}
            title="原始录制"
            showOverlay={true}
            onFrameChange={handleLeftFrameChange}
          />
          <VideoPlayer
            frames={displayFrames}
            title="标准参考"
            showOverlay={true}
            onFrameChange={handleRightFrameChange}
          />
        </div>

        <div className="flex items-center justify-center gap-4 mb-6">
          <label className="flex items-center gap-2 text-sm text-slate-400 cursor-pointer hover:text-white transition-colors">
            <input
              type="checkbox"
              checked={syncPlayback}
              onChange={(e) => setSyncPlayback(e.target.checked)}
              className="w-4 h-4 rounded border-slate-600 text-teal-500 focus:ring-teal-500 bg-slate-800"
            />
            <span>同步播放进度</span>
          </label>
          <ArrowLeftRight className="w-4 h-4 text-slate-600" />
          <span className="text-xs text-slate-500">
            左侧帧: {leftFrameIndex + 1} | 右侧帧: {rightFrameIndex + 1}
          </span>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50">
            <h3 className="text-sm font-medium text-slate-300 mb-3 flex items-center gap-2">
              <Clock className="w-4 h-4 text-teal-400" />
              词序列分析
            </h3>
            <WordSequence
              words={displayWords}
              errors={displayGrammarResult?.errors || []}
              correctedSequence={displayGrammarResult?.correctedSequence}
            />
          </div>

          <div className="space-y-4">
            <TranslationOutput
              translation={translation}
              originalText={originalText}
            />

            {hasError && displayGrammarResult && (
              <div className="bg-slate-800/30 rounded-xl p-4 border border-red-500/20">
                <h4 className="text-xs font-medium text-red-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  语法错误详情
                </h4>
                <div className="space-y-2">
                  {displayGrammarResult.errors.map((error, index) => (
                    <div
                      key={index}
                      className="bg-red-500/10 border border-red-500/20 rounded-lg p-3"
                    >
                      <div className="flex items-start gap-2">
                        <span className="px-2 py-0.5 bg-red-500/20 text-red-400 text-xs rounded font-medium whitespace-nowrap">
                          {getErrorTypeName(error.type)}
                        </span>
                        <span className="text-red-300 font-medium">"{error.word}"</span>
                      </div>
                      <p className="text-sm text-slate-400 mt-1">{error.description}</p>
                      <p className="text-sm text-teal-400 mt-1">建议：{error.suggestion}</p>
                    </div>
                  ))}
                </div>
                {displayGrammarResult.ruleApplied.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-slate-700/50">
                    <span className="text-xs text-slate-500">应用的语法规则：</span>
                    <div className="flex flex-wrap gap-1.5 mt-1.5">
                      {displayGrammarResult.ruleApplied.map((rule, i) => (
                        <span
                          key={i}
                          className="px-2 py-0.5 bg-slate-700/50 text-slate-400 text-xs rounded"
                        >
                          {rule}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {selectedSession && (
              <div className="bg-slate-800/30 rounded-xl p-4 border border-slate-700/30">
                <h4 className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
                  会话信息
                </h4>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <span className="text-slate-500">录制时间：</span>
                    <span className="text-white">{formatDate(selectedSession.timestamp)}</span>
                  </div>
                  <div>
                    <span className="text-slate-500">持续时长：</span>
                    <span className="text-white">{formatDuration(selectedSession.duration)}</span>
                  </div>
                  <div>
                    <span className="text-slate-500">词汇数量：</span>
                    <span className="text-white">{selectedSession.recognizedWords.length} 个</span>
                  </div>
                  <div>
                    <span className="text-slate-500">帧数量：</span>
                    <span className="text-white">{selectedSession.frames.length} 帧</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default PlaybackComparison;
