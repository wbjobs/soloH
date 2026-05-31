<template>
  <div class="privacy-coin-analysis-page">
    <div class="page-header">
      <h1>
        <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          <path d="m9 12 2 2 4-4"/>
        </svg>
        隐私币跨链关联分析
      </h1>
      <p class="subtitle">检测Monero、Zcash等隐私币关联，识别混币模式和跨链交易</p>
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
        <span v-else>开始隐私币分析</span>
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
          <h2>隐私币关联风险评分</h2>
          <span class="risk-badge" :class="result.riskLevel">{{ getRiskLabel(result.riskLevel) }}</span>
        </div>
        <div class="score-display">
          <div class="score-circle" :class="result.riskLevel">
            <span class="score-value">{{ result.overallRiskScore.toFixed(1) }}</span>
            <span class="score-max">/ 100</span>
          </div>
          <div class="score-details">
            <div class="detail-item">
              <span class="label">检测隐私币种类</span>
              <span class="value">{{ result.privacyCoinCount }} 种</span>
            </div>
            <div class="detail-item">
              <span class="label">关联地址数量</span>
              <span class="value">{{ result.associatedAddressCount }} 个</span>
            </div>
            <div class="detail-item">
              <span class="label">隐私相关交易额</span>
              <span class="value">{{ result.totalPrivacyRelatedValue.toFixed(4) }} BTC</span>
            </div>
            <div class="detail-item">
              <span class="label">可疑交易数</span>
              <span class="value">{{ result.suspiciousTransactions.length }} 笔</span>
            </div>
          </div>
        </div>
      </div>

      <div v-if="result.privacyCoinCount > 0" class="card">
        <h3>检测到的隐私币关联</h3>
        <div class="privacy-coins-grid">
          <div
            v-for="(coins, type) in result.detectedPrivacyCoins"
            :key="type"
            class="privacy-coin-card"
          >
            <div class="coin-header">
              <span class="coin-icon">{{ getPrivacyCoinIcon(type) }}</span>
              <span class="coin-name">{{ coins[0]?.coinName || type }}</span>
              <span class="risk-tag" :class="coins[0]?.riskLevel">
                {{ getRiskLabel(coins[0]?.riskLevel || 'medium') }}
              </span>
            </div>
            <div class="coin-addresses">
              <div v-for="(coin, idx) in coins" :key="idx" class="coin-address-item">
                <span class="label">关联地址:</span>
                <span class="mono address-value">{{ coin.address }}</span>
              </div>
              <p class="coin-desc">{{ coins[0]?.description }}</p>
            </div>
          </div>
        </div>
      </div>

      <div v-if="result.mixingPatterns.length > 0" class="card">
        <h3>检测到的混币模式</h3>
        <div class="mixing-patterns">
          <div
            v-for="(pattern, idx) in result.mixingPatterns"
            :key="idx"
            class="pattern-card"
          >
            <div class="pattern-header">
              <span class="pattern-type-badge">{{ getPatternTypeLabel(pattern.type) }}</span>
              <span class="confidence-badge">置信度 {{ (pattern.confidence * 100).toFixed(1) }}%</span>
            </div>
            <p class="pattern-description">{{ pattern.description }}</p>
            <div class="pattern-evidence">
              <h4>证据</h4>
              <div class="evidence-grid">
                <div v-for="(value, key) in pattern.evidence" :key="key" class="evidence-item">
                  <span class="evidence-label">{{ getEvidenceLabel(key as string) }}</span>
                  <span class="evidence-value">{{ formatEvidenceValue(key as string, value) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="result.crossChainLinks.length > 0" class="card">
        <h3>跨链关联</h3>
        <div class="cross-chain-links">
          <div
            v-for="(link, idx) in result.crossChainLinks"
            :key="idx"
            class="cross-chain-card"
            :class="link.type"
          >
            <div class="link-icon">
              <svg v-if="link.type === 'privacy_coin'" class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <path d="M16 8c-2 0-3 1-4 2s-2 2-4 2-3-1-4-2"/>
              </svg>
              <svg v-else class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/>
              </svg>
            </div>
            <div class="link-content">
              <div class="link-title">
                {{ link.type === 'privacy_coin' ? '隐私币跨链' : '隐私网关' }}
                <span class="risk-tag" :class="link.riskLevel">
                  {{ getRiskLabel(link.riskLevel || 'medium') }}
                </span>
              </div>
              <p class="link-description">{{ link.description }}</p>
              <div v-if="link.coinName" class="link-detail">
                <span class="detail-label">币种:</span>
                <span class="detail-value">{{ link.coinName }}</span>
              </div>
              <div v-if="link.gatewayName" class="link-detail">
                <span class="detail-label">网关:</span>
                <span class="detail-value">{{ link.gatewayName }} ({{ link.gatewayType }})</span>
              </div>
              <div v-if="link.transaction" class="link-transaction">
                <div class="tx-detail">
                  <span class="detail-label">交易:</span>
                  <span class="detail-value mono">{{ link.transaction.txid }}</span>
                </div>
                <div class="tx-flow">
                  <span class="mono">{{ link.transaction.from.slice(0, 8) }}...</span>
                  <svg class="arrow-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="5" y1="12" x2="19" y2="12"/>
                    <polyline points="12 5 19 12 12 19"/>
                  </svg>
                  <span class="mono">{{ link.transaction.to.slice(0, 8) }}...</span>
                  <span class="tx-value">{{ link.transaction.value.toFixed(4) }} BTC</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="card">
        <h3>可疑交易明细</h3>
        <div class="transactions-table-container">
          <table class="transactions-table">
            <thead>
              <tr>
                <th>交易ID</th>
                <th>类型</th>
                <th>金额 (BTC)</th>
                <th>发送方</th>
                <th>接收方</th>
                <th>时间</th>
                <th>隐私类型</th>
                <th>网关</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(tx, idx) in result.suspiciousTransactions" :key="idx">
                <td class="mono small">{{ tx.txid.slice(0, 16) }}...</td>
                <td>
                  <span class="direction-badge" :class="tx.direction">
                    {{ tx.direction === 'incoming' ? '流入' : '流出' }}
                  </span>
                </td>
                <td class="mono">{{ tx.value.toFixed(4) }}</td>
                <td class="mono small">{{ tx.fromAddress.slice(0, 12) }}...</td>
                <td class="mono small">{{ tx.toAddress.slice(0, 12) }}...</td>
                <td>{{ formatTimestamp(tx.timestamp) }}</td>
                <td>{{ tx.privacyType || '-' }}</td>
                <td>{{ tx.gatewayInfo?.name || '-' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div v-if="result.threatIntelligence" class="card threat-intel-card">
        <h3>威胁情报</h3>
        <div class="threat-summary">
          <div class="threat-level" :class="result.threatIntelligence.threatLevel">
            <span class="threat-label">威胁等级</span>
            <span class="threat-value">{{ getRiskLabel(result.threatIntelligence.threatLevel) }}</span>
          </div>
          <p class="threat-summary-text">{{ result.threatIntelligence.summary }}</p>
        </div>
        <div class="threat-indicators">
          <h4>威胁指标</h4>
          <div class="indicators-list">
            <div
              v-for="(indicator, idx) in result.threatIntelligence.threatIndicators"
              :key="idx"
              class="indicator-item"
              :class="indicator.severity"
            >
              <span class="indicator-dot"></span>
              <span class="indicator-type">{{ getIndicatorTypeLabel(indicator.type) }}:</span>
              <span class="indicator-description">{{ indicator.description }}</span>
            </div>
          </div>
        </div>
        <div class="recommended-actions">
          <h4>建议措施</h4>
          <ul>
            <li v-for="(action, idx) in result.threatIntelligence.recommendedActions" :key="idx">
              <svg class="check-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
              {{ action }}
            </li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { analyzePrivacyCoinAssociations, tryRealThenMock, mockApi } from '@/api'
import type { PrivacyCoinAnalysisResponse } from '@/types'

const address = ref('')
const depth = ref(3)
const loading = ref(false)
const error = ref('')
const result = ref<PrivacyCoinAnalysisResponse | null>(null)

function getRiskLabel(level: string): string {
  const labels: Record<string, string> = {
    low: '低风险',
    medium: '中风险',
    high: '高风险',
    critical: '极高风险'
  }
  return labels[level] || level
}

function getPrivacyCoinIcon(type: string): string {
  const icons: Record<string, string> = {
    monero: 'ɱ',
    zcash: 'Z',
    dash: 'D',
    coinjoin: 'CJ',
    tornado_cash: '🌪',
    wasabi: 'W',
    samourai: 'S',
    joinmarket: 'JM'
  }
  return icons[type] || '?'
}

function getPatternTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    value_matching: '金额匹配模式',
    automated_mixing: '自动化混币',
    structuring_split: '结构化拆分',
    coinjoin: 'CoinJoin混币',
    peel_chain: '剥皮链'
  }
  return labels[type] || type
}

function getEvidenceLabel(key: string): string {
  const labels: Record<string, string> = {
    matchingTransactionCount: '匹配交易数',
    totalValue: '总金额 (BTC)',
    timeWindowMinutes: '时间窗口 (分钟)',
    inputCount: '输入数量',
    outputCount: '输出数量',
    similarityThreshold: '相似度阈值'
  }
  return labels[key] || key
}

function formatEvidenceValue(key: string, value: unknown): string {
  if (typeof value === 'number') {
    if (key.includes('Value') || key.includes('Amount')) {
      return value.toFixed(4)
    }
    return value.toString()
  }
  return String(value)
}

function getIndicatorTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    privacy_coin_association: '隐私币关联',
    mixing_pattern: '混币模式',
    cross_chain_activity: '跨链活动',
    known_mixer: '已知混币器',
    dark_web_association: '暗网关联'
  }
  return labels[type] || type
}

function formatTimestamp(timestamp: number): string {
  const date = new Date(timestamp)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
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
      () => analyzePrivacyCoinAssociations({ address: address.value.trim(), depth: depth.value }),
      () => mockApi.analysis.analyzePrivacyCoinAssociations({ address: address.value.trim(), depth: depth.value }) as any,
      'analyzePrivacyCoinAssociations'
    )
    const respData = response as any
    result.value = (respData.data?.overallRiskScore !== undefined ? respData.data : respData) as PrivacyCoinAnalysisResponse
  } catch (e) {
    error.value = (e as Error).message || '分析失败，请稍后重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.privacy-coin-analysis-page {
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
  color: #8b5cf6;
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
  border-color: #8b5cf6;
  box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.1);
}

.btn-primary {
  background: linear-gradient(135deg, #8b5cf6, #6d28d9);
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
  box-shadow: 0 4px 12px rgba(139, 92, 246, 0.3);
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
  background: linear-gradient(135deg, #faf5ff, #f3e8ff);
  border-radius: 16px;
  padding: 32px;
  border: 2px solid transparent;
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
  display: grid;
  grid-template-columns: 1fr 1fr;
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

.privacy-coins-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
  gap: 16px;
}

.privacy-coin-card {
  background: linear-gradient(135deg, #faf5ff, #f3e8ff);
  border-radius: 12px;
  padding: 20px;
  border: 1px solid #e9d5ff;
}

.coin-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.coin-icon {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, #8b5cf6, #6d28d9);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 700;
}

.coin-name {
  flex: 1;
  font-weight: 600;
  color: #1e293b;
  font-size: 16px;
}

.risk-tag {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.risk-tag.critical {
  background: #fee2e2;
  color: #dc2626;
}

.risk-tag.high {
  background: #ffedd5;
  color: #ea580c;
}

.risk-tag.medium {
  background: #fef9c3;
  color: #a16207;
}

.risk-tag.low {
  background: #dcfce7;
  color: #15803d;
}

.coin-addresses {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.coin-address-item {
  display: flex;
  gap: 8px;
  font-size: 13px;
}

.coin-address-item .label {
  color: #64748b;
  flex-shrink: 0;
}

.address-value {
  color: #1e293b;
  font-size: 12px;
  word-break: break-all;
}

.coin-desc {
  color: #64748b;
  font-size: 13px;
  margin: 8px 0 0 0;
}

.mixing-patterns {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.pattern-card {
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 12px;
  padding: 20px;
}

.pattern-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.pattern-type-badge {
  background: linear-gradient(135deg, #f59e0b, #d97706);
  color: white;
  padding: 6px 14px;
  border-radius: 16px;
  font-size: 13px;
  font-weight: 600;
}

.confidence-badge {
  background: #fef3c7;
  color: #92400e;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.pattern-description {
  color: #475569;
  font-size: 14px;
  margin: 0 0 16px 0;
  line-height: 1.5;
}

.pattern-evidence h4 {
  font-size: 14px;
  font-weight: 600;
  color: #334155;
  margin: 0 0 12px 0;
}

.evidence-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
}

.evidence-item {
  background: white;
  padding: 10px 14px;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.evidence-label {
  font-size: 12px;
  color: #64748b;
}

.evidence-value {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
}

.cross-chain-links {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.cross-chain-card {
  display: flex;
  gap: 16px;
  padding: 20px;
  border-radius: 12px;
  border-left: 4px solid;
}

.cross-chain-card.privacy_coin {
  background: #faf5ff;
  border-left-color: #8b5cf6;
}

.cross-chain-card.privacy_gateway {
  background: #eff6ff;
  border-left-color: #3b82f6;
}

.link-icon {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.cross-chain-card.privacy_coin .link-icon {
  background: rgba(139, 92, 246, 0.1);
  color: #8b5cf6;
}

.cross-chain-card.privacy_gateway .link-icon {
  background: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
}

.link-icon .icon {
  width: 24px;
  height: 24px;
}

.link-content {
  flex: 1;
}

.link-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-weight: 600;
  color: #1e293b;
  font-size: 16px;
}

.link-description {
  color: #475569;
  font-size: 14px;
  margin: 0 0 12px 0;
}

.link-detail {
  display: flex;
  gap: 8px;
  font-size: 13px;
  margin-bottom: 4px;
}

.detail-label {
  color: #64748b;
}

.detail-value {
  color: #1e293b;
  font-weight: 500;
}

.link-transaction {
  background: white;
  padding: 12px;
  border-radius: 8px;
  margin-top: 12px;
}

.tx-detail {
  display: flex;
  gap: 8px;
  font-size: 13px;
  margin-bottom: 8px;
}

.tx-flow {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #475569;
}

.arrow-icon {
  width: 16px;
  height: 16px;
  color: #8b5cf6;
}

.tx-value {
  margin-left: auto;
  font-weight: 600;
  color: #1e293b;
}

.transactions-table-container {
  overflow-x: auto;
}

.transactions-table {
  width: 100%;
  border-collapse: collapse;
}

.transactions-table th,
.transactions-table td {
  padding: 12px 16px;
  text-align: left;
  border-bottom: 1px solid #f1f5f9;
}

.transactions-table th {
  background: #f8fafc;
  font-weight: 600;
  color: #475569;
  font-size: 13px;
}

.transactions-table td {
  font-size: 13px;
  color: #334155;
}

.small {
  font-size: 12px;
}

.direction-badge {
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.direction-badge.incoming {
  background: #dcfce7;
  color: #15803d;
}

.direction-badge.outgoing {
  background: #fee2e2;
  color: #dc2626;
}

.threat-intel-card {
  background: linear-gradient(135deg, #fef2f2, #fee2e2);
  border: 1px solid #fecaca;
}

.threat-summary {
  display: flex;
  gap: 24px;
  align-items: flex-start;
  margin-bottom: 24px;
}

.threat-level {
  padding: 16px 24px;
  border-radius: 12px;
  text-align: center;
  background: white;
  flex-shrink: 0;
}

.threat-level.critical {
  border: 2px solid #ef4444;
}

.threat-level.high {
  border: 2px solid #f97316;
}

.threat-level.medium {
  border: 2px solid #eab308;
}

.threat-level.low {
  border: 2px solid #22c55e;
}

.threat-label {
  display: block;
  font-size: 12px;
  color: #64748b;
  margin-bottom: 4px;
}

.threat-value {
  font-size: 18px;
  font-weight: 700;
  color: #1e293b;
}

.threat-summary-text {
  flex: 1;
  color: #475569;
  font-size: 14px;
  line-height: 1.6;
  margin: 0;
  padding: 12px 0;
}

.threat-indicators {
  margin-bottom: 20px;
}

.threat-indicators h4,
.recommended-actions h4 {
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
  margin: 0 0 12px 0;
}

.indicators-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.indicator-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: white;
  border-radius: 8px;
  border-left: 3px solid;
  font-size: 14px;
}

.indicator-item.critical {
  border-left-color: #ef4444;
}

.indicator-item.high {
  border-left-color: #f97316;
}

.indicator-item.medium {
  border-left-color: #eab308;
}

.indicator-item.low {
  border-left-color: #22c55e;
}

.indicator-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.indicator-item.critical .indicator-dot {
  background: #ef4444;
}

.indicator-item.high .indicator-dot {
  background: #f97316;
}

.indicator-item.medium .indicator-dot {
  background: #eab308;
}

.indicator-item.low .indicator-dot {
  background: #22c55e;
}

.indicator-type {
  font-weight: 600;
  color: #334155;
}

.indicator-description {
  color: #475569;
}

.recommended-actions ul {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.recommended-actions li {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 14px;
  background: white;
  border-radius: 8px;
  font-size: 14px;
  color: #334155;
}

.check-icon {
  width: 18px;
  height: 18px;
  color: #8b5cf6;
  flex-shrink: 0;
  margin-top: 1px;
}

@media (max-width: 1024px) {
  .score-display {
    flex-direction: column;
    gap: 24px;
  }
  
  .score-details {
    grid-template-columns: 1fr;
  }
  
  .analysis-form {
    flex-direction: column;
    align-items: stretch;
  }
  
  .threat-summary {
    flex-direction: column;
  }
}
</style>