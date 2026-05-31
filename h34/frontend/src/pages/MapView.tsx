import { useState, useMemo } from 'react'
import { useQuery } from 'react-query'
import {
  X,
  Calendar,
  Sprout,
  Thermometer,
  Droplets,
  Wind,
  Sun,
  CloudRain,
  AlertTriangle,
  MapPin,
} from 'lucide-react'
import { format } from 'date-fns'
import { zhCN } from 'date-fns/locale'
import RiskMap from '@/components/map/RiskMap'
import { useFilters, useUI } from '@/store'
import { forecastApi } from '@/services/api'
import {
  generateDateOptions,
  getRiskLevel,
  getRiskColor,
} from '@/types/map'
import type { CropType, RiskGrid } from '@/types'

const CROP_OPTIONS: { value: CropType; label: string; color: string }[] = [
  { value: 'wheat', label: '小麦', color: 'bg-amber-500' },
  { value: 'corn', label: '玉米', color: 'bg-green-500' },
  { value: 'potato', label: '马铃薯', color: 'bg-purple-500' },
  { value: 'rice', label: '水稻', color: 'bg-blue-500' },
]

export const MapView = () => {
  const { selectedCropType, selectedDate, setSelectedCropType, setSelectedDate } = useFilters()
  const { sidebarOpen } = useUI()
  const [selectedGrid, setSelectedGrid] = useState<RiskGrid | null>(null)
  const [timelineIndex, setTimelineIndex] = useState(0)

  const dateOptions = useMemo(() => generateDateOptions(7), [])

  const { data: forecastData } = useQuery(
    ['forecast', selectedGrid?.grid_id],
    async () => {
      if (!selectedGrid?.grid_id) return []
      const endDate = new Date(Date.now() + 7 * 86400000).toISOString().split('T')[0]
      const response = await forecastApi.getByGrid(selectedGrid.grid_id, selectedDate, endDate)
      return response.data || []
    },
    { enabled: !!selectedGrid?.grid_id }
  )

  const handleDateChange = (index: number) => {
    setTimelineIndex(index)
    setSelectedDate(dateOptions[index].date)
  }

  const handleCropChange = (crop: CropType) => {
    setSelectedCropType(crop)
    setSelectedGrid(null)
  }

  const latestForecast = forecastData?.[0]

  return (
    <div className="relative w-full h-[calc(100vh-64px)]">
      <div className="absolute top-4 left-4 right-4 z-10 flex flex-col gap-3">
        <div className="flex items-center gap-3">
          <div className="bg-white rounded-lg shadow-lg p-2 flex gap-1">
            {CROP_OPTIONS.map((crop) => (
              <button
                key={crop.value}
                onClick={() => handleCropChange(crop.value)}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-all flex items-center gap-2 ${
                  selectedCropType === crop.value
                    ? `${crop.color} text-white shadow-md`
                    : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                <Sprout className="w-4 h-4" />
                {crop.label}
              </button>
            ))}
          </div>

          <div className="flex-1" />

          <div className="bg-white rounded-lg shadow-lg px-4 py-2 flex items-center gap-2">
            <Calendar className="w-4 h-4 text-gray-500" />
            <span className="text-sm text-gray-600">
              {format(new Date(selectedDate), 'yyyy年MM月dd日', { locale: zhCN })}
            </span>
            {dateOptions[timelineIndex]?.isForecast && (
              <span className="px-2 py-0.5 bg-blue-100 text-blue-600 text-xs rounded">预报</span>
            )}
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-lg p-3">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs text-gray-500">时间轴</span>
            <div className="flex-1 h-px bg-gray-200" />
            <span className="text-xs text-blue-500 font-medium">点击查看历史/预报</span>
          </div>
          <div className="relative">
            <div className="absolute top-1/2 left-0 right-0 h-1 bg-gray-200 -translate-y-1/2 rounded-full" />
            <div className="relative flex justify-between px-1">
              {dateOptions.map((option, index) => (
                <button
                  key={option.date}
                  onClick={() => handleDateChange(index)}
                  className="relative z-10 flex flex-col items-center group"
                >
                  <div
                    className={`w-5 h-5 rounded-full border-2 transition-all ${
                      index === timelineIndex
                        ? 'bg-green-500 border-green-500 scale-125'
                        : option.isForecast
                        ? 'bg-white border-blue-400 hover:border-blue-500'
                        : 'bg-white border-gray-400 hover:border-gray-600'
                    }`}
                  />
                  <span
                    className={`mt-2 text-xs whitespace-nowrap ${
                      index === timelineIndex ? 'text-green-600 font-medium' : 'text-gray-500'
                    }`}
                  >
                    {option.label}
                  </span>
                  {option.isForecast && (
                    <span className="text-[10px] text-blue-400">预报</span>
                  )}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      <RiskMap />

      {sidebarOpen && selectedGrid && (
        <div className="absolute top-4 right-4 bottom-4 w-80 bg-white rounded-xl shadow-xl z-20 overflow-hidden flex flex-col">
          <div className="flex items-center justify-between p-4 border-b border-gray-100">
            <h3 className="font-semibold text-gray-900">格点详情</h3>
            <button
              onClick={() => setSelectedGrid(null)}
              className="p-1 hover:bg-gray-100 rounded transition-colors"
            >
              <X className="w-5 h-5 text-gray-500" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <MapPin className="w-4 h-4 text-gray-400" />
                <span className="text-sm text-gray-600">
                  网格 {selectedGrid.grid_id}
                </span>
              </div>
              <div
                className="px-3 py-1 rounded-full text-white text-sm font-medium"
                style={{ backgroundColor: getRiskColor(selectedGrid.risk_index) }}
              >
                {selectedGrid.risk_index.toFixed(1)}
              </div>
            </div>

            <div className="p-4 bg-gray-50 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-gray-600">风险等级</span>
                <span
                  className="font-medium"
                  style={{ color: getRiskColor(selectedGrid.risk_index) }}
                >
                  {getRiskLevel(selectedGrid.risk_index) === 'low' && '低风险'}
                  {getRiskLevel(selectedGrid.risk_index) === 'medium' && '中风险'}
                  {getRiskLevel(selectedGrid.risk_index) === 'high' && '高风险'}
                  {getRiskLevel(selectedGrid.risk_index) === 'extreme' && '极高风险'}
                </span>
              </div>
              <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${selectedGrid.risk_index}%`,
                    backgroundColor: getRiskColor(selectedGrid.risk_index),
                  }}
                />
              </div>
            </div>

            {selectedGrid.infection_probability !== undefined && (
              <div className="p-4 bg-orange-50 rounded-lg">
                <div className="flex items-center gap-2 mb-1">
                  <AlertTriangle className="w-4 h-4 text-orange-500" />
                  <span className="text-sm font-medium text-orange-800">感染概率</span>
                </div>
                <p className="text-2xl font-bold text-orange-600">
                  {selectedGrid.infection_probability.toFixed(1)}%
                </p>
              </div>
            )}

            {latestForecast && (
              <div>
                <h4 className="text-sm font-medium text-gray-700 mb-3">天气预报</h4>
                <div className="grid grid-cols-2 gap-3">
                  <div className="p-3 bg-blue-50 rounded-lg">
                    <div className="flex items-center gap-1.5 text-blue-600 mb-1">
                      <Thermometer className="w-4 h-4" />
                      <span className="text-xs">温度</span>
                    </div>
                    <p className="text-lg font-semibold text-blue-800">
                      {latestForecast.temperature?.toFixed(1) || '--'}°C
                    </p>
                  </div>
                  <div className="p-3 bg-cyan-50 rounded-lg">
                    <div className="flex items-center gap-1.5 text-cyan-600 mb-1">
                      <Droplets className="w-4 h-4" />
                      <span className="text-xs">湿度</span>
                    </div>
                    <p className="text-lg font-semibold text-cyan-800">
                      {latestForecast.humidity?.toFixed(0) || '--'}%
                    </p>
                  </div>
                  <div className="p-3 bg-sky-50 rounded-lg">
                    <div className="flex items-center gap-1.5 text-sky-600 mb-1">
                      <Wind className="w-4 h-4" />
                      <span className="text-xs">风速</span>
                    </div>
                    <p className="text-lg font-semibold text-sky-800">
                      {latestForecast.wind_speed?.toFixed(1) || '--'} m/s
                    </p>
                  </div>
                  <div className="p-3 bg-indigo-50 rounded-lg">
                    <div className="flex items-center gap-1.5 text-indigo-600 mb-1">
                      <CloudRain className="w-4 h-4" />
                      <span className="text-xs">降雨</span>
                    </div>
                    <p className="text-lg font-semibold text-indigo-800">
                      {latestForecast.rainfall?.toFixed(1) || '--'} mm
                    </p>
                  </div>
                </div>
              </div>
            )}

            {forecastData && forecastData.length > 1 && (
              <div>
                <h4 className="text-sm font-medium text-gray-700 mb-3">未来趋势</h4>
                <div className="space-y-2">
                  {forecastData.slice(1, 5).map((item, index) => (
                    <div
                      key={item.id || index}
                      className="flex items-center justify-between p-2 bg-gray-50 rounded-lg"
                    >
                      <div className="flex items-center gap-2">
                        <Sun className="w-4 h-4 text-yellow-500" />
                        <span className="text-sm text-gray-600">
                          {format(new Date(item.forecast_date), 'MM-dd')}
                        </span>
                      </div>
                      <span
                        className="text-sm font-medium"
                        style={{ color: getRiskColor(item.temperature || 50) }}
                      >
                        {item.temperature?.toFixed(1)}°C
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="p-4 border-t border-gray-100">
            <button className="w-full py-2.5 bg-green-500 hover:bg-green-600 text-white rounded-lg font-medium transition-colors">
              查看历史数据
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default MapView
