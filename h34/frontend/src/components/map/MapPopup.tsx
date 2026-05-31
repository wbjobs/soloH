import { useEffect, useRef } from 'react'
import type mapboxgl from 'mapbox-gl'
import { X, Cloud, Wind, Thermometer, Droplets, AlertTriangle } from 'lucide-react'
import { format } from 'date-fns'
import { zhCN } from 'date-fns/locale'
import { getRiskColor, getRiskLevel, CROP_TYPE_LABELS } from '@/types/map'
import type { PopupData } from '@/types/map'

interface MapPopupProps {
  map: mapboxgl.Map | null
  popupData: PopupData | null
  onClose: () => void
}

export const MapPopup = ({ map, popupData, onClose }: MapPopupProps) => {
  const popupRef = useRef<mapboxgl.Popup | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!map || !popupData) {
      if (popupRef.current) {
        popupRef.current.remove()
        popupRef.current = null
      }
      return
    }

    if (popupRef.current) {
      popupRef.current.remove()
    }

    const popup = new mapboxgl.Popup({
      closeButton: false,
      closeOnClick: false,
      anchor: 'bottom',
      offset: [0, -10],
      maxWidth: '320px',
    })

    popup.setLngLat(popupData.coordinates).addTo(map)

    const popupContent = document.createElement('div')
    popupContent.className = 'mapbox-popup-content'
    if (containerRef.current) {
      popupContent.appendChild(containerRef.current)
    }
    popup.setDOMContent(popupContent)

    popupRef.current = popup

    return () => {
      if (popupRef.current) {
        popupRef.current.remove()
        popupRef.current = null
      }
    }
  }, [map, popupData?.coordinates[0], popupData?.coordinates[1]])

  if (!popupData) return null

  const renderGridPopup = () => {
    const data = popupData.data as any
    const riskIndex = popupData.riskIndex ?? data.risk_index ?? 0
    const riskLevel = getRiskLevel(riskIndex)
    const riskColor = getRiskColor(riskIndex)

    return (
      <div className="p-4 min-w-[280px]">
        <div className="flex items-start justify-between mb-3">
          <div>
            <h3 className="font-semibold text-gray-900 text-lg">格点风险详情</h3>
            <p className="text-sm text-gray-500">
              {data.forecast_date && format(new Date(data.forecast_date), 'yyyy年MM月dd日', { locale: zhCN })}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-100 rounded-full transition-colors"
          >
            <X className="w-4 h-4 text-gray-400" />
          </button>
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5" style={{ color: riskColor }} />
              <span className="text-gray-700">风险指数</span>
            </div>
            <div className="text-right">
              <span className="text-2xl font-bold" style={{ color: riskColor }}>
                {riskIndex.toFixed(1)}
              </span>
              <span className="text-gray-500 text-sm">/100</span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div className="p-2 bg-white border border-gray-200 rounded-lg">
              <p className="text-xs text-gray-500 mb-1">风险等级</p>
              <p className="font-semibold" style={{ color: riskColor }}>
                {riskLevel === 'low' && '低风险'}
                {riskLevel === 'medium' && '中风险'}
                {riskLevel === 'high' && '高风险'}
                {riskLevel === 'extreme' && '极高风险'}
              </p>
            </div>
            <div className="p-2 bg-white border border-gray-200 rounded-lg">
              <p className="text-xs text-gray-500 mb-1">作物类型</p>
              <p className="font-semibold text-gray-700">
                {data.crop_type && CROP_TYPE_LABELS[data.crop_type]}
              </p>
            </div>
          </div>

          {data.infection_probability !== undefined && data.infection_probability !== null && (
            <div className="p-2 bg-white border border-gray-200 rounded-lg">
              <p className="text-xs text-gray-500 mb-1">感染概率</p>
              <p className="font-semibold text-gray-700">
                {(data.infection_probability * 100).toFixed(1)}%
              </p>
            </div>
          )}

          <div className="p-2 bg-white border border-gray-200 rounded-lg">
            <p className="text-xs text-gray-500 mb-1">位置坐标</p>
            <p className="font-mono text-sm text-gray-700">
              {data.lon?.toFixed(4)}, {data.lat?.toFixed(4)}
            </p>
          </div>

          {data.model_version && (
            <p className="text-xs text-gray-400">
              模型版本: {data.model_version}
            </p>
          )}
        </div>
      </div>
    )
  }

  const renderStationPopup = () => {
    const data = popupData.data as any

    return (
      <div className="p-4 min-w-[260px]">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className="w-10 h-10 bg-blue-500 rounded-full flex items-center justify-center">
              <Cloud className="w-5 h-5 text-white" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">{data.name}</h3>
              <p className="text-xs text-gray-500">气象站 · {data.code}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-100 rounded-full transition-colors"
          >
            <X className="w-4 h-4 text-gray-400" />
          </button>
        </div>

        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm">
            <Thermometer className="w-4 h-4 text-orange-500" />
            <span className="text-gray-600">温度:</span>
            <span className="font-medium text-gray-900">--°C</span>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <Droplets className="w-4 h-4 text-blue-500" />
            <span className="text-gray-600">湿度:</span>
            <span className="font-medium text-gray-900">--%</span>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <Wind className="w-4 h-4 text-cyan-500" />
            <span className="text-gray-600">风速:</span>
            <span className="font-medium text-gray-900">-- m/s</span>
          </div>
          {data.elevation && (
            <div className="pt-2 border-t border-gray-100">
              <p className="text-xs text-gray-500">
                海拔: {data.elevation}m · 状态: {data.is_active ? '在线' : '离线'}
              </p>
            </div>
          )}
        </div>
      </div>
    )
  }

  const renderSensorPopup = () => {
    const data = popupData.data as any

    return (
      <div className="p-4 min-w-[260px]">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className="w-10 h-10 bg-purple-500 rounded-full flex items-center justify-center">
              <Wind className="w-5 h-5 text-white" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">{data.name}</h3>
              <p className="text-xs text-gray-500">孢子传感器 · {data.code}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-100 rounded-full transition-colors"
          >
            <X className="w-4 h-4 text-gray-400" />
          </button>
        </div>

        <div className="space-y-2">
          <div className="p-2 bg-purple-50 rounded-lg">
            <p className="text-xs text-purple-600 mb-1">孢子类型</p>
            <p className="font-semibold text-purple-900">{data.spore_type}</p>
          </div>
          <div className="p-2 bg-gray-50 rounded-lg">
            <p className="text-xs text-gray-500 mb-1">监测作物</p>
            <p className="font-semibold text-gray-700">
              {data.crop_type && CROP_TYPE_LABELS[data.crop_type]}
            </p>
          </div>
          <div className="pt-2 border-t border-gray-100">
            <p className="text-xs text-gray-500">
              状态: {data.is_active ? '在线' : '离线'}
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div ref={containerRef} className="bg-white rounded-lg shadow-xl overflow-hidden">
      {popupData.type === 'grid' && renderGridPopup()}
      {popupData.type === 'station' && renderStationPopup()}
      {popupData.type === 'sensor' && renderSensorPopup()}
    </div>
  )
}

export default MapPopup
