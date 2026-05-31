import { useMemo } from 'react'
import { X, Thermometer, MapPin } from 'lucide-react'
import {
  getRiskLegendItems,
  getRiskColor,
  getRiskLevel,
  RISK_THRESHOLDS,
  type RiskLegendItem,
} from '@/types/map'

interface RiskLegendProps {
  visible: boolean
  onClose: () => void
  hoveredRiskIndex?: number | null
  mousePosition?: { lat: number; lng: number } | null
}

export const RiskLegend = ({
  visible,
  onClose,
  hoveredRiskIndex,
  mousePosition,
}: RiskLegendProps) => {
  const legendItems = useMemo(() => getRiskLegendItems(), [])

  const gradientStyle = useMemo(() => {
    const stops = legendItems.map((item) => {
      const percent = (item.max / 100) * 100
      return `${item.color} ${percent}%`
    })
    return `linear-gradient(to right, ${stops.join(', ')})`
  }, [legendItems])

  const indicatorPosition = useMemo(() => {
    if (hoveredRiskIndex === null || hoveredRiskIndex === undefined) return null
    return Math.max(0, Math.min(100, hoveredRiskIndex))
  }, [hoveredRiskIndex])

  const currentRiskLevel = useMemo(() => {
    if (hoveredRiskIndex === null || hoveredRiskIndex === undefined) return null
    return getRiskLevel(hoveredRiskIndex)
  }, [hoveredRiskIndex])

  const currentRiskColor = useMemo(() => {
    if (hoveredRiskIndex === null || hoveredRiskIndex === undefined) return null
    return getRiskColor(hoveredRiskIndex)
  }, [hoveredRiskIndex])

  const getLevelLabel = (level: string): string => {
    switch (level) {
      case 'low':
        return '低风险'
      case 'medium':
        return '中风险'
      case 'high':
        return '高风险'
      case 'extreme':
        return '极高风险'
      default:
        return ''
    }
  }

  if (!visible) return null

  return (
    <div className="absolute bottom-4 right-4 z-10 bg-white rounded-xl shadow-lg overflow-hidden min-w-[280px]">
      <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Thermometer className="w-5 h-5 text-orange-500" />
          <span className="font-semibold text-gray-700">风险图例</span>
        </div>
        <button
          onClick={onClose}
          className="p-1 hover:bg-gray-100 rounded-full transition-colors"
        >
          <X className="w-4 h-4 text-gray-400" />
        </button>
      </div>

      <div className="p-4 space-y-4">
        {hoveredRiskIndex !== null && hoveredRiskIndex !== undefined && (
          <div className="bg-gray-50 rounded-lg p-3">
            <p className="text-xs text-gray-500 mb-1">当前位置风险指数</p>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div
                  className="w-4 h-4 rounded-full"
                  style={{ backgroundColor: currentRiskColor || '#gray' }}
                />
                <span className="font-semibold text-gray-700">
                  {getLevelLabel(currentRiskLevel || '')}
                </span>
              </div>
              <span
                className="text-2xl font-bold"
                style={{ color: currentRiskColor || '#gray' }}
              >
                {hoveredRiskIndex.toFixed(1)}
              </span>
            </div>
            {mousePosition && (
              <div className="mt-2 flex items-center gap-1 text-xs text-gray-400">
                <MapPin className="w-3 h-3" />
                <span className="font-mono">
                  {mousePosition.lng.toFixed(4)}, {mousePosition.lat.toFixed(4)}
                </span>
              </div>
            )}
          </div>
        )}

        <div>
          <div className="flex justify-between text-xs text-gray-500 mb-2">
            <span>0</span>
            <span>风险指数</span>
            <span>100</span>
          </div>
          <div className="relative">
            <div
              className="h-8 rounded-lg shadow-inner"
              style={{ background: gradientStyle }}
            />
            {indicatorPosition !== null && (
              <div
                className="absolute top-0 w-0.5 h-8 bg-white shadow-md transform -translate-x-1/2 transition-all duration-100"
                style={{ left: `${indicatorPosition}%` }}
              >
                <div
                  className="absolute -top-1 left-1/2 transform -translate-x-1/2 w-2 h-2 rounded-full border-2 border-white shadow-md"
                  style={{ backgroundColor: currentRiskColor || '#fff' }}
                />
              </div>
            )}
          </div>
        </div>

        <div className="space-y-2">
          {legendItems.map((item: RiskLegendItem) => (
            <div key={item.level} className="flex items-center gap-3">
              <div
                className="w-4 h-4 rounded flex-shrink-0"
                style={{ backgroundColor: item.color }}
              />
              <div className="flex-1 flex items-center justify-between">
                <span className="text-sm text-gray-600">{item.label}</span>
                <span className="text-xs text-gray-400">
                  {item.min}
                  {item.max < 100 ? ` - ${item.max}` : '+'}
                </span>
              </div>
            </div>
          ))}
        </div>

        <div className="pt-2 border-t border-gray-100">
          <p className="text-xs text-gray-400">
            风险阈值：低 {'<'} {RISK_THRESHOLDS.low}，中 {RISK_THRESHOLDS.low}-{RISK_THRESHOLDS.medium - 1}，高 {RISK_THRESHOLDS.medium}-{RISK_THRESHOLDS.high - 1}，极高 {'>'}= {RISK_THRESHOLDS.high}
          </p>
        </div>
      </div>
    </div>
  )
}

export default RiskLegend
