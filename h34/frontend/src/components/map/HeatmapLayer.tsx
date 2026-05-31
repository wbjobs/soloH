import { useEffect, useMemo } from 'react'
import type mapboxgl from 'mapbox-gl'
import * as turf from '@turf/turf'
import type { RiskGrid } from '@/types'
import { RISK_GRADIENT, type HeatmapLayerConfig } from '@/types/map'

interface HeatmapLayerProps {
  map: mapboxgl.Map | null
  isLoaded: boolean
  isStyleLoaded: boolean
  data: RiskGrid[]
  visible: boolean
  config?: Partial<HeatmapLayerConfig>
  beforeId?: string
}

const HEATMAP_SOURCE_ID = 'risk-heatmap-source'
const HEATMAP_LAYER_ID = 'risk-heatmap-layer'

const DEFAULT_CONFIG: HeatmapLayerConfig = {
  radius: 40,
  weight: 1,
  opacity: 0.7,
  intensity: 0.8,
}

export const HeatmapLayer = ({
  map,
  isLoaded,
  isStyleLoaded,
  data,
  visible,
  config = {},
  beforeId,
}: HeatmapLayerProps) => {
  const mergedConfig = useMemo(
    () => ({ ...DEFAULT_CONFIG, ...config }),
    [config]
  )

  const geoJsonData = useMemo(() => {
    const features = data
      .filter((rg) => rg.grid_cell?.centroid?.coordinates)
      .map((rg) =>
        turf.point(rg.grid_cell!.centroid.coordinates, {
          risk_index: rg.risk_index,
          grid_id: rg.grid_id,
          crop_type: rg.crop_type,
          forecast_date: rg.forecast_date,
        })
      )
    return turf.featureCollection(features)
  }, [data])

  useEffect(() => {
    if (!map || !isLoaded || !isStyleLoaded) return

    const source = map.getSource(HEATMAP_SOURCE_ID) as mapboxgl.GeoJSONSource
    if (source) {
      source.setData(geoJsonData)
    } else {
      map.addSource(HEATMAP_SOURCE_ID, {
        type: 'geojson',
        data: geoJsonData,
      })
    }

    if (!map.getLayer(HEATMAP_LAYER_ID)) {
      map.addLayer(
        {
          id: HEATMAP_LAYER_ID,
          type: 'heatmap',
          source: HEATMAP_SOURCE_ID,
          maxzoom: 15,
          paint: {
            'heatmap-weight': [
              'interpolate',
              ['linear'],
              ['get', 'risk_index'],
              0,
              0,
              100,
              mergedConfig.weight,
            ],
            'heatmap-intensity': mergedConfig.intensity,
            'heatmap-color': [
              'interpolate',
              ['linear'],
              ['heatmap-density'],
              ...RISK_GRADIENT,
            ],
            'heatmap-radius': [
              'interpolate',
              ['linear'],
              ['zoom'],
              0,
              mergedConfig.radius * 0.5,
              15,
              mergedConfig.radius * 2,
            ],
            'heatmap-opacity': mergedConfig.opacity,
          },
        },
        beforeId
      )
    }

    return () => {
      if (map.getLayer(HEATMAP_LAYER_ID)) {
        map.removeLayer(HEATMAP_LAYER_ID)
      }
      if (map.getSource(HEATMAP_SOURCE_ID)) {
        map.removeSource(HEATMAP_SOURCE_ID)
      }
    }
  }, [map, isLoaded, isStyleLoaded, geoJsonData, beforeId])

  useEffect(() => {
    if (!map || !isStyleLoaded) return

    if (map.getLayer(HEATMAP_LAYER_ID)) {
      map.setLayoutProperty(
        HEATMAP_LAYER_ID,
        'visibility',
        visible ? 'visible' : 'none'
      )
    }
  }, [map, isStyleLoaded, visible])

  useEffect(() => {
    if (!map || !isStyleLoaded || !map.getLayer(HEATMAP_LAYER_ID)) return

    map.setPaintProperty(HEATMAP_LAYER_ID, 'heatmap-weight', [
      'interpolate',
      ['linear'],
      ['get', 'risk_index'],
      0,
      0,
      100,
      mergedConfig.weight,
    ])
    map.setPaintProperty(
      HEATMAP_LAYER_ID,
      'heatmap-intensity',
      mergedConfig.intensity
    )
    map.setPaintProperty(
      HEATMAP_LAYER_ID,
      'heatmap-radius',
      [
        'interpolate',
        ['linear'],
        ['zoom'],
        0,
        mergedConfig.radius * 0.5,
        15,
        mergedConfig.radius * 2,
      ]
    )
    map.setPaintProperty(
      HEATMAP_LAYER_ID,
      'heatmap-opacity',
      mergedConfig.opacity
    )
  }, [map, isStyleLoaded, mergedConfig])

  return null
}

export default HeatmapLayer
