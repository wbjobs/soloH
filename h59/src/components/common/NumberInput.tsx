import React from 'react';

interface NumberInputProps {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
  unit?: string;
  className?: string;
}

export const NumberInput: React.FC<NumberInputProps> = ({
  label,
  value,
  onChange,
  min,
  max,
  step = 1,
  unit,
  className = '',
}) => {
  return (
    <div className={`flex flex-col ${className}`}>
      <label className="text-xs text-slate-400 mb-1">{label}</label>
      <div className="flex items-center gap-1">
        <input
          type="number"
          value={value}
          onChange={(e) => {
            const num = parseFloat(e.target.value);
            if (!isNaN(num)) {
              let newValue = num;
              if (min !== undefined) newValue = Math.max(min, newValue);
              if (max !== undefined) newValue = Math.min(max, newValue);
              onChange(newValue);
            }
          }}
          min={min}
          max={max}
          step={step}
          className="w-full px-2 py-1.5 text-sm bg-slate-900 border border-slate-600 rounded text-slate-200 focus:border-cyan-500 focus:outline-none"
        />
        {unit && <span className="text-xs text-slate-500 whitespace-nowrap">{unit}</span>}
      </div>
    </div>
  );
};
