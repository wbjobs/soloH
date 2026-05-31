interface SliderInputProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  unit?: string;
  onChange: (value: number) => void;
  description?: string;
}

export function SliderInput({
  label,
  value,
  min,
  max,
  step,
  unit = '',
  onChange,
  description,
}: SliderInputProps) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-slate-300">{label}</label>
        <div className="flex items-center gap-1">
          <input
            type="number"
            value={value}
            min={min}
            max={max}
            step={step}
            onChange={(e) => onChange(Number(e.target.value))}
            className="w-20 px-2 py-1 bg-space-800/70 border border-slate-500/30 rounded text-right text-slate-200 font-mono text-sm focus:outline-none focus:border-quantum-400/50"
          />
          <span className="text-slate-500 text-xs w-8">{unit}</span>
        </div>
      </div>
      <input
        type="range"
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full"
      />
      {description && (
        <p className="text-xs text-slate-500">{description}</p>
      )}
    </div>
  );
}
