import { useMemo, useState } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Area,
  AreaChart,
  ComposedChart,
  Bar,
} from 'recharts';
import type { TimeSeriesPoint, EmotionCategory } from '@/types';
import { EMOTION_LABELS, EMOTION_COLORS } from '@/types';
import { formatNumber, formatTime, getDominantEmotion } from '@/utils';

type ChartType = 'area' | 'line' | 'bar';

interface EmotionTimeSeriesProps {
  data: TimeSeriesPoint[];
  height?: number;
  emotions?: EmotionCategory[];
  showValenceArousal?: boolean;
}

export function EmotionTimeSeries({
  data,
  height = 300,
  emotions = ['anger', 'joy', 'sadness', 'surprise', 'disgust', 'fear', 'neutral'],
  showValenceArousal = true,
}: EmotionTimeSeriesProps) {
  const [chartType, setChartType] = useState<ChartType>('area');
  const [selectedEmotions, setSelectedEmotions] = useState<Set<EmotionCategory>>(
    new Set(['joy', 'sadness', 'anger'])
  );
  const [hoveredPoint, setHoveredPoint] = useState<number | null>(null);

  const chartData = useMemo(() => {
    return data.map((point) => ({
      time: point.time,
      timeLabel: formatTime(point.time),
      valence: point.valence,
      arousal: point.arousal,
      dominantEmotion: point.emotion,
      ...point.probabilities,
    }));
  }, [data]);

  const emotionColors = useMemo(() => {
    const colors: Record<string, string> = {};
    emotions.forEach((emotion) => {
      colors[emotion] = EMOTION_COLORS[emotion];
    });
    return colors;
  }, [emotions]);

  const toggleEmotion = (emotion: EmotionCategory) => {
    const newSelected = new Set(selectedEmotions);
    if (newSelected.has(emotion)) {
      if (newSelected.size > 1) {
        newSelected.delete(emotion);
      }
    } else {
      newSelected.add(emotion);
    }
    setSelectedEmotions(newSelected);
  };

  const CustomTooltip = ({ active, payload, label }: { active?: boolean; payload?: Array<{ name: string; value: number; color: string; dataKey: string }>; label?: number }) => {
    if (active && payload && payload.length) {
      const point = data.find((d) => d.time === label);
      return (
        <div className="glass-card px-4 py-3 border-none min-w-[200px]">
          <p className="text-xs text-muted-foreground mb-2">时间: {formatTime(label || 0)}</p>
          {point && (
            <p className="text-sm mb-2">
              主导情感: <span style={{ color: EMOTION_COLORS[point.emotion] }} className="font-medium">
                {EMOTION_LABELS[point.emotion]}
              </span>
            </p>
          )}
          <div className="space-y-1">
            {payload.map((entry, index) => (
              <div key={index} className="flex items-center justify-between gap-4 text-sm">
                <div className="flex items-center gap-2">
                  <span
                    className="w-2 h-2 rounded-full"
                    style={{ backgroundColor: entry.color }}
                  />
                  <span className="text-muted-foreground">
                    {entry.dataKey === 'valence' ? '效价' : entry.dataKey === 'arousal' ? '唤醒度' : EMOTION_LABELS[entry.dataKey as EmotionCategory]}
                  </span>
                </div>
                <span className="font-mono font-medium" style={{ color: entry.color }}>
                  {formatNumber(entry.value, 3)}
                </span>
              </div>
            ))}
          </div>
        </div>
      );
    }
    return null;
  };

  const CustomLegend = ({ payload }: { payload?: Array<{ value: string; color: string }> }) => {
    return (
      <div className="flex flex-wrap justify-center gap-3 mt-4">
        {emotions.map((emotion) => (
          <button
            key={emotion}
            onClick={() => toggleEmotion(emotion)}
            className={[
              'flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-all',
              selectedEmotions.has(emotion)
                ? 'bg-white/10'
                : 'opacity-40 hover:opacity-60'
            ].join(' ')}
          >
            <span
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: EMOTION_COLORS[emotion] }}
            />
            <span>{EMOTION_LABELS[emotion]}</span>
          </button>
        ))}
      </div>
    );
  };

  const renderChart = () => {
    const commonProps = {
      data: chartData,
      margin: { top: 10, right: 30, left: 0, bottom: 0 },
    };

    const yAxisProps = {
      type: 'number' as const,
      domain: showValenceArousal ? [-1, 1] : [0, 1],
      tickCount: 5,
      tickFormatter: (value: number) => formatNumber(value, 1),
      stroke: 'rgba(255,255,255,0.5)',
    };

    const xAxisProps = {
      dataKey: 'time',
      type: 'number' as const,
      tickFormatter: (value: number) => formatTime(value),
      stroke: 'rgba(255,255,255,0.5)',
      label: { value: '时间', position: 'bottom', fill: 'rgba(255,255,255,0.7)', fontSize: 12 },
    };

    if (chartType === 'bar') {
      return (
        <ComposedChart {...commonProps}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
          <XAxis {...xAxisProps} />
          <YAxis {...yAxisProps} />
          <Tooltip content={<CustomTooltip />} />
          {Array.from(selectedEmotions).map((emotion) => (
            <Bar
              key={emotion}
              dataKey={emotion}
              fill={emotionColors[emotion]}
              opacity={0.7}
              animationDuration={500}
            />
          ))}
        </ComposedChart>
      );
    }

    if (chartType === 'line') {
      return (
        <LineChart {...commonProps}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
          <XAxis {...xAxisProps} />
          <YAxis {...yAxisProps} />
          <Tooltip content={<CustomTooltip />} />
          {Array.from(selectedEmotions).map((emotion) => (
            <Line
              key={emotion}
              type="monotone"
              dataKey={emotion}
              stroke={emotionColors[emotion]}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 6, strokeWidth: 2 }}
              animationDuration={500}
              onMouseEnter={() => setHoveredPoint(emotions.indexOf(emotion))}
              onMouseLeave={() => setHoveredPoint(null)}
            />
          ))}
          {showValenceArousal && (
            <>
              <Line
                type="monotone"
                dataKey="valence"
                stroke="#667eea"
                strokeWidth={2}
                strokeDasharray="5 5"
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="arousal"
                stroke="#764ba2"
                strokeWidth={2}
                strokeDasharray="5 5"
                dot={false}
              />
            </>
          )}
        </LineChart>
      );
    }

    return (
      <AreaChart {...commonProps}>
        <defs>
          {Array.from(selectedEmotions).map((emotion) => (
            <linearGradient key={emotion} id={`gradient-${emotion}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={emotionColors[emotion]} stopOpacity={0.5} />
              <stop offset="100%" stopColor={emotionColors[emotion]} stopOpacity={0} />
            </linearGradient>
          ))}
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
        <XAxis {...xAxisProps} />
        <YAxis {...yAxisProps} />
        <Tooltip content={<CustomTooltip />} />
        {Array.from(selectedEmotions).map((emotion) => (
          <Area
            key={emotion}
            type="monotone"
            dataKey={emotion}
            stroke={emotionColors[emotion]}
            strokeWidth={2}
            fill={`url(#gradient-${emotion})`}
            animationDuration={500}
          />
        ))}
      </AreaChart>
    );
  };

  if (data.length === 0) {
    return (
      <div
        className="flex items-center justify-center text-muted-foreground"
        style={{ height }}
      >
        暂无时序数据
      </div>
    );
  }

  return (
    <div className="w-full">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          {(['area', 'line', 'bar'] as ChartType[]).map((type) => (
            <button
              key={type}
              onClick={() => setChartType(type)}
              className={[
                'px-3 py-1.5 rounded-lg text-sm transition-all',
                chartType === type
                  ? 'bg-primary text-white'
                  : 'bg-white/5 text-muted-foreground hover:bg-white/10'
              ].join(' ')}
            >
              {type === 'area' ? '面积图' : type === 'line' ? '折线图' : '柱状图'}
            </button>
          ))}
        </div>

        {showValenceArousal && (
          <div className="flex items-center gap-4 text-xs">
            <div className="flex items-center gap-2">
              <span className="w-4 h-0.5 bg-primary" style={{ backgroundImage: 'linear-gradient(90deg, #667eea, #764ba2)' }} />
              <span className="text-muted-foreground">效价/唤醒度</span>
            </div>
          </div>
        )}
      </div>

      <div style={{ width: '100%', height }}>
        <ResponsiveContainer width="100%" height="100%">
          {renderChart()}
        </ResponsiveContainer>
      </div>

      <Legend content={<CustomLegend />} />
    </div>
  );
}

export default EmotionTimeSeries;
