<template>
  <div class="upload-area">
    <div
      class="upload-zone"
      :class="{ 'is-dragover': isDragging, 'is-uploading': uploading }"
      @dragover.prevent="handleDragOver"
      @dragleave.prevent="handleDragLeave"
      @drop.prevent="handleDrop"
      @click="triggerFileInput"
    >
      <input
        ref="fileInputRef"
        type="file"
        class="file-input"
        :accept="acceptTypes"
        multiple
        @change="handleFileSelect"
      />
      
      <template v-if="!uploading">
        <div class="upload-icon">
          <icon-park theme="outline" size="64" name="upload" :fill="['#C41E3A', '#F5D6D9']" />
        </div>
        <h3 class="upload-title">拖拽文件到此处上传</h3>
        <p class="upload-subtitle">或点击选择文件</p>
        <div class="upload-tips">
          <el-tag size="small" type="info">支持图片格式 (JPG, PNG, TIFF)</el-tag>
          <el-tag size="small" type="info">支持 PDF 文档</el-tag>
          <el-tag size="small" type="info">单文件最大 50MB</el-tag>
        </div>
      </template>

      <template v-else>
        <el-icon class="uploading-icon" :size="64">
          <Loading />
        </el-icon>
        <h3 class="upload-title">正在上传...</h3>
        <p class="upload-subtitle">{{ currentFileName }}</p>
      </template>
    </div>

    <div v-if="fileList.length > 0" class="file-list">
      <div v-for="file in fileList" :key="file.uid" class="file-item">
        <div class="file-info">
          <el-icon class="file-icon">
            <Document v-if="file.type === 'pdf'" />
            <Picture v-else />
          </el-icon>
          <div class="file-meta">
            <span class="file-name">{{ file.name }}</span>
            <span class="file-size">{{ formatFileSize(file.size) }}</span>
          </div>
        </div>
        <div class="file-progress">
          <el-progress
            :percentage="file.percentage"
            :status="file.status"
            :stroke-width="4"
            :show-text="false"
          />
        </div>
        <el-button
          v-if="file.status !== 'uploading'"
          type="text"
          :icon="file.status === 'success' ? Check : Close"
          :class="['status-btn', file.status]"
          @click.stop="removeFile(file)"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { ElMessage } from 'element-plus';
import { Loading, Document, Picture, Check, Close } from '@element-plus/icons-vue';
import { uploadFile } from '../api';
import type { UploadResponse } from '../types';

interface UploadFileItem {
  uid: string;
  name: string;
  size: number;
  type: string;
  file: File;
  percentage: number;
  status: 'uploading' | 'success' | 'exception';
  taskId?: string;
}

const props = defineProps<{
  acceptTypes?: string;
  maxSize?: number;
}>();

const emit = defineEmits<{
  (e: 'upload-success', response: UploadResponse): void;
  (e: 'upload-error', error: Error): void;
  (e: 'file-added', file: File): void;
  (e: 'file-removed', file: UploadFileItem): void;
}>();

const acceptTypes = computed(() => props.acceptTypes || 'image/*,.pdf,.jpg,.jpeg,.png,.tiff,.tif');
const maxSize = computed(() => props.maxSize || 50 * 1024 * 1024);

const fileInputRef = ref<HTMLInputElement | null>(null);
const isDragging = ref(false);
const uploading = ref(false);
const currentFileName = ref('');
const fileList = ref<UploadFileItem[]>([]);

const generateUid = () => Math.random().toString(36).substring(2, 15);

const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
};

const getFileType = (file: File): string => {
  if (file.type === 'application/pdf') return 'pdf';
  if (file.type.startsWith('image/')) return 'image';
  return file.type;
};

const validateFile = (file: File): boolean => {
  const validTypes = ['image/jpeg', 'image/png', 'image/tiff', 'image/jpg', 'image/tif', 'application/pdf'];
  if (!validTypes.includes(file.type) && !/\.(jpg|jpeg|png|tiff|tif|pdf)$/i.test(file.name)) {
    ElMessage.error(`不支持的文件格式: ${file.name}`);
    return false;
  }
  if (file.size > maxSize.value) {
    ElMessage.error(`文件大小超过限制: ${file.name} (最大 ${maxSize.value / 1024 / 1024}MB)`);
    return false;
  }
  return true;
};

const triggerFileInput = () => {
  if (!uploading.value && fileInputRef.value) {
    fileInputRef.value.click();
  }
};

const handleDragOver = () => {
  if (!uploading.value) {
    isDragging.value = true;
  }
};

const handleDragLeave = () => {
  isDragging.value = false;
};

const handleDrop = (e: DragEvent) => {
  isDragging.value = false;
  if (uploading.value) return;
  
  const files = Array.from(e.dataTransfer?.files || []);
  handleFiles(files);
};

const handleFileSelect = (e: Event) => {
  const target = e.target as HTMLInputElement;
  const files = Array.from(target.files || []);
  handleFiles(files);
  target.value = '';
};

const handleFiles = async (files: File[]) => {
  const validFiles = files.filter(validateFile);
  if (validFiles.length === 0) return;

  for (const file of validFiles) {
    const fileItem: UploadFileItem = {
      uid: generateUid(),
      name: file.name,
      size: file.size,
      type: getFileType(file),
      file,
      percentage: 0,
      status: 'uploading'
    };
    
    fileList.value.push(fileItem);
    emit('file-added', file);
    
    await uploadSingleFile(fileItem);
  }
};

const uploadSingleFile = async (fileItem: UploadFileItem) => {
  uploading.value = true;
  currentFileName.value = fileItem.name;
  
  try {
    const response = await uploadFile(fileItem.file, (progress) => {
      fileItem.percentage = Math.min(progress, 99);
    });
    
    fileItem.percentage = 100;
    fileItem.status = 'success';
    fileItem.taskId = response.taskId;
    
    emit('upload-success', response);
    ElMessage.success(`${fileItem.name} 上传成功`);
  } catch (error) {
    fileItem.status = 'exception';
    const err = error instanceof Error ? error : new Error('上传失败');
    emit('upload-error', err);
    ElMessage.error(`${fileItem.name} 上传失败: ${err.message}`);
  } finally {
    uploading.value = false;
    currentFileName.value = '';
  }
};

const removeFile = (fileItem: UploadFileItem) => {
  const index = fileList.value.findIndex(f => f.uid === fileItem.uid);
  if (index > -1) {
    fileList.value.splice(index, 1);
    emit('file-removed', fileItem);
  }
};
</script>

<style lang="scss" scoped>
.upload-area {
  width: 100%;
}

.upload-zone {
  position: relative;
  padding: 60px 40px;
  text-align: center;
  background: var(--color-rice-paper-light);
  border: 2px dashed var(--color-rice-paper-dark);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: all var(--transition-normal);

  &:hover {
    border-color: var(--color-vermilion);
    background: rgba(196, 30, 58, 0.02);
  }

  &.is-dragover {
    border-color: var(--color-vermilion);
    background: rgba(196, 30, 58, 0.05);
    transform: scale(1.01);
  }

  &.is-uploading {
    cursor: not-allowed;
    opacity: 0.7;
  }
}

.file-input {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  opacity: 0;
  cursor: pointer;
}

.upload-icon,
.uploading-icon {
  margin-bottom: 16px;
  color: var(--color-vermilion);
}

.uploading-icon {
  animation: rotate 1s linear infinite;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.upload-title {
  font-family: var(--font-serif);
  font-size: 20px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0 0 8px 0;
}

.upload-subtitle {
  font-size: 14px;
  color: var(--color-ink-lighter);
  margin: 0 0 20px 0;
}

.upload-tips {
  display: flex;
  justify-content: center;
  gap: 8px;
  flex-wrap: wrap;
}

.file-list {
  margin-top: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  background: var(--color-rice-paper-light);
  border: 1px solid var(--color-rice-paper-dark);
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);

  &:hover {
    border-color: var(--color-ink-lighter);
  }
}

.file-info {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
}

.file-icon {
  font-size: 28px;
  color: var(--color-ink-light);
  flex-shrink: 0;
}

.file-meta {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.file-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-size {
  font-size: 12px;
  color: var(--color-ink-lighter);
}

.file-progress {
  width: 160px;
  flex-shrink: 0;
}

.status-btn {
  &.success {
    color: var(--color-success);
  }
  &.exception {
    color: var(--color-danger);
  }
}

@media (max-width: 768px) {
  .upload-zone {
    padding: 40px 20px;
  }

  .file-item {
    flex-direction: column;
    align-items: stretch;
  }

  .file-progress {
    width: 100%;
  }
}
</style>
