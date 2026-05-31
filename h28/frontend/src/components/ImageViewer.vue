<template>
  <div class="image-viewer" ref="viewerRef">
    <div class="viewer-toolbar">
      <div class="toolbar-left">
        <el-button
          size="small"
          :icon="ZoomOut"
          @click="handleZoomOut"
          :disabled="scale <= minScale"
        />
        <span class="zoom-value">{{ Math.round(scale * 100) }}%</span>
        <el-button
          size="small"
          :icon="ZoomIn"
          @click="handleZoomIn"
          :disabled="scale >= maxScale"
        />
        <el-button
          size="small"
          :icon="RefreshLeft"
          @click="handleReset"
        />
        <el-button
          size="small"
          :icon="FullScreen"
          @click="handleFitWidth"
        />
      </div>
      <div class="toolbar-right">
        <el-tooltip content="显示检测框">
          <el-button
            size="small"
            :type="showBoxes ? 'primary' : 'default'"
            :icon="Grid"
            @click="showBoxes = !showBoxes"
          />
        </el-tooltip>
        <el-tooltip content="显示文字">
          <el-button
            size="small"
            :type="showText ? 'primary' : 'default'"
            :icon="Tickets"
            @click="showText = !showText"
          />
        </el-tooltip>
      </div>
    </div>

    <div
      class="viewer-container"
      ref="containerRef"
      @wheel.prevent="handleWheel"
      @mousedown="handleMouseDown"
      @mousemove="handleMouseMove"
      @mouseup="handleMouseUp"
      @mouseleave="handleMouseUp"
    >
      <div
        class="image-wrapper"
        :style="wrapperStyle"
      >
        <img
          :src="imageUrl"
          :alt="alt"
          class="viewer-image"
          @load="handleImageLoad"
          draggable="false"
        />

        <svg
          v-if="showBoxes"
          class="boxes-overlay"
          :width="imageWidth"
          :height="imageHeight"
        >
          <g v-for="line in textLines" :key="line.id">
            <polygon
              :points="getBoxPoints(line.textBox)"
              :class="['text-box', { 'is-selected': selectedLineId === line.id }]"
              :style="{ fill: getBoxColor(line.textBox.confidence) }"
              @click.stop="handleBoxClick(line)"
            />
            <text
              v-if="showText"
              :x="getBoxCenter(line.textBox).x"
              :y="getBoxCenter(line.textBox).y"
              class="box-text"
              text-anchor="middle"
              dominant-baseline="middle"
            >
              {{ line.content }}
            </text>
          </g>
        </svg>
      </div>
    </div>

    <div class="viewer-footer">
      <div class="footer-info">
        <span v-if="imageLoaded">
          尺寸: {{ imageWidth }} × {{ imageHeight }} 像素
        </span>
      </div>
      <div class="footer-hint">
        <el-tag size="small" type="info">滚轮缩放</el-tag>
        <el-tag size="small" type="info">拖拽平移</el-tag>
        <el-tag size="small" type="info">点击框选文字</el-tag>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, watch, onMounted, onUnmounted } from 'vue';
import { ZoomIn, ZoomOut, RefreshLeft, FullScreen, Grid, Tickets } from '@element-plus/icons-vue';
import type { TextLine, TextBox } from '../types';

const props = defineProps<{
  imageUrl: string;
  textLines?: TextLine[];
  selectedLineId?: string;
  minScale?: number;
  maxScale?: number;
  stepScale?: number;
  alt?: string;
}>();

const emit = defineEmits<{
  (e: 'line-click', line: TextLine): void;
  (e: 'scale-change', scale: number): void;
  (e: 'image-load', info: { width: number; height: number }): void;
}>();

const viewerRef = ref<HTMLDivElement | null>(null);
const containerRef = ref<HTMLDivElement | null>(null);
const imageWidth = ref(0);
const imageHeight = ref(0);
const imageLoaded = ref(false);
const showBoxes = ref(true);
const showText = ref(false);

const scale = ref(1);
const minScale = computed(() => props.minScale || 0.25);
const maxScale = computed(() => props.maxScale || 4);
const stepScale = computed(() => props.stepScale || 0.1);

const transform = reactive({
  x: 0,
  y: 0
});

const isDragging = ref(false);
const dragStart = reactive({
  x: 0,
  y: 0,
  startX: 0,
  startY: 0
});

const wrapperStyle = computed(() => ({
  transform: `translate(${transform.x}px, ${transform.y}px) scale(${scale.value})`,
  transformOrigin: 'top left',
  width: imageWidth.value + 'px',
  height: imageHeight.value + 'px'
}));

const getBoxPoints = (box: TextBox): string => {
  return `${box.x1},${box.y1} ${box.x2},${box.y2} ${box.x3},${box.y3} ${box.x4},${box.y4}`;
};

const getBoxCenter = (box: TextBox): { x: number; y: number } => {
  const x = (box.x1 + box.x2 + box.x3 + box.x4) / 4;
  const y = (box.y1 + box.y2 + box.y3 + box.y4) / 4;
  return { x, y };
};

const getBoxColor = (confidence: number): string => {
  const alpha = 0.15 + (confidence * 0.2);
  if (confidence >= 0.9) return `rgba(103, 194, 58, ${alpha})`;
  if (confidence >= 0.7) return `rgba(230, 162, 60, ${alpha})`;
  return `rgba(196, 30, 58, ${alpha})`;
};

const handleImageLoad = (e: Event) => {
  const img = e.target as HTMLImageElement;
  imageWidth.value = img.naturalWidth;
  imageHeight.value = img.naturalHeight;
  imageLoaded.value = true;
  emit('image-load', { width: imageWidth.value, height: imageHeight.value });
};

const handleWheel = (e: WheelEvent) => {
  if (!containerRef.value) return;

  const delta = e.deltaY > 0 ? -stepScale.value : stepScale.value;
  const newScale = Math.max(minScale.value, Math.min(maxScale.value, scale.value + delta));

  const rect = containerRef.value.getBoundingClientRect();
  const mouseX = e.clientX - rect.left;
  const mouseY = e.clientY - rect.top;

  const scaleChange = newScale / scale.value;
  transform.x = mouseX - (mouseX - transform.x) * scaleChange;
  transform.y = mouseY - (mouseY - transform.y) * scaleChange;

  scale.value = newScale;
  emit('scale-change', scale.value);
};

const handleZoomIn = () => {
  const newScale = Math.min(maxScale.value, scale.value + stepScale.value * 2);
  scale.value = newScale;
  emit('scale-change', scale.value);
};

const handleZoomOut = () => {
  const newScale = Math.max(minScale.value, scale.value - stepScale.value * 2);
  scale.value = newScale;
  emit('scale-change', scale.value);
};

const handleReset = () => {
  scale.value = 1;
  transform.x = 0;
  transform.y = 0;
  emit('scale-change', scale.value);
};

const handleFitWidth = () => {
  if (!containerRef.value || !imageWidth.value) return;
  
  const containerWidth = containerRef.value.clientWidth - 40;
  const newScale = Math.min(containerWidth / imageWidth.value, maxScale.value);
  
  scale.value = newScale;
  transform.x = 20;
  transform.y = 20;
  emit('scale-change', scale.value);
};

const handleMouseDown = (e: MouseEvent) => {
  if (e.button !== 0) return;
  if ((e.target as HTMLElement).tagName === 'polygon' || (e.target as HTMLElement).tagName === 'text') return;

  isDragging.value = true;
  dragStart.x = e.clientX;
  dragStart.y = e.clientY;
  dragStart.startX = transform.x;
  dragStart.startY = transform.y;

  if (containerRef.value) {
    containerRef.value.style.cursor = 'grabbing';
  }
};

const handleMouseMove = (e: MouseEvent) => {
  if (!isDragging.value) return;

  const dx = e.clientX - dragStart.x;
  const dy = e.clientY - dragStart.y;

  transform.x = dragStart.startX + dx;
  transform.y = dragStart.startY + dy;
};

const handleMouseUp = () => {
  isDragging.value = false;
  if (containerRef.value) {
    containerRef.value.style.cursor = 'grab';
  }
};

const handleBoxClick = (line: TextLine) => {
  emit('line-click', line);
};

watch(() => props.selectedLineId, (newId) => {
  if (newId && imageLoaded.value && props.textLines) {
    const line = props.textLines.find(l => l.id === newId);
    if (line) {
      scrollToBox(line.textBox);
    }
  }
});

const scrollToBox = (box: TextBox) => {
  if (!containerRef.value) return;

  const center = getBoxCenter(box);
  const containerRect = containerRef.value.getBoundingClientRect();

  const targetX = containerRect.width / 2 - center.x * scale.value;
  const targetY = containerRect.height / 2 - center.y * scale.value;

  transform.x = targetX;
  transform.y = targetY;
};

const handleKeyDown = (e: KeyboardEvent) => {
  if (e.key === '+' || e.key === '=') {
    handleZoomIn();
  } else if (e.key === '-') {
    handleZoomOut();
  } else if (e.key === '0') {
    handleReset();
  }
};

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown);
  if (containerRef.value) {
    containerRef.value.style.cursor = 'grab';
  }
});

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown);
});
</script>

<style lang="scss" scoped>
.image-viewer {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 400px;
  background: var(--color-rice-paper-light);
  border: 1px solid var(--color-rice-paper-dark);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.viewer-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: var(--color-rice-paper);
  border-bottom: 1px solid var(--color-rice-paper-dark);
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 4px;
}

.zoom-value {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-ink-light);
  min-width: 50px;
  text-align: center;
}

.viewer-container {
  flex: 1;
  overflow: hidden;
  position: relative;
  background: repeating-conic-gradient(#E8E0D0 0% 25%, #FAF7F0 0% 50%) 50% / 20px 20px;
}

.image-wrapper {
  position: relative;
  will-change: transform;
  user-select: none;
}

.viewer-image {
  display: block;
  max-width: none;
  user-select: none;
  -webkit-user-drag: none;
}

.boxes-overlay {
  position: absolute;
  top: 0;
  left: 0;
  pointer-events: none;
}

.text-box {
  stroke: var(--color-vermilion);
  stroke-width: 2;
  cursor: pointer;
  pointer-events: auto;
  transition: all var(--transition-fast);

  &:hover {
    stroke-width: 3;
    fill-opacity: 0.4;
  }

  &.is-selected {
    stroke: var(--color-vermilion);
    stroke-width: 3;
    fill-opacity: 0.4;
    animation: pulse 1.5s ease-in-out infinite;
  }
}

@keyframes pulse {
  0%, 100% {
    stroke-opacity: 1;
  }
  50% {
    stroke-opacity: 0.5;
  }
}

.box-text {
  font-size: 14px;
  font-weight: 600;
  fill: var(--color-ink);
  pointer-events: none;
  text-shadow: 
    -1px -1px 0 white,
    1px -1px 0 white,
    -1px 1px 0 white,
    1px 1px 0 white;
}

.viewer-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: var(--color-rice-paper);
  border-top: 1px solid var(--color-rice-paper-dark);
}

.footer-info {
  font-size: 12px;
  color: var(--color-ink-lighter);
}

.footer-hint {
  display: flex;
  gap: 6px;
}

@media (max-width: 768px) {
  .viewer-toolbar {
    flex-wrap: wrap;
    gap: 8px;
  }

  .footer-hint {
    display: none;
  }
}
</style>
