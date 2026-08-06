<template>
  <div class="time-control">
    <!-- Current time display -->
    <div class="time-display" v-if="currentTime">
      <el-icon><Clock /></el-icon>
      <span class="time-text">{{ formatTime(currentTime) }}</span>
      <el-tag size="small" type="info">UTC</el-tag>
      <span class="time-index">({{ timeIdx + 1 }} / {{ totalTimes }})</span>
    </div>
    <div class="time-display" v-else>
      <el-icon><Clock /></el-icon>
      <span class="time-text">加载中...</span>
    </div>

    <!-- Transport controls -->
    <div class="transport-controls">
      <el-button-group>
        <el-button size="small" @click="prev" :disabled="timeIdx <= 0">
          <el-icon><DArrowLeft /></el-icon>
        </el-button>
        <el-button
          size="small"
          @click="togglePlay"
          :type="playing ? 'primary' : 'default'"
        >
          <el-icon v-if="!playing"><VideoPlay /></el-icon>
          <el-icon v-else><VideoPause /></el-icon>
        </el-button>
        <el-button size="small" @click="reset">
          <el-icon><RefreshLeft /></el-icon>
        </el-button>
        <el-button size="small" @click="next" :disabled="timeIdx >= totalTimes - 1">
          <el-icon><DArrowRight /></el-icon>
        </el-button>
      </el-button-group>
    </div>

    <!-- Speed control -->
    <div class="speed-control">
      <span class="speed-label">速度</span>
      <el-select
        v-model="speed"
        size="small"
        style="width: 90px"
        @change="onSpeedChange"
      >
        <el-option
          v-for="s in speedOptions"
          :key="s.value"
          :label="s.label"
          :value="s.value"
        />
      </el-select>
    </div>

    <!-- Time slider -->
    <div class="slider-container">
      <el-slider
        v-model="sliderValue"
        :min="0"
        :max="totalTimes - 1"
        :step="1"
        :show-tooltip="true"
        :format-tooltip="formatSliderTooltip"
        @input="onSliderInput"
        @change="onSliderChange"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import {
  Clock,
  DArrowLeft,
  DArrowRight,
  VideoPlay,
  VideoPause,
  RefreshLeft,
} from '@element-plus/icons-vue'

const props = defineProps({
  times: { type: Array, default: () => [] },
  timeIdx: { type: Number, default: 0 },
})

const emit = defineEmits(['update:timeIdx', 'timeChange'])

const playing = ref(false)
const speed = ref(1000)
const sliderValue = ref(0)
let playTimer = null

const speedOptions = [
  { label: '0.5x', value: 2000 },
  { label: '1x', value: 1000 },
  { label: '2x', value: 500 },
  { label: '4x', value: 250 },
  { label: '8x', value: 125 },
]

const totalTimes = computed(() => props.times.length)
const currentTime = computed(() => props.times[props.timeIdx] || null)

// Sync slider with prop
watch(
  () => props.timeIdx,
  (val) => {
    sliderValue.value = val
  }
)

function changeTime(newIdx) {
  const idx = Math.max(0, Math.min(totalTimes.value - 1, newIdx))
  emit('update:timeIdx', idx)
  emit('timeChange', idx)
}

function prev() {
  changeTime(props.timeIdx - 1)
}

function next() {
  changeTime(props.timeIdx + 1)
}

function reset() {
  playing.value = false
  clearPlayTimer()
  changeTime(0)
}

function togglePlay() {
  playing.value = !playing.value
  if (playing.value) {
    startPlay()
  } else {
    clearPlayTimer()
  }
}

function startPlay() {
  clearPlayTimer()
  playTimer = setInterval(() => {
    if (props.timeIdx >= totalTimes.value - 1) {
      playing.value = false
      clearPlayTimer()
      return
    }
    changeTime(props.timeIdx + 1)
  }, speed.value)
}

function clearPlayTimer() {
  if (playTimer) {
    clearInterval(playTimer)
    playTimer = null
  }
}

function onSpeedChange() {
  if (playing.value) {
    startPlay()
  }
}

function onSliderInput(val) {
  sliderValue.value = val
}

function onSliderChange(val) {
  changeTime(val)
}

function formatSliderTooltip(val) {
  const t = props.times[val]
  if (!t) return ''
  const d = new Date(t)
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:00`
}

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const h = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  return `${y}-${m}-${day} ${h}:${min}`
}

onBeforeUnmount(() => {
  clearPlayTimer()
})
</script>

<style scoped>
.time-control {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 8px 16px;
  background: rgba(255, 255, 255, 0.95);
  border-top: 1px solid #e4e7ed;
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.05);
}

.time-display {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 220px;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.time-index {
  font-size: 11px;
  color: #909399;
  font-weight: 400;
}

.transport-controls {
  display: flex;
  align-items: center;
}

.speed-control {
  display: flex;
  align-items: center;
  gap: 6px;
}

.speed-label {
  font-size: 12px;
  color: #909399;
}

.slider-container {
  flex: 1;
  min-width: 200px;
}
</style>
