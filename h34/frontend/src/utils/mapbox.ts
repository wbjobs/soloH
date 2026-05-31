import mapboxgl from 'mapbox-gl'
import * as turf from '@turf/turf'
import type { GeoPoint, GeoPolygon, Coordinate, RiskLevel } from '@/types'
import { getRiskLevel, getRiskColor, RISK_THRESHOLDS } from '@/types/map'

export const MAPBOX_ACCESS_TOKEN = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN

mapboxgl.accessToken = MAPBOX_ACCESS_TOKEN

export const initMapbox = () => {
  mapboxgl.accessToken = MAPBOX_ACCESS_TOKEN
}

export { getRiskColor, getRiskLevel }

export const geoPointToCoordinate = (point: GeoPoint): Coordinate => ({
  lat: point.coordinates[1],
  lng: point.coordinates[0],
})

export const coordinateToGeoPoint = (coord: Coordinate): GeoPoint => ({
  type: 'Point',
  coordinates: [coord.lng, coord.lat],
})

export const geoPolygonToTurfPolygon = (polygon: GeoPolygon): turf.Polygon => {
  return turf.polygon(polygon.coordinates)
}

export const createGridCellFeature = (
  bounds: GeoPolygon,
  properties: Record<string, any> = {}
): turf.Feature<turf.Polygon> => {
  return turf.polygon(bounds.coordinates, properties)
}

export const createHeatmapFeatureCollection = (
  riskGrids: Array<{ grid_cell: { bounds: GeoPolygon }; risk_index: number }>
): turf.FeatureCollection<turf.Polygon> => {
  const features = riskGrids.map((rg) =>
    createGridCellFeature(rg.grid_cell.bounds, {
      risk_index: rg.risk_index,
      color: getRiskColor(rg.risk_index),
    })
  )
  return turf.featureCollection(features)
}

export const calculateDistance = (
  coord1: Coordinate,
  coord2: Coordinate,
  units: turf.Units = 'kilometers'
): number => {
  const from = turf.point([coord1.lng, coord1.lat])
  const to = turf.point([coord2.lng, coord2.lat])
  return turf.distance(from, to, { units })
}

export const findNearestStation = (
  target: Coordinate,
  stations: Array<{ latitude: number; longitude: number }>
): { index: number; distance: number } | null => {
  if (stations.length === 0) return null

  let minDistance = Infinity
  let nearestIndex = -1

  stations.forEach((station, index) => {
    const distance = calculateDistance(target, {
      lat: station.latitude,
      lng: station.longitude,
    })
    if (distance < minDistance) {
      minDistance = distance
      nearestIndex = index
    }
  })

  return nearestIndex >= 0 ? { index: nearestIndex, distance: minDistance } : null
}

export const createMapPopup = (
  map: mapboxgl.Map,
  coordinates: [number, number],
  html: string
): mapboxgl.Popup => {
  return new mapboxgl.Popup({ closeOnClick: false, anchor: 'bottom' })
    .setLngLat(coordinates)
    .setHTML(html)
    .addTo(map)
}

export const createMarker = (
  map: mapboxgl.Map,
  coordinates: [number, number],
  options?: Omit<mapboxgl.MarkerOptions, 'element'> & { element?: HTMLElement }
): mapboxgl.Marker => {
  return new mapboxgl.Marker(options)
    .setLngLat(coordinates)
    .addTo(map)
}

export const flyTo = (
  map: mapboxgl.Map,
  center: [number, number],
  zoom: number = 12,
  duration: number = 1000
): void => {
  map.flyTo({
    center,
    zoom,
    duration,
    essential: true,
  })
}

export const fitBounds = (
  map: mapboxgl.Map,
  bounds: [[number, number], [number, number]],
  padding: number = 50
): void => {
  map.fitBounds(bounds, {
    padding,
    duration: 1000,
  })
}

export const getBoundsFromPolygon = (polygon: GeoPolygon): [[number, number], [number, number]] => {
  const turfPolygon = geoPolygonToTurfPolygon(polygon)
  const bbox = turf.bbox(turfPolygon)
  return [
    [bbox[0], bbox[1]],
    [bbox[2], bbox[3]],
  ]
}

export const isPointInPolygon = (point: Coordinate, polygon: GeoPolygon): boolean => {
  const turfPoint = turf.point([point.lng, point.lat])
  const turfPolygon = geoPolygonToTurfPolygon(polygon)
  return turf.booleanPointInPolygon(turfPoint, turfPolygon)
}

export const generateRiskLegend = (): Array<{ level: RiskLevel; color: string; label: string; min: number; max: number }> => {
  return [
    { level: 'low', color: '#22c55e', label: '低风险', min: 0, max: RISK_THRESHOLDS.low - 1 },
    { level: 'medium', color: '#eab308', label: '中风险', min: RISK_THRESHOLDS.low, max: RISK_THRESHOLDS.medium - 1 },
    { level: 'high', color: '#f97316', label: '高风险', min: RISK_THRESHOLDS.medium, max: RISK_THRESHOLDS.high - 1 },
    { level: 'extreme', color: '#ef4444', label: '极高风险', min: RISK_THRESHOLDS.high, max: RISK_THRESHOLDS.extreme },
  ]
}

export default {
  initMapbox,
  getRiskColor,
  getRiskLevel,
  geoPointToCoordinate,
  coordinateToGeoPoint,
  createHeatmapFeatureCollection,
  calculateDistance,
  findNearestStation,
  createMapPopup,
  createMarker,
  flyTo,
  fitBounds,
  isPointInPolygon,
  generateRiskLegend,
}
