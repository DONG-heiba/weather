<template>
  <div class="weather-panel">
    <h3 class="panel-title">📍 单点天气</h3>

    <!-- No point selected -->
    <div v-if="!point && !loading" class="panel-hint">
      <p>点击地图任意位置<br />或搜索城市查看天气</p>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="panel-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
    </div>

    <!-- Error -->
    <div v-if="error" class="panel-error">
      <span>{{ error }}</span>
    </div>

    <!-- Weather data -->
    <div v-if="point && !loading" class="panel-content">
      <div class="point-header">
        <span class="point-coords">{{ point.query.lat.toFixed(2) }}°N, {{ point.query.lon.toFixed(2) }}°E</span>
        <span class="grid-info">最近格点: {{ point.nearest_grid.lat }}°N, {{ point.nearest_grid.lon }}°E</span>
      </div>

      <div class="point-time">
        <el-icon><Clock /></el-icon>
        {{ formatTime(point.time_iso) }}
      </div>

      <el-divider />

      <!-- Main weather variables -->
      <div class="weather-grid">
        <div class="weather-item" v-for="item in weatherItems" :key="item.key">
          <div class="item-icon">{{ item.icon }}</div>
          <div class="item-info">
            <div class="item-value">{{ item.value }}</div>
            <div class="item-label">{{ item.label }}</div>
          </div>
        </div>
      </div>

      <el-divider />

      <!-- Wind detail -->
      <div class="wind-detail" v-if="point.wind_speed != null">
        <div class="detail-row">
          <span class="detail-label">💨 风速</span>
          <span class="detail-value">{{ point.wind_speed }} m/s</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">🧭 风向</span>
          <span class="detail-value">
            {{ point.wind_direction_text }} ({{ point.wind_direction }}°)
          </span>
        </div>
      </div>

      <el-divider />

      <!-- Current layer value -->
      <div class="current-layer" v-if="currentLayerValue != null">
        <div class="detail-row highlight">
          <span class="detail-label">
            {{ layerName }} {{ layerUnit ? '(' + layerUnit + ')' : '' }}
          </span>
          <span class="detail-value">{{ currentLayerValue }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Clock, Loading } from '@element-plus/icons-vue'

const props = defineProps({
  point: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  error: { type: String, default: null },
  activeLayer: { type: String, default: 'temperature' },
})

const layerNames = {
  temperature: '温度',
  precipitation: '降雨',
  wind: '风速',
  clouds: '云量',
  pressure: '气压',
}

const layerUnits = {
  temperature: '°C',
  precipitation: 'mm/h',
  wind: 'm/s',
  clouds: '%',
  pressure: 'hPa',
}

const layerName = computed(() => layerNames[props.activeLayer] || props.activeLayer)
const layerUnit = computed(() => layerUnits[props.activeLayer] || '')

const weatherItems = computed(() => {
  if (!props.point) return []
  return [
    {
      key: 'temperature',
      icon: '🌡️',
      value: props.point.temperature != null ? `${props.point.temperature}°C` : '--',
      label: '温度',
    },
    {
      key: 'wind',
      icon: '💨',
      value: props.point.wind_speed != null ? `${props.point.wind_speed} m/s` : '--',
      label: '风速',
    },
    {
      key: 'precipitation',
      icon: '🌧️',
      value: props.point.precipitation != null ? `${props.point.precipitation} mm/h` : '--',
      label: '降雨',
    },
    {
      key: 'clouds',
      icon: '☁️',
      value: props.point.clouds != null ? `${props.point.clouds}%` : '--',
      label: '云量',
    },
    {
      key: 'pressure',
      icon: '📊',
      value: props.point.pressure != null ? `${props.point.pressure} hPa` : '--',
      label: '气压',
    },
  ]
})

const currentLayerValue = computed(() => {
  if (!props.point || !props.point.layers) return null
  const lv = props.point.layers[props.activeLayer]
  if (!lv) return null
  return `${lv.value} ${lv.unit}`
})

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const h = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  return `${y}-${m}-${day} ${h}:${min} (UTC)`
}
</script>

<style scoped>
.weather-panel {
  background: rgba(255, 255, 255, 0.95);
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  min-height: 200px;
  overflow-y: auto;
  font-size: 13px;
}

.panel-title {
  margin: 0 0 12px 0;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.panel-hint {
  color: #909399;
  text-align: center;
  padding: 32px 0;
  line-height: 1.8;
}

.panel-loading {
  text-align: center;
  padding: 32px 0;
  font-size: 24px;
  color: #409eff;
}

.panel-error {
  color: #e74c3c;
  padding: 12px 0;
}

.point-header {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.point-coords {
  font-size: 16px;
  font-weight: 700;
  color: #303133;
  font-family: 'Courier New', monospace;
  letter-spacing: 1px;
}

.grid-info {
  font-size: 11px;
  color: #a8abb2;
}

.point-time {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
  font-size: 12px;
  color: #606266;
}

.weather-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.weather-item {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #f5f7fa;
  padding: 8px 10px;
  border-radius: 6px;
}

.item-icon {
  font-size: 18px;
}

.item-value {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.item-label {
  font-size: 11px;
  color: #909399;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
}

.detail-row.highlight {
  background: #ecf5ff;
  padding: 8px 10px;
  border-radius: 6px;
  margin-top: 2px;
}

.detail-label {
  color: #606266;
}

.detail-value {
  font-weight: 600;
  color: #303133;
  font-size: 14px;
}

:deep(.el-divider) {
  margin: 10px 0;
}
</style>
