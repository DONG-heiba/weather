<template>
  <div class="legend-bar">
    <!-- Color scale bar -->
    <div class="color-scale">
      <span class="legend-title">{{ layerName }}</span>
      <canvas ref="gradientCanvas" class="gradient-canvas"></canvas>
      <div class="scale-labels">
        <span class="scale-label">{{ rangeMin }}</span>
        <span v-if="rangeMid != null" class="scale-label scale-mid">{{ rangeMid }}</span>
        <span class="scale-label">{{ rangeMax }}</span>
      </div>
      <span class="unit-label">{{ unit }}</span>
    </div>

    <!-- Layer description -->
    <div class="legend-desc" v-if="description">
      <span>{{ description }}</span>
    </div>

    <!-- Statistics -->
    <div class="legend-stats" v-if="stats">
      <span class="stat-item">
        范围: {{ rangeMin }} – {{ rangeMax }} {{ unit }}
      </span>
      <span class="stat-sep">|</span>
      <span class="stat-item">
        均值: {{ stats.avg }}
      </span>
    </div>

    <!-- Sources -->
    <div class="legend-sources">
      <span class="source-item">
        🌐 天气数据: {{ weatherSource }}
      </span>
      <span class="source-sep">|</span>
      <span class="source-item">
        🗺️ 地图: {{ mapSource }}
      </span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { temperatureColor, precipitationColor, cloudsColor, pressureColor, windColor } from '../api/index.js'

const props = defineProps({
  layer: { type: Object, default: null },
  fieldData: { type: Object, default: null },
  sources: { type: Object, default: () => ({ weather: '', map: '' }) },
})

const gradientCanvas = ref(null)

const layerName = computed(() => props.layer?.name || '')
const unit = computed(() => props.layer?.unit || '')
const description = computed(() => props.layer?.description || '')
const weatherSource = computed(() => props.sources?.weather || '')
const mapSource = computed(() => props.sources?.map || '')

const rangeMin = computed(() => {
  if (!props.fieldData) return '--'
  return props.fieldData.min != null ? props.fieldData.min : '--'
})

const rangeMax = computed(() => {
  if (!props.fieldData) return '--'
  return props.fieldData.max != null ? props.fieldData.max : '--'
})

const rangeMid = computed(() => {
  if (!props.fieldData || props.fieldData.min == null || props.fieldData.max == null) return null
  return ((props.fieldData.min + props.fieldData.max) / 2).toFixed(1)
})

const stats = computed(() => {
  if (!props.fieldData) return null
  const values = props.fieldData.values
  if (!values) return null
  let sum = 0, count = 0
  for (const row of values) {
    for (const v of row) {
      if (v != null && !isNaN(v)) {
        sum += v
        count++
      }
    }
  }
  if (count === 0) return null
  return { avg: (sum / count).toFixed(1) }
})

function drawGradient() {
  if (!gradientCanvas.value) return
  const canvas = gradientCanvas.value
  const ctx = canvas.getContext('2d')
  const w = canvas.width
  const h = canvas.height

  const layerId = props.layer?.id || 'temperature'
  const min = props.fieldData?.min ?? 0
  const max = props.fieldData?.max ?? 1

  for (let x = 0; x < w; x++) {
    const t = x / (w - 1)
    const val = min + t * (max - min)
    let color
    if (layerId === 'temperature') {
      color = temperatureColor(val, min, max)
    } else if (layerId === 'precipitation') {
      color = precipitationColor(val, max)
    } else if (layerId === 'clouds') {
      color = cloudsColor(val)
    } else if (layerId === 'pressure') {
      color = pressureColor(val, min, max)
    } else if (layerId === 'wind') {
      color = windColor(val, max)
    } else {
      color = 'gray'
    }
    ctx.fillStyle = color
    ctx.fillRect(x, 0, 1, h)
  }
}

watch(
  () => [props.layer, props.fieldData],
  () => {
    nextTick(() => drawGradient())
  },
  { deep: true }
)

onMounted(() => {
  nextTick(() => drawGradient())
})
</script>

<style scoped>
.legend-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  padding: 8px 16px;
  background: rgba(255, 255, 255, 0.95);
  border-top: 1px solid #e4e7ed;
  font-size: 12px;
  color: #606266;
}

.color-scale {
  display: flex;
  align-items: center;
  gap: 8px;
}

.legend-title {
  font-weight: 600;
  color: #303133;
  min-width: 36px;
}

.gradient-canvas {
  width: 120px;
  height: 14px;
  border-radius: 3px;
  border: 1px solid #dcdfe6;
}

.scale-labels {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  font-size: 10px;
  color: #909399;
  line-height: 1;
}

.unit-label {
  font-size: 11px;
  color: #909399;
  font-weight: 500;
}

.legend-desc {
  color: #909399;
  font-size: 11px;
  max-width: 280px;
}

.legend-stats {
  display: flex;
  align-items: center;
  gap: 6px;
}

.stat-sep,
.source-sep {
  color: #dcdfe6;
}

.legend-sources {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #909399;
  font-size: 11px;
  margin-left: auto;
}

@media (max-width: 900px) {
  .legend-bar {
    gap: 8px;
    flex-direction: column;
    align-items: flex-start;
  }
  .legend-sources {
    margin-left: 0;
  }
}
</style>
