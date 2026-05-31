<template>
  <div class="task-card" :class="{ 'is-clickable': !disabled }">
    <div class="card-header">
      <div class="task-icon">
        <el-icon :size="28">
          <Document v-if="task.fileType === 'pdf'" />
          <Picture v-else />
        </el-icon>
      </div>
      <el-tag :type="tagType" effect="light" size="small">
        {{ statusText }}
      </el-tag>
    </div>

    <div class="card-body">
      <h3 class="task-title" :title="task.fileName">
        {{ task.fileName }}
      </h3>
      <div class="task-meta">
        <span class="meta-item">
          <el-icon :size="12"><Files /></el-icon>
          {{ task.pageCount }} 页
        </span>
        <span class="meta-item">
          <el-icon :size="12"><Clock /></el-icon>
          {{ formatDate(task.createdAt) }}
        </span>
      </div>

      <div v-if="progress" class="progress-section">
        <div class="progress-header">
          <span class="progress-text">{{ progress.message }}</span>
          <span class="progress-value">{{ progress.progress }}%</span>
        </div>
        <el-progress
          :percentage="progress.progress"
          :stroke-width="6"
          :color="progressColor"
        />
      </div>

      <div v-else-if="task.status === 'completed'" class="completed-section">
        <span class="completed-text">识别完成</span>
        <span class="completed-time">{{ formatDate(task.completedAt || '') }}</span>
      </div>

      <div v-else-if="task.status === 'failed'" class="failed-section">
        <el-alert
          :title="task.errorMessage || '识别失败'"
          type="error"
          :closable="false"
          show-icon
        />
      </div>
    </div>

    <div class="card-footer">
      <el-button
        v-if="task.status === 'completed'"
        type="primary"
        size="small"
        @click.stop="$emit('view', task)"
      >
        查看
      </el-button>
      <el-button
        v-else-if="task.status === 'failed'"
        type="primary"
        size="small"
        @click.stop="$emit('rerun', task)"
      >
        重新识别
      </el-button>
      <el-button
        v-else
        size="small"
        disabled
      >
        {{ statusText }}
      </el-button>
      <el-dropdown trigger="click" @command="handleCommand">
        <el-button size="small" :icon="MoreFilled" />
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="view">
              <span v-if="task.status === 'completed'">查看结果</span>
              <span v-else>查看详情</span>
            </el-dropdown-item>
            <el-dropdown-item v-if="task.status === 'failed' || task.status === 'completed'" command="rerun">
              重新识别
            </el-dropdown-item>
            <el-dropdown-item divided command="delete" class="text-danger">
              删除
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { Document, Picture, Files, Clock, MoreFilled } from '@element-plus/icons-vue';
import type { Task, ProgressMessage } from '../types';
import { TASK_STATUS_LABELS, TASK_STATUS_COLORS } from '../types';
import { formatDate } from '../utils/tesseract';

const props = defineProps<{
  task: Task;
  progress?: ProgressMessage;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  (e: 'view', task: Task): void;
  (e: 'delete', task: Task): void;
  (e: 'rerun', task: Task): void;
}>();

const statusText = computed(() => TASK_STATUS_LABELS[props.task.status]);

const tagType = computed(() => {
  switch (props.task.status) {
    case 'completed': return 'success';
    case 'failed': return 'danger';
    default: return 'warning';
  }
});

const progressColor = computed(() => {
  if (props.progress) {
    return TASK_STATUS_COLORS[props.progress.status];
  }
  return TASK_STATUS_COLORS[props.task.status];
});

const handleCommand = (command: string) => {
  switch (command) {
    case 'view':
      emit('view', props.task);
      break;
    case 'delete':
      emit('delete', props.task);
      break;
    case 'rerun':
      emit('rerun', props.task);
      break;
  }
};
</script>

<style lang="scss" scoped>
.task-card {
  background: #FFF;
  border: 1px solid #E8DFD0;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  transition: all 0.3s ease;

  &.is-clickable:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 24px rgba(196, 30, 58, 0.1);
    border-color: #C41E3A;
  }
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 16px 16px 12px;
  border-bottom: 1px solid #F5F0E6;
}

.task-icon {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  background: #FDF5E6;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #C41E3A;
}

.card-body {
  padding: 16px;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-title {
  font-family: 'Noto Serif SC', serif;
  font-size: 16px;
  font-weight: 600;
  color: #2C1810;
  margin: 0;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.task-meta {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #8B7355;
}

.progress-section,
.completed-section,
.failed-section {
  margin-top: 8px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.progress-text {
  font-size: 12px;
  color: #6B5B4F;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 180px;
}

.progress-value {
  font-size: 12px;
  font-weight: 600;
  color: #C41E3A;
}

.completed-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: rgba(103, 194, 58, 0.08);
  border-radius: 6px;
}

.completed-text {
  font-size: 13px;
  font-weight: 500;
  color: #67C23A;
}

.completed-time {
  font-size: 12px;
  color: #8B7355;
}

.card-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 16px 16px;
  border-top: 1px solid #F5F0E6;
}

.text-danger {
  color: #C41E3A !important;
}
</style>
