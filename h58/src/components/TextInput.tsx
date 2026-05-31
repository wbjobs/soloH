import React from 'react';
import { Type, Sparkles } from 'lucide-react';
import { useAppStore } from '../store/useAppStore';
import { generateText } from '../utils/characterGenerator';

interface TextInputProps {
  className?: string;
  onGenerate: () => void;
}

export const TextInput: React.FC<TextInputProps> = ({ className = '', onGenerate }) => {
  const { targetText, setTargetText, samples, parameters, setGeneratedCharacters, resetAnimation } = useAppStore();
  const [isGenerating, setIsGenerating] = React.useState(false);

  const handleGenerate = async () => {
    if (!targetText.trim()) {
      alert('请输入要生成的文本');
      return;
    }
    
    setIsGenerating(true);
    resetAnimation();
    
    try {
      const generated = generateText(targetText, samples, parameters);
      setGeneratedCharacters(generated);
      onGenerate();
    } catch (error) {
      console.error('生成失败:', error);
      alert('生成失败，请重试');
    } finally {
      setIsGenerating(false);
    }
  };

  const presetTexts = ['永字八法', '天道酬勤', '厚德载物', '上善若水', '龙马精神'];

  return (
    <div className={`${className}`}>
      <h3 className="font-calligraphy text-xl mb-4 text-[#1a1a1a] flex items-center gap-2">
        <Type className="w-5 h-5" />
        目标文本
      </h3>
      
      <div className="mb-3">
        <textarea
          value={targetText}
          onChange={(e) => setTargetText(e.target.value)}
          placeholder="请输入要生成的汉字文本..."
          className="w-full h-24 p-3 bg-[#f5f0e6] border border-[#6b6b6b]/30 rounded-lg focus:border-[#c41e3a] focus:outline-none resize-none font-serif-sc text-[#1a1a1a]"
        />
        <div className="flex justify-between text-xs text-[#6b6b6b] mt-1">
          <span>建议输入 1-10 个汉字</span>
          <span>{targetText.length} 字</span>
        </div>
      </div>
      
      <div className="mb-4">
        <p className="text-xs text-[#6b6b6b] mb-2">快捷输入</p>
        <div className="flex flex-wrap gap-2">
          {presetTexts.map((text) => (
            <button
              key={text}
              onClick={() => setTargetText(text)}
              className={`px-3 py-1 text-sm rounded transition-all ${
                targetText === text
                  ? 'bg-[#c41e3a] text-white'
                  : 'bg-[#e8e0cf] text-[#3d3d3d] hover:bg-[#d8cfb8]'
              }`}
            >
              {text}
            </button>
          ))}
        </div>
      </div>
      
      <button
        onClick={handleGenerate}
        disabled={isGenerating || !targetText.trim()}
        className="ink-button vermilion-button w-full py-3 flex items-center justify-center gap-2 rounded-lg"
      >
        {isGenerating ? (
          <>
            <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
            生成中...
          </>
        ) : (
          <>
            <Sparkles className="w-5 h-5" />
            生成手写体
          </>
        )}
      </button>
      
      {samples.length === 0 && (
        <p className="text-xs text-[#c41e3a] mt-2 text-center">
          提示：上传样本字可获得更贴合的风格
        </p>
      )}
    </div>
  );
};
