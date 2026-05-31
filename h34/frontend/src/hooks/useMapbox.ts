import { useEffect, useRef, useState, useCallback } from 'react'
import mapboxgl from 'mapbox-gl'
import type { MapboxConfig, MapState, MapMouseEvent } from '@/types/map'

type QueryOptions = {
  layers?: string[]
  filter?: any[]
}

const MAPBOX_ACCESS_TOKEN = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN

const DEFAULT_CONFIG: Partial<MapboxConfig> = {
  style: 'mapbox://styles/mapbox/light-v11',
  minZoom: 3,
  maxZoom: 18,
  pitch: 0,
  bearing: 0,
}

interface UseMapboxOptions extends Partial<MapboxConfig> {
  containerId: string
  onLoad?: (map: mapboxgl.Map) => void
  onStyleLoad?: (map: mapboxgl.Map) => void
  onMove?: (map: mapboxgl.Map) => void
  onZoom?: (map: mapboxgl.Map) => void
  onClick?: (e: MapMouseEvent, map: mapboxgl.Map) => void
  onMouseMove?: (e: MapMouseEvent, map: mapboxgl.Map) => void
  onMouseLeave?: (map: mapboxgl.Map) => void
}

interface UseMapboxReturn {
  map: mapboxgl.Map | null
  mapState: MapState
  containerRef: React.RefObject<HTMLDivElement>
  flyTo: (center: [number, number], zoom?: number, duration?: number) => void
  fitBounds: (bounds: [[number, number], [number, number]], padding?: number) => void
  setLayerVisibility: (layerId: string, visible: boolean) => void
  getLayerVisibility: (layerId: string) => boolean
  addSource: (sourceId: string, source: mapboxgl.AnySourceData) => void
  removeSource: (sourceId: string) => void
  addLayer: (layer: mapboxgl.AnyLayer, beforeId?: string) => void
  removeLayer: (layerId: string) => void
  setSourceData: (sourceId: string, data: any) => void
  queryRenderedFeatures: (point: [number, number], options?: QueryOptions) => mapboxgl.MapboxGeoJSONFeature[]
}

export const useMapbox = (options: UseMapboxOptions): UseMapboxReturn => {
  const {
    containerId,
    center = [116.4074, 39.9042],
    zoom = 10,
    style = DEFAULT_CONFIG.style,
    minZoom = DEFAULT_CONFIG.minZoom!,
    maxZoom = DEFAULT_CONFIG.maxZoom!,
    pitch = DEFAULT_CONFIG.pitch!,
    bearing = DEFAULT_CONFIG.bearing!,
    onLoad,
    onStyleLoad,
    onMove,
    onZoom,
    onClick,
    onMouseMove,
    onMouseLeave,
  } = options

  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<mapboxgl.Map | null>(null)
  const [mapState, setMapState] = useState<MapState>({
    isLoaded: false,
    isStyleLoaded: false,
    error: null,
  })

  useEffect(() => {
    if (!MAPBOX_ACCESS_TOKEN) {
      setMapState(prev => ({
        ...prev,
        error: new Error('Mapbox access token is not configured'),
      }))
      return
    }

    mapboxgl.accessToken = MAPBOX_ACCESS_TOKEN

    if (!containerRef.current) return

    const map = new mapboxgl.Map({
      container: containerRef.current,
      style,
      center,
      zoom,
      minZoom,
      maxZoom,
      pitch,
      bearing,
      attributionControl: true,
      logoPosition: 'bottom-left',
    })

    mapRef.current = map

    map.addControl(new mapboxgl.NavigationControl({ showCompass: false }), 'top-right')
    map.addControl(new mapboxgl.ScaleControl({ unit: 'metric' }), 'bottom-left')

    const handleLoad = () => {
      setMapState(prev => ({ ...prev, isLoaded: true }))
      onLoad?.(map)
    }

    const handleStyleLoad = () => {
      setMapState(prev => ({ ...prev, isStyleLoaded: true }))
      onStyleLoad?.(map)
    }

    const handleMove = () => {
      onMove?.(map)
    }

    const handleZoom = () => {
      onZoom?.(map)
    }

    const handleClick = (e: mapboxgl.MapMouseEvent) => {
      const features = map.queryRenderedFeatures(e.point)
      onClick?.(
        {
          lngLat: { lng: e.lngLat.lng, lat: e.lngLat.lat },
          point: { x: e.point.x, y: e.point.y },
          features: features.map(f => ({
            id: f.id!,
            properties: (f.properties || {}) as Record<string, any>,
            geometry: f.geometry,
          })),
        },
        map
      )
    }

    const handleMouseMove = (e: mapboxgl.MapMouseEvent) => {
      const features = map.queryRenderedFeatures(e.point)
      onMouseMove?.(
        {
          lngLat: { lng: e.lngLat.lng, lat: e.lngLat.lat },
          point: { x: e.point.x, y: e.point.y },
          features: features.map(f => ({
            id: f.id!,
            properties: (f.properties || {}) as Record<string, any>,
            geometry: f.geometry,
          })),
        },
        map
      )
    }

    const handleMouseLeave = () => {
      onMouseLeave?.(map)
    }

    const handleError = (e: mapboxgl.ErrorEvent) => {
      const error = e.error instanceof Error ? e.error : new Error(String(e.error.message || 'Unknown error'))
      setMapState(prev => ({ ...prev, error }))
    }

    map.on('load', handleLoad)
    map.on('styledata', handleStyleLoad)
    map.on('move', handleMove)
    map.on('zoom', handleZoom)
    map.on('click', handleClick)
    map.on('mousemove', handleMouseMove)
    map.on('mouseleave', handleMouseLeave)
    map.on('error', handleError)

    return () => {
      map.off('load', handleLoad)
      map.off('styledata', handleStyleLoad)
      map.off('move', handleMove)
      map.off('zoom', handleZoom)
      map.off('click', handleClick)
      map.off('mousemove', handleMouseMove)
      map.off('mouseleave', handleMouseLeave)
      map.off('error', handleError)
      map.remove()
      mapRef.current = null
    }
  }, [containerId, style, minZoom, maxZoom, pitch, bearing])

  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    const handleCenterChange = () => {
      const newCenter = map.getCenter()
      if (newCenter.lng !== center[0] || newCenter.lat !== center[1]) {
        map.setCenter(center)
      }
    }

    const handleZoomChange = () => {
      if (map.getZoom() !== zoom) {
        map.setZoom(zoom)
      }
    }

    map.off('move', handleCenterChange)
    map.off('zoom', handleZoomChange)
  }, [center, zoom])

  const flyTo = useCallback((center: [number, number], zoom: number = 12, duration: number = 1000) => {
    const map = mapRef.current
    if (!map) return
    map.flyTo({
      center,
      zoom,
      duration,
      essential: true,
    })
  }, [])

  const fitBounds = useCallback((bounds: [[number, number], [number, number]], padding: number = 50) => {
    const map = mapRef.current
    if (!map) return
    map.fitBounds(bounds, {
      padding,
      duration: 1000,
    })
  }, [])

  const setLayerVisibility = useCallback((layerId: string, visible: boolean) => {
    const map = mapRef.current
    if (!map || !map.getLayer(layerId)) return
    map.setLayoutProperty(layerId, 'visibility', visible ? 'visible' : 'none')
  }, [])

  const getLayerVisibility = useCallback((layerId: string): boolean => {
    const map = mapRef.current
    if (!map || !map.getLayer(layerId)) return false
    return map.getLayoutProperty(layerId, 'visibility') !== 'none'
  }, [])

  const addSource = useCallback((sourceId: string, source: mapboxgl.AnySourceData) => {
    const map = mapRef.current
    if (!map) return
    if (map.getSource(sourceId)) {
      map.removeSource(sourceId)
    }
    map.addSource(sourceId, source)
  }, [])

  const removeSource = useCallback((sourceId: string) => {
    const map = mapRef.current
    if (!map || !map.getSource(sourceId)) return
    map.removeSource(sourceId)
  }, [])

  const addLayer = useCallback((layer: mapboxgl.AnyLayer, beforeId?: string) => {
    const map = mapRef.current
    if (!map) return
    if (map.getLayer(layer.id)) {
      map.removeLayer(layer.id)
    }
    map.addLayer(layer, beforeId)
  }, [])

  const removeLayer = useCallback((layerId: string) => {
    const map = mapRef.current
    if (!map || !map.getLayer(layerId)) return
    map.removeLayer(layerId)
  }, [])

  const setSourceData = useCallback((sourceId: string, data: any) => {
    const map = mapRef.current
    if (!map) return
    const source = map.getSource(sourceId) as mapboxgl.GeoJSONSource
    if (source) {
      source.setData(data)
    }
  }, [])

  const queryRenderedFeatures = useCallback(
    (point: [number, number], options?: QueryOptions): mapboxgl.MapboxGeoJSONFeature[] => {
      const map = mapRef.current
      if (!map) return []
      return map.queryRenderedFeatures(point, options as any)
    },
    []
  )

  return {
    map: mapRef.current,
    mapState,
    containerRef,
    flyTo,
    fitBounds,
    setLayerVisibility,
    getLayerVisibility,
    addSource,
    removeSource,
    addLayer,
    removeLayer,
    setSourceData,
    queryRenderedFeatures,
  }
}

export default useMapbox
