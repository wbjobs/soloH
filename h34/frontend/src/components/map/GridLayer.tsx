import { useEffect, useMemo, useState, useCallback } from 'react'
import type mapboxgl from 'mapbox-gl'
import * as turf from '@turf/turf'
import type { RiskGrid } from '@/types'
import { getRiskColor, type GridLayerConfig, type HoveredFeature } from '@/types/map'

interface GridLayerProps {
  map: mapboxgl.Map | null
  isLoaded: boolean
  isStyleLoaded: boolean
  data: RiskGrid[]
  visible: boolean
  config?: Partial<GridLayerConfig>
  beforeId?: string
  onHover?: (feature: HoveredFeature | null) => void
  onClick?: (feature: HoveredFeature, coordinates: [number, number]) => void
}

const GRID_SOURCE_ID = 'risk-grid-source'
const GRID_LAYER_ID = 'risk-grid-layer'
const GRID_HIGHLIGHT_LAYER_ID = 'risk-grid-highlight-layer'

const DEFAULT_CONFIG: GridLayerConfig = {
  opacity: 0.6,
  strokeWidth: 0.5,
  strokeColor: 'rgba(255, 255, 255, 0.5)',
  highlightOpacity: 0.9,
}

export const GridLayer = ({
  map,
  isLoaded,
  isStyleLoaded,
  data,
  visible,
  config = {},
  beforeId,
  onHover,
  onClick,
}: GridLayerProps) => {
  const mergedConfig = useMemo(
    () => ({ ...DEFAULT_CONFIG, ...config }),
    [config]
  )

  const [hoveredId, setHoveredId] = useState<string | number | null>(null)

  const geoJsonData = useMemo(() => {
    const features = data
      .filter((rg) => rg.grid_cell?.bounds?.coordinates)
      .map((rg) =>
        turf.polygon(rg.grid_cell!.bounds.coordinates, {
          id: rg.id,
          grid_id: rg.grid_id,
          risk_index: rg.risk_index,
          crop_type: rg.crop_type,
          forecast_date: rg.forecast_date,
          infection_probability: rg.infection_probability,
          model_version: rg.model_version,
          color: getRiskColor(rg.risk_index),
          lat: rg.grid_cell?.lat,
          lon: rg.grid_cell?.lon,
        })
      )
    return turf.featureCollection(features)
  }, [data])

  const handleMouseMove = useCallback(
    (e: mapboxgl.MapMouseEvent) => {
      if (!map || !visible) return

      const features = map.queryRenderedFeatures(e.point, {
        layers: [GRID_LAYER_ID],
      })

      if (features.length > 0) {
        const feature = features[0]
        setHoveredId(feature.id!)
        onHover?.({
          id: feature.id!,
          layerId: GRID_LAYER_ID,
          properties: feature.properties || {},
        })
        map.getCanvas().style.cursor = 'pointer'
      } else {
        setHoveredId(null)
        onHover?.(null)
        map.getCanvas().style.cursor = ''
      }
    },
    [map, visible, onHover]
  )

  const handleClick = useCallback(
    (e: mapboxgl.MapMouseEvent) => {
      if (!map || !visible) return

      const features = map.queryRenderedFeatures(e.point, {
        layers: [GRID_LAYER_ID],
      })

      if (features.length > 0) {
        const feature = features[0]
        onClick?.(
          {
            id: feature.id!,
            layerId: GRID_LAYER_ID,
            properties: feature.properties || {},
          },
          [e.lngLat.lng, e.lngLat.lat]
        )
      }
    },
    [map, visible, onClick]
  )

  const handleMouseLeave = useCallback(() => {
    if (!map) return
    setHoveredId(null)
    onHover?.(null)
    map.getCanvas().style.cursor = ''
  }, [map, onHover])

  useEffect(() => {
    if (!map || !isLoaded || !isStyleLoaded) return

    const source = map.getSource(GRID_SOURCE_ID) as mapboxgl.GeoJSONSource
    if (source) {
      source.setData(geoJsonData)
    } else {
      map.addSource(GRID_SOURCE_ID, {
        type: 'geojson',
        data: geoJsonData,
      })
    }

    if (!map.getLayer(GRID_LAYER_ID)) {
      map.addLayer(
        {
          id: GRID_LAYER_ID,
          type: 'fill',
          source: GRID_SOURCE_ID,
          paint: {
            'fill-color': ['get', 'color'],
            'fill-opacity': [
              'case',
              ['boolean', ['feature-state', 'hover'], false],
              mergedConfig.highlightOpacity,
              mergedConfig.opacity,
            ],
            'fill-outline-color': mergedConfig.strokeColor,
          },
        },
        beforeId
      )
    }

    if (!map.getLayer(GRID_HIGHLIGHT_LAYER_ID)) {
      map.addLayer(
        {
          id: GRID_HIGHLIGHT_LAYER_ID,
          type: 'line',
          source: GRID_SOURCE_ID,
          paint: {
            'line-color': '#ffffff',
            'line-width': [
              'case',
              ['boolean', ['feature-state', 'hover'], false],
              2,
              mergedConfig.strokeWidth,
            ],
            'line-opacity': [
              'case',
              ['boolean', ['feature-state', 'hover'], false],
              1,
              0.5,
            ],
          },
          filter: ['==', 'id', hoveredId ?? ''],
        },
        GRID_LAYER_ID
      )
    }

    map.on('mousemove', handleMouseMove)
    map.on('click', handleClick)
    map.on('mouseleave', handleMouseLeave)

    return () => {
      map.off('mousemove', handleMouseMove)
      map.off('click', handleClick)
      map.off('mouseleave', handleMouseLeave)

      if (map.getLayer(GRID_HIGHLIGHT_LAYER_ID)) {
        map.removeLayer(GRID_HIGHLIGHT_LAYER_ID)
      }
      if (map.getLayer(GRID_LAYER_ID)) {
        map.removeLayer(GRID_LAYER_ID)
      }
      if (map.getSource(GRID_SOURCE_ID)) {
        map.removeSource(GRID_SOURCE_ID)
      }
    }
  }, [map, isLoaded, isStyleLoaded, geoJsonData, beforeId, handleMouseMove, handleClick, handleMouseLeave])

  useEffect(() => {
    if (!map || !isStyleLoaded) return

    if (map.getLayer(GRID_LAYER_ID)) {
      map.setLayoutProperty(
        GRID_LAYER_ID,
        'visibility',
        visible ? 'visible' : 'none'
      )
    }
    if (map.getLayer(GRID_HIGHLIGHT_LAYER_ID)) {
      map.setLayoutProperty(
        GRID_HIGHLIGHT_LAYER_ID,
        'visibility',
        visible ? 'visible' : 'none'
      )
    }
  }, [map, isStyleLoaded, visible])

  useEffect(() => {
    if (!map || !isStyleLoaded) return

    if (hoveredId !== null) {
      map.setFilter(GRID_HIGHLIGHT_LAYER_ID, ['==', 'id', hoveredId])
      map.setFeatureState(
        { source: GRID_SOURCE_ID, id: hoveredId },
        { hover: true }
      )
    } else {
      map.setFilter(GRID_HIGHLIGHT_LAYER_ID, ['==', 'id', ''])
      const features = map.querySourceFeatures(GRID_SOURCE_ID)
      features.forEach((feature) => {
        map.setFeatureState(
          { source: GRID_SOURCE_ID, id: feature.id! },
          { hover: false }
        )
      })
    }
  }, [map, isStyleLoaded, hoveredId])

  useEffect(() => {
    if (!map || !isStyleLoaded || !map.getLayer(GRID_LAYER_ID)) return

    map.setPaintProperty(GRID_LAYER_ID, 'fill-opacity', [
      'case',
      ['boolean', ['feature-state', 'hover'], false],
      mergedConfig.highlightOpacity,
      mergedConfig.opacity,
    ])
    map.setPaintProperty(
      GRID_LAYER_ID,
      'fill-outline-color',
      mergedConfig.strokeColor
    )
    map.setPaintProperty(
      GRID_HIGHLIGHT_LAYER_ID,
      'line-width',
      [
        'case',
        ['boolean', ['feature-state', 'hover'], false],
        2,
        mergedConfig.strokeWidth,
      ]
    )
  }, [map, isStyleLoaded, mergedConfig])

  return null
}

export default GridLayer
