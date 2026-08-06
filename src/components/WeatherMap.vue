<template>
  <div class="weather-map-wrapper">
    <div ref="mapContainer" class="map-container"></div>

    <div v-if="loading" class="map-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>加载天气数据中...</span>
    </div>

    <div v-if="error" class="map-error">
      <el-icon><WarningFilled /></el-icon>
      <span>{{ error }}</span>
      <el-button size="small" @click="refresh">重试</el-button>
    </div>

    <div class="layer-switcher">
      <el-radio-group v-model="activeLayer" size="small" @change="onLayerChange">
        <el-radio-button v-for="lyr in layers" :key="lyr.id" :value="lyr.id">
          {{ lyr.name }}
        </el-radio-button>
      </el-radio-group>
    </div>

    <div class="city-search">
      <el-autocomplete
        v-model="searchQuery"
        :fetch-suggestions="searchCities"
        :trigger-on-focus="false"
        clearable
        placeholder="搜索城市（输入拼音或中文）..."
        size="small"
        :debounce="400"
        @select="onSearchSelect"
        popper-class="city-search-popper"
      >
        <template #default="{ item }">
          <div class="search-item">
            <span class="search-name">{{ item.value }}</span>
            <span class="search-detail">{{ item.display_name }}</span>
          </div>
        </template>
      </el-autocomplete>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import L from 'leaflet'
import { Loading, WarningFilled } from '@element-plus/icons-vue'
import {
  fetchMeta, fetchField,
  temperatureColor, precipitationColor, cloudsColor, pressureColor, windColor,
} from '../api/index.js'
import { CHINESE_CITIES } from '../data/cities.js'

const props = defineProps({ timeIdx: { type: Number, default: 0 } })
const emit = defineEmits(['pointSelect', 'layerChange'])

const mapContainer = ref(null)
const activeLayer = ref('temperature')
const layers = ref([])
const searchQuery = ref('')
const loading = ref(true)
const error = ref(null)

let map = null
let fieldData = null
let metaLoaded = false
let baseLayer = null
let fallbackBaseLayer = null

const BASE_TILE_SOURCES = [
  'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
  'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
  'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',
]

const TRANSPARENT_TILE =
  'data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs='

const SIMPLE_LAND_SHAPES = [
  [[-168, 72], [-136, 71], [-113, 60], [-98, 49], [-84, 31], [-100, 16], [-122, 23], [-150, 47]],
  [[-82, 13], [-70, 9], [-53, -10], [-46, -23], [-57, -52], [-72, -55], [-80, -30], [-77, -5]],
  [[-18, 35], [6, 50], [39, 56], [62, 44], [46, 31], [27, 32], [9, 42], [-9, 43]],
  [[-18, 35], [32, 36], [50, 12], [42, -35], [16, -35], [-5, -6]],
  [[26, 71], [78, 74], [122, 64], [150, 51], [153, 24], [124, 14], [100, 6], [78, 9], [54, 25], [36, 42]],
  [[70, 25], [89, 25], [94, 8], [78, 6]],
  [[100, 20], [121, 24], [142, 9], [133, -11], [108, -8], [96, 7]],
  [[112, -12], [154, -18], [153, -40], [130, -43], [113, -31]],
  [[-180, -66], [180, -66], [180, -90], [-180, -90]],
]

const FALLBACK_LABELS = [
  { text: 'ASIA', lat: 45, lon: 90 },
  { text: 'EUROPE', lat: 51, lon: 15 },
  { text: 'AFRICA', lat: 8, lon: 20 },
  { text: 'AUSTRALIA', lat: -25, lon: 135 },
  { text: 'AMERICA', lat: 43, lon: -105 },
]

// Canvases — created in Leaflet overlayPane for auto-panning
let sCanvas = null   // scalar
let wCanvas = null   // wind

// Canvas offset in layer coordinates — needed for layerPointToLatLng
let canvasOffset = L.point(0, 0)

// Wind particles
let windParticles = []
let windAnimId = null
let prevTime = 0

// ---- Lifecycle ----
onMounted(async () => {
  try {
    const meta = await fetchMeta()
    layers.value = meta.layers
    metaLoaded = true
    await nextTick()
    initMap()
    await loadField()
    loading.value = false
  } catch (e) {
    console.error('Init error:', e)
    error.value = '数据加载失败: ' + e.message
    loading.value = false
  }
})

onBeforeUnmount(() => {
  if (windAnimId) cancelAnimationFrame(windAnimId)
  if (map) { map.remove(); map = null }
})

// ---- Map init ----
function initMap() {
  map = L.map(mapContainer.value, {
    center: [30, 110], zoom: 4,
    minZoom: 2, maxZoom: 10,
    zoomControl: true, attributionControl: true,
    fadeAnimation: false,
    zoomAnimation: false,
    markerZoomAnimation: false,
  })

  map.createPane('localFallbackPane')
  map.getPane('localFallbackPane').style.zIndex = 180
  fallbackBaseLayer = createFallbackBaseLayer()
  fallbackBaseLayer.addTo(map)

  // Light basemap with per-tile fallbacks. Failed network tiles otherwise show
  // up as large square blanks at Leaflet's 256px tile boundaries.
  baseLayer = L.tileLayer(BASE_TILE_SOURCES[0], {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
    subdomains: 'abcd',
    maxZoom: 19,
    keepBuffer: 3,
    updateWhenIdle: true,
    updateWhenZooming: false,
    errorTileUrl: TRANSPARENT_TILE,
  })
  baseLayer.on('tileerror', retryFailedTile)
  baseLayer.on('tileload', ({ tile }) => {
    tile.classList.remove('leaflet-tile-retrying')
  })
  baseLayer.addTo(map)

  // Create canvases INSIDE overlayPane → Leaflet auto-pans them
  const pane = map.getPanes().overlayPane

  sCanvas = L.DomUtil.create('canvas', 'weather-canvas-leaflet', pane)
  sCanvas.style.pointerEvents = 'none'

  wCanvas = L.DomUtil.create('canvas', 'weather-canvas-leaflet', pane)
  wCanvas.style.pointerEvents = 'none'
  wCanvas.style.display = 'none'

  // Click handler
  map.on('click', (e) => {
    emit('pointSelect', { lat: +e.latlng.lat.toFixed(4), lon: +e.latlng.lng.toFixed(4) })
  })

  // Sync canvas on map change
  map.on('moveend zoomend resize', syncCanvas)
  syncCanvas()
}

function createFallbackBaseLayer() {
  const CanvasFallbackLayer = L.GridLayer.extend({
    createTile(coords) {
      return createFallbackTile(coords, this.getTileSize())
    },
  })

  return new CanvasFallbackLayer({
    pane: 'localFallbackPane',
    tileSize: 256,
    updateWhenIdle: true,
    updateWhenZooming: false,
    keepBuffer: 3,
  })
}

function createFallbackTile(coords, size) {
  const tile = L.DomUtil.create('canvas', 'local-fallback-tile')
  tile.width = size.x
  tile.height = size.y

  const ctx = tile.getContext('2d')
  const scale = 256 * Math.pow(2, coords.z)
  const originX = coords.x * 256
  const originY = coords.y * 256

  ctx.fillStyle = '#cfd8db'
  ctx.fillRect(0, 0, size.x, size.y)
  drawFallbackGraticule(ctx, coords, scale, originX, originY)

  ctx.fillStyle = '#f7f8f6'
  ctx.strokeStyle = '#d9d2cb'
  ctx.lineWidth = coords.z <= 3 ? 0.8 : 1
  for (const shape of SIMPLE_LAND_SHAPES) {
    drawFallbackPolygon(ctx, shape, scale, originX, originY)
  }

  if (coords.z <= 4) drawFallbackLabels(ctx, coords, scale, originX, originY)
  return tile
}

function projectFallbackPoint(lon, lat, scale, originX, originY) {
  const clampedLat = Math.max(-85.0511, Math.min(85.0511, lat))
  const sin = Math.sin((clampedLat * Math.PI) / 180)
  return {
    x: ((lon + 180) / 360) * scale - originX,
    y: (0.5 - Math.log((1 + sin) / (1 - sin)) / (4 * Math.PI)) * scale - originY,
  }
}

function drawFallbackPolygon(ctx, shape, scale, originX, originY) {
  ctx.beginPath()
  shape.forEach(([lon, lat], index) => {
    const point = projectFallbackPoint(lon, lat, scale, originX, originY)
    if (index === 0) ctx.moveTo(point.x, point.y)
    else ctx.lineTo(point.x, point.y)
  })
  ctx.closePath()
  ctx.fill()
  ctx.stroke()
}

function drawFallbackGraticule(ctx, coords, scale, originX, originY) {
  if (coords.z > 4) return
  ctx.strokeStyle = 'rgba(255,255,255,0.32)'
  ctx.lineWidth = 0.7
  for (let lon = -180; lon <= 180; lon += 30) {
    const top = projectFallbackPoint(lon, 84, scale, originX, originY)
    const bottom = projectFallbackPoint(lon, -84, scale, originX, originY)
    ctx.beginPath()
    ctx.moveTo(top.x, top.y)
    ctx.lineTo(bottom.x, bottom.y)
    ctx.stroke()
  }
  for (let lat = -60; lat <= 60; lat += 30) {
    const left = projectFallbackPoint(-180, lat, scale, originX, originY)
    const right = projectFallbackPoint(180, lat, scale, originX, originY)
    ctx.beginPath()
    ctx.moveTo(left.x, left.y)
    ctx.lineTo(right.x, right.y)
    ctx.stroke()
  }
}

function drawFallbackLabels(ctx, coords, scale, originX, originY) {
  ctx.fillStyle = 'rgba(111,128,139,0.58)'
  ctx.font = '700 12px Arial, sans-serif'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  for (const label of FALLBACK_LABELS) {
    const point = projectFallbackPoint(label.lon, label.lat, scale, originX, originY)
    if (point.x > -40 && point.x < 296 && point.y > -20 && point.y < 276) {
      ctx.fillText(label.text, point.x, point.y)
    }
  }
}

function retryFailedTile(event) {
  const tile = event.tile
  const coords = event.coords
  const nextSourceIndex = Number(tile.dataset.sourceIndex || 0) + 1

  if (nextSourceIndex >= BASE_TILE_SOURCES.length) {
    tile.src = TRANSPARENT_TILE
    tile.classList.add('leaflet-tile-fallback-empty')
    return
  }

  tile.dataset.sourceIndex = String(nextSourceIndex)
  tile.classList.add('leaflet-tile-retrying')
  tile.src = L.Util.template(BASE_TILE_SOURCES[nextSourceIndex], {
    ...coords,
    s: 'a',
    r: L.Browser.retina ? '@2x' : '',
  })
}

// ---- Canvas sync (called after pan/zoom) ----
function syncCanvas() {
  if (!map) return
  const size = map.getSize()
  const topLeft = map.containerPointToLayerPoint([0, 0])
  canvasOffset = topLeft  // store for drawScalar / wind particles

  // Show/hide based on layer type
  const isWind = activeLayer.value === 'wind'
  if (sCanvas) sCanvas.style.display = isWind ? 'none' : ''
  if (wCanvas) wCanvas.style.display = isWind ? '' : 'none'

  // Size & position scalar canvas
  if (sCanvas) {
    sCanvas.width = size.x; sCanvas.height = size.y
    sCanvas.style.width = size.x + 'px'; sCanvas.style.height = size.y + 'px'
    L.DomUtil.setPosition(sCanvas, topLeft)
    if (!isWind) drawScalar()
  }

  // Size & position wind canvas
  if (wCanvas) {
    wCanvas.width = size.x; wCanvas.height = size.y
    wCanvas.style.width = size.x + 'px'; wCanvas.style.height = size.y + 'px'
    L.DomUtil.setPosition(wCanvas, topLeft)
    if (isWind) { initParticles(); startWindAnim() }
  }
}

// ---- Data loading ----
async function loadField() {
  if (!metaLoaded) return
  try {
    const data = await fetchField(activeLayer.value, props.timeIdx)
    fieldData = data
    if (activeLayer.value === 'wind') { initParticles(); startWindAnim() }
    else drawScalar()
  } catch (e) {
    console.error('Field load error:', e)
    error.value = '天气数据加载失败: ' + e.message
  }
}

watch(() => props.timeIdx, loadField)

// =========================================================================
//  SMOOTH SCALAR RENDERING
// =========================================================================

function bilinearInterpolate(lats, lons, values, lat, lng) {
  if (lat < lats[0] || lat > lats[lats.length - 1]) return null
  if (lng < lons[0] || lng > lons[lons.length - 1]) return null

  const step = lats[1] - lats[0]
  const i0 = Math.floor((lat - lats[0]) / step)
  const j0 = Math.floor((lng - lons[0]) / step)
  const i1 = i0 + 1, j1 = j0 + 1
  if (i0 < 0 || i1 >= lats.length || j0 < 0 || j1 >= lons.length) return null

  const get = (arr, i, j) => { const v = arr[i]?.[j]; return (v != null && !isNaN(v)) ? v : null }
  const v00 = get(values, i0, j0), v10 = get(values, i1, j0)
  const v01 = get(values, i0, j1), v11 = get(values, i1, j1)

  const corners = [v00, v10, v01, v11].filter(v => v !== null)
  if (corners.length === 0) return null

  const ti = (lat - lats[i0]) / step, tj = (lng - lons[j0]) / step

  let result = 0
  if (v00 !== null) result += (1 - ti) * (1 - tj) * v00
  if (v10 !== null) result += ti * (1 - tj) * v10
  if (v01 !== null) result += (1 - ti) * tj * v01
  if (v11 !== null) result += ti * tj * v11

  return result
}

function getColor(layerId, val, min, max) {
  if (layerId === 'temperature') return temperatureColor(val, min, max)
  if (layerId === 'precipitation') return precipitationColor(val, max)
  if (layerId === 'clouds') return cloudsColor(val)
  if (layerId === 'pressure') return pressureColor(val, min, max)
  return 'rgba(0,0,0,0)'
}

function drawScalar() {
  if (!sCanvas || !fieldData) return
  const ctx = sCanvas.getContext('2d')
  const { lats, lons, values, layer, min, max } = fieldData
  if (!lats || !lons || !values) return

  const w = sCanvas.width, h = sCanvas.height
  if (w === 0 || h === 0) return

  const STEP = 2
  const imageData = ctx.createImageData(w, h)
  const data = imageData.data

  for (let py = 0; py < h; py += STEP) {
    for (let px = 0; px < w; px += STEP) {
      // Canvas pixel → absolute layer coords → lat/lng
      const latlng = map.layerPointToLatLng(L.point(canvasOffset.x + px, canvasOffset.y + py))
      const val = bilinearInterpolate(lats, lons, values, latlng.lat, latlng.lng)
      if (val === null) continue

      const color = getColor(layer, val, min, max)
      const m = color.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/)
      if (!m) continue
      const r = +m[1], g = +m[2], b = +m[3]

      const maxY = Math.min(py + STEP, h), maxX = Math.min(px + STEP, w)
      for (let dy = py; dy < maxY; dy++) {
        for (let dx = px; dx < maxX; dx++) {
          const idx = (dy * w + dx) * 4
          data[idx] = r; data[idx + 1] = g; data[idx + 2] = b; data[idx + 3] = 120
        }
      }
    }
  }

  ctx.putImageData(imageData, 0, 0)
}

// =========================================================================
//  WIND PARTICLES
// =========================================================================

function initParticles() {
  if (!wCanvas) return
  const count = Math.min(2000, Math.floor((wCanvas.width * wCanvas.height) / 600))
  windParticles = []
  for (let i = 0; i < count; i++) {
    windParticles.push({
      x: Math.random() * wCanvas.width,
      y: Math.random() * wCanvas.height,
      age: Math.random() * 100,
      maxAge: 80 + Math.random() * 120,
    })
  }
}

function getWindAt(lat, lng) {
  if (!fieldData || !fieldData.lats || !fieldData.u) return { u: 0, v: 0, speed: 0 }
  const { lats, lons, u, v, speed } = fieldData

  lat = Math.max(lats[0], Math.min(lats[lats.length - 1], lat))
  lng = Math.max(lons[0], Math.min(lons[lons.length - 1], lng))

  const step = lats[1] - lats[0]
  const i0 = Math.floor((lat - lats[0]) / step), j0 = Math.floor((lng - lons[0]) / step)
  const i1 = i0 + 1, j1 = j0 + 1
  if (i0 < 0 || i1 >= lats.length || j0 < 0 || j1 >= lons.length) return { u: 0, v: 0, speed: 0 }

  const ti = (lat - lats[i0]) / step, tj = (lng - lons[j0]) / step
  const get = (arr) => {
    const a00 = arr[i0]?.[j0] || 0, a10 = arr[i1]?.[j0] || 0
    const a01 = arr[i0]?.[j1] || 0, a11 = arr[i1]?.[j1] || 0
    return (1 - ti) * (1 - tj) * a00 + ti * (1 - tj) * a10 + (1 - ti) * tj * a01 + ti * tj * a11
  }
  return { u: get(u), v: get(v), speed: get(speed) }
}

function startWindAnim() {
  if (windAnimId) cancelAnimationFrame(windAnimId)
  prevTime = performance.now()
  windAnimId = requestAnimationFrame(animateWind)
}

function animateWind(now) {
  windAnimId = requestAnimationFrame(animateWind)
  if (!wCanvas || activeLayer.value !== 'wind' || !fieldData) return

  const dt = Math.min((now - prevTime) / 1000, 0.1)
  prevTime = now

  const ctx = wCanvas.getContext('2d')
  const w = wCanvas.width, h = wCanvas.height
  ctx.clearRect(0, 0, w, h)

  const maxSpeed = fieldData.max_speed || 30
  ctx.lineWidth = 1.4
  ctx.lineCap = 'round'

  for (const p of windParticles) {
    p.age += dt * 60
    if (p.age >= p.maxAge) {
      p.x = Math.random() * w; p.y = Math.random() * h
      p.age = 0; p.maxAge = 80 + Math.random() * 120
    }

    const latlng = map.layerPointToLatLng(L.point(canvasOffset.x + p.x, canvasOffset.y + p.y))
    const wind = getWindAt(latlng.lat, latlng.lng)

    const nx = p.x + wind.u * dt * 3, ny = p.y + wind.v * dt * 3

    const alpha = Math.sin((p.age / p.maxAge) * Math.PI) * 0.7
    // Black/dark particles — speed controls opacity (stronger = darker)
    const k = Math.min(wind.speed / maxSpeed, 1)
    const grey = Math.round(60 - k * 60)  // 60 (light grey) → 0 (black)
    ctx.strokeStyle = `rgba(${grey},${grey},${grey},${alpha})`

    ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(nx, ny); ctx.stroke()

    p.x = nx; p.y = ny
    if (p.x < -20) p.x = w + 20; if (p.x > w + 20) p.x = -20
    if (p.y < -20) p.y = h + 20; if (p.y > h + 20) p.y = -20
  }
}

// ---- Layer ----
function onLayerChange(layerId) {
  emit('layerChange', layerId)
  if (windAnimId) { cancelAnimationFrame(windAnimId); windAnimId = null }
  syncCanvas()
  loadField()
}

// ---- City search (local database, no network) ----
function searchCities(query, cb) {
  if (!query || query.trim().length < 1) { cb([]); return }
  const q = query.trim().toLowerCase()
  const results = CHINESE_CITIES
    .filter(c => c.name.toLowerCase().includes(q) || (c.pinyin && c.pinyin.includes(q)))
    .slice(0, 8)
    .map(c => ({
      value: c.name,
      display_name: `${c.name} (${c.lat.toFixed(2)}°, ${c.lon.toFixed(2)}°)`,
      lat: c.lat,
      lon: c.lon,
    }))
  cb(results)
}

function onSearchSelect(item) {
  if (!item || !map) return
  map.setView([item.lat, item.lon], 8, { animate: true })
  emit('pointSelect', { lat: item.lat, lon: item.lon })
}

function refresh() { error.value = null; loadField() }

defineExpose({ activeLayer, refresh })
</script>

<style scoped>
.weather-map-wrapper { position: relative; width: 100%; height: 100%; }
.map-container { width: 100%; height: 100%; }

.map-loading, .map-error {
  position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
  z-index: 1000; background: rgba(255,255,255,0.95);
  padding: 16px 24px; border-radius: 8px; display: flex;
  align-items: center; gap: 8px; box-shadow: 0 2px 12px rgba(0,0,0,0.15); font-size: 14px;
}
.map-error { color: #e74c3c; flex-direction: column; gap: 8px; }

.layer-switcher {
  position: absolute; top: 12px; left: 50%; transform: translateX(-50%);
  z-index: 500; background: rgba(255,255,255,0.95);
  border-radius: 6px; padding: 4px; box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}
.city-search { position: absolute; top: 12px; right: 12px; z-index: 500; width: 240px; }

.search-item { display: flex; flex-direction: column; gap: 2px; }
.search-name { font-weight: 600; font-size: 13px; color: #303133; }
.search-detail { font-size: 11px; color: #909399; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
</style>

<style>
.city-search-popper { z-index: 2000 !important; }
.weather-canvas-leaflet {
  position: absolute;
  pointer-events: none !important;
  image-rendering: auto;
}
.leaflet-tile {
  background: transparent !important;
}
.leaflet-tile-retrying {
  opacity: 0;
}
.leaflet-tile-fallback-empty {
  display: none;
}
.leaflet-container {
  background: #d8e1e4 !important;
}
</style>
