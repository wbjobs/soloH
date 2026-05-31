import { useMemo } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import { RISK_THRESHOLDS, RISK_COLORS, CROP_TYPE_LABELS } from '@/types/map'
import type { CropType } from '@/types'

interface TrendDataPoint {
  date: string
  label: string
  [key: string]: string | number
}

interface RiskTrendChartProps {
  data: TrendDataPoint[]
  crops: CropType[]
  showThreshold?: boolean
  height?: number
}

const CROP_COLORS: Record<CropType, string> = {
  wheat: '#f59e0b',
  potato: '#8b5cf6',
  corn: '#10b981',
  rice: '#0ea5e9',
}

export const RiskTrendChart = ({
  data,
  crops,
  showThreshold = true,
  height = 350,
}: RiskTrendChartProps) => {
  const lines = useMemo(() => {
    return crops.map((crop) => ({
      dataKey: crop,
      name: CROP_TYPE_LABELS[crop],
      color: CROP_COLORS[crop],
    }))
  }, [crops])

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3">
          <p className="text-sm font-medium text-gray-900 mb-2">{label}</p>
          {payload.map((entry: any, index: number) => (
            <div key={index} className="flex items-center gap-2 text-sm">
              <div
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: entry.color }}
              />
              <span className="text-gray-600">{entry.name}:</span>
              <span className="font-medium text-gray-900">
                {entry.value?.toFixed(1) || 0}
              </span>
            </div>
          ))}
        </div>
      )
    }
    return null
  }

  return (
    <div className="w-full" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={data}
          margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 12, fill: '#6b7280' }}
            axisLine={{ stroke: '#d1d5db' }}
            tickLine={{ stroke: '#d1d5db' }}
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fontSize: 12, fill: '#6b7280' }}
            axisLine={{ stroke: '#d1d5db' }}
            tickLine={{ stroke: '#d1d5db' }}
            tickFormatter={(value) => `${value}`}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{ paddingTop: '20px' }}
            iconType="circle"
            formatter={(value) => <span className="text-sm text-gray-600">{value}</span>}
          />

          {showThreshold && (
            <>
              <ReferenceLine
                y={RISK_THRESHOLDS.low}
                stroke={RISK_COLORS.low}
                strokeDasharray="5 5"
                strokeWidth={1}
                label={{
                  value: '低风险',
                  position: 'right',
                  fill: RISK_COLORS.low,
                  fontSize: 11,
                }}
              />
              <ReferenceLine
                y={RISK_THRESHOLDS.medium}
                stroke={RISK_COLORS.medium}
                strokeDasharray="5 5"
                strokeWidth={1}
                label={{
                  value: '中风险',
                  position: 'right',
                  fill: RISK_COLORS.medium,
                  fontSize: 11,
                }}
              />
              <ReferenceLine
                y={RISK_THRESHOLDS.high}
                stroke={RISK_COLORS.high}
                strokeDasharray="5 5"
                strokeWidth={1}
                label={{
                  value: '高风险',
                  position: 'right',
                  fill: RISK_COLORS.high,
                  fontSize: 11,
                }}
              />
            </>
          )}

          {lines.map((line) => (
            <Line
              key={line.dataKey}
              type="monotone"
              dataKey={line.dataKey}
              name={line.name}
              stroke={line.color}
              strokeWidth={2.5}
              dot={{ r: 4, strokeWidth: 2, fill: '#fff' }}
              activeDot={{ r: 6, strokeWidth: 2 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export default RiskTrendChart
