import type { ReactNode } from 'react';
import { TrendingUp } from 'lucide-react';

interface ResultCardProps {
  title: string;
  value: string | number;
  unit?: string;
  icon: ReactNode;
  color: 'quantum' | 'energy' | 'slate';
  description?: string;
  trend?: number;
}

export function ResultCard({ title, value, unit, icon, color, description, trend }: ResultCardProps) {
  const colorClasses = {
    quantum: 'from-quantum-400/20 to-quantum-400/5 border-quantum-400/30 text-quantum-400',
    energy: 'from-energy-400/20 to-energy-400/5 border-energy-400/30 text-energy-400',
    slate: 'from-slate-500/20 to-slate-500/5 border-slate-500/30 text-slate-300',
  };

  const bgColorClasses = {
    quantum: 'bg-quantum-400/20',
    energy: 'bg-energy-400/20',
    slate: 'bg-slate-500/20',
  };

  return (
    <div className={`glass-card p-5 bg-gradient-to-br ${colorClasses[color]} transition-all duration-300 hover:scale-[1.02] hover:shadow-lg`}>
      <div className="flex items-start justify-between mb-4">
        <div className={`w-10 h-10 rounded-lg ${bgColorClasses[color]} flex items-center justify-center`}>
          {icon}
        </div>
        {trend !== undefined && (
          <div className="flex items-center gap-1 text-xs">
            <TrendingUp className="w-3 h-3 text-green-400" />
            <span className="text-green-400">{trend.toFixed(1)}%</span>
          </div>
        )}
      </div>
      <p className="text-sm text-slate-400 mb-1">{title}</p>
      <div className="flex items-baseline gap-1">
        <span className="text-2xl font-bold font-mono">{value}</span>
        {unit && <span className="text-sm text-slate-500">{unit}</span>}
      </div>
      {description && (
        <p className="text-xs text-slate-500 mt-2">{description}</p>
      )}
    </div>
  );
}
