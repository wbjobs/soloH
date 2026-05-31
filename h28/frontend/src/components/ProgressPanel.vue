<template>
  <div class="progress-panel">
    <div class="panel-header">
      <h3 class="panel-title">处理进度</h3>
      <el-tag
        v-if="progressData"
        :type="getTagType(progressData.status)"
        size="small"
      >
        {{ getStatusLabel(progressData.status) }}
      </el-tag>
    </div>

    <div class="progress-stages">
      <div
        v-for="(stage, index) in stages"
        :key="stage.key"
        class="stage-item"
        :class="{
          'is-active': progressData && progressData.status === stage.key,
          'is-completed': getStageIndex(progressData?.status) > index
        }"
      >
        <div class="stage-icon">
          <el-icon v-if="getStageIndex(progressData?.status) > index">
            <Check />
          </el-icon>
          <el-icon v-else-if="progressData && progressData.status === stage.key" class="processing">
            <Loading />
          </el-icon>
          <span v-else class="stage-number">{{ index + 1 }}</span>
        </div>
        <div class="stage-info">
          <span class="stage-name">{{ stage.label }}</span>
          <span class="stage-desc" v-if="progressData && progressData.status === stage.key">
            {{ progressData.message }}
          </span>
        </div>
      </div>
    </div>

    <div class="progress-main">
      <div class="progress-header">
        <span class="progress-label">整体进度</span>
        <span class="progress-value">{{ overallProgress }}%</span>
      </div>
      <el-progress
        :percentage="overallProgress"
        :stroke-width="8"
        :show-text="false"
        :status="getProgressStatus()"
      />
    </div>

    <div v-if="progressData && (progressData.currentPage || progressData.totalPages)" class="page-progress">
      <div class="page-info">
        <el-icon><Document /></el-icon>
        <span>
          第 {{ progressData.currentPage || 0 }} / {{ progressData.totalPages || 0 }} 页
        </span>
      </div>
      <el-progress
        :percentage="pageProgress"
        :stroke-width="4"
        :show-text="false"
        color="#409EFF"
      />
    </div>

    <div v-if="progressData?.status === 'failed'" class="error-section">
      <el-alert
        :title="progressData.message || '处理失败'"
        type="error"
        :closable="false"
        show-icon
      />
    </div>

    <div v-if="progressData?.status === 'completed'" class="success-section">
      <div class="success-content">
        <el-icon size="32" color="#67C23A"><CircleCheck /></el-icon>
        <div>
          <h4 class="success-title">处理完成</h4>
          <p class="success-desc">共 {{ progressData.totalPages || 0 }} 页，识别完成</p>
        </div>
      </div>
    </div>

    <div v-if="!connected && !autoReconnect" class="connection-warning">
      <el-alert
        title="WebSocket 连接已断开"
        type="warning"
        :closable="false"
        show-icon
      >
        <template #default>
          <p>实时进度更新将不可用</p>
          <el-button size="small" type="primary" @click="handleReconnect">重新连接</el-button>
        </template>
      </el-alert>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import { ElMessage } from 'element-plus';
import { Loading, Check, Document, CircleCheck } from '@element-plus/icons-vue';
import { socketManager } from '../utils/socket';
import type { ProgressMessage, TaskStatus } from '../types';
import { TASK_STATUS_LABELS } from '../types';

const props = defineProps<{
  taskId: string;
  autoReconnect?: boolean;
}>();

const emit = defineEmits<{
  (e: 'progress', data: ProgressMessage): void;
  (e: 'completed', result: any): void;
  (e: 'failed', error: string): void;
  (e: 'status-change', status: TaskStatus): void;
}>();

const stages = [
  { key: 'pending', label: '等待中' },
  { key: 'preprocessing', label: '预处理' },
  { key: 'detecting', label: '文本检测' },
  { key: 'recognizing', label: '文字识别' },
  { key: 'postprocessing', label: '后处理' },
  { key: 'punctuating', label: '标点处理' },
  { key: 'completed', label: '已完成' }
] as const;

const connected = ref(true);
const reconnecting = ref(false);
const progressData = ref<ProgressMessage | null>(null);

const getStageIndex = (status?: TaskStatus): number => {
  if (!status) return -1;
  return stages.findIndex(s => s.key === status);
};

const getStatusLabel = (status: TaskStatus): string => {
  return TASK_STATUS_LABELS[status] || status;
};

const getTagType = (status: TaskStatus): string => {
  if (status === 'completed') return 'success';
  if (status === 'failed') return 'danger';
  if (status === 'pending') return 'info';
  return 'warning';
};

const overallProgress = computed(() => {
  if (!progressData.value) return 0;
  return Math.min(Math.round(progressData.value.progress * 100), 100);
});

const pageProgress = computed(() => {
  if (!progressData.value?.totalPages || !progressData.value?.currentPage) return 0;
  return Math.round((progressData.value.currentPage / progressData.value.totalPages) * 100);
});

const getProgressStatus = (): '' | 'success' | 'exception' | 'warning' => {
  if (!progressData.value) return '';
  if (progressData.value.status === 'completed') return 'success';
  if (progressData.value.status === 'failed') return 'exception';
  return '';
};

const handleProgress = (data: ProgressMessage) => {
  if (data.taskId !== props.taskId) return;
  
  const oldStatus = progressData.value?.status;
  progressData.value = data;
  
  emit('progress', data);
  
  if (oldStatus !== data.status) {
    emit('status-change', data.status);
  }
};

const handleCompleted = (data: { taskId: string; result: any }) => {
  if (data.taskId !== props.taskId) return;
  emit('completed', data.result);
};

const handleFailed = (data: { taskId: string; error: string }) => {
  if (data.taskId !== props.taskId) return;
  emit('failed', data.error);
  if (progressData.value) {
    progressData.value.status = 'failed';
    progressData.value.message = data.error;
  }
};

const handleConnect = () => {
  connected.value = true;
  reconnecting.value = false;
  socketManager.joinTask(props.taskId);
};

const handleDisconnect = () => {
  connected.value = false;
};

const handleConnectError = () => {
  connected.value = false;
};

const handleReconnect = async () => {
  if (reconnecting.value) return;
  
  reconnecting.value = true;
  try {
    socketManager.connect();
    ElMessage.success('连接成功');
  } catch (e) {
    ElMessage.error('连接失败，请稍后重试');
  } finally {
    reconnecting.value = false;
  }
};

watch(() => props.taskId, (newTaskId, oldTaskId) => {
  if (oldTaskId) {
    socketManager.leaveTask(oldTaskId);
  }
  if (newTaskId) {
    socketManager.joinTask(newTaskId);
    progressData.value = null;
  }
});

onMounted(() => {
  socketManager.connect();
  socketManager.on('progress', handleProgress);
  socketManager.on('completed', handleCompleted);
  socketManager.on('failed', handleFailed);
  socketManager.on('connect', handleConnect);
  socketManager.on('disconnect', handleDisconnect);
  socketManager.on('connect_error', handleConnectError);
  
  socketManager.joinTask(props.taskId);
});

onUnmounted(() => {
  socketManager.off('progress', handleProgress);
  socketManager.off('completed', handleCompleted);
  socketManager.off('failed', handleFailed);
  socketManager.off('connect', handleConnect);
  socketManager.off('disconnect', handleDisconnect);
  socketManager.off('connect_error', handleConnectError);
  
  socketManager.leaveTask(props.taskId);
});
</script>

<style lang="scss" scoped>
.progress-panel {
  background: var(--color-rice-paper-light);
  border: 1px solid var(--color-rice-paper-dark);
  border-radius: var(--radius-lg);
  padding: 24px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.panel-title {
  font-family: var(--font-serif);
  font-size: 18px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0;
}

.progress-stages {
  margin-bottom: 24px;
}

.stage-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid var(--color-rice-paper-dark);
  opacity: 0.5;
  transition: all var(--transition-fast);

  &:last-child {
    border-bottom: none;
  }

  &.is-active {
    opacity: 1;

    .stage-number,
    .stage-icon {
      background: var(--color-vermilion);
      color: white;
      border-color: var(--color-vermilion);
    }

    .stage-name {
      color: var(--color-vermilion);
      font-weight: 600;
    }
  }

  &.is-completed {
    opacity: 1;

    .stage-icon {
      background: var(--color-success);
      color: white;
      border-color: var(--color-success);
    }

    .stage-name {
      color: var(--color-success);
    }
  }
}

.stage-icon {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--color-rice-paper-dark);
  border: 2px solid var(--color-rice-paper-dark);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-ink-lighter);
  transition: all var(--transition-fast);

  &.processing {
    animation: rotate 1s linear infinite;
  }
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.stage-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}

.stage-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-ink);
  transition: color var(--transition-fast);
}

.stage-desc {
  font-size: 12px;
  color: var(--color-ink-lighter);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.progress-main {
  margin-bottom: 20px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.progress-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-ink);
}

.progress-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-vermilion);
}

.page-progress {
  margin-bottom: 20px;
  padding: 12px;
  background: var(--color-rice-paper);
  border-radius: var(--radius-md);
}

.page-info {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 13px;
  color: var(--color-ink-light);

  .el-icon {
    color: var(--color-vermilion);
  }
}

.error-section {
  margin-top: 16px;
}

.success-section {
  margin-top: 16px;
  padding: 20px;
  background: rgba(103, 194, 58, 0.1);
  border-radius: var(--radius-md);
  border: 1px solid rgba(103, 194, 58, 0.3);
}

.success-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.success-title {
  font-family: var(--font-serif);
  font-size: 16px;
  font-weight: 600;
  color: var(--color-success);
  margin: 0 0 4px 0;
}

.success-desc {
  font-size: 13px;
  color: var(--color-ink-light);
  margin: 0;
}

.connection-warning {
  margin-top: 16px;
}

@media (max-width: 768px) {
  .progress-panel {
    padding: 16px;
  }
}
</style>
