import React from 'react';
import { Layers, SlidersHorizontal } from 'lucide-react';
import { useAppStore } from '../store/useAppStore';

interface StyleFusionProps {
  className?: string;
}

export const StyleFusion: React.FC<StyleFusionProps> = ({ className = '' }) => {
  const { samples, updateSampleWeight } = useAppStore();

  if (samples.length === 0) {
    return (
      <div className={`${className}`}>
        <h3 className="font-calligraphy text-xl mb-4 text-[#1a1a1a]">风格融合</h3>
        <div className="text-center py-8 text-[#6b6b6b] bg-[#e8e0cf]/30 rounded-lg">
          <Layers className="w-10 h-10 mx-auto mb-2 opacity-50" />
          <p className="text-sm">上传多个样本字后可调节风格权重</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`${className}`}>
      <h3 className="font-calligraphy text-xl mb-4 text-[#1a1a1a] flex items-center gap-2">
        <SlidersHorizontal className="w-5 h-5" />
        风格融合
      </h3>
      
      <p className="text-sm text-[#6b6b6b] mb-4">
        调节各样本的权重，实现多风格融合效果
      </p>
      
      <div className="space-y-4">
        {samples.map((sample, index) => (
          <div key={sample.id} className="bg-[#e8e0cf]/30 rounded-lg p-3">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 rounded overflow-hidden border border-[#6b6b6b]/30">
                <img 
                  src={sample.originalImage} 
                  alt={sample.name}
                  className="w-full h-full object-cover"
                />
              </div>
              <div className="flex-1">
                <div className="flex items-center justify-between">
                  <span className="font-calligraphy text-[#1a1a1a]">{sample.character}</span>
                  <span className="text-[#c41e3a] font-mono text-sm font-bold">
                    {Math.round(sample.weight * 100)}%
                  </span>
                </div>
                <p className="text-xs text-[#6b6b6b]">{sample.name}</p>
              </div>
            </div>
            
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={sample.weight}
              onChange={(e) => updateSampleWeight(sample.id, Number(e.target.value))}
              className="slider-ink w-full h-1"
            />
            
            <div className="flex justify-between text-xs text-[#6b6b6b] mt-1">
              <span>弱</span>
              <span>强</span>
            </div>
          </div>
        ))}
      </div>
      
      <div className="mt-4 p-3 bg-[#1a1a1a]/5 rounded-lg">
        <p className="text-xs text-[#3d3d3d] text-center">
          当前融合 {samples.length} 种风格
        </p>
      </div>
    </div>
  );
};
