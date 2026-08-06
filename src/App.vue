<template>
  <div class="app-root">
    <!-- Initial loading state -->
    <div v-if="initLoading" class="app-init-loading">
      <el-icon class="is-loading init-icon"><Loading /></el-icon>
      <h2>正在初始化天气预报系统...</h2>
      <p class="init-text">检查数据源连接</p>
    </div>

    <!-- Error state -->
    <div v-else-if="initError" class="app-init-error">
      <el-icon class="error-icon"><WarningFilled /></el-icon>
      <h2>系统初始化失败</h2>
      <p>{{ initError }}</p>
      <el-button type="primary" @click="initApp">重新加载</el-button>
    </div>

    <!-- Main application -->
    <template v-else>
      <!-- Header -->
      <header class="app-header">
        <div class="header-left">
          <h1 class="header-title">🌤️ 2026 年 8 月天气预报可视化</h1>
          <span class="header-badge">Open-Meteo / ECMWF IFS</span>
        </div>
        <div class="header-right">
          <el-tag
            :type="healthOk ? 'success' : 'danger'"
            size="small"
            effect="plain"
          >
            {{ healthOk ? '数据正常' : '数据异常' }}
          </el-tag>
          <span class="header-update" v-if="dataUpdateTime">
            数据更新: {{ dataUpdateTime }}
          </span>
        </div>
      </header>

      <!-- Main content area -->
      <div class="app-main">
        <!-- Map -->
        <div class="map-area">
          <WeatherMap
            ref="weatherMapRef"
            :time-idx="timeIdx"
            @point-select="onPointSelect"
            @layer-change="onLayerChange"
          />
        </div>

        <!-- Right panel -->
        <aside class="side-panel">
          <WeatherPanel
            :point="selectedPoint"
            :loading="pointLoading"
            :error="pointError"
            :active-layer="activeLayer"
          />
        </aside>
      </div>

      <!-- Bottom controls -->
      <footer class="app-footer">
        <div class="footer-top">
          <LegendBar
            :layer="currentLayerDef"
            :field-data="currentFieldData"
            :sources="sources"
          />
        </div>
        <TimeControl
          :times="times"
          :time-idx="timeIdx"
          @update:time-idx="onTimeChange"
          @time-change="onTimeChange"
        />
      </footer>
    </template>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Loading, WarningFilled } from '@element-plus/icons-vue'
import WeatherMap from './components/WeatherMap.vue'
import WeatherPanel from './components/WeatherPanel.vue'
import TimeControl from './components/TimeControl.vue'
import LegendBar from './components/LegendBar.vue'
import { fetchHealth, fetchMeta, fetchField, fetchPoint } from './api/index.js'

// -----------------------------------------------------------------------
// State
// -----------------------------------------------------------------------

const initLoading = ref(true)
const initError = ref(null)
const healthOk = ref(false)
const dataUpdateTime = ref(null)

const times = ref([])
const layers = ref([])
const places = ref([])
const sources = ref({ weather: '', map: '' })

const timeIdx = ref(0)
const activeLayer = ref('temperature')
const selectedPoint = ref(null)
const pointLoading = ref(false)
const pointError = ref(null)
const currentFieldData = ref(null)

const weatherMapRef = ref(null)

// -----------------------------------------------------------------------
// Computed helpers
// -----------------------------------------------------------------------

const currentLayerDef = ref(null)

function getLayerDef(id) {
  return layers.value.find((l) => l.id === id) || null
}

// -----------------------------------------------------------------------
// Initialization
// -----------------------------------------------------------------------

onMounted(async () => {
  await initApp()
})

async function initApp() {
  initLoading.value = true
  initError.value = null

  try {
    // Check health
    const health = await fetchHealth()
    healthOk.value = health.status === 'ok'

    // Load metadata
    const meta = await fetchMeta()
    times.value = meta.times
    layers.value = meta.layers
    places.value = meta.places
    sources.value = meta.sources
    currentLayerDef.value = getLayerDef('temperature')
    dataUpdateTime.value = meta.time_start

    // Load initial field data
    const field = await fetchField('temperature', 0)
    currentFieldData.value = field

    initLoading.value = false
  } catch (e) {
    console.error('Init failed:', e)
    initError.value = '无法连接到后端服务，请确认已启动: python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000'
    initLoading.value = false
  }
}

// -----------------------------------------------------------------------
// Event handlers
// -----------------------------------------------------------------------

async function onPointSelect({ lat, lon }) {
  pointLoading.value = true
  pointError.value = null
  selectedPoint.value = null

  try {
    const url = `/api/point?lat=${lat}&lon=${lon}&time_idx=${timeIdx.value}`
    const res = await fetch(url)
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail || `HTTP ${res.status}`)
    }
    const pt = await res.json()
    selectedPoint.value = { ...pt }
  } catch (e) {
    pointError.value = '获取点天气数据失败: ' + e.message
    selectedPoint.value = null
  } finally {
    pointLoading.value = false
  }
}

function onLayerChange(layerId) {
  activeLayer.value = layerId
  currentLayerDef.value = getLayerDef(layerId)
  loadFieldData(layerId, timeIdx.value)
}

function onTimeChange(newTimeIdx) {
  timeIdx.value = newTimeIdx
  loadFieldData(activeLayer.value, newTimeIdx)

  // Refresh point data if a point is selected
  if (selectedPoint.value) {
    onPointSelect({
      lat: selectedPoint.value.query.lat,
      lon: selectedPoint.value.query.lon,
    })
  }
}

async function loadFieldData(layer, idx) {
  try {
    const field = await fetchField(layer, idx)
    currentFieldData.value = field
  } catch (e) {
    console.error('Field data load error:', e)
  }
}
</script>

<style>
/* -----------------------------------------------------------------------
 * Global reset & Leaflet overrides
 * ----------------------------------------------------------------------- */
*,
*::before,
*::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html,
body {
  height: 100%;
  overflow: hidden;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
    'Helvetica Neue', Arial, 'Noto Sans', 'PingFang SC', 'Microsoft YaHei',
    sans-serif;
  font-size: 14px;
  color: #303133;
  background: #f0f2f5;
}

#app {
  height: 100%;
}

/* Leaflet container fix */
.leaflet-container {
  background: #e8f0f8 !important;
}

/* Canvas overlay */
.weather-canvas {
  pointer-events: none !important;
  z-index: 450 !important;
}
</style>

<style scoped>
.app-root {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

/* -----------------------------------------------------------------------
 * Init states
 * ----------------------------------------------------------------------- */
.app-init-loading,
.app-init-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100vh;
  gap: 16px;
  background: #f0f2f5;
}

.init-icon,
.error-icon {
  font-size: 48px;
  color: #409eff;
}

.error-icon {
  color: #e74c3c;
}

.app-init-error h2 {
  color: #e74c3c;
}

.app-init-error p {
  color: #606266;
  max-width: 500px;
  text-align: center;
}

.init-text {
  color: #909399;
}

/* -----------------------------------------------------------------------
 * Header
 * ----------------------------------------------------------------------- */
.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  background: linear-gradient(135deg, #1a73e8, #0d47a1);
  color: #fff;
  flex-shrink: 0;
  z-index: 10;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-title {
  font-size: 18px;
  font-weight: 600;
  letter-spacing: 1px;
}

.header-badge {
  font-size: 11px;
  background: rgba(255, 255, 255, 0.2);
  padding: 2px 8px;
  border-radius: 10px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-update {
  font-size: 11px;
  opacity: 0.85;
}

/* -----------------------------------------------------------------------
 * Main content
 * ----------------------------------------------------------------------- */
.app-main {
  flex: 1;
  display: flex;
  overflow: hidden;
  min-height: 0;
}

.map-area {
  flex: 1;
  position: relative;
  overflow: hidden;
}

.side-panel {
  width: 300px;
  flex-shrink: 0;
  overflow-y: auto;
  border-left: 1px solid #e4e7ed;
  background: #fafafa;
  z-index: 5;
}

/* -----------------------------------------------------------------------
 * Footer
 * ----------------------------------------------------------------------- */
.app-footer {
  flex-shrink: 0;
  z-index: 5;
}

/* -----------------------------------------------------------------------
 * Responsive
 * ----------------------------------------------------------------------- */
@media (max-width: 900px) {
  .app-main {
    flex-direction: column;
  }

  .side-panel {
    width: 100%;
    max-height: 40vh;
    border-left: none;
    border-top: 1px solid #e4e7ed;
  }

  .header-title {
    font-size: 14px;
  }

  .header-badge {
    display: none;
  }
}
</style>
