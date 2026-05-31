import React from 'react';
import { Framer, CircleDot, Sparkles, Square, Contrast } from 'lucide-react';
import { useAppStore } from '../store/useAppStore';

interface RubbingControlsProps {
  className?: string;
}

export const RubbingControls: React.FC<RubbingControlsProps> = ({ className = '' }) => {
  const { rubbing, setRubbing } = useAppStore();

  const presetStyles = [
    { name: '经典拓片', invert: true, mottle: 40, edge: 30, contrast: 70 },
    { name: '浅拓', invert: true, mottle: 20, edge: 15, contrast: 50 },
    { name: '深拓', invert: true, mottle: 60, edge: 50, contrast: 85 },
    { name: '残碑', invert: true, mottle: 80, edge: 70, contrast: 90 },
  ];

  return (
    <div className={`${className}`}>
      <h3 className="font-calligraphy text-xl mb-4 text-[#1a1a1a] flex items-center gap-2">
        <Framer className="w-5 h-5 text-[#c41e3a]" />
        拓片效果
      </h3>
      
      <div className="flex items-center gap-2 mb-4">
        <input
          type="checkbox"
          id="rubbing-enabled"
          checked={rubbing.enabled}
          onChange={(e) => setRubbing({ enabled: e.target.checked })}
          className="w-4 h-4 accent-[#c41e3a]"
        />
        <label htmlFor="rubbing-enabled" className="text-sm text-[#3d3d3d]">
          启⽤拓片效果
        </label>
      </div>
      
      <div className="grid grid-cols-2 gap-2 mb-4">
        {presetStyles.map((preset) => (
          <button
            key={preset.name}
            onClick={() => setRubbing({
              enabled: true,
              invert: preset.invert,
              mottleIntensity: preset.mottle,
              edgeRoughness: preset.edge,
              contrast: preset.contrast
            })}
            className="py-2 px-2 text-xs bg-[#e8e0cf] hover:bg-[#d8cfb8] rounded transition-colors text-left"
          >
            {preset.name}
          </button>
        ))}
      </div>
      
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="rubbing-invert"
            checked={rubbing.invert}
            onChange={(e) => setRubbing({ invert: e.target.checked })}
            disabled={!rubbing.enabled}
            className="w-4 h-4 accent-[#c41e3a] disabled:opacity-50"
          />
          <label htmlFor="rubbing-invert" className="text-sm text-[#3d3d3d] flex items-center gap-1">
            <CircleDot className="w-4 h-4 text-[#6b6b6b]" />
            黑白反转（黑底白字）
          </label>
        </div>
        
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="rubbing-paper"
            checked={rubbing.paperTexture}
            onChange={(e) => setRubbing({ paperTexture: e.target.checked })}
            disabled={!rubbing.enabled}
            className="w-4 h-4 accent-[#c41e3a] disabled:opacity-50"
          />
          <label htmlFor="rubbing-paper" className="text-sm text-[#3d3d3d] flex items-center gap-1">
            <Square className="w-4 h-4 text-[#6b6b6b]" />
            宣纸纹理
          </label>
        </div>
        
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-sm text-[#3d3d3d] flex items-center gap-1">
              <Sparkles className="w-4 h-4 text-[#6b6b6b]" />
              斑驳程度
            </label>
            <span className="text-xs font-mono bg-[#e8e0cf] px-2 py-0.5 rounded">
              {rubbing.mottleIntensity}%
            </span>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            value={rubbing.mottleIntensity}
            onChange={(e) => setRubbing({ mottleIntensity: parseInt(e.target.value) })}
            disabled={!rubbing.enabled}
            className="w-full slider-ink disabled:opacity-50"
          />
        </div>
        
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-sm text-[#3d3d3d] flex items-center gap-1">
              <Sparkles className="w-4 h-4 text-[#6b6b6b]" />
              边缘风化
            </label>
            <span className="text-xs font-mono bg-[#e8e0cf] px-2 py-0.5 rounded">
              {rubbing.edgeRoughness}%
            </span>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            value={rubbing.edgeRoughness}
            onChange={(e) => setRubbing({ edgeRoughness: parseInt(e.target.value) })}
            disabled={!rubbing.enabled}
            className="w-full slider-ink disabled:opacity-50"
          />
        </div>
        
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-sm text-[#3d3d3d] flex items-center gap-1">
              <Contrast className="w-4 h-4 text-[#6b6b6b]" />
              对比度
            </label>
            <span className="text-xs font-mono bg-[#e8e0cf] px-2 py-0.5 rounded">
              {rubbing.contrast}%
            </span>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            value={rubbing.contrast}
            onChange={(e) => setRubbing({ contrast: parseInt(e.target.value) })}
            disabled={!rubbing.enabled}
            className="w-full slider-ink disabled:opacity-50"
          />
        </div>
      </div>
      
      <div className="mt-4 p-3 bg-[#e8e0cf]/30 rounded-lg">
        <h4 className="text-sm font-semibold text-[#3d3d3d] mb-2">效果说明</h4>
        <ul className="text-xs text-[#6b6b6b] space-y-1">
          <li>• <strong>黑白反转</strong>：模拟黑底白字的碑拓效果</li>
          <li>• <strong>斑驳程度</strong>：年代久远造成的石面风化痕迹</li>
          <li>• <strong>边缘风化</strong>：笔画边缘的自然磨损效果</li>
          <li>• <strong>宣纸纹理</strong>：叠加纤维质感，更接近真实拓片</li>
        </ul>
      </div>
    </div>
  );
};
