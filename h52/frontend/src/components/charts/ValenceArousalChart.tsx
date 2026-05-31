import { useMemo, useState } from 'react';
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ZAxis,
} from 'recharts';
import type { ValenceArousal, TimeSeriesPoint } from '@/types';
import { getQuadrant, getQuadrantLabel, formatNumber } from '@/utils';

interface ValenceArousalChartProps {
  current: ValenceArousal;
  history?: TimeSeriesPoint[];
  size?: number;
}

export function ValenceArousalChart({
  current,
  history = [],
  size = 350,
}: ValenceArousalChartProps) {
  const [hoveredPoint, setHoveredPoint] = useState<number | null>(null);

  const data = useMemo(() => {
    return history.map((point, index) => ({
      x: point.valence,
      y: point.arousal,
      z: 50 + index * 2,
      time: point.time,
      emotion: point.emotion,
      isLast: index === history.length - 1,
    }));
  }, [history]);

  const currentPoint = useMemo(() => ({
    x: current.valence,
    y: current.arousal,
    z: 200,
    isCurrent: true,
  }), [current]);

  const quadrant = getQuadrant(current.valence, current.arousal);
  const quadrantLabel = getQuadrantLabel(quadrant);

  const quadrantColors: Record<string, string> = {
    Q1: 'rgba(241, 196, 15, 0.1)',
    Q2: 'rgba(231, 76, 60, 0.1)',
    Q3: 'rgba(52, 152, 219, 0.1)',
    Q4: 'rgba(39, 174, 96, 0.1)',
  };

  const CustomTooltip = ({ active, payload }: { active?: boolean; payload?: Array<{ payload: { x: number; y: number; time?: number; isCurrent?: boolean } }> }) => {
    if (active && payload && payload.length) {
      const point = payload[0].payload;
      return (
        <div className="glass-card px-4 py-2 border-none text-sm">
          {point.time !== undefined && (
            <p className="text-muted-foreground mb-1">时间: {formatNumber(point.time, 1)}s</p>
          )}
          <p>效价: <span className="text-primary">{formatNumber(point.x)}</span></p>
          <p>唤醒度: <span className="text-secondary">{formatNumber(point.y)}</span></p>
          {point.isCurrent && (
            <p className="text-accent font-medium mt-1">当前位置</p>
          )}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="w-full">
      <div className="text-center mb-4">
        <span
          className="inline-block px-4 py-2 rounded-full text-sm font-medium"
          style={{ backgroundColor: quadrantColors[quadrant], color: '#fff' }}
        >
          {quadrantLabel}
        </span>
      </div>

      <div style={{ width: '100%', height: size }} className="relative">
        <div className="absolute top-2 right-2 z-10 text-xs text-muted-foreground space-y-1">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-primary" />
            <span>历史轨迹</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded-full bg-gradient-primary animate-pulse" />
            <span>当前位置</span>
          </div>
        </div>

        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart
            margin={{ top: 20, right: 20, bottom: 20, left: 20 }}
          >
            <defs>
              <linearGradient id="valenceGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#e74c3c" stopOpacity={0.3} />
                <stop offset="50%" stopColor="#95a5a6" stopOpacity={0.1} />
                <stop offset="100%" stopColor="#27ae60" stopOpacity={0.3} />
              </linearGradient>
              <linearGradient id="arousalGradient" x1="0%" y1="100%" x2="0%" y2="0%">
                <stop offset="0%" stopColor="#3498db" stopOpacity={0.3} />
                <stop offset="50%" stopColor="#95a5a6" stopOpacity={0.1} />
                <stop offset="100%" stopColor="#e67e22" stopOpacity={0.3} />
              </linearGradient>
            </defs>

            <CartesianGrid
              strokeDasharray="3 3"
              stroke="rgba(255,255,255,0.1)"
            />

            <XAxis
              type="number"
              dataKey="x"
              domain={[-1, 1]}
              tickCount={5}
              tickFormatter={(value) => formatNumber(value)}
              stroke="rgba(255,255,255,0.5)"
              label={{
                value: '效价 (消极 ← → 积极)',
                position: 'bottom',
                fill: 'rgba(255,255,255,0.7)',
                fontSize: 12,
              }}
            />

            <YAxis
              type="number"
              dataKey="y"
              domain={[-1, 1]}
              tickCount={5}
              tickFormatter={(value) => formatNumber(value)}
              stroke="rgba(255,255,255,0.5)"
              label={{
                value: '唤醒度 (平静 ← → 兴奋)',
                angle: -90,
                position: 'left',
                fill: 'rgba(255,255,255,0.7)',
                fontSize: 12,
              }}
            />

            <ZAxis type="number" range={[20, 200]} />

            <ReferenceLine x={0} stroke="rgba(255,255,255,0.3)" strokeDasharray="5 5" />
            <ReferenceLine y={0} stroke="rgba(255,255,255,0.3)" strokeDasharray="5 5" />

            <Tooltip content={<CustomTooltip />} cursor={{ strokeDasharray: '3 3' }} />

            {data.length > 0 && (
              <Scatter
                name="历史轨迹"
                data={data}
                fill="#667eea"
                opacity={0.6}
                animationBegin={0}
                animationDuration={500}
              />
            )}

            <Scatter
              name="当前位置"
              data={[currentPoint]}
              fill="url(#colorCurrent)"
              className="animate-pulse"
              onMouseEnter={() => setHoveredPoint(0)}
              onMouseLeave={() => setHoveredPoint(null)}
            >
              <defs>
                <radialGradient id="colorCurrent">
                  <stop offset="0%" stopColor="#f093fb" />
                  <stop offset="100%" stopColor="#667eea" />
                </radialGradient>
              </defs>
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>

        <div className="absolute bottom-16 left-4 text-xs text-muted-foreground">
          <span className="text-red-400">消极</span>
          <span className="mx-2">/</span>
          <span className="text-green-400">积极</span>
        </div>
        <div className="absolute top-1/2 right-4 -translate-y-1/2 text-xs text-muted-foreground">
          <div className="writing-mode-vertical">
            <span className="text-orange-400">兴奋</span>
          </div>
          <div className="mt-2">
            <span className="text-blue-400">平静</span>
          </div>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-4">
        <div className="text-center p-3 rounded-xl bg-white/5">
          <p className="text-xs text-muted-foreground mb-1">效价</p>
          <p className="text-2xl font-bold text-gradient font-mono">
            {formatNumber(current.valence)}
          </p>
        </div>
        <div className="text-center p-3 rounded-xl bg-white/5">
          <p className="text-xs text-muted-foreground mb-1">唤醒度</p>
          <p className="text-2xl font-bold text-gradient font-mono">
            {formatNumber(current.arousal)}
          </p>
        </div>
      </div>
    </div>
  );
}

export default ValenceArousalChart;
