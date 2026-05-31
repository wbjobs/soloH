<template>
  <div class="compliance-report-page">
    <div class="page-header">
      <h1>
        <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <line x1="16" y1="13" x2="8" y2="13"/>
          <line x1="16" y1="17" x2="8" y2="17"/>
          <polyline points="10 9 9 9 8 9"/>
        </svg>
        合规报告生成
      </h1>
      <p class="subtitle">自动生成专业的PDF合规调查报告，包含完整的风险评估和交易明细</p>
    </div>

    <div class="main-content">
      <div class="report-form-card">
        <h2>报告配置</h2>
        
        <div class="form-group">
          <label for="address">比特币地址</label>
          <input
            id="address"
            v-model="address"
            type="text"
            placeholder="输入要分析的比特币地址"
            @keyup.enter="generateReport"
          />
        </div>

        <div class="form-group">
          <label>报告格式</label>
          <div class="format-options">
            <label class="format-option">
              <input type="radio" v-model="format" value="pdf" />
              <span class="format-icon">📄</span>
              <span class="format-name">PDF 文档</span>
              <span class="format-desc">专业排版，适合打印和归档</span>
            </label>
            <label class="format-option">
              <input type="radio" v-model="format" value="json" />
              <span class="format-icon">{ }</span>
              <span class="format-name">JSON 数据</span>
              <span class="format-desc">结构化数据，便于系统集成</span>
            </label>
          </div>
        </div>

        <div class="form-group">
          <label class="checkbox-label">
            <input type="checkbox" v-model="includeVisualizations" />
            <span class="checkbox-custom"></span>
            <span class="checkbox-text">包含可视化图表</span>
          </label>
        </div>

        <button class="btn-generate" @click="generateReport" :disabled="loading || !address">
          <svg v-if="loading" class="spinner" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10" stroke-opacity="0.25"/>
            <path d="M4 12a8 8 0 018-8"/>
          </svg>
          <svg v-else class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="7 10 12 15 17 10"/>
            <line x1="12" y1="15" x2="12" y2="3"/>
          </svg>
          {{ loading ? '生成中...' : '生成合规报告' }}
        </button>

        <div v-if="error" class="error-alert">
          <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <line x1="12" y1="8" x2="12" y2="12"/>
            <line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          {{ error }}
        </div>
      </div>

      <div class="report-preview-card">
        <h2>报告概览</h2>
        <p class="preview-desc">生成的合规报告将包含以下内容：</p>
        
        <div class="report-sections">
          <div class="section-item">
            <div class="section-icon cover">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
              </svg>
            </div>
            <div class="section-info">
              <h3>封面页</h3>
              <p>包含报告标题、分析地址、生成日期</p>
            </div>
          </div>

          <div class="section-item">
            <div class="section-icon summary">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="8" y1="6" x2="21" y2="6"/>
                <line x1="8" y1="12" x2="21" y2="12"/>
                <line x1="8" y1="18" x2="21" y2="18"/>
                <line x1="3" y1="6" x2="3.01" y2="6"/>
                <line x1="3" y1="12" x2="3.01" y2="12"/>
                <line x1="3" y1="18" x2="3.01" y2="18"/>
              </svg>
            </div>
            <div class="section-info">
              <h3>执行摘要</h3>
              <p>关键发现、风险等级、主要结论</p>
            </div>
          </div>

          <div class="section-item">
            <div class="section-icon risk">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                <line x1="12" y1="9" x2="12" y2="13"/>
                <line x1="12" y1="17" x2="12.01" y2="17"/>
              </svg>
            </div>
            <div class="section-info">
              <h3>风险评估</h3>
              <p>综合风险评分、风险等级判定</p>
            </div>
          </div>

          <div class="section-item">
            <div class="section-icon gnn">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="3"/>
                <path d="M12 1v6m0 6v6m4.22-13.22l4.24 4.24M1.54 1.54l4.24 4.24M20.46 20.46l-4.24-4.24M1.54 20.46l4.24-4.24"/>
              </svg>
            </div>
            <div class="section-info">
              <h3>GNN异常分析</h3>
              <p>图神经网络异常评分、特征重要性</p>
            </div>
          </div>

          <div class="section-item">
            <div class="section-icon privacy">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                <path d="m9 12 2 2 4-4"/>
              </svg>
            </div>
            <div class="section-info">
              <h3>隐私币分析</h3>
              <p>混币模式检测、跨链关联分析</p>
            </div>
          </div>

          <div class="section-item">
            <div class="section-icon patterns">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 20V10"/>
                <path d="M18 20V4"/>
                <path d="M6 20v-4"/>
              </svg>
            </div>
            <div class="section-info">
              <h3>可疑模式</h3>
              <p>检测到的可疑交易模式列表</p>
            </div>
          </div>

          <div class="section-item">
            <div class="section-icon transactions">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="3" width="18" height="18" rx="2"/>
                <line x1="3" y1="9" x2="21" y2="9"/>
                <line x1="3" y1="15" x2="21" y2="15"/>
                <line x1="9" y1="3" x2="9" y2="21"/>
              </svg>
            </div>
            <div class="section-info">
              <h3>交易明细</h3>
              <p>可疑交易的详细信息表格</p>
            </div>
          </div>

          <div v-if="includeVisualizations" class="section-item">
            <div class="section-icon charts">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="20" x2="18" y2="10"/>
                <line x1="12" y1="20" x2="12" y2="4"/>
                <line x1="6" y1="20" x2="6" y2="14"/>
              </svg>
            </div>
            <div class="section-info">
              <h3>可视化图表</h3>
              <p>风险评分饼图、特征重要性柱状图</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="reportInfo" class="report-result">
      <div class="result-card">
        <div class="result-header">
          <div class="result-icon success">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
              <polyline points="22 4 12 14.01 9 11.01"/>
            </svg>
          </div>
          <div class="result-info">
            <h2>报告生成成功</h2>
            <p class="filename">{{ reportInfo.filename }}</p>
          </div>
        </div>

        <div v-if="reportInfo.summary" class="report-summary">
          <h3>报告摘要</h3>
          <div class="summary-grid">
            <div class="summary-item">
              <div class="summary-label">综合风险评分</div>
              <div class="summary-value large" :class="getRiskLevelClass(reportInfo.summary.riskLevel)">
                {{ reportInfo.summary.overallRiskScore.toFixed(1) }}
              </div>
              <div class="summary-risk-badge" :class="reportInfo.summary.riskLevel">
                {{ getRiskLabel(reportInfo.summary.riskLevel) }}
              </div>
            </div>
            <div class="summary-item">
              <div class="summary-label">GNN异常评分</div>
              <div class="summary-value">{{ reportInfo.summary.gnnAnomalyScore.toFixed(1) }}</div>
            </div>
            <div class="summary-item">
              <div class="summary-label">隐私风险评分</div>
              <div class="summary-value">{{ reportInfo.summary.privacyRiskScore.toFixed(1) }}</div>
            </div>
            <div class="summary-item">
              <div class="summary-label">可疑模式数</div>
              <div class="summary-value">{{ reportInfo.summary.suspiciousPatternCount }}</div>
            </div>
            <div class="summary-item">
              <div class="summary-label">隐私币关联</div>
              <div class="summary-value">{{ reportInfo.summary.privacyCoinAssociations }}</div>
            </div>
            <div class="summary-item">
              <div class="summary-label">文件大小</div>
              <div class="summary-value">{{ formatFileSize(reportInfo.fileSize || 0) }}</div>
            </div>
          </div>

          <div class="report-meta">
            <div class="meta-item">
              <span class="meta-label">分析周期:</span>
              <span class="meta-value">{{ reportInfo.summary.analysisPeriod }}</span>
            </div>
            <div class="meta-item">
              <span class="meta-label">生成时间:</span>
              <span class="meta-value">{{ formatDate(reportInfo.generatedAt) }}</span>
            </div>
          </div>
        </div>

        <div class="result-actions">
          <button class="btn-download" @click="downloadReport">
            <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="7 10 12 15 17 10"/>
              <line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
            下载报告
          </button>
          <button class="btn-new" @click="resetForm">
            <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
              <path d="M3 3v5h5"/>
            </svg>
            生成新报告
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { generateComplianceReport, generateReportInfo, tryRealThenMock, mockApi } from '@/api'
import type { ComplianceReportResponse } from '@/types'

const address = ref('')
const format = ref('pdf')
const includeVisualizations = ref(true)
const loading = ref(false)
const error = ref('')
const reportInfo = ref<ComplianceReportResponse | null>(null)
const lastBlob = ref<Blob | null>(null)

function getRiskLabel(level: string): string {
  const labels: Record<string, string> = {
    low: '低风险',
    medium: '中风险',
    high: '高风险',
    critical: '极高风险'
  }
  return labels[level] || level
}

function getRiskLevelClass(level: string): string {
  return level
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

async function generateReport() {
  if (!address.value.trim()) {
    error.value = '请输入比特币地址'
    return
  }

  loading.value = true
  error.value = ''
  reportInfo.value = null

  try {
    const mockResponse = await mockApi.analysis.generateComplianceReport({
      address: address.value.trim(),
      format: format.value as 'pdf' | 'json',
      includeVisualizations: includeVisualizations.value
    }) as any

    let infoData: ComplianceReportResponse
    if (mockResponse.data?.summary) {
      infoData = mockResponse.data as ComplianceReportResponse
    } else if (mockResponse.data?.data?.summary) {
      infoData = mockResponse.data.data as ComplianceReportResponse
    } else {
      infoData = mockResponse as unknown as ComplianceReportResponse
    }
    reportInfo.value = infoData

    if (format.value === 'pdf') {
      lastBlob.value = (mockResponse as any).blob || new Blob(['PDF Report Content Placeholder'], { type: 'application/pdf' })
    }
  } catch (e) {
    error.value = (e as Error).message || '报告生成失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

function downloadReport() {
  if (!reportInfo.value || !lastBlob.value) return

  const url = URL.createObjectURL(lastBlob.value)
  const link = document.createElement('a')
  link.href = url
  link.download = reportInfo.value.filename || `compliance-report-${Date.now()}.pdf`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

function resetForm() {
  address.value = ''
  reportInfo.value = null
  lastBlob.value = null
  error.value = ''
}
</script>

<style scoped>
.compliance-report-page {
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 24px;
}

.page-header h1 {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 28px;
  font-weight: 700;
  color: #1e293b;
  margin: 0 0 8px 0;
}

.page-header h1 .icon {
  width: 32px;
  height: 32px;
  color: #059669;
}

.subtitle {
  color: #64748b;
  font-size: 16px;
  margin: 0;
}

.main-content {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  margin-bottom: 24px;
}

.report-form-card,
.report-preview-card {
  background: white;
  border-radius: 12px;
  padding: 28px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.report-form-card h2,
.report-preview-card h2 {
  font-size: 20px;
  font-weight: 700;
  color: #1e293b;
  margin: 0 0 24px 0;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  font-weight: 600;
  color: #334155;
  font-size: 14px;
  margin-bottom: 8px;
}

.form-group input[type="text"] {
  width: 100%;
  padding: 12px 16px;
  border: 2px solid #e2e8f0;
  border-radius: 8px;
  font-size: 14px;
  transition: all 0.2s;
  box-sizing: border-box;
}

.form-group input[type="text"]:focus {
  outline: none;
  border-color: #059669;
  box-shadow: 0 0 0 3px rgba(5, 150, 105, 0.1);
}

.format-options {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.format-option {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px;
  border: 2px solid #e2e8f0;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  text-align: center;
}

.format-option:hover {
  border-color: #cbd5e1;
  background: #f8fafc;
}

.format-option input[type="radio"] {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}

.format-option input[type="radio"]:checked + .format-icon + .format-name + .format-desc,
.format-option:has(input:checked) {
  border-color: #059669;
  background: #ecfdf5;
}

.format-option input[type="radio"]:checked ~ .format-name {
  color: #059669;
}

.format-icon {
  font-size: 28px;
  margin-bottom: 8px;
}

.format-name {
  font-weight: 600;
  color: #1e293b;
  font-size: 14px;
  margin-bottom: 4px;
}

.format-desc {
  font-size: 12px;
  color: #64748b;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  font-weight: 500;
  color: #334155;
  font-size: 14px;
}

.checkbox-label input[type="checkbox"] {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}

.checkbox-custom {
  width: 20px;
  height: 20px;
  border: 2px solid #cbd5e1;
  border-radius: 4px;
  position: relative;
  transition: all 0.2s;
  flex-shrink: 0;
}

.checkbox-label input[type="checkbox"]:checked ~ .checkbox-custom {
  background: #059669;
  border-color: #059669;
}

.checkbox-label input[type="checkbox"]:checked ~ .checkbox-custom::after {
  content: '';
  position: absolute;
  left: 5px;
  top: 1px;
  width: 5px;
  height: 10px;
  border: solid white;
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
}

.checkbox-text {
  user-select: none;
}

.btn-generate {
  width: 100%;
  background: linear-gradient(135deg, #059669, #047857);
  color: white;
  border: none;
  padding: 14px 24px;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 8px;
}

.btn-generate:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(5, 150, 105, 0.3);
}

.btn-generate:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.spinner {
  width: 20px;
  height: 20px;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.btn-generate .icon {
  width: 20px;
  height: 20px;
}

.error-alert {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #dc2626;
  padding: 14px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 16px;
  font-size: 14px;
}

.error-alert .icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}

.preview-desc {
  color: #64748b;
  font-size: 14px;
  margin: -8px 0 20px 0;
}

.report-sections {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-item {
  display: flex;
  gap: 14px;
  padding: 14px;
  border-radius: 10px;
  background: #f8fafc;
  transition: all 0.2s;
}

.section-item:hover {
  background: #f1f5f9;
}

.section-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.section-icon svg {
  width: 22px;
  height: 22px;
}

.section-icon.cover {
  background: #fef3c7;
  color: #d97706;
}

.section-icon.summary {
  background: #dbeafe;
  color: #2563eb;
}

.section-icon.risk {
  background: #fee2e2;
  color: #dc2626;
}

.section-icon.gnn {
  background: #ede9fe;
  color: #7c3aed;
}

.section-icon.privacy {
  background: #ddd6fe;
  color: #6d28d9;
}

.section-icon.patterns {
  background: #fce7f3;
  color: #db2777;
}

.section-icon.transactions {
  background: #d1fae5;
  color: #059669;
}

.section-icon.charts {
  background: #cffafe;
  color: #0891b2;
}

.section-info h3 {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  margin: 0 0 4px 0;
}

.section-info p {
  font-size: 13px;
  color: #64748b;
  margin: 0;
}

.report-result {
  margin-top: 24px;
}

.result-card {
  background: white;
  border-radius: 16px;
  padding: 32px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  border: 2px solid #d1fae5;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 28px;
  padding-bottom: 20px;
  border-bottom: 1px solid #f1f5f9;
}

.result-icon {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.result-icon.success {
  background: #d1fae5;
  color: #059669;
}

.result-icon svg {
  width: 32px;
  height: 32px;
}

.result-info h2 {
  font-size: 22px;
  font-weight: 700;
  color: #1e293b;
  margin: 0 0 4px 0;
}

.filename {
  color: #64748b;
  font-size: 14px;
  margin: 0;
  font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
}

.report-summary h3 {
  font-size: 18px;
  font-weight: 600;
  color: #1e293b;
  margin: 0 0 20px 0;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.summary-item {
  background: #f8fafc;
  border-radius: 12px;
  padding: 20px;
  text-align: center;
}

.summary-label {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 8px;
}

.summary-value {
  font-size: 28px;
  font-weight: 700;
  color: #1e293b;
  line-height: 1.2;
}

.summary-value.large {
  font-size: 36px;
}

.summary-value.critical {
  color: #ef4444;
}

.summary-value.high {
  color: #f97316;
}

.summary-value.medium {
  color: #eab308;
}

.summary-value.low {
  color: #22c55e;
}

.summary-risk-badge {
  display: inline-block;
  margin-top: 8px;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.summary-risk-badge.critical {
  background: #fee2e2;
  color: #dc2626;
}

.summary-risk-badge.high {
  background: #ffedd5;
  color: #ea580c;
}

.summary-risk-badge.medium {
  background: #fef9c3;
  color: #a16207;
}

.summary-risk-badge.low {
  background: #dcfce7;
  color: #15803d;
}

.report-meta {
  background: #f1f5f9;
  border-radius: 10px;
  padding: 16px 20px;
  display: flex;
  flex-wrap: wrap;
  gap: 24px;
  margin-bottom: 24px;
}

.meta-item {
  display: flex;
  gap: 8px;
  font-size: 14px;
}

.meta-label {
  color: #64748b;
  font-weight: 500;
}

.meta-value {
  color: #1e293b;
  font-weight: 600;
}

.result-actions {
  display: flex;
  gap: 16px;
  justify-content: flex-end;
}

.btn-download,
.btn-new {
  padding: 12px 24px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 8px;
}

.btn-download {
  background: linear-gradient(135deg, #059669, #047857);
  color: white;
  border: none;
}

.btn-download:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(5, 150, 105, 0.3);
}

.btn-new {
  background: white;
  color: #334155;
  border: 2px solid #e2e8f0;
}

.btn-new:hover {
  border-color: #cbd5e1;
  background: #f8fafc;
}

.btn-download .icon,
.btn-new .icon {
  width: 18px;
  height: 18px;
}

@media (max-width: 1024px) {
  .main-content {
    grid-template-columns: 1fr;
  }
  
  .format-options {
    grid-template-columns: 1fr;
  }
  
  .result-actions {
    flex-direction: column;
  }
  
  .btn-download,
  .btn-new {
    justify-content: center;
  }
}
</style>