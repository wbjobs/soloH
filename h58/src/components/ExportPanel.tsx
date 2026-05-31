import React, { useState } from 'react';
import { Download, Copy, Check, FileText, Code } from 'lucide-react';
import { useAppStore } from '../store/useAppStore';
import { generateFullTextSVG, generateCharacterSVG, downloadSVG, copySVGToClipboard } from '../utils/svgGenerator';

interface ExportPanelProps {
  className?: string;
}

export const ExportPanel: React.FC<ExportPanelProps> = ({ className = '' }) => {
  const { generatedCharacters, parameters, layout, seal, signature, rubbing } = useAppStore();
  const [copied, setCopied] = useState(false);
  const [showCode, setShowCode] = useState(false);
  const [exportFormat, setExportFormat] = useState<'animated' | 'static'>('animated');
  const [svgContent, setSvgContent] = useState<string>('');

  const generateSVG = () => {
    if (generatedCharacters.length === 0) return '';
    
    if (exportFormat === 'animated') {
      return generateFullTextSVG(generatedCharacters, 200, 200, true, layout, seal, signature, rubbing);
    } else {
      return generateFullTextSVG(generatedCharacters, 200, 200, false, layout, seal, signature, rubbing);
    }
  };

  const handleDownload = () => {
    const svg = generateSVG();
    if (svg) {
      const filename = `handwriting_${Date.now()}.svg`;
      downloadSVG(svg, filename);
    }
  };

  const handleCopyCode = async () => {
    const svg = generateSVG();
    if (svg) {
      await copySVGToClipboard(svg);
      setCopied(true);
      setSvgContent(svg);
      setShowCode(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleViewCode = () => {
    const svg = generateSVG();
    setSvgContent(svg);
    setShowCode(!showCode);
  };

  if (generatedCharacters.length === 0) {
    return (
      <div className={`${className}`}>
        <h3 className="font-calligraphy text-xl mb-4 text-[#1a1a1a]">导出</h3>
        <div className="text-center py-6 text-[#6b6b6b] bg-[#e8e0cf]/30 rounded-lg">
          <FileText className="w-10 h-10 mx-auto mb-2 opacity-50" />
          <p className="text-sm">生成手写体后可导出 SVG 文件</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`${className}`}>
      <h3 className="font-calligraphy text-xl mb-4 text-[#1a1a1a]">导出</h3>
      
      <div className="flex gap-2 mb-4">
        <button
          onClick={() => setExportFormat('animated')}
          className={`flex-1 py-2 text-sm rounded transition-all ${
            exportFormat === 'animated'
              ? 'bg-[#1a1a1a] text-[#f5f0e6]'
              : 'bg-[#e8e0cf] text-[#6b6b6b] hover:bg-[#d8cfb8]'
          }`}
        >
          动画版
        </button>
        <button
          onClick={() => setExportFormat('static')}
          className={`flex-1 py-2 text-sm rounded transition-all ${
            exportFormat === 'static'
              ? 'bg-[#1a1a1a] text-[#f5f0e6]'
              : 'bg-[#e8e0cf] text-[#6b6b6b] hover:bg-[#d8cfb8]'
          }`}
        >
          静态版
        </button>
      </div>
      
      <div className="space-y-3">
        <button
          onClick={handleDownload}
          className="ink-button w-full py-3 flex items-center justify-center gap-2 rounded-lg"
        >
          <Download className="w-5 h-5" />
          下载 SVG 文件
        </button>
        
        <button
          onClick={handleCopyCode}
          className="w-full py-3 flex items-center justify-center gap-2 rounded-lg border-2 border-[#1a1a1a] text-[#1a1a1a] hover:bg-[#1a1a1a] hover:text-[#f5f0e6] transition-colors font-semibold"
        >
          {copied ? (
            <>
              <Check className="w-5 h-5" />
              已复制到剪贴板
            </>
          ) : (
            <>
              <Copy className="w-5 h-5" />
              复制 SVG 代码
            </>
          )}
        </button>
        
        <button
          onClick={handleViewCode}
          className={`w-full py-2 text-sm flex items-center justify-center gap-2 rounded-lg transition-colors ${
            showCode 
              ? 'bg-[#c41e3a] text-white' 
              : 'bg-[#e8e0cf] text-[#3d3d3d] hover:bg-[#d8cfb8]'
          }`}
        >
          <Code className="w-4 h-4" />
          {showCode ? '隐藏代码' : '查看 SVG 代码'}
        </button>
      </div>
      
      {showCode && svgContent && (
        <div className="mt-4">
          <p className="text-xs text-[#6b6b6b] mb-2">SVG 代码预览：</p>
          <pre className="bg-[#1a1a1a] text-[#f5f0e6] p-3 rounded-lg text-xs overflow-x-auto scrollbar-ink max-h-40">
            {svgContent.substring(0, 500)}
            {svgContent.length > 500 && '...'}
          </pre>
          <p className="text-xs text-[#6b6b6b] mt-2 text-center">
            共 {svgContent.length} 字符
          </p>
        </div>
      )}
      
      <div className="mt-4 p-3 bg-[#e8e0cf]/30 rounded-lg">
        <h4 className="text-sm font-semibold text-[#3d3d3d] mb-2">导出信息</h4>
        <div className="text-xs text-[#6b6b6b] space-y-1">
          <p>字符数：{generatedCharacters.filter(c => c.character.trim() !== '').length} 字</p>
          <p>总笔画：{generatedCharacters.reduce((sum, c) => sum + c.strokes.length, 0)} 笔</p>
          <p>格式：{exportFormat === 'animated' ? '带书写动画' : '静态图像'}</p>
        </div>
      </div>
    </div>
  );
};
