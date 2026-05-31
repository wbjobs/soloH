import React from 'react';
import { Grid3X3, ArrowLeftRight, ArrowUpDown, Shuffle, AlignLeft, AlignCenter, AlignRight, LayoutGrid, LayoutList } from 'lucide-react';
import { useAppStore } from '../store/useAppStore';

interface LayoutControlsProps {
  className?: string;
}

export const LayoutControls: React.FC<LayoutControlsProps> = ({ className = '' }) => {
  const { layout, setLayout } = useAppStore();

  return (
    <div className={`${className}`}>
      <h3 className="font-calligraphy text-xl mb-4 text-[#1a1a1a] flex items-center gap-2">
        <Grid3X3 className="w-5 h-5 text-[#c41e3a]" />
        章法布局
      </h3>
      
      <div className="space-y-4">
        <div className="flex gap-2 mb-4">
          <button
            onClick={() => setLayout({ direction: 'horizontal' })}
            className={`flex-1 py-2 px-3 text-sm rounded flex items-center justify-center gap-1 transition-all ${
              layout.direction === 'horizontal'
                ? 'bg-[#1a1a1a] text-[#f5f0e6]'
                : 'bg-[#e8e0cf] text-[#6b6b6b] hover:bg-[#d8cfb8]'
            }`}
          >
            <LayoutList className="w-4 h-4" />
            横排
          </button>
          <button
            onClick={() => setLayout({ direction: 'vertical' })}
            className={`flex-1 py-2 px-3 text-sm rounded flex items-center justify-center gap-1 transition-all ${
              layout.direction === 'vertical'
                ? 'bg-[#1a1a1a] text-[#f5f0e6]'
                : 'bg-[#e8e0cf] text-[#6b6b6b] hover:bg-[#d8cfb8]'
            }`}
          >
            <LayoutGrid className="w-4 h-4" />
            竖排
          </button>
        </div>
        
        <div className="flex gap-2 mb-4">
          <button
            onClick={() => setLayout({ alignment: 'left' })}
            className={`flex-1 py-2 rounded transition-all ${
              layout.alignment === 'left'
                ? 'bg-[#c41e3a] text-white'
                : 'bg-[#e8e0cf] text-[#6b6b6b] hover:bg-[#d8cfb8]'
            }`}
            title="左对齐"
          >
            <AlignLeft className="w-4 h-4 mx-auto" />
          </button>
          <button
            onClick={() => setLayout({ alignment: 'center' })}
            className={`flex-1 py-2 rounded transition-all ${
              layout.alignment === 'center'
                ? 'bg-[#c41e3a] text-white'
                : 'bg-[#e8e0cf] text-[#6b6b6b] hover:bg-[#d8cfb8]'
            }`}
            title="居中对齐"
          >
            <AlignCenter className="w-4 h-4 mx-auto" />
          </button>
          <button
            onClick={() => setLayout({ alignment: 'right' })}
            className={`flex-1 py-2 rounded transition-all ${
              layout.alignment === 'right'
                ? 'bg-[#c41e3a] text-white'
                : 'bg-[#e8e0cf] text-[#6b6b6b] hover:bg-[#d8cfb8]'
            }`}
            title="右对齐"
          >
            <AlignRight className="w-4 h-4 mx-auto" />
          </button>
        </div>
        
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-sm text-[#3d3d3d] flex items-center gap-1">
              <ArrowLeftRight className="w-4 h-4 text-[#6b6b6b]" />
              字间距
            </label>
            <span className="text-xs font-mono bg-[#e8e0cf] px-2 py-0.5 rounded">
              {layout.charSpacing}px
            </span>
          </div>
          <input
            type="range"
            min="0"
            max="60"
            value={layout.charSpacing}
            onChange={(e) => setLayout({ charSpacing: parseInt(e.target.value) })}
            className="w-full slider-ink"
          />
        </div>
        
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-sm text-[#3d3d3d] flex items-center gap-1">
              <ArrowUpDown className="w-4 h-4 text-[#6b6b6b]" />
              行间距
            </label>
            <span className="text-xs font-mono bg-[#e8e0cf] px-2 py-0.5 rounded">
              {layout.lineSpacing}px
            </span>
          </div>
          <input
            type="range"
            min="10"
            max="80"
            value={layout.lineSpacing}
            onChange={(e) => setLayout({ lineSpacing: parseInt(e.target.value) })}
            className="w-full slider-ink"
          />
        </div>
        
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-sm text-[#3d3d3d] flex items-center gap-1">
              <Shuffle className="w-4 h-4 text-[#6b6b6b]" />
              错落程度
            </label>
            <span className="text-xs font-mono bg-[#e8e0cf] px-2 py-0.5 rounded">
              {layout.scatterAmount}%
            </span>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            value={layout.scatterAmount}
            onChange={(e) => setLayout({ scatterAmount: parseInt(e.target.value) })}
            className="w-full slider-ink"
          />
        </div>
        
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-sm text-[#3d3d3d]">
              每行字数
            </label>
            <span className="text-xs font-mono bg-[#e8e0cf] px-2 py-0.5 rounded">
              {layout.charsPerLine}
            </span>
          </div>
          <input
            type="range"
            min="1"
            max="20"
            value={layout.charsPerLine}
            onChange={(e) => setLayout({ charsPerLine: parseInt(e.target.value) })}
            className="w-full slider-ink"
          />
        </div>
      </div>
      
      <div className="mt-4 p-3 bg-[#e8e0cf]/30 rounded-lg">
        <h4 className="text-sm font-semibold text-[#3d3d3d] mb-2">布局说明</h4>
        <ul className="text-xs text-[#6b6b6b] space-y-1">
          <li>• <strong>错落</strong>：模拟手写自然的位置偏移和角度变化</li>
          <li>• <strong>竖排</strong>：从右至左，传统书法排版</li>
          <li>• <strong>对齐</strong>：控制整体文本的对齐方式</li>
        </ul>
      </div>
    </div>
  );
};
