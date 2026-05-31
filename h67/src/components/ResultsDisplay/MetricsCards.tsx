import React from 'react';
import { Droplet, Zap, Activity, Ruler } from 'lucide-react';
import { SimulationResult } from '../../types';

interface MetricsCardsProps {
  result: SimulationResult | undefined;
}

export const MetricsCards: React.FC<MetricsCardsProps> = ({ result }) => {
  const formatNumber = (num: number | undefined, decimals: number = 2): string => {
    if (num === undefined) return '--';
    return num.toFixed(decimals);
  };

  const cards = [
    {
      title: '液滴尺寸',
      value: formatNumber(result?.dropletSize),
      unit: 'μm',
      icon: <Droplet size={24} />,
      color: 'blue',
      bgColor: 'bg-blue-500/10',
      borderColor: 'border-blue-500/30',
      textColor: 'text-blue-400'
    },
    {
      title: '生成频率',
      value: formatNumber(result?.generationFrequency),
      unit: 'Hz',
      icon: <Zap size={24} />,
      color: 'amber',
      bgColor: 'bg-amber-500/10',
      borderColor: 'border-amber-500/30',
      textColor: 'text-amber-400'
    },
    {
      title: '流量比 Qd/Qc',
      value: formatNumber(result?.flowRateRatio, 3),
      unit: '',
      icon: <Activity size={24} />,
      color: 'green',
      bgColor: 'bg-green-500/10',
      borderColor: 'border-green-500/30',
      textColor: 'text-green-400'
    },
    {
      title: '毛细管数 Ca',
      value: formatNumber(result?.capillaryNumber, 5),
      unit: '',
      icon: <Ruler size={24} />,
      color: 'purple',
      bgColor: 'bg-purple-500/10',
      borderColor: 'border-purple-500/30',
      textColor: 'text-purple-400'
    }
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {cards.map((card, index) => (
        <div
          key={index}
          className={`${card.bgColor} border ${card.borderColor} rounded-xl p-4 transition-all duration-300 hover:scale-[1.02]`}
        >
          <div className="flex items-start justify-between mb-2">
            <span className="text-xs text-zinc-400 font-medium">{card.title}</span>
            <div className={`${card.textColor} opacity-70`}>
              {card.icon}
            </div>
          </div>
          <div className="flex items-baseline gap-1">
            <span className={`text-2xl font-mono font-bold ${card.textColor}`}>
              {card.value}
            </span>
            {card.unit && (
              <span className="text-xs text-zinc-500 font-mono">{card.unit}</span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
};
