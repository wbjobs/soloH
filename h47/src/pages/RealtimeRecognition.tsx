import { useAppStore } from '@/store/appStore';
import VideoCapture from '@/components/VideoCapture';
import ControlPanel from '@/components/ControlPanel';
import WordSequence from '@/components/WordSequence';
import TranslationOutput from '@/components/TranslationOutput';
import EnhancedFeaturesPanel from '@/components/EnhancedFeaturesPanel';
import { BookOpen, Info } from 'lucide-react';
import { GRAMMAR_RULES } from '@/data/grammarRules';

const RealtimeRecognition = () => {
  const { recognizedWords, grammarResult, isRecording, sessionStartTime } = useAppStore();

  const originalText = recognizedWords.map(w => w.word).join(' ');
  const translation = grammarResult?.translation || '';

  return (
    <div className="min-h-screen bg-slate-950">
      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-4">
            <VideoCapture />
            <ControlPanel />
          </div>

          <div className="space-y-4">
            <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50">
              <h3 className="text-sm font-medium text-slate-300 mb-3 flex items-center gap-2">
                <BookOpen className="w-4 h-4 text-teal-400" />
                识别结果
              </h3>
              <div className="max-h-96 overflow-y-auto pr-1 space-y-4">
                <WordSequence
                  words={recognizedWords}
                  errors={grammarResult?.errors || []}
                  correctedSequence={grammarResult?.correctedSequence}
                />
              </div>
            </div>

            <TranslationOutput
              translation={translation}
              originalText={originalText}
            />

            <EnhancedFeaturesPanel />

            <div className="bg-slate-800/30 rounded-xl p-4 border border-slate-700/30">
              <h4 className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                <Info className="w-3.5 h-3.5" />
                中国手语语法规则
              </h4>
              <div className="space-y-2">
                {GRAMMAR_RULES.map((rule) => (
                  <div key={rule.id} className="text-xs text-slate-500">
                    <span className="text-teal-400 font-medium">{rule.name}：</span>
                    {rule.description}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {isRecording && sessionStartTime && (
          <div className="fixed bottom-6 left-1/2 transform -translate-x-1/2 px-6 py-3 bg-slate-800/90 backdrop-blur-sm rounded-xl border border-slate-700 text-sm text-slate-300 flex items-center gap-3">
            <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
            录制中
            <span className="text-slate-500">|</span>
            <span className="font-mono">
              {Math.floor((Date.now() - sessionStartTime) / 1000)}s
            </span>
            <span className="text-slate-500">|</span>
            <span>{recognizedWords.length} 个词汇</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default RealtimeRecognition;
