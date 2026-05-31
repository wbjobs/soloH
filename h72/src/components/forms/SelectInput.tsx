import { ChevronDown } from 'lucide-react';

interface SelectInputProps<T extends string> {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
  description?: string;
}

export function SelectInput<T extends string>({
  label,
  value,
  options,
  onChange,
  description,
}: SelectInputProps<T>) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-slate-300 block">{label}</label>
      <div className="relative">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value as T)}
          className="w-full px-4 py-2.5 bg-space-800/50 border border-slate-500/30 rounded-lg text-slate-300 font-mono text-sm appearance-none focus:outline-none focus:border-quantum-400/60 focus:ring-2 focus:ring-quantum-400/20 transition-all duration-300 pr-10"
        >
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none" />
      </div>
      {description && (
        <p className="text-xs text-slate-500">{description}</p>
      )}
    </div>
  );
}
