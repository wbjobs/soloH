<template>
  <el-dialog
    v-model="visible"
    title="导出识别结果"
    width="480px"
    :close-on-click-modal="!exporting"
    :close-on-press-escape="!exporting"
    @close="handleClose"
  >
    <div class="export-dialog">
      <div v-if="!exporting" class="export-form">
        <div class="form-group">
          <label class="form-label">导出格式</label>
          <div class="format-options">
            <div
              v-for="format in formats"
              :key="format.value"
              class="format-option"
              :class="{ 'is-active': selectedFormat === format.value }"
              @click="selectedFormat = format.value"
            >
              <div class="format-icon">
                <el-icon :size="24">
                  <component :is="format.icon" />
                </el-icon>
              </div>
              <div class="format-info">
                <span class="format-name">{{ format.label }}</span>
                <span class="format-desc">{{ format.desc }}</span>
              </div>
              <el-radio :model-value="selectedFormat" :label="format.value" />
            </div>
          </div>
        </div>

        <div class="form-group">
          <label class="form-label">导出选项</label>
          <div class="option-list">
            <el-checkbox v-model="includeConfidence">
              包含置信度信息
            </el-checkbox>
            <el-checkbox v-model="includeBBox">
              包含文本框坐标
            </el-checkbox>
            <el-checkbox v-model="includeImages">
              包含原始图片
            </el-checkbox>
          </div>
        </div>

        <div v-if="selectedFormat === 'tei'" class="form-group">
          <label class="form-label">TEI 配置</label>
          <div class="option-list">
            <el-input
              v-model="teiTitle"
              placeholder="文档标题"
              clearable
            />
            <el-input
              v-model="teiAuthor"
              placeholder="作者"
              clearable
            />
            <el-select
              v-model="teiLanguage"
              placeholder="语言"
              class="w-full"
            >
              <el-option label="中文 (zh)" value="zh" />
              <el-option label="英文 (en)" value="en" />
              <el-option label="日文 (ja)" value="ja" />
            </el-select>
          </div>
        </div>

        <div v-if="selectedFormat === 'markdown'" class="form-group">
          <label class="form-label">Markdown 配置</label>
          <div class="option-list">
            <el-checkbox v-model="mdPageBreak">
              分页处插入分隔符
            </el-checkbox>
            <el-checkbox v-model="mdFrontMatter">
              包含 YAML Front Matter
            </el-checkbox>
          </div>
        </div>

        <div class="form-group">
          <label class="form-label">导出范围</label>
          <el-radio-group v-model="exportRange">
            <el-radio value="all">全部 ({{ totalPages }} 页)</el-radio>
            <el-radio value="range">指定范围</el-radio>
          </el-radio-group>
          <el-input
            v-if="exportRange === 'range'"
            v-model="pageRange"
            placeholder="例如: 1-5, 8, 10-12"
            class="range-input"
          />
        </div>
      </div>

      <div v-else class="export-progress">
        <div class="progress-icon">
          <el-icon :size="48" :class="{ 'is-success': exportComplete, 'is-error': exportError }">
            <Loading v-if="!exportComplete && !exportError" class="rotating" />
            <CircleCheck v-else-if="exportComplete" />
            <CircleClose v-else />
          </el-icon>
        </div>
        <h4 class="progress-title">
          {{ exportComplete ? '导出完成' : exportError ? '导出失败' : '正在导出...' }}
        </h4>
        <p class="progress-desc">
          {{ exportComplete ? fileName : exportError || currentStep }}
        </p>

        <div class="progress-bar-wrapper">
          <el-progress
            :percentage="exportProgress"
            :status="exportComplete ? 'success' : exportError ? 'exception' : ''"
            :stroke-width="6"
          />
        </div>

        <div v-if="exportComplete && downloadUrl" class="download-section">
          <el-button type="primary" :icon="Download" @click="handleDownload">
            下载文件
          </el-button>
          <span class="file-info">{{ fileSize }}</span>
        </div>

        <div v-if="exportError" class="error-section">
          <el-button type="primary" @click="handleRetry">
            重试
          </el-button>
        </div>
      </div>
    </div>

    <template #footer>
      <template v-if="!exporting">
        <el-button @click="handleClose">取消</el-button>
        <el-button type="primary" :disabled="!canExport" @click="handleExport">
          开始导出
        </el-button>
      </template>
      <template v-else>
        <el-button v-if="exportComplete || exportError" @click="handleClose">
          {{ exportComplete ? '完成' : '关闭' }}
        </el-button>
      </template>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { ElMessage } from 'element-plus';
import {
  Loading,
  CircleCheck,
  CircleClose,
  Download,
  Document,
  Files
} from '@element-plus/icons-vue';
import { exportTask } from '../api';

const props = defineProps<{
  modelValue: boolean;
  taskId: string;
  taskName?: string;
  totalPages?: number;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
  (e: 'success', data: { url: string; fileName: string }): void;
  (e: 'error', error: Error): void;
}>();

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
});

const formats = [
  { value: 'markdown', label: 'Markdown', desc: '通用文本格式，便于阅读和编辑', icon: Document },
  { value: 'tei', label: 'TEI XML', desc: '文本编码倡议标准，适合学术研究', icon: Files }
] as const;

const selectedFormat = ref<'markdown' | 'tei'>('markdown');
const includeConfidence = ref(false);
const includeBBox = ref(false);
const includeImages = ref(false);
const exportRange = ref<'all' | 'range'>('all');
const pageRange = ref('');
const teiTitle = ref('');
const teiAuthor = ref('');
const teiLanguage = ref('zh');
const mdPageBreak = ref(true);
const mdFrontMatter = ref(false);

const exporting = ref(false);
const exportComplete = ref(false);
const exportError = ref<string | null>(null);
const exportProgress = ref(0);
const currentStep = ref('准备导出...');
const downloadUrl = ref('');
const fileName = ref('');
const fileSize = ref('');

const canExport = computed(() => {
  if (exportRange.value === 'range' && !pageRange.value.trim()) {
    return false;
  }
  return true;
});

const steps = [
  '正在准备导出数据...',
  '正在生成文档结构...',
  '正在写入内容...',
  '正在处理图片资源...',
  '正在生成文件...',
  '导出完成'
];

const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
};

const simulateProgress = async () => {
  for (let i = 0; i < steps.length; i++) {
    if (exportError.value) return;
    currentStep.value = steps[i];
    exportProgress.value = Math.round(((i + 1) / steps.length) * 100);
    await new Promise(resolve => setTimeout(resolve, 600));
  }
};

const handleExport = async () => {
  if (!canExport.value) return;

  exporting.value = true;
  exportComplete.value = false;
  exportError.value = null;
  exportProgress.value = 0;
  currentStep.value = steps[0];
  downloadUrl.value = '';

  try {
    const format = selectedFormat.value as 'markdown' | 'tei';

    const progressPromise = simulateProgress();

    const blob = await exportTask(props.taskId, format);

    await progressPromise;

    const ext = selectedFormat.value === 'tei' ? 'xml' : 'md';
    fileName.value = `${props.taskName || 'export'}.${ext}`;
    
    const url = URL.createObjectURL(blob);
    downloadUrl.value = url;
    fileSize.value = formatFileSize(blob.size);
    exportComplete.value = true;
    exportProgress.value = 100;

    emit('success', { url, fileName: fileName.value });
  } catch (error) {
    exportError.value = error instanceof Error ? error.message : '导出失败，请稍后重试';
    emit('error', error instanceof Error ? error : new Error('导出失败'));
  }
};

const handleDownload = () => {
  if (!downloadUrl.value) return;

  const link = document.createElement('a');
  link.href = downloadUrl.value;
  link.download = fileName.value;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  ElMessage.success('开始下载');
};

const handleRetry = () => {
  exportError.value = null;
  exportProgress.value = 0;
  handleExport();
};

const handleClose = () => {
  if (exporting.value && !exportComplete.value && !exportError.value) {
    return;
  }
  resetState();
  visible.value = false;
};

const resetState = () => {
  exporting.value = false;
  exportComplete.value = false;
  exportError.value = null;
  exportProgress.value = 0;
  currentStep.value = '';
  downloadUrl.value = '';
  fileName.value = '';
  fileSize.value = '';
};

watch(visible, (newVal) => {
  if (newVal) {
    resetState();
  }
});
</script>

<style lang="scss" scoped>
.export-dialog {
  min-height: 300px;
}

.export-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.form-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-ink);
}

.format-options {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.format-option {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border: 2px solid var(--color-rice-paper-dark);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);

  &:hover {
    border-color: var(--color-vermilion);
    background: rgba(196, 30, 58, 0.02);
  }

  &.is-active {
    border-color: var(--color-vermilion);
    background: rgba(196, 30, 58, 0.05);

    .format-icon {
      background: var(--color-vermilion);
      color: white;
    }

    .format-name {
      color: var(--color-vermilion);
    }
  }
}

.format-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  background: var(--color-rice-paper-dark);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-ink-light);
  transition: all var(--transition-fast);
}

.format-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.format-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-ink);
  transition: color var(--transition-fast);
}

.format-desc {
  font-size: 12px;
  color: var(--color-ink-lighter);
}

.option-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.range-input {
  margin-top: 8px;
}

.export-progress {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  text-align: center;
}

.progress-icon {
  margin-bottom: 20px;

  .el-icon {
    transition: all var(--transition-normal);

    &.rotating {
      animation: rotate 1s linear infinite;
      color: var(--color-vermilion);
    }

    &.is-success {
      color: var(--color-success);
    }

    &.is-error {
      color: var(--color-danger);
    }
  }
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.progress-title {
  font-family: var(--font-serif);
  font-size: 18px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0 0 8px 0;
}

.progress-desc {
  font-size: 14px;
  color: var(--color-ink-lighter);
  margin: 0 0 24px 0;
  max-width: 300px;
  word-break: break-all;
}

.progress-bar-wrapper {
  width: 100%;
  max-width: 320px;
  margin-bottom: 24px;
}

.download-section {
  display: flex;
  align-items: center;
  gap: 12px;
}

.file-info {
  font-size: 13px;
  color: var(--color-ink-lighter);
}

.error-section {
  display: flex;
  gap: 12px;
}

:deep(.el-dialog__header) {
  border-bottom: 1px solid var(--color-rice-paper-dark);
  padding-bottom: 16px;
  margin-right: 0;
}

:deep(.el-dialog__title) {
  font-family: var(--font-serif);
  font-size: 18px;
  color: var(--color-ink);
}

:deep(.el-dialog__footer) {
  border-top: 1px solid var(--color-rice-paper-dark);
  padding-top: 16px;
}

:deep(.el-radio__input.is-checked .el-radio__inner) {
  background-color: var(--color-vermilion);
  border-color: var(--color-vermilion);
}

:deep(.el-checkbox__input.is-checked .el-checkbox__inner) {
  background-color: var(--color-vermilion);
  border-color: var(--color-vermilion);
}

:deep(.el-radio__label) {
  font-size: 14px;
}

@media (max-width: 768px) {
  :deep(.el-dialog) {
    width: 95% !important;
    margin: 2.5vh auto !important;
  }

  .export-form {
    gap: 16px;
  }

  .format-option {
    padding: 10px 12px;
  }
}
</style>
