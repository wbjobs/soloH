import { useEffect, useMemo, useCallback } from 'react'
import type mapboxgl from 'mapbox-gl'
import * as turf from '@turf/turf'
import { Cloud, Wind } from 'lucide-react'
import type { WeatherStation, SporeSensor } from '@/types'
import type { HoveredFeature } from '@/types/map'

interface StationMarkersProps {
  map: mapboxgl.Map | null
  isLoaded: boolean
  isStyleLoaded: boolean
  weatherStations: WeatherStation[]
  sporeSensors: SporeSensor[]
  visible: boolean
  beforeId?: string
  onHover?: (feature: HoveredFeature | null) => void
  onClick?: (feature: HoveredFeature, coordinates: [number, number]) => void
}

const STATION_SOURCE_ID = 'weather-stations-source'
const STATION_LAYER_ID = 'weather-stations-layer'
const SENSOR_SOURCE_ID = 'spore-sensors-source'
const SENSOR_LAYER_ID = 'spore-sensors-layer'

const createMarkerElement = (
  icon: React.ReactNode,
  bgColor: string,
  size: number = 32
): HTMLElement => {
  const container = document.createElement('div')
  container.style.cssText = `
    width: ${size}px;
    height: ${size}px;
    background-color: ${bgColor};
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
    border: 2px solid white;
    cursor: pointer;
    transition: transform 0.2s;
  `
  
  const svgContainer = document.createElement('div')
  svgContainer.style.cssText = `
    width: ${size * 0.6}px;
    height: ${size * 0.6}px;
    color: white;
  `
  
  const tempDiv = document.createElement('div')
  tempDiv.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="${size * 0.6}" height="${size * 0.6}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${icon}</svg>`
  const svg = tempDiv.querySelector('svg')
  if (svg) {
    svgContainer.appendChild(svg)
  }
  
  container.appendChild(svgContainer)
  
  container.addEventListener('mouseenter', () => {
    container.style.transform = 'scale(1.2)'
  })
  container.addEventListener('mouseleave', () => {
    container.style.transform = 'scale(1)'
  })
  
  return container
}

export const StationMarkers = ({
  map,
  isLoaded,
  isStyleLoaded,
  weatherStations,
  sporeSensors,
  visible,
  beforeId,
  onHover,
  onClick,
}: StationMarkersProps) => {
  const stationGeoJson = useMemo(() => {
    const features = weatherStations
      .filter((station) => station.location?.coordinates)
      .map((station) =>
        turf.point(station.location.coordinates, {
          id: station.id,
          type: 'station',
          name: station.name,
          code: station.code,
          elevation: station.elevation,
          is_active: station.is_active,
          latitude: station.latitude,
          longitude: station.longitude,
        })
      )
    return turf.featureCollection(features)
  }, [weatherStations])

  const sensorGeoJson = useMemo(() => {
    const features = sporeSensors
      .filter((sensor) => sensor.location?.coordinates)
      .map((sensor) =>
        turf.point(sensor.location.coordinates, {
          id: sensor.id,
          type: 'sensor',
          name: sensor.name,
          code: sensor.code,
          crop_type: sensor.crop_type,
          spore_type: sensor.spore_type,
          is_active: sensor.is_active,
          latitude: sensor.latitude,
          longitude: sensor.longitude,
        })
      )
    return turf.featureCollection(features)
  }, [sporeSensors])

  const handleMouseMove = useCallback(
    (e: mapboxgl.MapMouseEvent) => {
      if (!map || !visible) return

      const features = map.queryRenderedFeatures(e.point, {
        layers: [STATION_LAYER_ID, SENSOR_LAYER_ID],
      })

      if (features.length > 0) {
        const feature = features[0]
        onHover?.({
          id: feature.id!,
          layerId: feature.layer.id,
          properties: feature.properties || {},
        })
        map.getCanvas().style.cursor = 'pointer'
      } else {
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
        layers: [STATION_LAYER_ID, SENSOR_LAYER_ID],
      })

      if (features.length > 0) {
        const feature = features[0]
        onClick?.(
          {
            id: feature.id!,
            layerId: feature.layer.id,
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
    onHover?.(null)
    map.getCanvas().style.cursor = ''
  }, [map, onHover])

  useEffect(() => {
    if (!map || !isLoaded || !isStyleLoaded) return

    const stationSource = map.getSource(STATION_SOURCE_ID) as mapboxgl.GeoJSONSource
    if (stationSource) {
      stationSource.setData(stationGeoJson)
    } else {
      map.addSource(STATION_SOURCE_ID, {
        type: 'geojson',
        data: stationGeoJson,
      })
    }

    if (!map.getLayer(STATION_LAYER_ID)) {
      map.addLayer(
        {
          id: STATION_LAYER_ID,
          type: 'circle',
          source: STATION_SOURCE_ID,
          paint: {
            'circle-radius': 10,
            'circle-color': '#3b82f6',
            'circle-stroke-color': '#ffffff',
            'circle-stroke-width': 2,
            'circle-opacity': 0.9,
          },
        },
        beforeId
      )
    }

    const sensorSource = map.getSource(SENSOR_SOURCE_ID) as mapboxgl.GeoJSONSource
    if (sensorSource) {
      sensorSource.setData(sensorGeoJson)
    } else {
      map.addSource(SENSOR_SOURCE_ID, {
        type: 'geojson',
        data: sensorGeoJson,
      })
    }

    if (!map.getLayer(SENSOR_LAYER_ID)) {
      map.addLayer(
        {
          id: SENSOR_LAYER_ID,
          type: 'circle',
          source: SENSOR_SOURCE_ID,
          paint: {
            'circle-radius': 8,
            'circle-color': '#8b5cf6',
            'circle-stroke-color': '#ffffff',
            'circle-stroke-width': 2,
            'circle-opacity': 0.9,
          },
        },
        beforeId
      )
    }

    map.on('mousemove', handleMouseMove)
    map.on('click', handleClick)
    map.on('mouseleave', handleMouseLeave)

    return () => {
      map.off('mousemove', handleMouseMove)
      map.off('click', handleClick)
      map.off('mouseleave', handleMouseLeave)

      if (map.getLayer(SENSOR_LAYER_ID)) {
        map.removeLayer(SENSOR_LAYER_ID)
      }
      if (map.getSource(SENSOR_SOURCE_ID)) {
        map.removeSource(SENSOR_SOURCE_ID)
      }
      if (map.getLayer(STATION_LAYER_ID)) {
        map.removeLayer(STATION_LAYER_ID)
      }
      if (map.getSource(STATION_SOURCE_ID)) {
        map.removeSource(STATION_SOURCE_ID)
      }
    }
  }, [map, isLoaded, isStyleLoaded, stationGeoJson, sensorGeoJson, beforeId, handleMouseMove, handleClick, handleMouseLeave])

  useEffect(() => {
    if (!map || !isStyleLoaded) return

    if (map.getLayer(STATION_LAYER_ID)) {
      map.setLayoutProperty(
        STATION_LAYER_ID,
        'visibility',
        visible ? 'visible' : 'none'
      )
    }
    if (map.getLayer(SENSOR_LAYER_ID)) {
      map.setLayoutProperty(
        SENSOR_LAYER_ID,
        'visibility',
        visible ? 'visible' : 'none'
      )
    }
  }, [map, isStyleLoaded, visible])

  return null
}

export default StationMarkers
