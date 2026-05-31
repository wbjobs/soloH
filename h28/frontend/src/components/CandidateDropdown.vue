<template>
  <Teleport to="body">
    <Transition name="dropdown-fade">
      <div
        v-if="visible"
        class="candidate-dropdown"
        :style="dropdownStyle"
        @click.stop
      >
        <div class="dropdown-header">
          <span class="header-title">候选词</span>
          <span class="header-count">{{ candidates.length }} 个</span>
        </div>
        <div class="dropdown-list">
          <div
            v-for="(candidate, index) in candidates"
            :key="index"
            class="candidate-item"
            :class="{ 'is-active': activeIndex === index }"
            @click="handleSelect(candidate, index)"
            @mouseenter="activeIndex = index"
          >
            <span class="candidate-text">{{ candidate }}</span>
            <span class="candidate-index">{{ index + 1 }}</span>
          </div>
        </div>
        <div class="dropdown-footer">
          <span class="footer-hint">↑↓ 选择 · Enter 确认 · Esc 关闭</span>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue';

interface CandidateWithConfidence {
  text: string;
  confidence: number;
}

const props = defineProps<{
  candidates: string[] | CandidateWithConfidence[];
  visible: boolean;
  position: { x: number; y: number };
  width?: number;
  maxHeight?: number;
}>();

const emit = defineEmits<{
  (e: 'select', candidate: string, index: number): void;
  (e: 'close'): void;
}>();

const activeIndex = ref(0);

const dropdownStyle = computed(() => {
  const width = props.width || 240;
  const maxHeight = props.maxHeight || 300;
  
  let left = props.position.x;
  let top = props.position.y;
  
  if (left + width > window.innerWidth) {
    left = window.innerWidth - width - 16;
  }
  if (top + maxHeight > window.innerHeight) {
    top = props.position.y - maxHeight - 4;
  }
  
  return {
    left: `${left}px`,
    top: `${top}px`,
    width: `${width}px`,
    maxHeight: `${maxHeight}px`
  };
});

const handleSelect = (candidate: string | CandidateWithConfidence, index: number) => {
  const text = typeof candidate === 'string' ? candidate : candidate.text;
  emit('select', text, index);
};

const handleKeyDown = (e: KeyboardEvent) => {
  if (!props.visible || props.candidates.length === 0) return;

  switch (e.key) {
    case 'ArrowDown':
      e.preventDefault();
      activeIndex.value = (activeIndex.value + 1) % props.candidates.length;
      scrollToActive();
      break;
    case 'ArrowUp':
      e.preventDefault();
      activeIndex.value = (activeIndex.value - 1 + props.candidates.length) % props.candidates.length;
      scrollToActive();
      break;
    case 'Enter':
      e.preventDefault();
      if (props.candidates[activeIndex.value] !== undefined) {
        handleSelect(props.candidates[activeIndex.value], activeIndex.value);
      }
      break;
    case 'Escape':
      e.preventDefault();
      emit('close');
      break;
    case '1':
    case '2':
    case '3':
    case '4':
    case '5':
    case '6':
    case '7':
    case '8':
    case '9':
      const numIndex = parseInt(e.key) - 1;
      if (numIndex < props.candidates.length) {
        e.preventDefault();
        handleSelect(props.candidates[numIndex], numIndex);
      }
      break;
  }
};

const scrollToActive = async () => {
  await nextTick();
  const activeElement = document.querySelector('.candidate-item.is-active');
  if (activeElement) {
    activeElement.scrollIntoView({ block: 'nearest' });
  }
};

const handleClickOutside = (e: MouseEvent) => {
  if (!props.visible) return;
  const target = e.target as HTMLElement;
  if (!target.closest('.candidate-dropdown')) {
    emit('close');
  }
};

watch(() => props.visible, (newVal) => {
  if (newVal) {
    activeIndex.value = 0;
  }
});

watch(() => props.candidates, () => {
  if (activeIndex.value >= props.candidates.length) {
    activeIndex.value = Math.max(0, props.candidates.length - 1);
  }
});

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown);
  window.addEventListener('click', handleClickOutside);
});

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown);
  window.removeEventListener('click', handleClickOutside);
});
</script>

<style lang="scss" scoped>
.candidate-dropdown {
  position: fixed;
  z-index: 9999;
  background: var(--color-rice-paper-light);
  border: 1px solid var(--color-rice-paper-dark);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.dropdown-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: var(--color-rice-paper);
  border-bottom: 1px solid var(--color-rice-paper-dark);
}

.header-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-ink);
}

.header-count {
  font-size: 12px;
  color: var(--color-ink-lighter);
}

.dropdown-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px;
}

.candidate-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);

  &:hover,
  &.is-active {
    background: rgba(196, 30, 58, 0.1);

    .candidate-text {
      color: var(--color-vermilion);
    }

    .candidate-index {
      background: var(--color-vermilion);
      color: white;
    }
  }
}

.candidate-text {
  font-family: var(--font-serif);
  font-size: 15px;
  font-weight: 500;
  color: var(--color-ink);
  letter-spacing: 1px;
}

.candidate-index {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-ink-lighter);
  background: var(--color-rice-paper-dark);
  width: 20px;
  height: 20px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition-fast);
}

.dropdown-footer {
  padding: 8px 14px;
  background: var(--color-rice-paper);
  border-top: 1px solid var(--color-rice-paper-dark);
}

.footer-hint {
  font-size: 11px;
  color: var(--color-ink-lighter);
}

.dropdown-fade-enter-active,
.dropdown-fade-leave-active {
  transition: all var(--transition-fast);
}

.dropdown-fade-enter-from,
.dropdown-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
