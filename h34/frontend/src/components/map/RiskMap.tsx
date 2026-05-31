import { useState, useCallback, useEffect, useRef } from 'react'
import { useQuery } from 'react-query'
import 'mapbox-gl/dist/mapbox-gl.css'
import { Loader2, AlertCircle } from 'lucide-react'
import type mapboxgl from 'mapbox-gl'
import { useMapbox } from '@/hooks/useMapbox'
import { useMapSettings, useFilters } from '@/store'
import { riskGridApi, weatherStationApi, sporeSensorApi } from '@/services/api'
import type { RiskGrid, WeatherStation, SporeSensor } from '@/types'
import {
  type MapLayerState,
  type LayerType,
  type HoveredFeature,
  type PopupData,
} from '@/types/map'
import HeatmapLayer from './HeatmapLayer'
import GridLayer from './GridLayer'
import StationMarkers from './StationMarkers'
import MapControls from './MapControls'
import RiskLegend from './RiskLegend'
import MapPopup from './MapPopup'

const DEFAULT_LAYERS: MapLayerState = {
  heatmap: true,
  grid: false,
  stations: true,
  roads: true,
}

export const RiskMap = () => {
  const { mapCenter, mapZoom, setMapCenter, setMapZoom } = useMapSettings()
  const { selectedCropType, selectedDate } = useFilters()
  const containerRef = useRef<HTMLDivElement>(null)

  const [layers, setLayers] = useState<MapLayerState>(DEFAULT_LAYERS)
  const [showLegend, setShowLegend] = useState(true)
  const [hoveredFeature, setHoveredFeature] = useState<HoveredFeature | null>(null)
  const [popupData, setPopupData] = useState<PopupData | null>(null)
  const [mousePosition, setMousePosition] = useState<{ lat: number; lng: number } | null>(null)

  const {
    data: riskGridData,
    isLoading: riskGridLoading,
    error: riskGridError,
    refetch: refetchRiskGrid,
  } = useQuery<RiskGrid[]>(
    ['riskGrid', selectedCropType, selectedDate],
    async () => {
      const response = await riskGridApi.getHeatmap(selectedCropType, selectedDate)
      return response.data || []
    },
    {
      enabled: true,
      refetchInterval: 5 * 60 * 1000,
      staleTime: 1 * 60 * 1000,
    }
  )

  const {
    data: weatherStations,
    isLoading: stationsLoading,
  } = useQuery<WeatherStation[]>(
    ['weatherStations'],
    async () => {
      const response = await weatherStationApi.list({ page_size: 100 })
      return response.data?.items || []
    },
    {
      staleTime: 30 * 60 * 1000,
    }
  )

  const {
    data: sporeSensors,
    isLoading: sensorsLoading,
  } = useQuery<SporeSensor[]>(
    ['sporeSensors', selectedCropType],
    async () => {
      const response = await sporeSensorApi.list({ page_size: 100, crop_type: selectedCropType })
      return response.data?.items || []
    },
    {
      staleTime: 30 * 60 * 1000,
    }
  )

  const handleMapMove = useCallback(
    (map: mapboxgl.Map) => {
      const center = map.getCenter()
      const zoom = map.getZoom()
      setMapCenter([center.lng, center.lat])
      setMapZoom(zoom)
    },
    [setMapCenter, setMapZoom]
  )

  const handleMapClick = useCallback(
    (e: { lngLat: { lng: number; lat: number }; features?: Array<{ id: string | number; properties: Record<string, any>; geometry: any }> }) => {
      if (!e.features || e.features.length === 0) {
        setPopupData(null)
        return
      }

      const feature = e.features[0]
      const properties = feature.properties || {}

      if (properties.type === 'station') {
        const station = weatherStations?.find((s) => s.id === properties.id)
        if (station) {
          setPopupData({
            type: 'station',
            coordinates: [e.lngLat.lng, e.lngLat.lat],
            data: station,
          })
        }
      } else if (properties.type === 'sensor') {
        const sensor = sporeSensors?.find((s) => s.id === properties.id)
        if (sensor) {
          setPopupData({
            type: 'sensor',
            coordinates: [e.lngLat.lng, e.lngLat.lat],
            data: sensor,
          })
        }
      } else if (properties.risk_index !== undefined) {
        const riskGrid = riskGridData?.find((rg) => rg.id === properties.id)
        setPopupData({
          type: 'grid',
          coordinates: [e.lngLat.lng, e.lngLat.lat],
          data: riskGrid || (properties as any),
          riskIndex: properties.risk_index,
        })
      }
    },
    [weatherStations, sporeSensors, riskGridData]
  )

  const handleGridClick = useCallback(
    (feature: HoveredFeature, coordinates: [number, number]) => {
      const riskGrid = riskGridData?.find((rg) => rg.id === feature.id)
      setPopupData({
        type: 'grid',
        coordinates,
        data: riskGrid || (feature.properties as any),
        riskIndex: feature.properties.risk_index,
      })
    },
    [riskGridData]
  )

  const handleStationClick = useCallback(
    (feature: HoveredFeature, coordinates: [number, number]) => {
      if (feature.properties.type === 'station') {
        const station = weatherStations?.find((s) => s.id === feature.properties.id)
        if (station) {
          setPopupData({
            type: 'station',
            coordinates,
            data: station,
          })
        }
      } else if (feature.properties.type === 'sensor') {
        const sensor = sporeSensors?.find((s) => s.id === feature.properties.id)
        if (sensor) {
          setPopupData({
            type: 'sensor',
            coordinates,
            data: sensor,
          })
        }
      }
    },
    [weatherStations, sporeSensors]
  )

  const handleHover = useCallback(
    (feature: HoveredFeature | null) => {
      setHoveredFeature(feature)
    },
    []
  )

  const handleLayerToggle = useCallback((layer: LayerType) => {
    setLayers((prev) => ({
      ...prev,
      [layer]: !prev[layer],
    }))
  }, [])

  const handleMouseMove = useCallback((e: { lngLat: { lng: number; lat: number } }) => {
    setMousePosition({
      lat: e.lngLat.lat,
      lng: e.lngLat.lng,
    })
  }, [])

  const handleMouseLeave = useCallback(() => {
    setMousePosition(null)
  }, [])

  const { map, mapState, containerRef: mapContainerRef } = useMapbox({
    containerId: 'risk-map',
    center: mapCenter,
    zoom: mapZoom,
    onMove: handleMapMove,
    onZoom: handleMapMove,
    onClick: handleMapClick,
    onMouseMove: handleMouseMove,
    onMouseLeave: handleMouseLeave,
  })

  useEffect(() => {
    if (map && layers.roads) {
      if (map.getLayer('road-simple')) {
        map.setLayoutProperty('road-simple', 'visibility', 'visible')
      }
      if (map.getLayer('road-primary')) {
        map.setLayoutProperty('road-primary', 'visibility', 'visible')
      }
      if (map.getLayer('road-secondary')) {
        map.setLayoutProperty('road-secondary', 'visibility', 'visible')
      }
      if (map.getLayer('road-tertiary')) {
        map.setLayoutProperty('road-tertiary', 'visibility', 'visible')
      }
    } else if (map && !layers.roads) {
      if (map.getLayer('road-simple')) {
        map.setLayoutProperty('road-simple', 'visibility', 'none')
      }
      if (map.getLayer('road-primary')) {
        map.setLayoutProperty('road-primary', 'visibility', 'none')
      }
      if (map.getLayer('road-secondary')) {
        map.setLayoutProperty('road-secondary', 'visibility', 'none')
      }
      if (map.getLayer('road-tertiary')) {
        map.setLayoutProperty('road-tertiary', 'visibility', 'none')
      }
    }
  }, [map, layers.roads, mapState.isStyleLoaded])

  const isLoading = riskGridLoading || stationsLoading || sensorsLoading
  const hasError = riskGridError

  return (
    <div className="relative w-full h-full" ref={containerRef}>
      <div
        ref={mapContainerRef}
        id="risk-map"
        className="w-full h-full"
        style={{ minHeight: '600px' }}
      />

      {isLoading && (
        <div className="absolute inset-0 bg-white/80 flex items-center justify-center z-20">
          <div className="flex flex-col items-center gap-2">
            <Loader2 className="w-8 h-8 text-green-500 animate-spin" />
            <p className="text-gray-600 font-medium">加载地图数据中...</p>
          </div>
        </div>
      )}

      {hasError && (
        <div className="absolute top-4 right-4 z-20 bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
          <div className="flex-1">
            <p className="text-sm font-medium text-red-800">数据加载失败</p>
            <p className="text-xs text-red-600">请稍后重试</p>
          </div>
          <button
            onClick={() => refetchRiskGrid()}
            className="px-3 py-1 bg-red-500 text-white text-xs rounded hover:bg-red-600 transition-colors"
          >
            重试
          </button>
        </div>
      )}

      {mapState.error && (
        <div className="absolute inset-0 bg-gray-100 flex items-center justify-center z-20">
          <div className="text-center p-8">
            <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-gray-800 mb-2">地图加载失败</h3>
            <p className="text-gray-600 mb-4">{mapState.error.message}</p>
            <p className="text-sm text-gray-500">
              请检查 Mapbox Access Token 是否已正确配置
            </p>
          </div>
        </div>
      )}

      <MapControls
        map={map}
        layers={layers}
        onLayerToggle={handleLayerToggle}
        showLegend={showLegend}
        onLegendToggle={() => setShowLegend(!showLegend)}
      />

      <RiskLegend
        visible={showLegend}
        onClose={() => setShowLegend(false)}
        hoveredRiskIndex={hoveredFeature?.properties?.risk_index}
        mousePosition={mousePosition}
      />

      <MapPopup
        map={map}
        popupData={popupData}
        onClose={() => setPopupData(null)}
      />

      {map && mapState.isLoaded && mapState.isStyleLoaded && (
        <>
          <HeatmapLayer
            map={map}
            isLoaded={mapState.isLoaded}
            isStyleLoaded={mapState.isStyleLoaded}
            data={riskGridData || []}
            visible={layers.heatmap}
          />

          <GridLayer
            map={map}
            isLoaded={mapState.isLoaded}
            isStyleLoaded={mapState.isStyleLoaded}
            data={riskGridData || []}
            visible={layers.grid}
            beforeId="risk-heatmap-layer"
            onHover={handleHover}
            onClick={handleGridClick}
          />

          <StationMarkers
            map={map}
            isLoaded={mapState.isLoaded}
            isStyleLoaded={mapState.isStyleLoaded}
            weatherStations={weatherStations || []}
            sporeSensors={sporeSensors || []}
            visible={layers.stations}
            beforeId="risk-grid-layer"
            onHover={handleHover}
            onClick={handleStationClick}
          />
        </>
      )}
    </div>
  )
}

export default RiskMap
