import { useState, useMemo, useCallback } from 'react'
import {
  Layers,
  ChevronDown,
  ChevronUp,
  Plus,
  Minus,
  Maximize,
  Calendar,
  Sprout,
  Thermometer,
  MapPin,
  Route,
  Flame,
  Grid3X3,
} from 'lucide-react'
import { format } from 'date-fns'
import { zhCN } from 'date-fns/locale'
import type { CropType } from '@/types'
import {
  generateDateOptions,
  CROP_TYPE_LABELS,
  type MapLayerState,
  type LayerType,
} from '@/types/map'
import { useFilters } from '@/store'

interface MapControlsProps {
  map: mapboxgl.Map | null
  layers: MapLayerState
  onLayerToggle: (layer: LayerType) => void
  showLegend: boolean
  onLegendToggle: () => void
}

const CROP_TYPES: CropType[] = ['wheat', 'potato', 'corn', 'rice']

const CROP_ICONS: Record<CropType, string> = {
  wheat: '🌾',
  potato: '🥔',
  corn: '🌽',
  rice: '🍚',
}

export const MapControls = ({
  map,
  layers,
  onLayerToggle,
  showLegend,
  onLegendToggle,
}: MapControlsProps) => {
  const { selectedCropType, setSelectedCropType, setSelectedDate } = useFilters()
  const [expanded, setExpanded] = useState(true)
  const [dateSliderIndex, setDateSliderIndex] = useState(0)

  const dateOptions = useMemo(() => generateDateOptions(7), [])

  const handleZoomIn = useCallback(() => {
    if (!map) return
    map.zoomIn()
  }, [map])

  const handleZoomOut = useCallback(() => {
    if (!map) return
    map.zoomOut()
  }, [map])

  const handleFullscreen = useCallback(() => {
    if (!map) return
    const container = map.getContainer()
    if (document.fullscreenElement) {
      document.exitFullscreen()
    } else {
      container.requestFullscreen()
    }
  }, [map])

  const handleCropChange = useCallback(
    (crop: CropType) => {
      setSelectedCropType(crop)
    },
    [setSelectedCropType]
  )

  const handleDateChange = useCallback(
    (index: number) => {
      setDateSliderIndex(index)
      setSelectedDate(dateOptions[index].date)
    },
    [dateOptions, setSelectedDate]
  )

  const layerButtons: Array<{
    key: LayerType
    label: string
    icon: React.ReactNode
  }> = [
    { key: 'heatmap', label: '热图', icon: <Flame className="w-4 h-4" /> },
    { key: 'grid', label: '格点', icon: <Grid3X3 className="w-4 h-4" /> },
    { key: 'stations', label: '站点', icon: <MapPin className="w-4 h-4" /> },
    { key: 'roads', label: '道路', icon: <Route className="w-4 h-4" /> },
  ]

  return (
    <div className="absolute top-4 left-4 z-10 space-y-3">
      <div className="bg-white rounded-xl shadow-lg overflow-hidden">
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors"
        >
          <div className="flex items-center gap-2">
            <Layers className="w-5 h-5 text-gray-600" />
            <span className="font-medium text-gray-700">地图控制</span>
          </div>
          {expanded ? (
            <ChevronUp className="w-5 h-5 text-gray-400" />
          ) : (
            <ChevronDown className="w-5 h-5 text-gray-400" />
          )}
        </button>

        {expanded && (
          <div className="px-4 pb-4 space-y-4">
            <div>
              <label className="flex items-center gap-2 text-sm font-medium text-gray-600 mb-2">
                <Sprout className="w-4 h-4" />
                作物类型
              </label>
              <div className="grid grid-cols-2 gap-2">
                {CROP_TYPES.map((crop) => (
                  <button
                    key={crop}
                    onClick={() => handleCropChange(crop)}
                    className={`px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                      selectedCropType === crop
                        ? 'bg-green-500 text-white shadow-md'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    }`}
                  >
                    <span className="mr-1">{CROP_ICONS[crop]}</span>
                    {CROP_TYPE_LABELS[crop]}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="flex items-center gap-2 text-sm font-medium text-gray-600 mb-2">
                <Calendar className="w-4 h-4" />
                预测日期
              </label>
              <div className="bg-gray-50 rounded-lg p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-gray-500">
                    {dateOptions[dateSliderIndex]?.isForecast ? '预测' : '今天'}
                  </span>
                  <span className="text-sm font-medium text-gray-700">
                    {format(new Date(dateOptions[dateSliderIndex]?.date || new Date()), 'MM月dd日 EEEE', { locale: zhCN })}
                  </span>
                </div>
                <input
                  type="range"
                  min="0"
                  max={dateOptions.length - 1}
                  value={dateSliderIndex}
                  onChange={(e) => handleDateChange(parseInt(e.target.value))}
                  className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-green-500"
                />
                <div className="flex justify-between mt-1">
                  {dateOptions.map((option, index) => (
                    <button
                      key={option.date}
                      onClick={() => handleDateChange(index)}
                      className={`text-xs px-1 py-0.5 rounded transition-colors ${
                        index === dateSliderIndex
                          ? 'bg-green-500 text-white'
                          : 'text-gray-500 hover:text-gray-700'
                      }`}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div>
              <label className="flex items-center gap-2 text-sm font-medium text-gray-600 mb-2">
                <Layers className="w-4 h-4" />
                图层显示
              </label>
              <div className="grid grid-cols-2 gap-2">
                {layerButtons.map(({ key, label, icon }) => (
                  <button
                    key={key}
                    onClick={() => onLayerToggle(key)}
                    className={`px-3 py-2 rounded-lg text-sm font-medium transition-all flex items-center justify-center gap-1.5 ${
                      layers[key]
                        ? 'bg-blue-500 text-white shadow-md'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {icon}
                    {label}
                  </button>
                ))}
              </div>
            </div>

            <button
              onClick={onLegendToggle}
              className={`w-full px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center justify-center gap-2 ${
                showLegend
                  ? 'bg-purple-500 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              <Thermometer className="w-4 h-4" />
              {showLegend ? '隐藏图例' : '显示图例'}
            </button>
          </div>
        )}
      </div>

      <div className="bg-white rounded-xl shadow-lg p-2 flex flex-col gap-1">
        <button
          onClick={handleZoomIn}
          className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          title="放大"
        >
          <Plus className="w-5 h-5 text-gray-600" />
        </button>
        <div className="h-px bg-gray-200" />
        <button
          onClick={handleZoomOut}
          className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          title="缩小"
        >
          <Minus className="w-5 h-5 text-gray-600" />
        </button>
        <div className="h-px bg-gray-200" />
        <button
          onClick={handleFullscreen}
          className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          title="全屏"
        >
          <Maximize className="w-5 h-5 text-gray-600" />
        </button>
      </div>
    </div>
  )
}

export default MapControls
