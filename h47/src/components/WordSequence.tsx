import { RecognizedWord, GrammarError } from '@/types';
import { getErrorTypeName } from '@/data/grammarRules';
import { AlertTriangle, CheckCircle2, Sparkles } from 'lucide-react';

interface WordSequenceProps {
  words: RecognizedWord[];
  errors: GrammarError[];
  correctedSequence?: RecognizedWord[];
}

const WordSequence = ({ words, errors, correctedSequence }: WordSequenceProps) => {
  const errorPositions = new Set(errors.map(e => e.position));

  const detectEmphasis = (wordIndex: number): { isEmphasis: boolean; repeatCount: number } => {
    if (wordIndex === 0) return { isEmphasis: false, repeatCount: 1 };

    const currentWord = words[wordIndex].word;
    let repeatCount = 1;
    let i = wordIndex - 1;

    while (i >= 0 && words[i].word === currentWord) {
      repeatCount++;
      i--;
    }

    const isEmphasis = repeatCount > 1 && words[wordIndex].endTime - words[wordIndex - repeatCount + 1].startTime < 3000;

    return { isEmphasis, repeatCount };
  };

  if (words.length === 0) {
    return (
      <div className="bg-slate-800/50 rounded-xl p-8 text-center border border-dashed border-slate-700">
        <div className="w-12 h-12 bg-slate-700/50 rounded-full flex items-center justify-center mx-auto mb-3">
          <Sparkles className="w-6 h-6 text-slate-500" />
        </div>
        <p className="text-slate-500 text-sm">开始手语表达，词汇将显示在这里</p>
        <p className="text-slate-600 text-xs mt-1">支持 300 个常见手语词汇识别</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h4 className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
          识别结果
        </h4>
        <div className="flex flex-wrap gap-2">
          {words.map((word, index) => {
            const hasError = errorPositions.has(index);
            const { isEmphasis, repeatCount } = detectEmphasis(index);
            const isFirstOfEmphasis = isEmphasis && (index === 0 || words[index - 1].word !== word.word);

            if (isEmphasis && !isFirstOfEmphasis) {
              return null;
            }

            const displayWord = isEmphasis ? word.word.repeat(repeatCount) : word.word;
            const avgConfidence = isEmphasis
              ? Math.max(...words.slice(index, index + repeatCount).map(w => w.confidence))
              : word.confidence;

            return (
              <div
                key={`${word.word}-${index}`}
                className={`group relative px-3 py-2 rounded-lg font-medium transition-all duration-200 ${
                  hasError
                    ? 'bg-red-500/20 text-red-400 border border-red-500/30 animate-pulse'
                    : isEmphasis
                    ? 'bg-gradient-to-r from-amber-500/20 to-orange-500/20 text-amber-300 border border-amber-500/30 shadow-lg shadow-amber-500/10'
                    : 'bg-slate-700/50 text-white border border-slate-600/50'
                }`}
              >
                <span className="text-base">{displayWord}</span>
                <span className="text-xs opacity-60 ml-1">{word.pinyin}</span>
                <div className="text-xs opacity-40 mt-0.5">
                  {Math.round(avgConfidence * 100)}%
                </div>
                {isEmphasis && (
                  <span className="absolute -top-2 -right-2 px-1.5 py-0.5 bg-amber-500 text-white text-[10px] rounded-full font-bold">
                    {repeatCount}×
                  </span>
                )}
                {hasError && (
                  <AlertTriangle className="w-3.5 h-3.5 absolute -top-1.5 -right-1.5 text-red-400" />
                )}
                {word.category && (
                  <div className="absolute -bottom-1 left-1/2 transform -translate-x-1/2 translate-y-full opacity-0 group-hover:opacity-100 transition-opacity bg-slate-900 text-xs text-slate-300 px-2 py-1 rounded whitespace-nowrap z-10 mt-1">
                    {word.category}
                    {isEmphasis && <span className="text-amber-400 ml-1">(表强调)</span>}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {correctedSequence && correctedSequence.length > 0 && !words.every((w, i) => correctedSequence[i]?.word === w.word) && (
        <div>
          <h4 className="text-xs font-medium text-teal-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5" />
            正确语法序列
          </h4>
          <div className="flex flex-wrap gap-2">
            {correctedSequence.map((word, index) => {
              const originalWord = words[index];
              const isChanged = originalWord?.word !== word.word;
              return (
                <div
                  key={`corrected-${word.word}-${index}`}
                  className={`px-3 py-2 rounded-lg font-medium ${
                    isChanged
                      ? 'bg-teal-500/20 text-teal-400 border border-teal-500/30'
                      : 'bg-slate-700/30 text-slate-400 border border-slate-600/30'
                  }`}
                >
                  <span className="text-base">{word.word}</span>
                  <span className="text-xs opacity-60 ml-1">{word.pinyin}</span>
                  {isChanged && (
                    <span className="text-xs ml-1 text-teal-400">↻</span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {errors.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-xs font-medium text-red-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5" />
            语法错误 ({errors.length})
          </h4>
          <div className="space-y-2">
            {errors.map((error, index) => (
              <div
                key={index}
                className="bg-red-500/10 border border-red-500/20 rounded-lg p-3"
              >
                <div className="flex items-start gap-2">
                  <span className="px-2 py-0.5 bg-red-500/20 text-red-400 text-xs rounded font-medium">
                    {getErrorTypeName(error.type)}
                  </span>
                  <span className="text-red-300 font-medium">"{error.word}"</span>
                </div>
                <p className="text-sm text-slate-400 mt-1">{error.description}</p>
                <p className="text-sm text-teal-400 mt-1 flex items-center gap-1">
                  <Sparkles className="w-3.5 h-3.5" />
                  建议：{error.suggestion}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default WordSequence;
