<template>
  <div class="text-editor">
    <div class="editor-toolbar">
      <div class="toolbar-left">
        <h3 class="editor-title">文本编辑</h3>
        <el-tag size="small" type="info" v-if="columns">
          {{ columns.length }} 列 / {{ totalLines }} 行
        </el-tag>
      </div>
      <div class="toolbar-right">
        <el-tooltip content="竖排显示">
          <el-button
            size="small"
            :type="verticalLayout ? 'primary' : 'default'"
            :icon="Calendar"
            @click="verticalLayout = !verticalLayout"
          />
        </el-tooltip>
        <el-tooltip content="显示置信度">
          <el-button
            size="small"
            :type="showConfidence ? 'primary' : 'default'"
            :icon="DataAnalysis"
            @click="showConfidence = !showConfidence"
          />
        </el-tooltip>
      </div>
    </div>

    <div class="editor-content" :class="{ 'is-vertical': verticalLayout }">
      <div
        v-for="(column, colIndex) in displayColumns"
        :key="colIndex"
        class="text-column"
        :style="getColumnStyle(colIndex)"
      >
        <div
          v-for="line in column"
          :key="line.id"
          class="text-line-wrapper"
          @click="handleLineClick(line)"
        >
          <div
            class="text-line"
            :class="{
              'is-selected': selectedLineId === line.id,
              'is-editing': editingLineId === line.id
            }"
            :style="{ background: getLineBackground(line.confidence) }"
          >
            <template v-if="editingLineId === line.id">
              <input
                ref="editInputRef"
                v-model="editingContent"
                class="edit-input"
                @blur="handleEditComplete"
                @keyup.enter="handleEditComplete"
                @keyup.esc="handleEditCancel"
                @input="handleEditInput"
              />
              <CandidateDropdown
                v-if="showCandidates && line.candidates?.length"
                :candidates="line.candidates"
                :visible="dropdownVisible"
                :position="dropdownPosition"
                @select="handleCandidateSelect"
                @close="dropdownVisible = false"
              />
            </template>
            <template v-else>
              <span class="line-content">{{ line.content }}</span>
              <span v-if="showConfidence" class="line-confidence">
                {{ formatConfidence(line.confidence) }}
              </span>
            </template>
          </div>
          <div v-if="selectedLineId === line.id" class="line-indicator" />
        </div>
      </div>
    </div>

    <div v-if="selectedLine" class="editor-footer">
      <div class="footer-info">
        <span class="info-label">当前行:</span>
        <span class="info-value">{{ selectedLine.content }}</span>
      </div>
      <div class="footer-info">
        <span class="info-label">置信度:</span>
        <el-progress
          :percentage="Math.round(selectedLine.confidence * 100)"
          :color="getConfidenceColor(selectedLine.confidence)"
          :stroke-width="8"
          :width="80"
        />
      </div>
      <div class="footer-actions">
        <el-button size="small" :icon="Edit" @click="startEditing(selectedLine)">
          编辑
        </el-button>
        <el-dropdown trigger="click" @command="handleQuickAction">
          <el-button size="small" :icon="MoreFilled">
            更多
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="edit">编辑文字</el-dropdown-item>
              <el-dropdown-item command="show-candidates">显示候选词</el-dropdown-item>
              <el-dropdown-item command="copy">复制文字</el-dropdown-item>
              <el-dropdown-item divided command="delete">删除行</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <div v-else-if="!columns || columns.length === 0" class="empty-editor">
      <el-empty description="暂无识别结果" :image-size="80">
        <template #description>
          <span>上传图片或PDF开始识别</span>
        </template>
      </el-empty>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue';
import { ElMessage } from 'element-plus';
import { Calendar, DataAnalysis, Edit, MoreFilled } from '@element-plus/icons-vue';
import CandidateDropdown from './CandidateDropdown.vue';
import type { TextLine } from '../types';

const props = defineProps<{
  columns?: TextLine[][];
  textLines?: TextLine[];
  selectedLineId?: string;
  readOnly?: boolean;
}>();

const emit = defineEmits<{
  (e: 'line-click', line: TextLine): void;
  (e: 'line-update', lineId: string, content: string): void;
  (e: 'line-delete', lineId: string): void;
  (e: 'candidate-select', lineId: string, candidate: string): void;
}>();

const verticalLayout = ref(true);
const showConfidence = ref(true);
const editingLineId = ref<string | null>(null);
const editingContent = ref('');
const showCandidates = ref(false);
const dropdownVisible = ref(false);
const dropdownPosition = ref({ x: 0, y: 0 });
const editInputRef = ref<HTMLInputElement | null>(null);

const selectedLine = computed(() => {
  const allLines = props.columns?.flat() || props.textLines || [];
  return allLines.find(l => l.id === props.selectedLineId);
});

const displayColumns = computed(() => {
  if (props.columns && props.columns.length > 0) {
    return verticalLayout.value ? [...props.columns].reverse() : props.columns;
  }
  if (props.textLines && props.textLines.length > 0) {
    const defaultColumn: TextLine[][] = [props.textLines];
    return verticalLayout.value ? defaultColumn.reverse() : defaultColumn;
  }
  return [];
});

const totalLines = computed(() => {
  return displayColumns.value.reduce((sum, col) => sum + col.length, 0);
});

const getLineBackground = (confidence: number): string => {
  if (!showConfidence.value) return 'transparent';
  if (confidence >= 0.9) return 'rgba(103, 194, 58, 0.05)';
  if (confidence >= 0.7) return 'rgba(230, 162, 60, 0.08)';
  return 'rgba(196, 30, 58, 0.1)';
};

const getConfidenceColor = (confidence: number): string => {
  if (confidence >= 0.9) return '#67C23A';
  if (confidence >= 0.7) return '#E6A23C';
  return '#C41E3A';
};

const formatConfidence = (confidence: number): string => {
  return (confidence * 100).toFixed(0) + '%';
};

const getColumnStyle = (index: number) => {
  if (verticalLayout.value) {
    return { order: index };
  }
  return {};
};

const handleLineClick = (line: TextLine) => {
  emit('line-click', line);
};

const startEditing = (line: TextLine) => {
  if (props.readOnly) return;
  
  editingLineId.value = line.id;
  editingContent.value = line.content;
  showCandidates.value = true;
  dropdownVisible.value = false;
  
  nextTick(() => {
    if (editInputRef.value) {
      editInputRef.value.focus();
      editInputRef.value.select();
      updateDropdownPosition();
    }
  });
};

const handleEditInput = () => {
  updateDropdownPosition();
  if (editingContent.value.length > 0) {
    dropdownVisible.value = true;
  }
};

const handleEditComplete = () => {
  if (!editingLineId.value) return;
  
  const line = [...(props.columns?.flat() || props.textLines || [])].find(l => l.id === editingLineId.value);
  if (line && editingContent.value.trim() !== line.content) {
    emit('line-update', editingLineId.value, editingContent.value.trim());
    ElMessage.success('已更新');
  }
  
  cancelEditing();
};

const handleEditCancel = () => {
  cancelEditing();
};

const cancelEditing = () => {
  editingLineId.value = null;
  editingContent.value = '';
  showCandidates.value = false;
  dropdownVisible.value = false;
};

const updateDropdownPosition = () => {
  if (!editInputRef.value) return;
  
  const rect = editInputRef.value.getBoundingClientRect();
  dropdownPosition.value = {
    x: rect.left,
    y: rect.bottom + 4
  };
};

const handleCandidateSelect = (candidate: string) => {
  if (!editingLineId.value) return;
  
  editingContent.value = candidate;
  dropdownVisible.value = false;
  emit('candidate-select', editingLineId.value, candidate);
  handleEditComplete();
};

const handleQuickAction = (command: string) => {
  const line = selectedLine.value;
  if (!line) return;

  switch (command) {
    case 'edit':
      startEditing(line);
      break;
    case 'show-candidates':
      if (line.candidates?.length) {
        startEditing(line);
        dropdownVisible.value = true;
      } else {
        ElMessage.info('暂无候选词');
      }
      break;
    case 'copy':
      navigator.clipboard.writeText(line.content);
      ElMessage.success('已复制');
      break;
    case 'delete':
      emit('line-delete', line.id);
      break;
  }
};

const handleKeyDown = (e: KeyboardEvent) => {
  if (e.key === 'Enter' && selectedLine.value && !editingLineId.value) {
    startEditing(selectedLine.value);
  }
};

watch(() => props.selectedLineId, (_, oldId) => {
  if (oldId && editingLineId.value === oldId) {
    cancelEditing();
  }
});

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown);
});

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown);
});
</script>

<style lang="scss" scoped>
.text-editor {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 400px;
  background: var(--color-rice-paper-light);
  border: 1px solid var(--color-rice-paper-dark);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.editor-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: var(--color-rice-paper);
  border-bottom: 1px solid var(--color-rice-paper-dark);
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.editor-title {
  font-family: var(--font-serif);
  font-size: 16px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 4px;
}

.editor-content {
  flex: 1;
  overflow: auto;
  padding: 24px;
  display: flex;
  gap: 32px;

  &.is-vertical {
    flex-direction: row-reverse;
    align-items: flex-start;
    justify-content: flex-end;
  }
}

.text-column {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 120px;
}

.text-line-wrapper {
  position: relative;
}

.text-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 12px;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);

  &:hover {
    border-color: var(--color-rice-paper-dark);
    background: rgba(196, 30, 58, 0.03);
  }

  &.is-selected {
    border-color: var(--color-vermilion);
    background: rgba(196, 30, 58, 0.08);

    .line-content {
      color: var(--color-vermilion);
    }
  }

  &.is-editing {
    padding: 4px 8px;
    cursor: text;
  }
}

.line-content {
  font-family: var(--font-serif);
  font-size: 16px;
  font-weight: 500;
  color: var(--color-ink);
  letter-spacing: 2px;
  line-height: 1.8;
  flex: 1;
}

.line-confidence {
  font-size: 11px;
  font-weight: 500;
  color: var(--color-ink-lighter);
  flex-shrink: 0;
}

.edit-input {
  flex: 1;
  padding: 4px 8px;
  font-family: var(--font-serif);
  font-size: 16px;
  font-weight: 500;
  color: var(--color-ink);
  border: 1px solid var(--color-vermilion);
  border-radius: var(--radius-sm);
  background: white;
  outline: none;

  &:focus {
    box-shadow: 0 0 0 3px rgba(196, 30, 58, 0.1);
  }
}

.line-indicator {
  position: absolute;
  left: -8px;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 60%;
  background: var(--color-vermilion);
  border-radius: 2px;
}

.editor-footer {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 12px 16px;
  background: var(--color-rice-paper);
  border-top: 1px solid var(--color-rice-paper-dark);
}

.footer-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.info-label {
  font-size: 12px;
  color: var(--color-ink-lighter);
}

.info-value {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-ink);
  max-width: 200px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.footer-actions {
  margin-left: auto;
  display: flex;
  gap: 8px;
}

.empty-editor {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

@media (max-width: 768px) {
  .editor-content {
    padding: 16px;
    gap: 16px;

    &.is-vertical {
      overflow-x: auto;
      overflow-y: hidden;
    }
  }

  .editor-footer {
    flex-wrap: wrap;
    gap: 12px;

    .footer-actions {
      margin-left: 0;
      width: 100%;
      justify-content: flex-end;
    }
  }
}
</style>
