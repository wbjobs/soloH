<template>
  <div class="gnn-anomaly-analysis-page">
    <div class="page-header">
      <h1>
        <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2"/>
          <circle cx="12" cy="12" r="4"/>
        </svg>
        GNN异常交易评分
      </h1>
      <p class="subtitle">基于图神经网络的多维特征异常检测与可解释性分析</p>
    </div>

    <div class="analysis-form">
      <div class="form-group">
        <label for="address">比特币地址</label>
        <input
          id="address"
          v-model="address"
          type="text"
          placeholder="输入比特币地址 (e.g., 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa)"
          @keyup.enter="analyzeAddress"
        />
      </div>
      <div class="form-group">
        <label for="depth">分析深度</label>
        <select id="depth" v-model="depth">
          <option :value="1">1 层 (直接关联)</option>
          <option :value="2">2 层 (间接关联)</option>
          <option :value="3">3 层 (深度关联)</option>
          <option :value="4">4 层 (全量分析)</option>
        </select>
      </div>
      <button class="btn-primary" @click="analyzeAddress" :disabled="loading || !address">
        <span v-if="loading">分析中...</span>
        <span v-else>开始GNN分析</span>
      </button>
    </div>

    <div v-if="error" class="error-alert">
      <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/>
        <line x1="12" y1="8" x2="12" y2="12"/>
        <line x1="12" y1="16" x2="12.01" y2="16"/>
      </svg>
      {{ error }}
    </div>

    <div v-if="result" class="analysis-results">
      <div class="score-card" :class="result.riskLevel">
        <div class="score-header">
          <h2>异常风险评分</h2>
          <span class="risk-badge" :class="result.riskLevel">{{ getRiskLabel(result.riskLevel) }}</span>
        </div>
        <div class="score-display">
          <div class="score-circle" :class="result.riskLevel">
            <span class="score-value">{{ result.anomalyScore.toFixed(1) }}</span>
            <span class="score-max">/ 100</span>
          </div>
          <div class="score-details">
            <div class="detail-item">
              <span class="label">分析地址</span>
              <span class="value mono">{{ result.address }}</span>
            </div>
            <div class="detail-item">
              <span class="label">分析深度</span>
              <span class="value">{{ result.analysisDepth }} 层</span>
            </div>
            <div class="detail-item">
              <span class="label">子图规模</span>
              <span class="value">{{ result.subgraphSize.nodes }} 节点, {{ result.subgraphSize.edges }} 边</span>
            </div>
          </div>
        </div>
      </div>

      <div class="two-column-layout">
        <div class="card">
          <h3>特征重要性</h3>
          <div class="feature-importance">
            <div
              v-for="(importance, feature) in sortedFeatureImportance"
              :key="feature"
              class="feature-row"
            >
              <span class="feature-name">{{ getFeatureLabel(feature as string) }}</span>
              <div class="feature-bar-container">
                <div
                  class="feature-bar"
                  :style="{ width: `${importance * 100}%` }"
                  :class="getBarColorClass(importance as number)"
                ></div>
              </div>
              <span class="feature-value">{{ (importance * 100).toFixed(0) }}%</span>
            </div>
          </div>
        </div>

        <div class="card">
          <h3>核心特征值</h3>
          <div class="features-grid">
            <div class="feature-card">
              <div class="feature-label">金额分布熵</div>
              <div class="feature-value-large">{{ result.features.value_entropy?.toFixed(4) || 'N/A' }}</div>
              <div class="feature-desc">衡量金额分布的不规则程度</div>
            </div>
            <div class="feature-card">
              <div class="feature-label">聚类系数</div>
              <div class="feature-value-large">{{ result.features.clustering_coefficient?.toFixed(4) || 'N/A' }}</div>
              <div class="feature-desc">地址聚集程度</div>
            </div>
            <div class="feature-card">
              <div class="feature-label">PageRank</div>
              <div class="feature-value-large">{{ result.features.pagerank?.toFixed(4) || 'N/A' }}</div>
              <div class="feature-desc">网络重要性评分</div>
            </div>
            <div class="feature-card">
              <div class="feature-label">资金流向比</div>
              <div class="feature-value-large">{{ result.features.flow_ratio?.toFixed(2) || 'N/A' }}</div>
              <div class="feature-desc">流入/流出比率</div>
            </div>
          </div>
        </div>
      </div>

      <div class="card">
        <h3>可解释性分析</h3>
        <div class="explanations-list">
          <div
            v-for="(explanation, index) in result.explanations"
            :key="index"
            class="explanation-item"
            :class="explanation.severity"
          >
            <div class="explanation-icon">
              <svg v-if="explanation.severity === 'critical'" class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="8" x2="12" y2="12"/>
                <line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
              <svg v-else-if="explanation.severity === 'high'" class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                <line x1="12" y1="9" x2="12" y2="13"/>
                <line x1="12" y1="17" x2="12.01" y2="17"/>
              </svg>
              <svg v-else-if="explanation.severity === 'medium'" class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="16" x2="12" y2="12"/>
                <line x1="12" y1="8" x2="12.01" y2="8"/>
              </svg>
              <svg v-else class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                <polyline points="22 4 12 14.01 9 11.01"/>
              </svg>
            </div>
            <div class="explanation-content">
              <div class="explanation-header">
                <span class="explanation-type">{{ getExplanationTypeLabel(explanation.type) }}</span>
                <span class="contribution-badge">贡献度 {{ explanation.contribution.toFixed(1) }}%</span>
              </div>
              <div class="explanation-description">{{ explanation.description }}</div>
            </div>
          </div>
        </div>
      </div>

      <div class="card">
        <h3>完整特征列表</h3>
        <div class="features-table-container">
          <table class="features-table">
            <thead>
              <tr>
                <th>特征名称</th>
                <th>特征值</th>
                <th>特征名称</th>
                <th>特征值</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(_, index) in Math.ceil(Object.keys(result.features).length / 2)" :key="index">
                <td v-if="allFeatures[index * 2]">
                  <span class="feature-label-cell">{{ getFeatureLabel(allFeatures[index * 2] as string) }}</span>
                </td>
                <td v-if="allFeatures[index * 2]" class="mono">
                  {{ formatFeatureValue(allFeatures[index * 2] as string, result.features[allFeatures[index * 2] as string]) }}
                </td>
                <td v-if="allFeatures[index * 2 + 1]">
                  <span class="feature-label-cell">{{ getFeatureLabel(allFeatures[index * 2 + 1] as string) }}</span>
                </td>
                <td v-if="allFeatures[index * 2 + 1]" class="mono">
                  {{ formatFeatureValue(allFeatures[index * 2 + 1] as string, result.features[allFeatures[index * 2 + 1] as string]) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { calculateGNNAnomalyScore, tryRealThenMock, mockApi } from '@/api'
import type { GNNAnomalyScoreResponse } from '@/types'

const address = ref('')
const depth = ref(3)
const loading = ref(false)
const error = ref('')
const result = ref<GNNAnomalyScoreResponse | null>(null)

const featureLabels: Record<string, string> = {
  in_degree: '入度',
  out_degree: '出度',
  total_in_value: '总流入金额',
  total_out_value: '总流出金额',
  mean_in_value: '平均流入金额',
  mean_out_value: '平均流出金额',
  std_in_value: '流入金额标准差',
  std_out_value: '流出金额标准差',
  value_entropy: '金额分布熵',
  flow_ratio: '资金流向比',
  clustering_coefficient: '聚类系数',
  pagerank: 'PageRank值',
  min_time_interval: '最小时间间隔(秒)',
  max_time_interval: '最大时间间隔(秒)',
  mean_time_interval: '平均时间间隔(秒)',
  std_time_interval: '时间间隔标准差',
  unique_days: '活跃天数',
  total_tx_count: '总交易数',
  anomaly_pattern_score: '异常模式评分',
  transaction_count: '交易数量'
}

const explanationTypeLabels: Record<string, string> = {
  value_entropy: '金额分布熵',
  anomaly_pattern_score: '异常模式综合',
  flow_ratio: '资金流向比率',
  clustering_coefficient: '聚类系数',
  pagerank: 'PageRank重要性',
  min_time_interval: '时间间隔模式'
}

const sortedFeatureImportance = computed(() => {
  if (!result.value?.featureImportance) return {}
  return Object.fromEntries(
    Object.entries(result.value.featureImportance).sort((a, b) => b[1] - a[1])
  )
})

const allFeatures = computed(() => {
  if (!result.value?.features) return []
  return Object.keys(result.value.features)
})

function getRiskLabel(level: string): string {
  const labels: Record<string, string> = {
    low: '低风险',
    medium: '中风险',
    high: '高风险',
    critical: '极高风险'
  }
  return labels[level] || level
}

function getFeatureLabel(feature: string): string {
  return featureLabels[feature] || feature
}

function getExplanationTypeLabel(type: string): string {
  return explanationTypeLabels[type] || type
}

function getBarColorClass(value: number): string {
  if (value >= 0.2) return 'high'
  if (value >= 0.1) return 'medium'
  return 'low'
}

function formatFeatureValue(feature: string, value: number): string {
  if (value === undefined || value === null) return 'N/A'
  if (feature.includes('time') && feature.includes('interval')) {
    if (value < 60) return `${value.toFixed(1)} 秒`
    if (value < 3600) return `${(value / 60).toFixed(1)} 分钟`
    if (value < 86400) return `${(value / 3600).toFixed(1)} 小时`
    return `${(value / 86400).toFixed(1)} 天`
  }
  if (feature.includes('value') || feature.includes('ratio')) {
    return value.toFixed(4)
  }
  if (feature.includes('entropy') || feature.includes('coefficient') || feature.includes('pagerank')) {
    return value.toFixed(4)
  }
  return Math.round(value).toString()
}

async function analyzeAddress() {
  if (!address.value.trim()) {
    error.value = '请输入比特币地址'
    return
  }

  loading.value = true
  error.value = ''
  result.value = null

  try {
    const response = await tryRealThenMock(
      () => calculateGNNAnomalyScore({ address: address.value.trim(), depth: depth.value }),
      () => mockApi.analysis.calculateGNNAnomalyScore({ address: address.value.trim(), depth: depth.value }) as any,
      'calculateGNNAnomalyScore'
    )
    const respData = response as any
    result.value = (respData.data?.anomalyScore !== undefined ? respData.data : respData) as GNNAnomalyScoreResponse
  } catch (e) {
    error.value = (e as Error).message || '分析失败，请稍后重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.gnn-anomaly-analysis-page {
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
  color: #3b82f6;
}

.subtitle {
  color: #64748b;
  font-size: 16px;
  margin: 0;
}

.analysis-form {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  margin-bottom: 24px;
  display: flex;
  gap: 16px;
  align-items: flex-end;
}

.form-group {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-group label {
  font-weight: 600;
  color: #334155;
  font-size: 14px;
}

.form-group input,
.form-group select {
  padding: 12px 16px;
  border: 2px solid #e2e8f0;
  border-radius: 8px;
  font-size: 14px;
  transition: all 0.2s;
}

.form-group input:focus,
.form-group select:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.btn-primary {
  background: linear-gradient(135deg, #3b82f6, #1d4ed8);
  color: white;
  border: none;
  padding: 12px 32px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.btn-primary:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.error-alert {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #dc2626;
  padding: 16px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}

.error-alert .icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

.analysis-results {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.score-card {
  background: linear-gradient(135deg, #f8fafc, #f1f5f9);
  border-radius: 16px;
  padding: 32px;
  border: 2px solid transparent;
  position: relative;
  overflow: hidden;
}

.score-card.critical {
  border-color: #ef4444;
  background: linear-gradient(135deg, #fef2f2, #fee2e2);
}

.score-card.high {
  border-color: #f97316;
  background: linear-gradient(135deg, #fff7ed, #ffedd5);
}

.score-card.medium {
  border-color: #eab308;
  background: linear-gradient(135deg, #fefce8, #fef9c3);
}

.score-card.low {
  border-color: #22c55e;
  background: linear-gradient(135deg, #f0fdf4, #dcfce7);
}

.score-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.score-header h2 {
  font-size: 20px;
  font-weight: 700;
  color: #1e293b;
  margin: 0;
}

.risk-badge {
  padding: 6px 16px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 600;
}

.risk-badge.critical {
  background: #ef4444;
  color: white;
}

.risk-badge.high {
  background: #f97316;
  color: white;
}

.risk-badge.medium {
  background: #eab308;
  color: #713f12;
}

.risk-badge.low {
  background: #22c55e;
  color: white;
}

.score-display {
  display: flex;
  gap: 48px;
  align-items: center;
}

.score-circle {
  width: 160px;
  height: 160px;
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: white;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
  border: 6px solid;
  flex-shrink: 0;
}

.score-circle.critical {
  border-color: #ef4444;
}

.score-circle.high {
  border-color: #f97316;
}

.score-circle.medium {
  border-color: #eab308;
}

.score-circle.low {
  border-color: #22c55e;
}

.score-value {
  font-size: 48px;
  font-weight: 800;
  color: #1e293b;
  line-height: 1;
}

.score-max {
  font-size: 16px;
  color: #64748b;
}

.score-details {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.detail-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.8);
  border-radius: 8px;
}

.detail-item .label {
  color: #64748b;
  font-size: 14px;
}

.detail-item .value {
  font-weight: 600;
  color: #1e293b;
}

.mono {
  font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
}

.two-column-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}

.card {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.card h3 {
  font-size: 18px;
  font-weight: 700;
  color: #1e293b;
  margin: 0 0 20px 0;
}

.feature-importance {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.feature-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.feature-name {
  width: 120px;
  font-size: 13px;
  color: #475569;
  flex-shrink: 0;
}

.feature-bar-container {
  flex: 1;
  height: 12px;
  background: #f1f5f9;
  border-radius: 6px;
  overflow: hidden;
}

.feature-bar {
  height: 100%;
  border-radius: 6px;
  transition: width 0.5s ease;
}

.feature-bar.high {
  background: linear-gradient(90deg, #ef4444, #f97316);
}

.feature-bar.medium {
  background: linear-gradient(90deg, #eab308, #84cc16);
}

.feature-bar.low {
  background: linear-gradient(90deg, #22c55e, #06b6d4);
}

.feature-value {
  width: 48px;
  text-align: right;
  font-size: 13px;
  font-weight: 600;
  color: #334155;
}

.features-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.feature-card {
  background: #f8fafc;
  border-radius: 10px;
  padding: 16px;
  text-align: center;
}

.feature-label {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 8px;
}

.feature-value-large {
  font-size: 24px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 4px;
}

.feature-desc {
  font-size: 11px;
  color: #94a3b8;
}

.explanations-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.explanation-item {
  display: flex;
  gap: 16px;
  padding: 20px;
  border-radius: 10px;
  background: #f8fafc;
  border-left: 4px solid transparent;
}

.explanation-item.critical {
  border-left-color: #ef4444;
  background: #fef2f2;
}

.explanation-item.high {
  border-left-color: #f97316;
  background: #fff7ed;
}

.explanation-item.medium {
  border-left-color: #eab308;
  background: #fefce8;
}

.explanation-item.low {
  border-left-color: #22c55e;
  background: #f0fdf4;
}

.explanation-icon {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: white;
}

.explanation-item.critical .explanation-icon {
  color: #ef4444;
}

.explanation-item.high .explanation-icon {
  color: #f97316;
}

.explanation-item.medium .explanation-icon {
  color: #eab308;
}

.explanation-item.low .explanation-icon {
  color: #22c55e;
}

.explanation-icon .icon {
  width: 24px;
  height: 24px;
}

.explanation-content {
  flex: 1;
}

.explanation-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.explanation-type {
  font-weight: 600;
  color: #1e293b;
  font-size: 15px;
}

.contribution-badge {
  background: rgba(0, 0, 0, 0.1);
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.explanation-description {
  color: #475569;
  font-size: 14px;
  line-height: 1.5;
}

.features-table-container {
  overflow-x: auto;
}

.features-table {
  width: 100%;
  border-collapse: collapse;
}

.features-table th,
.features-table td {
  padding: 12px 16px;
  text-align: left;
  border-bottom: 1px solid #f1f5f9;
}

.features-table th {
  background: #f8fafc;
  font-weight: 600;
  color: #475569;
  font-size: 13px;
}

.features-table td {
  font-size: 14px;
  color: #334155;
}

.feature-label-cell {
  color: #64748b;
  font-size: 13px;
}

@media (max-width: 1024px) {
  .two-column-layout {
    grid-template-columns: 1fr;
  }
  
  .score-display {
    flex-direction: column;
    gap: 24px;
  }
  
  .analysis-form {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>