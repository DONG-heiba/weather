/**
 * API client for weather visualization backend.
 */

const BASE = '/api'

async function request(path, params = {}) {
  const url = new URL(path, window.location.origin)
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null) url.searchParams.set(k, v)
  })
  const res = await fetch(url.toString())
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(detail.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

/** Check backend and database availability. */
export function fetchHealth() {
  return request('/api/health')
}

/** Get metadata: times, layers, places, grid, sources. */
export function fetchMeta() {
  return request('/api/meta')
}

/** Get grid field data for a layer and time index. */
export function fetchField(layer, timeIdx) {
  return request('/api/field', { layer, time_idx: timeIdx })
}

/** Get point weather for lat/lon and time index. */
export function fetchPoint(lat, lon, timeIdx) {
  return request('/api/point', { lat, lon, time_idx: timeIdx })
}

/**
 * Color scales for rendering.
 */

// Temperature: blue (cold) → cyan → green → yellow → orange → red (hot)
export function temperatureColor(t, min, max) {
  if (t == null || isNaN(t)) return 'rgba(0,0,0,0)'
  const v = Math.max(0, Math.min(1, (t - min) / (max - min || 1)))
  // Use a multi-stop gradient
  const stops = [
    [0, 0, 128],     // dark blue
    [0, 128, 255],   // blue
    [0, 255, 255],   // cyan
    [128, 255, 128], // light green
    [255, 255, 0],   // yellow
    [255, 128, 0],   // orange
    [255, 0, 0],     // red
  ]
  const idx = v * (stops.length - 1)
  const lo = Math.floor(idx)
  const hi = Math.min(lo + 1, stops.length - 1)
  const t2 = idx - lo
  const r = Math.round(stops[lo][0] + (stops[hi][0] - stops[lo][0]) * t2)
  const g = Math.round(stops[lo][1] + (stops[hi][1] - stops[lo][1]) * t2)
  const b = Math.round(stops[lo][2] + (stops[hi][2] - stops[lo][2]) * t2)
  return `rgb(${r},${g},${b})`
}

// Precipitation: transparent → light blue → blue → dark blue → purple
export function precipitationColor(p, max) {
  if (p == null || isNaN(p) || p <= 0.01) return 'rgba(0,0,0,0)'
  const v = Math.max(0, Math.min(1, p / (max || 1)))
  const stops = [
    [200, 230, 255],
    [100, 180, 255],
    [30, 100, 220],
    [0, 30, 150],
    [80, 0, 150],
  ]
  const idx = v * (stops.length - 1)
  const lo = Math.floor(idx)
  const hi = Math.min(lo + 1, stops.length - 1)
  const t2 = idx - lo
  const r = Math.round(stops[lo][0] + (stops[hi][0] - stops[lo][0]) * t2)
  const g = Math.round(stops[lo][1] + (stops[hi][1] - stops[lo][1]) * t2)
  const b = Math.round(stops[lo][2] + (stops[hi][2] - stops[lo][2]) * t2)
  return `rgb(${r},${g},${b})`
}

// Clouds: clear (white/transparent) → overcast (dark blue-grey)
export function cloudsColor(c) {
  if (c == null || isNaN(c)) return 'rgba(0,0,0,0)'
  const v = Math.max(0, Math.min(1, c / 100))
  // 0% → white-ish, 100% → dark slate
  const r = Math.round(255 - v * 200)
  const g = Math.round(255 - v * 210)
  const b = Math.round(255 - v * 180)
  return `rgb(${r},${g},${b})`
}

// Pressure: diverging — low (blue) → normal (green) → high (red)
export function pressureColor(p, min, max) {
  if (p == null || isNaN(p)) return 'rgba(0,0,0,0)'
  const mid = (min + max) / 2
  if (p <= mid) {
    const v = Math.max(0, Math.min(1, (p - min) / (mid - min || 1)))
    const r = Math.round(0 + v * 100)
    const g = Math.round(100 + v * 155)
    const b = Math.round(255 - v * 100)
    return `rgb(${r},${g},${b})`
  } else {
    const v = Math.max(0, Math.min(1, (p - mid) / (max - mid || 1)))
    const r = Math.round(100 + v * 155)
    const g = Math.round(255 - v * 155)
    const b = Math.round(155 - v * 155)
    return `rgb(${r},${g},${b})`
  }
}

// Wind speed: black (strong) → grey → light grey (weak)
export function windColor(speed, maxSpeed) {
  if (speed == null || isNaN(speed)) return 'rgba(0,0,0,0)'
  const v = Math.max(0, Math.min(1, speed / (maxSpeed || 1)))
  const g = Math.round(180 - v * 180)  // 180 (light) → 0 (black)
  return `rgb(${g},${g},${g})`
}
