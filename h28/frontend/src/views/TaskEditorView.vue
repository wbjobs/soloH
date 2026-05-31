<template>
  <div class="task-editor-view">
    <div class="editor-header">
      <div class="header-left">
        <el-button text @click="$router.push('/tasks')">
          <icon-park theme="outline" size="20" name="back" />
          返回列表
        </el-button>
        <div class="task-info">
          <h1 class="task-title">{{ currentTask?.fileName || '加载中...' }}</h1>
          <div class="task-meta">
            <el-tag
              :type="statusType"
              effect="light"
              size="small"
            >
              {{ statusText }}
            </el-tag>
            <span v-if="currentTaskResult" class="meta-item">
              共 {{ currentTaskResult.pages.length }} 页
            </span>
            <span class="meta-item">
              {{ formatDate(currentTask?.createdAt || '') }}
            </span>
          </div>
        </div>
      </div>
      <div class="header-right">
        <el-button @click="handleRerun">
          <icon-park theme="outline" size="16" name="refresh" />
          重新识别
        </el-button>
        <el-button type="primary" @click="showExportDialog = true">
          <icon-park theme="outline" size="16" name="download" />
          导出
        </el-button>
      </div>
    </div>

    <template v-if="loading">
      <div class="loading-container">
        <el-icon class="is-loading" :size="48">
          <Loading />
        </el-icon>
        <p>加载识别结果...</p>
      </div>
    </template>

    <template v-else-if="!currentTaskResult">
      <div class="empty-state">
        <icon-park theme="outline" size="80" name="file" :fill="['#D4C4B0']" />
        <h3>暂无识别结果</h3>
        <p v-if="currentTask?.status !== 'completed' && currentTask?.status !== 'failed'">请等待识别完成...</p>
        <p v-else-if="currentTask?.status === 'failed'">识别失败，请尝试重新识别</p>
      </div>
    </template>

    <template v-else>
      <div class="editor-toolbar">
        <div class="page-nav">
          <el-button
            size="small"
            :disabled="currentPage <= 1"
            @click="currentPage--"
          >
            <icon-park theme="outline" size="16" name="left" />
            上一页
          </el-button>
          <span class="page-indicator">
            第 {{ currentPage }} / {{ currentTaskResult.pages.length }} 页
          </span>
          <el-button
            size="small"
            :disabled="currentPage >= currentTaskResult.pages.length"
            @click="currentPage++"
          >
            下一页
            <icon-park theme="outline" size="16" name="right" />
          </el-button>
        </div>
        <div class="toolbar-actions">
          <el-tooltip content="显示检测框">
            <el-button
              size="small"
              :type="showBoxes ? 'primary' : 'default'"
              @click="showBoxes = !showBoxes"
            >
              <icon-park theme="outline" size="16" name="check-item" />
            </el-button>
          </el-tooltip>
          <el-tooltip content="显示置信度">
            <el-button
              size="small"
              :type="showConfidence ? 'primary' : 'default'"
              @click="showConfidence = !showConfidence"
            >
              <icon-park theme="outline" size="16" name="histogram" />
            </el-button>
          </el-tooltip>
          <el-slider
            v-model="zoomLevel"
            :min="50"
            :max="200"
            :step="10"
            class="zoom-slider"
          />
          <span class="zoom-label">{{ zoomLevel }}%</span>
        </div>
      </div>

      <div class="editor-content">
        <div class="pane image-pane">
          <div class="pane-header">
            <span class="pane-title">原图预览</span>
          </div>
          <div class="pane-body">
            <ImageViewer
              v-if="currentPageData"
              :image-url="currentPageData.imageUrl"
              :text-lines="currentPageData.textLines"
              :show-boxes="showBoxes"
              :selected-line-id="selectedBoxId ?? undefined"
              @line-click="handleLineClick"
            />
          </div>
        </div>

        <div class="pane text-pane">
          <div class="pane-header">
            <span class="pane-title">识别文本</span>
            <span class="pane-subtitle">点击文字可编辑</span>
          </div>
          <div class="pane-body">
            <TextEditor
              v-if="currentPageData"
              :columns="currentPageData.columns"
              :text-lines="currentPageData.textLines"
              :show-confidence="showConfidence"
              :selected-line-id="selectedBoxId ?? undefined"
              @line-click="handleLineClick"
              @line-update="handleLineUpdate"
            />
          </div>
        </div>
      </div>
    </template>

    <CandidateDropdown
      v-model:visible="showCandidateDropdown"
      :candidates="currentCandidates"
      :position="dropdownPosition"
      @select="handleCandidateSelect"
      @close="showCandidateDropdown = false"
    />

    <ExportDialog
      v-model:modelValue="showExportDialog"
      :task-id="taskId"
      :task-name="currentTask?.fileName"
      :total-pages="currentTaskResult?.pages.length"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import { useRoute } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Loading } from '@element-plus/icons-vue';
import ImageViewer from '../components/ImageViewer.vue';
import TextEditor from '../components/TextEditor.vue';
import CandidateDropdown from '../components/CandidateDropdown.vue';
import ExportDialog from '../components/ExportDialog.vue';
import { useTaskStore } from '../stores/task';
import { updateTaskResult, rerunTask } from '../api';
import { formatDate } from '../utils/tesseract';
import type { PageResult, TextLine } from '../types';
import { TASK_STATUS_LABELS } from '../types';

const route = useRoute();
const taskStore = useTaskStore();

const taskId = computed(() => route.params.id as string);
const currentTask = computed(() => taskStore.currentTask);
const currentTaskResult = computed(() => taskStore.currentTaskResult);
const loading = computed(() => taskStore.loading);

const currentPage = ref(1);
const showBoxes = ref(true);
const showConfidence = ref(false);
const zoomLevel = ref(100);
const selectedBoxId = ref<string | null>(null);
const showCandidateDropdown = ref(false);
const dropdownPosition = ref({ x: 0, y: 0 });
const currentCandidates = ref<string[]>([]);
const showExportDialog = ref(false);

const statusType = computed(() => {
  const status = currentTask.value?.status;
  switch (status) {
    case 'completed': return 'success';
    case 'pending':
    case 'preprocessing':
    case 'detecting':
    case 'recognizing':
    case 'postprocessing':
    case 'punctuating': return 'warning';
    case 'failed': return 'danger';
    default: return 'info';
  }
});

const statusText = computed(() => {
  const status = currentTask.value?.status;
  if (!status) return '未知';
  return TASK_STATUS_LABELS[status] || '未知';
});

const currentPageData = computed<PageResult | undefined>(() => {
  return currentTaskResult.value?.pages.find(
    (p) => p.pageNumber === currentPage.value
  );
});

const handleLineClick = (line: TextLine, event?: MouseEvent) => {
  selectedBoxId.value = line.id;
  
  if (line.candidates && line.candidates.length > 0 && event) {
    currentCandidates.value = [line.content, ...line.candidates.filter((c) => c !== line.content)];
    dropdownPosition.value = { x: event.clientX, y: event.clientY };
    showCandidateDropdown.value = true;
  }
};

const handleLineUpdate = async (lineId: string, text: string) => {
  try {
    await updateTaskResult(taskId.value, {
      pageNumber: currentPage.value,
      lineId,
      content: text
    });
    taskStore.updateBoxText(currentPage.value, lineId, text);
    ElMessage.success('已保存修改');
  } catch (e) {
    ElMessage.error('保存失败');
  }
};

const handleCandidateSelect = (candidate: string) => {
  if (selectedBoxId.value) {
    handleLineUpdate(selectedBoxId.value, candidate);
  }
  showCandidateDropdown.value = false;
};

const handleRerun = async () => {
  if (!currentTask.value) return;
  
  try {
    await ElMessageBox.confirm(
      `确定要重新识别 "${currentTask.value.fileName}" 吗？`,
      '确认重跑',
      {
        confirmButtonText: '重跑',
        cancelButtonText: '取消',
        type: 'info',
      }
    );
    const updatedTask = await rerunTask(taskId.value);
    taskStore.addTask(updatedTask);
    taskStore.subscribeToTask(taskId.value);
    ElMessage.success('已开始重新识别');
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('操作失败');
    }
  }
};

const loadData = async () => {
  try {
    await taskStore.loadTask(taskId.value);
    if (currentTask.value?.status === 'completed') {
      await taskStore.loadTaskResult(taskId.value);
    }
    taskStore.subscribeToTask(taskId.value);
  } catch (e) {
    ElMessage.error('加载任务失败');
  }
};

watch(currentPage, () => {
  selectedBoxId.value = null;
});

onMounted(() => {
  taskStore.connectWebSocket();
  loadData();
});

onUnmounted(() => {
  taskStore.unsubscribeFromTask(taskId.value);
  taskStore.clearCurrent();
});
</script>

<style lang="scss" scoped>
.task-editor-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #F5F0E6;
  overflow: hidden;
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: #FFF;
  border-bottom: 1px solid #E8DFD0;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.task-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.task-title {
  font-family: 'Noto Serif SC', serif;
  font-size: 20px;
  font-weight: 600;
  color: #2C1810;
  margin: 0;
}

.task-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  color: #8B7355;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.header-right {
  display: flex;
  gap: 8px;

  .el-button--primary {
    background: #C41E3A;
    border-color: #C41E3A;

    &:hover {
      background: #A0182E;
      border-color: #A0182E;
    }
  }
}

.loading-container,
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #8B7355;

  p {
    margin-top: 16px;
    font-size: 14px;
  }

  h3 {
    font-family: 'Noto Serif SC', serif;
    font-size: 20px;
    color: #5C4033;
    margin: 16px 0 8px 0;
  }
}

.loading-container .el-icon {
  color: #C41E3A;
}

.editor-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 24px;
  background: #FFF;
  border-bottom: 1px solid #E8DFD0;
  flex-shrink: 0;
}

.page-nav {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-indicator {
  font-family: 'Noto Serif SC', serif;
  font-size: 14px;
  color: #2C1810;
  min-width: 100px;
  text-align: center;
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.zoom-slider {
  width: 120px;
  margin: 0 8px;
}

.zoom-label {
  font-size: 12px;
  color: #6B5B4F;
  min-width: 48px;
  text-align: right;
}

.editor-content {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.pane {
  display: flex;
  flex-direction: column;
  background: #FFF;
  overflow: hidden;
}

.image-pane {
  flex: 1;
  border-right: 1px solid #E8DFD0;
}

.text-pane {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.pane-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  background: #FAF7F2;
  border-bottom: 1px solid #E8DFD0;
  flex-shrink: 0;
}

.pane-title {
  font-family: 'Noto Serif SC', serif;
  font-size: 14px;
  font-weight: 600;
  color: #2C1810;
}

.pane-subtitle {
  font-size: 12px;
  color: #8B7355;
}

.pane-body {
  flex: 1;
  overflow: auto;
}

@media (max-width: 768px) {
  .editor-header {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
    padding: 12px 16px;
  }

  .header-right {
    justify-content: flex-end;
  }

  .editor-toolbar {
    flex-direction: column;
    gap: 12px;
    padding: 12px 16px;
  }

  .toolbar-actions {
    width: 100%;
    justify-content: space-between;
  }

  .zoom-slider {
    flex: 1;
  }

  .editor-content {
    flex-direction: column;
  }

  .image-pane {
    flex: 1;
    border-right: none;
    border-bottom: 1px solid #E8DFD0;
  }

  .text-pane {
    flex: 1;
  }
}
</style>
