<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Upload as UploadIcon, FileX, Eye, Trash2, Check, AlertCircle, FileText, Dna, Users } from 'lucide-vue-next';
import { useFileStore } from '@/stores';
import { uploadAPI, analysisAPI } from '@/services/api';
import type { UploadFile, SampleMatchResult } from '@/types';

const fileStore = useFileStore();

const activeTab = ref<'vcf' | 'phenotype' | 'covariate'>('vcf');

const vcfUploading = ref(false);
const phenotypeUploading = ref(false);
const covariateUploading = ref(false);
const uploadProgress = ref(0);
const previewFile = ref<UploadFile | null>(null);
const previewData = ref<any>(null);
const previewLoading = ref(false);

const isDragging = ref(false);
const sampleMatchResult = ref<SampleMatchResult | null>(null);
const matchLoading = ref(false);

const loadFiles = async () => {
  try {
    const [vcfs, phenotypes, covariates] = await Promise.all([
      uploadAPI.listFiles('vcf'),
      uploadAPI.listFiles('phenotype'),
      uploadAPI.listFiles('covariate'),
    ]);
    fileStore.setVCFFiles(vcfs);
    fileStore.setPhenotypeFiles(phenotypes);
    fileStore.setCovariateFiles(covariates);
  } catch (e) {
    console.error('Failed to load files:', e);
  }
};

const handleFileUpload = async (event: any, type: 'vcf' | 'phenotype' | 'covariate') => {
  const files = event.target.files || event.dataTransfer?.files;
  if (!files || files.length === 0) return;
  
  const file = files[0];
  
  const allowedExtensions = type === 'vcf' 
    ? ['.vcf', '.vcf.gz'] 
    : ['.csv', '.txt'];
  
  const fileName = file.name.toLowerCase();
  const isValid = allowedExtensions.some(ext => fileName.endsWith(ext));
  
  if (!isValid) {
    ElMessage.error(`不支持的文件格式，请上传${allowedExtensions.join('、')}文件`);
    return;
  }
  
  try {
    if (type === 'vcf') vcfUploading.value = true;
    else if (type === 'phenotype') phenotypeUploading.value = true;
    else covariateUploading.value = true;
    
    uploadProgress.value = 0;
    
    const onProgress = (progress: number) => {
      uploadProgress.value = progress;
    };
    
    let result: UploadFile;
    if (type === 'vcf') {
      result = await uploadAPI.uploadVCF(file, onProgress);
      fileStore.addVCFFile(result);
    } else if (type === 'phenotype') {
      result = await uploadAPI.uploadPhenotype(file, onProgress);
      fileStore.addPhenotypeFile(result);
    } else {
      result = await uploadAPI.uploadCovariate(file, onProgress);
      fileStore.addCovariateFile(result);
    }
    
    ElMessage.success(`${file.name} 上传成功`);
  } catch (e) {
    console.error('Upload failed:', e);
  } finally {
    vcfUploading.value = false;
    phenotypeUploading.value = false;
    covariateUploading.value = false;
    uploadProgress.value = 0;
  }
};

const handleDragOver = (e: DragEvent) => {
  e.preventDefault();
  isDragging.value = true;
};

const handleDragLeave = () => {
  isDragging.value = false;
};

const handleDrop = (e: DragEvent, type: 'vcf' | 'phenotype' | 'covariate') => {
  e.preventDefault();
  isDragging.value = false;
  handleFileUpload(e, type);
};

const handlePreview = async (file: UploadFile) => {
  try {
    previewLoading.value = true;
    previewFile.value = file;
    const result = await uploadAPI.getFilePreview(file.fileId);
    previewData.value = result.preview;
  } catch (e) {
    console.error('Preview failed:', e);
  } finally {
    previewLoading.value = false;
  }
};

const handleDelete = async (file: UploadFile) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除文件 "${file.fileName}" 吗？此操作不可恢复。`,
      '确认删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    );
    
    await uploadAPI.deleteFile(file.fileId);
    fileStore.removeFile(file.fileId, file.fileType);
    ElMessage.success('文件删除成功');
    
    if (previewFile.value?.fileId === file.fileId) {
      previewFile.value = null;
      previewData.value = null;
    }
  } catch (e) {
    if (e !== 'cancel') {
      console.error('Delete failed:', e);
    }
  }
};

const handleSelectFile = (file: UploadFile) => {
  if (file.fileType === 'vcf') {
    fileStore.selectedVCF = file;
  } else if (file.fileType === 'phenotype') {
    fileStore.selectedPhenotype = file;
    fileStore.selectedPhenotypeName = '';
  }
};

const handleMatchSamples = async () => {
  if (!fileStore.selectedVCF || !fileStore.selectedPhenotype) {
    ElMessage.warning('请先选择VCF文件和表型文件');
    return;
  }
  
  try {
    matchLoading.value = true;
    sampleMatchResult.value = await analysisAPI.matchSamples(
      fileStore.selectedVCF.fileId,
      fileStore.selectedPhenotype.fileId
    );
  } catch (e) {
    console.error('Match failed:', e);
  } finally {
    matchLoading.value = false;
  }
};

const formatFileSize = (bytes: number) => {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
};

const filesByType = computed(() => {
  return {
    vcf: fileStore.vcfFiles,
    phenotype: fileStore.phenotypeFiles,
    covariate: fileStore.covariateFiles,
  };
});

const selectedFileInfo = computed(() => {
  return {
    vcf: fileStore.selectedVCF,
    phenotype: fileStore.selectedPhenotype,
  };
});

const matchStatus = computed(() => {
  if (!sampleMatchResult.value) return null;
  const { matchCount, vcfTotal, phenotypeTotal } = sampleMatchResult.value;
  if (matchCount === 0) return 'error';
  if (matchCount < Math.min(vcfTotal, phenotypeTotal) * 0.8) return 'warning';
  return 'success';
});

onMounted(() => {
  loadFiles();
});
</script>

<template>
  <div class="upload-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">数据上传</h2>
        <p class="page-desc">上传基因型数据（VCF）、表型数据（CSV）和协变量文件进行GWAS分析</p>
      </div>
      <div class="quick-actions">
        <el-button type="primary" @click="handleMatchSamples" :loading="matchLoading">
          <Check class="btn-icon" />
          匹配样本
        </el-button>
      </div>
    </div>
    
    <div class="upload-tabs">
      <button
        v-for="tab in ['vcf', 'phenotype', 'covariate'] as const"
        :key="tab"
        :class="['tab-btn', { active: activeTab === tab }]"
        @click="activeTab = tab"
      >
        <Dna v-if="tab === 'vcf'" class="tab-icon" />
        <FileText v-else-if="tab === 'phenotype'" class="tab-icon" />
        <Users v-else class="tab-icon" />
        {{ tab === 'vcf' ? '基因型数据 (VCF)' : tab === 'phenotype' ? '表型数据 (CSV)' : '协变量文件' }}
        <span v-if="filesByType[tab].length > 0" class="tab-badge">
          {{ filesByType[tab].length }}
        </span>
      </button>
    </div>
    
    <div class="upload-area-wrapper">
      <div
        class="upload-area"
        :class="{ dragging: isDragging }"
        @dragover="handleDragOver"
        @dragleave="handleDragLeave"
        @drop="handleDrop($event, activeTab)"
      >
        <input
          type="file"
          :id="`file-input-${activeTab}`"
          class="file-input"
          :accept="activeTab === 'vcf' ? '.vcf,.vcf.gz' : '.csv,.txt'"
          @change="handleFileUpload($event, activeTab)"
          :disabled="activeTab === 'vcf' ? vcfUploading : activeTab === 'phenotype' ? phenotypeUploading : covariateUploading"
        />
        
        <label :for="`file-input-${activeTab}`" class="upload-label">
          <div class="upload-icon-wrapper">
            <UploadIcon class="upload-icon" />
          </div>
          <h3 class="upload-title">
            {{ activeTab === 'vcf' ? '上传VCF文件' : activeTab === 'phenotype' ? '上传表型CSV文件' : '上传协变量文件' }}
          </h3>
          <p class="upload-desc">
            点击或拖拽文件到此处上传<br />
            <span class="format-hint">
              支持格式: {{ activeTab === 'vcf' ? '.vcf, .vcf.gz' : '.csv, .txt' }}
            </span>
          </p>
          
          <div v-if="uploadProgress > 0" class="progress-bar-wrapper">
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: uploadProgress + '%' }"></div>
            </div>
            <span class="progress-text">{{ uploadProgress }}%</span>
          </div>
        </label>
      </div>
    </div>
    
    <div v-if="sampleMatchResult" class="match-result-card" :class="matchStatus">
      <div class="match-header">
        <AlertCircle v-if="matchStatus === 'error'" class="match-icon error" />
        <AlertCircle v-else-if="matchStatus === 'warning'" class="match-icon warning" />
        <Check v-else class="match-icon success" />
        <h3 class="match-title">样本匹配结果</h3>
      </div>
      <div class="match-stats">
        <div class="stat">
          <span class="stat-value">{{ sampleMatchResult.vcfTotal }}</span>
          <span class="stat-label">VCF样本</span>
        </div>
        <div class="stat">
          <span class="stat-value">{{ sampleMatchResult.phenotypeTotal }}</span>
          <span class="stat-label">表型样本</span>
        </div>
        <div class="stat highlight">
          <span class="stat-value">{{ sampleMatchResult.matchCount }}</span>
          <span class="stat-label">匹配成功</span>
        </div>
        <div class="stat">
          <span class="stat-value">{{ sampleMatchResult.vcfOnlySamples.length }}</span>
          <span class="stat-label">仅VCF</span>
        </div>
        <div class="stat">
          <span class="stat-value">{{ sampleMatchResult.phenotypeOnlySamples.length }}</span>
          <span class="stat-label">仅表型</span>
        </div>
      </div>
    </div>
    
    <div class="files-section">
      <h3 class="section-title">
        已上传的{{ activeTab === 'vcf' ? '基因型' : activeTab === 'phenotype' ? '表型' : '协变量' }}文件
      </h3>
      
      <div v-if="filesByType[activeTab].length === 0" class="empty-state">
        <FileX class="empty-icon" />
        <p class="empty-text">暂无{{ activeTab === 'vcf' ? 'VCF' : activeTab === 'phenotype' ? '表型' : '协变量' }}文件</p>
      </div>
      
      <div v-else class="files-grid">
        <div
          v-for="file in filesByType[activeTab]"
          :key="file.fileId"
          :class="['file-card', { selected: selectedFileInfo[file.fileType as keyof typeof selectedFileInfo]?.fileId === file.fileId }]"
        >
          <div class="file-header">
            <div class="file-icon-wrapper" :class="file.fileType">
              <Dna v-if="file.fileType === 'vcf'" class="file-icon" />
              <FileText v-else class="file-icon" />
            </div>
            <div class="file-info">
              <h4 class="file-name" :title="file.fileName">{{ file.fileName }}</h4>
              <div class="file-meta">
                <span>{{ formatFileSize(file.fileSize) }}</span>
                <span v-if="file.sampleCount">{{ file.sampleCount }} 样本</span>
                <span v-if="file.variantCount">{{ file.variantCount.toLocaleString() }} 变异</span>
              </div>
            </div>
          </div>
          
          <div v-if="file.phenotypeNames" class="phenotype-tags">
            <el-tag
              v-for="name in file.phenotypeNames.slice(0, 5)"
              :key="name"
              size="small"
              :type="fileStore.selectedPhenotypeName === name ? 'success' : 'info'"
              class="phenotype-tag"
              @click="fileStore.selectedPhenotypeName = name"
            >
              {{ name }}
            </el-tag>
            <span v-if="file.phenotypeNames.length > 5" class="more-tags">
              +{{ file.phenotypeNames.length - 5 }}
            </span>
          </div>
          
          <div class="file-actions">
            <button class="action-btn" @click="handlePreview(file)" :loading="previewLoading && previewFile?.fileId === file.fileId">
              <Eye class="action-icon" />
              预览
            </button>
            <button 
              class="action-btn select-btn" 
              @click="handleSelectFile(file)"
              :class="{ active: selectedFileInfo[file.fileType as keyof typeof selectedFileInfo]?.fileId === file.fileId }"
            >
              <Check class="action-icon" />
              {{ selectedFileInfo[file.fileType as keyof typeof selectedFileInfo]?.fileId === file.fileId ? '已选择' : '选择' }}
            </button>
            <button class="action-btn delete-btn" @click="handleDelete(file)">
              <Trash2 class="action-icon" />
            </button>
          </div>
        </div>
      </div>
    </div>
    
    <el-dialog v-model="previewFile" title="文件预览" width="900px" class="preview-dialog">
      <div class="preview-content">
        <div class="preview-header">
          <span class="preview-filename">{{ previewFile?.fileName }}</span>
          <span class="preview-type">{{ previewFile?.fileType?.toUpperCase() }}</span>
        </div>
        
        <div v-if="previewLoading" class="preview-loading">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>加载中...</span>
        </div>
        
        <div v-else-if="previewData" class="preview-table-wrapper">
          <el-table :data="previewData.rows" border size="small" max-height="500">
            <el-table-column
              v-for="(header, index) in previewData.headers"
              :key="index"
              :prop="index.toString()"
              :label="header"
              :min-width="120"
            >
              <template #default="{ row }">
                {{ row[index] }}
              </template>
            </el-table-column>
          </el-table>
          <p class="preview-note">* 仅显示前10行数据</p>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script lang="ts">
import { Loading } from '@element-plus/icons-vue';
export default { components: { Loading } };
</script>

<style scoped>
.upload-page {
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 32px;
}

.page-title {
  font-size: 28px;
  font-weight: 700;
  color: #FFFFFF;
  margin: 0 0 8px 0;
}

.page-desc {
  font-size: 14px;
  color: #94A3B8;
  margin: 0;
}

.btn-icon {
  margin-right: 6px;
}

.upload-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
  background: rgba(30, 41, 59, 0.5);
  padding: 6px;
  border-radius: 12px;
  width: fit-content;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  border: none;
  background: transparent;
  color: #94A3B8;
  font-size: 14px;
  font-weight: 500;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.tab-btn:hover {
  color: #FFFFFF;
  background: rgba(51, 65, 85, 0.5);
}

.tab-btn.active {
  background: linear-gradient(135deg, #165DFF, #00B42A);
  color: #FFFFFF;
  box-shadow: 0 4px 12px rgba(22, 93, 255, 0.3);
}

.tab-icon {
  width: 18px;
  height: 18px;
}

.tab-badge {
  min-width: 22px;
  height: 22px;
  padding: 0 6px;
  background: rgba(255, 255, 255, 0.2);
  color: white;
  font-size: 11px;
  font-weight: 600;
  border-radius: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.upload-area-wrapper {
  margin-bottom: 32px;
}

.upload-area {
  border: 2px dashed #334155;
  border-radius: 16px;
  padding: 48px;
  text-align: center;
  background: rgba(30, 41, 59, 0.3);
  transition: all 0.3s ease;
}

.upload-area:hover,
.upload-area.dragging {
  border-color: #165DFF;
  background: rgba(22, 93, 255, 0.05);
}

.file-input {
  display: none;
}

.upload-label {
  cursor: pointer;
  display: block;
}

.upload-icon-wrapper {
  width: 72px;
  height: 72px;
  margin: 0 auto 20px;
  background: linear-gradient(135deg, rgba(22, 93, 255, 0.1), rgba(0, 180, 42, 0.1));
  border: 2px dashed rgba(22, 93, 255, 0.3);
  border-radius: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.upload-icon {
  width: 36px;
  height: 36px;
  color: #165DFF;
}

.upload-title {
  font-size: 18px;
  font-weight: 600;
  color: #FFFFFF;
  margin: 0 0 8px 0;
}

.upload-desc {
  font-size: 14px;
  color: #94A3B8;
  margin: 0;
  line-height: 1.6;
}

.format-hint {
  font-size: 12px;
  color: #64748B;
}

.progress-bar-wrapper {
  margin-top: 24px;
  max-width: 300px;
  margin-left: auto;
  margin-right: auto;
}

.progress-bar {
  height: 8px;
  background: #1E293B;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 8px;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #165DFF, #00B42A);
  border-radius: 4px;
  transition: width 0.3s ease;
}

.progress-text {
  font-size: 12px;
  color: #165DFF;
  font-weight: 500;
}

.match-result-card {
  background: rgba(30, 41, 59, 0.5);
  border: 1px solid #334155;
  border-radius: 16px;
  padding: 24px;
  margin-bottom: 32px;
}

.match-result-card.success {
  border-color: rgba(0, 180, 42, 0.5);
  background: rgba(0, 180, 42, 0.05);
}

.match-result-card.warning {
  border-color: rgba(255, 125, 0, 0.5);
  background: rgba(255, 125, 0, 0.05);
}

.match-result-card.error {
  border-color: rgba(245, 63, 63, 0.5);
  background: rgba(245, 63, 63, 0.05);
}

.match-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.match-icon {
  width: 28px;
  height: 28px;
}

.match-icon.success {
  color: #00B42A;
}

.match-icon.warning {
  color: #FF7D00;
}

.match-icon.error {
  color: #F53F3F;
}

.match-title {
  font-size: 18px;
  font-weight: 600;
  color: #FFFFFF;
  margin: 0;
}

.match-stats {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
}

.stat {
  text-align: center;
  padding: 16px;
  background: rgba(15, 23, 42, 0.5);
  border-radius: 12px;
}

.stat.highlight {
  background: rgba(22, 93, 255, 0.1);
  border: 1px solid rgba(22, 93, 255, 0.3);
}

.stat-value {
  display: block;
  font-size: 28px;
  font-weight: 700;
  color: #FFFFFF;
  margin-bottom: 4px;
}

.stat.highlight .stat-value {
  color: #165DFF;
}

.stat-label {
  font-size: 12px;
  color: #94A3B8;
}

.files-section {
  margin-top: 32px;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: #FFFFFF;
  margin: 0 0 20px 0;
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  background: rgba(30, 41, 59, 0.3);
  border-radius: 12px;
}

.empty-icon {
  width: 48px;
  height: 48px;
  color: #475569;
  margin-bottom: 16px;
}

.empty-text {
  font-size: 14px;
  color: #64748B;
  margin: 0;
}

.files-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 16px;
}

.file-card {
  background: rgba(30, 41, 59, 0.5);
  border: 1px solid #334155;
  border-radius: 14px;
  padding: 20px;
  transition: all 0.2s ease;
}

.file-card:hover {
  border-color: #165DFF;
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
}

.file-card.selected {
  border-color: #00B42A;
  background: rgba(0, 180, 42, 0.05);
}

.file-header {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  margin-bottom: 16px;
}

.file-icon-wrapper {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.file-icon-wrapper.vcf {
  background: linear-gradient(135deg, rgba(22, 93, 255, 0.2), rgba(114, 46, 209, 0.2));
}

.file-icon-wrapper.phenotype {
  background: linear-gradient(135deg, rgba(0, 180, 42, 0.2), rgba(20, 201, 201, 0.2));
}

.file-icon-wrapper.covariate {
  background: linear-gradient(135deg, rgba(255, 125, 0, 0.2), rgba(245, 63, 63, 0.2));
}

.file-icon {
  width: 24px;
  height: 24px;
}

.file-icon-wrapper.vcf .file-icon {
  color: #165DFF;
}

.file-icon-wrapper.phenotype .file-icon {
  color: #00B42A;
}

.file-icon-wrapper.covariate .file-icon {
  color: #FF7D00;
}

.file-info {
  flex: 1;
  min-width: 0;
}

.file-name {
  font-size: 14px;
  font-weight: 600;
  color: #FFFFFF;
  margin: 0 0 6px 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #64748B;
}

.phenotype-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 16px;
  align-items: center;
}

.phenotype-tag {
  cursor: pointer;
  transition: all 0.2s ease;
}

.phenotype-tag:hover {
  transform: scale(1.05);
}

.more-tags {
  font-size: 12px;
  color: #64748B;
}

.file-actions {
  display: flex;
  gap: 8px;
}

.action-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 12px;
  background: rgba(51, 65, 85, 0.5);
  border: 1px solid #334155;
  border-radius: 8px;
  color: #94A3B8;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.action-btn:hover {
  color: #FFFFFF;
  background: #334155;
  border-color: #165DFF;
}

.action-btn.select-btn.active {
  background: rgba(0, 180, 42, 0.2);
  border-color: #00B42A;
  color: #00B42A;
}

.action-btn.delete-btn:hover {
  background: rgba(245, 63, 63, 0.1);
  border-color: #F53F3F;
  color: #F53F3F;
}

.action-icon {
  width: 14px;
  height: 14px;
}

.preview-dialog :deep(.el-dialog__body) {
  padding: 0;
}

.preview-content {
  padding: 24px;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #1E293B;
}

.preview-filename {
  font-size: 16px;
  font-weight: 600;
  color: #FFFFFF;
}

.preview-type {
  padding: 4px 12px;
  background: rgba(22, 93, 255, 0.1);
  color: #165DFF;
  font-size: 12px;
  font-weight: 500;
  border-radius: 6px;
}

.preview-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 60px;
  color: #94A3B8;
}

.preview-table-wrapper {
  background: #0F172A;
  border-radius: 8px;
  overflow: hidden;
}

.preview-note {
  text-align: center;
  font-size: 12px;
  color: #64748B;
  margin: 12px 0 0 0;
}

:deep(.el-table) {
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-header-bg-color: #1E293B;
  --el-table-border-color: #334155;
  --el-table-text-color: #E2E8F0;
  --el-table-header-text-color: #94A3B8;
}

:deep(.el-table tbody tr:hover > td) {
  background-color: rgba(22, 93, 255, 0.05);
}

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    gap: 16px;
  }
  
  .match-stats {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .files-grid {
    grid-template-columns: 1fr;
  }
}
</style>
