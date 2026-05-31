import { Copy, Check, Volume2 } from 'lucide-react';
import { useState } from 'react';

interface TranslationOutputProps {
  translation: string;
  originalText?: string;
}

const TranslationOutput = ({ translation, originalText }: TranslationOutputProps) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    if (!translation) return;
    try {
      await navigator.clipboard.writeText(translation);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (e) {
      console.error('Copy failed:', e);
    }
  };

  const handleSpeak = () => {
    if (!translation) return;
    const utterance = new SpeechSynthesisUtterance(translation);
    utterance.lang = 'zh-CN';
    utterance.rate = 0.9;
    speechSynthesis.speak(utterance);
  };

  if (!translation && !originalText) {
    return (
      <div className="bg-slate-800/50 rounded-xl p-6 border border-slate-700/50">
        <div className="text-center py-8">
          <div className="w-16 h-16 bg-slate-700/30 rounded-full flex items-center justify-center mx-auto mb-4">
            <Volume2 className="w-8 h-8 text-slate-600" />
          </div>
          <p className="text-slate-500 text-sm">翻译结果将显示在这里</p>
          <p className="text-slate-600 text-xs mt-1">支持语音朗读和一键复制</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-700/50 flex items-center justify-between">
        <h3 className="text-sm font-medium text-slate-300">翻译输出</h3>
        <div className="flex items-center gap-1">
          <button
            onClick={handleSpeak}
            disabled={!translation}
            className="p-2 text-slate-400 hover:text-white hover:bg-slate-700/50 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title="语音朗读"
          >
            <Volume2 className="w-4 h-4" />
          </button>
          <button
            onClick={handleCopy}
            disabled={!translation}
            className="p-2 text-slate-400 hover:text-white hover:bg-slate-700/50 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title="复制文本"
          >
            {copied ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
          </button>
        </div>
      </div>

      <div className="p-5 space-y-4">
        {originalText && (
          <div>
            <div className="text-xs text-slate-500 uppercase tracking-wider mb-1.5">
              原文
            </div>
            <div className="text-slate-400 text-base leading-relaxed">
              {originalText}
            </div>
          </div>
        )}

        {translation && (
          <div>
            <div className="text-xs text-teal-400 uppercase tracking-wider mb-1.5">
              正确翻译
            </div>
            <div className="text-white text-lg leading-relaxed font-medium">
              {translation}
            </div>
          </div>
        )}
      </div>

      <div className="px-4 py-3 bg-slate-900/50 border-t border-slate-700/50">
        <div className="flex items-center justify-between text-xs text-slate-500">
          <span>基于中国手语语法规则翻译</span>
          <span>
            {translation ? `${translation.length} 字符` : ''}
          </span>
        </div>
      </div>
    </div>
  );
};

export default TranslationOutput;
