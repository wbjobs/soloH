import { useMemo } from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts';
import type { EmotionProbabilities } from '@/types';
import { EMOTION_LABELS, EMOTION_COLORS } from '@/types';
import { formatPercent } from '@/utils';

interface EmotionPieChartProps {
  probabilities: EmotionProbabilities;
  size?: number;
  showLegend?: boolean;
}

export function EmotionPieChart({
  probabilities,
  size = 300,
  showLegend = true,
}: EmotionPieChartProps) {
  const data = useMemo(() => {
    return Object.entries(probabilities)
      .map(([key, value]) => ({
        name: EMOTION_LABELS[key as keyof typeof EMOTION_LABELS],
        value,
        color: EMOTION_COLORS[key as keyof typeof EMOTION_COLORS],
      }))
      .filter((item) => item.value > 0.01)
      .sort((a, b) => b.value - a.value);
  }, [probabilities]);

  const RADIAN = Math.PI / 180;

  const renderCustomizedLabel = ({
    cx,
    cy,
    midAngle,
    innerRadius,
    outerRadius,
    percent,
  }: {
    cx: number;
    cy: number;
    midAngle: number;
    innerRadius: number;
    outerRadius: number;
    percent: number;
  }) => {
    if (percent < 0.05) return null;

    const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
    const x = cx + radius * Math.cos(-midAngle * RADIAN);
    const y = cy + radius * Math.sin(-midAngle * RADIAN);

    return (
      <text
        x={x}
        y={y}
        fill="white"
        textAnchor="middle"
        dominantBaseline="central"
        className="text-xs font-medium"
      >
        {formatPercent(percent, 0)}
      </text>
    );
  };

  const CustomTooltip = ({ active, payload }: { active?: boolean; payload?: Array<{ payload: { name: string; value: number; color: string } }> }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="glass-card px-4 py-2 border-none">
          <p className="font-medium" style={{ color: data.color }}>
            {data.name}
          </p>
          <p className="text-sm text-muted-foreground">
            {formatPercent(data.value)}
          </p>
        </div>
      );
    }
    return null;
  };

  const CustomLegend = ({ payload }: { payload?: Array<{ value: string; color: string }> }) => {
    return (
      <ul className="flex flex-wrap justify-center gap-3 mt-4">
        {payload?.map((entry, index) => (
          <li key={index} className="flex items-center gap-2">
            <span
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: entry.color }}
            />
            <span className="text-sm text-muted-foreground">{entry.value}</span>
          </li>
        ))}
      </ul>
    );
  };

  if (data.length === 0) {
    return (
      <div
        className="flex items-center justify-center text-muted-foreground"
        style={{ height: size }}
      >
        暂无数据
      </div>
    );
  }

  return (
    <div style={{ width: '100%', height: size }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <defs>
            {data.map((entry, index) => (
              <filter key={`shadow-${index}`} id={`shadow-${index}`}>
                <feDropShadow dx="0" dy="2" stdDeviation="3" floodOpacity="0.3" />
              </filter>
            ))}
          </defs>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            labelLine={false}
            label={renderCustomizedLabel}
            outerRadius={size * 0.35}
            innerRadius={size * 0.15}
            paddingAngle={2}
            dataKey="value"
            animationBegin={0}
            animationDuration={800}
          >
            {data.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={entry.color}
                stroke="rgba(255,255,255,0.1)"
                strokeWidth={1}
                filter={`url(#shadow-${index})`}
                className="cursor-pointer transition-opacity hover:opacity-80"
              />
            ))}
          </Pie>
          <Tooltip content={<CustomTooltip />} />
          {showLegend && <Legend content={<CustomLegend />} />}
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

export default EmotionPieChart;
