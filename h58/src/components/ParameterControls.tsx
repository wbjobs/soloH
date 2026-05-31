import React from 'react';
import { PenTool, Zap, Wind } from 'lucide-react';
import { useAppStore } from '../store/useAppStore';

interface ParameterControlsProps {
  className?: string;
}

export const ParameterControls: React.FC<ParameterControlsProps> = ({ className = '' }) => {
  const { parameters, setParameters } = useAppStore();

  return (
    <div className={`${className}`}>
      <h3 className="font-calligraphy text-xl mb-4 text-[#1a1a1a]">参数调节</h3>
      
      <div className="space-y-5">
        <ParameterSlider
          label="笔画粗细"
          value={parameters.thickness}
          onChange={(v) => setParameters({ thickness: v })}
          min={10}
          max={100}
          icon={<PenTool className="w-4 h-4" />}
          description="控制笔画的整体粗细程度"
        />
        
        <ParameterSlider
          label="书写速度"
          value={parameters.speed}
          onChange={(v) => setParameters({ speed: v })}
          min={10}
          max={100}
          icon={<Zap className="w-4 h-4" />}
          description="影响动画播放速度和笔画流畅度"
        />
        
        <ParameterSlider
          label="飞白效果"
          value={parameters.flyingWhite}
          onChange={(v) => setParameters({ flyingWhite: v })}
          min={0}
          max={100}
          icon={<Wind className="w-4 h-4" />}
          description="控制笔画中的飞白（枯笔）效果强度"
        />
      </div>
    </div>
  );
};

interface ParameterSliderProps {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min: number;
  max: number;
  icon: React.ReactNode;
  description: string;
}

const ParameterSlider: React.FC<ParameterSliderProps> = ({
  label,
  value,
  onChange,
  min,
  max,
  icon,
  description
}) => {
  return (
    <div className="group">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-[#3d3d3d]">{icon}</span>
          <span className="font-semibold text-[#1a1a1a]">{label}</span>
        </div>
        <span className="text-[#c41e3a] font-bold font-mono text-sm">{value}</span>
      </div>
      
      <input
        type="range"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="slider-ink w-full"
      />
      
      <div className="flex justify-between text-xs text-[#6b6b6b] mt-1">
        <span>{min}</span>
        <span className="text-[#3d3d3d]">{description}</span>
        <span>{max}</span>
      </div>
    </div>
  );
};
