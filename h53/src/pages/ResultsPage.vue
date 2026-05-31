<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import {
  BarChart3,
  Download,
  FileText,
  Image,
  Table,
  Dna,
  AlertCircle,
  TrendingUp,
  Target,
  Filter,
  Settings2,
  ArrowLeft,
  Play,
  ArrowDown,
  Loader2,
  ArrowRight,
  GitBranch,
  Network,
  Crosshair,
  Database,
  Map
} from 'lucide-vue-next';
import { useTaskStore } from '@/stores';
import { resultAPI, analysisAPI, taskAPI } from '@/services/api';
import ManhattanPlot from '@/components/charts/ManhattanPlot.vue';
import QQPlot from '@/components/charts/QQPlot.vue';
import LDHeatmap from '@/components/charts/LDHeatmap.vue';
import type { 
  GWASResult, 
  SignificantSNP, 
  LDHeatmapResponse, 
  AnalysisTask,
  MultiPhenotypeResult,
  EnrichmentResult,
  FineMappingResult,
  EnrichmentTerm
} from '@/types';

const route = useRoute();
const router = useRouter();
const taskStore = useTaskStore();

const taskId = computed(() => route.params.taskId as string);

const result = ref<GWASResult | MultiPhenotypeResult | EnrichmentResult | FineMappingResult | null>(null);
const task = ref<AnalysisTask | null>(null);
const isLoading = ref(true);
const snpPage = ref(1);
const snpPageSize = ref(50);
const snpTotal = ref(0);
const snpList = ref<SignificantSNP[]>([]);
const snpFilter = ref({
  chr: '',
  minLog10P: 0,
});

const resultType = computed(() => {
  const r = result.value;
  if (!r) return 'unknown';
  if ('resultType' in r) {
    return r.resultType;
  }
  return 'gwas';
});

const activeTab = ref<string>('overview');

const ldRegion = ref({
  chr: '',
  start: 0,
  end: 0,
});

const ldResult = ref<LDHeatmapResponse | null>(null);
const ldLoading = ref(false);
const ldTaskId = ref<string | null>(null);

const enrichmentPage = ref(1);
const enrichmentPageSize = ref(20);

const ccaComponentIndex = ref(0);

const tabsConfig = computed(() => {
  const type = resultType.value;
  const baseTabs = [
    { key: 'overview', label: '总览', icon: BarChart3 },
  ];
  
  if (type === 'gwas') {
    return [
      ...baseTabs,
      { key: 'manhattan', label: '曼哈顿图', icon: BarChart3 },
      { key: 'qq', label: 'QQ图', icon: TrendingUp },
      { key: 'snps', label: '显著SNP', icon: Table },
      { key: 'ld', label: 'LD热图', icon: Dna },
    ];
  } else if (type === 'multiphenotype') {
    return [
      ...baseTabs,
      { key: 'manhattan', label: '曼哈顿图', icon: BarChart3 },
      { key: 'cca', label: 'CCA结果', icon: GitBranch },
      { key: 'snps', label: '显著SNP', icon: Table },
    ];
  } else if (type === 'enrichment') {
    return [
      ...baseTabs,
      { key: 'barplot', label: '富集条形图', icon: BarChart3 },
      { key: 'network', label: '基因-概念网络', icon: Network },
      { key: 'genes', label: '候选基因', icon: Database },
    ];
  } else if (type === 'finemapping') {
    return [
      ...baseTabs,
      { key: 'pip', label: 'PIP图', icon: Crosshair },
      { key: 'credible', label: '可信集合', icon: Table },
      { key: 'ld', label: 'LD热图', icon: Dna },
    ];
  }
  
  return baseTabs;
});

const gwasResult = computed(() => {
  return resultType.value === 'gwas' ? (result.value as GWASResult) : null;
});

const multiphenotypeResult = computed(() => {
  return resultType.value === 'multiphenotype' ? (result.value as MultiPhenotypeResult) : null;
});

const enrichmentResult = computed(() => {
  return resultType.value === 'enrichment' ? (result.value as EnrichmentResult) : null;
});

const finemappingResult = computed(() => {
  return resultType.value === 'finemapping' ? (result.value as FineMappingResult) : null;
});

const paginatedEnrichmentTerms = computed(() => {
  if (!enrichmentResult.value?.enrichmentData) return [];
  const start = (enrichmentPage.value - 1) * enrichmentPageSize.value;
  const end = start + enrichmentPageSize.value;
  return enrichmentResult.value.enrichmentData.slice(start, end);
});

const loadTask = async () => {
  try {
    task.value = await taskAPI.getTask(taskId.value);
  } catch (e) {
    console.error('Failed to load task:', e);
  }
};

const loadResult = async () => {
  try {
    isLoading.value = true;
    result.value = await resultAPI.getResult(taskId.value);
    taskStore.setCurrentResult(result.value);
    
    if (resultType.value === 'gwas' && (result.value as GWASResult).significantSNPs) {
      snpTotal.value = (result.value as GWASResult).significantSNPCount;
      snpList.value = (result.value as GWASResult).significantSNPs.slice(0, snpPageSize.value);
    }
    
    activeTab.value = 'overview';
  } catch (e) {
    console.error('Failed to load result:', e);
  } finally {
    isLoading.value = false;
  }
};

const loadSNPs = async () => {
  if (resultType.value !== 'gwas') return;
  
  try {
    const response = await resultAPI.getSNPs(
      taskId.value,
      snpPage.value,
      snpPageSize.value,
      snpFilter.value.chr || undefined,
      snpFilter.value.minLog10P || undefined
    );
    snpTotal.value = response.total;
    snpList.value = response.snps;
  } catch (e) {
    console.error('Failed to load SNPs:', e);
  }
};

const handleSnpClick = (snp: any) => {
  ldRegion.value = {
    chr: snp.chr,
    start: Math.max(0, snp.pos - 500000),
    end: snp.pos + 500000,
  };
  activeTab.value = 'ld';
};

const calculateLDHeatmap = async () => {
  if (!task.value || !ldRegion.value.chr) return;
  
  const vcfFileId = task.value.parameters.vcf_file_id;
  if (!vcfFileId) {
    ElMessage.warning('无法找到VCF文件信息');
    return;
  }
  
  try {
    ldLoading.value = true;
    const response = await analysisAPI.calculateLDHeatmap({
      vcfFileId,
      chr: ldRegion.value.chr,
      start: ldRegion.value.start,
      end: ldRegion.value.end,
    });
    ldTaskId.value = response.taskId;
    ElMessage.success('LD热图分析任务已提交');
    
    const checkInterval = setInterval(async () => {
      try {
        const taskStatus = await taskAPI.getTask(ldTaskId.value!);
        if (taskStatus.status === 'completed') {
          clearInterval(checkInterval);
          if (taskStatus.parameters.ld_result) {
            ldResult.value = {
              snpNames: taskStatus.parameters.ld_result.snpNames,
              positions: taskStatus.parameters.ld_result.positions,
              ldMatrix: taskStatus.parameters.ld_result.ldMatrix,
              hapBlocks: taskStatus.parameters.ld_result.hapBlocks,
            };
          }
          ldLoading.value = false;
        } else if (taskStatus.status === 'failed') {
          clearInterval(checkInterval);
          ldLoading.value = false;
          ElMessage.error('LD热图分析失败');
        }
      } catch (e) {
        console.error('LD task check failed:', e);
      }
    }, 3000);
  } catch (e) {
    ldLoading.value = false;
    console.error('LD analysis failed:', e);
  }
};

const downloadFile = (type: string) => {
  const urls: Record<string, string> = {
    manhattan: resultAPI.downloadManhattan(taskId.value),
    qq: resultAPI.downloadQQ(taskId.value),
    snps: resultAPI.downloadSNPsCSV(taskId.value),
    report: resultAPI.downloadReport(taskId.value),
  };
  
  const url = urls[type];
  if (!url) return;
  
  const link = document.createElement('a');
  link.href = url;
  link.target = '_blank';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  
  ElMessage.success('下载已开始');
};

const chromosomes = computed(() => {
  const r = result.value;
  if (!r) return [];
  
  let manhattanData = [];
  if ('manhattanData' in r) {
    manhattanData = r.manhattanData;
  }
  
  return Array.from(new Set(manhattanData.map(d => d.chr)))
    .sort((a, b) => parseInt(a) - parseInt(b));
});

const topSNPs = computed(() => {
  const r = result.value;
  if (!r) return [];
  
  if (resultType.value === 'gwas') {
    return (r as GWASResult).significantSNPs?.slice(0, 10) || [];
  } else if (resultType.value === 'multiphenotype') {
    return (r as MultiPhenotypeResult).topVariants?.slice(0, 10) || [];
  }
  return [];
});

const resultQuality = computed(() => {
  if (resultType.value !== 'gwas') return 'unknown';
  const lambda = (result.value as GWASResult).inflationFactor;
  if (!lambda) return 'unknown';
  if (lambda < 1.05) return 'good';
  if (lambda < 1.2) return 'moderate';
  return 'high';
});

const qualityConfig = computed(() => {
  const configs = {
    good: { label: '良好', color: '#00B42A', bg: 'rgba(0, 180, 42, 0.1)' },
    moderate: { label: '一般', color: '#FF7D00', bg: 'rgba(255, 125, 0, 0.1)' },
    high: { label: '偏高', color: '#F53F3F', bg: 'rgba(245, 63, 63, 0.1)' },
    unknown: { label: '未知', color: '#64748B', bg: 'rgba(100, 116, 139, 0.1)' },
  };
  return configs[resultQuality.value];
});

const leadVariantInfo = computed(() => {
  if (resultType.value !== 'finemapping' || !finemappingResult.value?.leadVariant) {
    return null;
  }
  return finemappingResult.value.leadVariant;
});

watch(snpPage, loadSNPs);
watch(snpPageSize, loadSNPs);
watch(snpFilter, loadSNPs, { deep: true });

onMounted(() => {
  loadTask();
  loadResult();
});
</script>

<template>
  <div class="results-page">
    <div class="page-header">
      <div class="header-left">
        <button class="back-btn" @click="router.push('/tasks')">
          <ArrowLeft class="back-icon" />
        </button>
        <div>
          <h2 class="page-title">
            分析结果
            <el-tag 
              :type="task?.status === 'completed' ? 'success' : 'info'" 
              size="small" 
              class="status-tag"
            >
              {{ task?.status === 'completed' ? '已完成' : task?.status }}
            </el-tag>
          </h2>
          <p class="page-desc">
            <template v-if="resultType === 'gwas'">
              {{ gwasResult?.model }}分析 - {{ gwasResult?.phenotype }} - {{ taskId }}
            </template>
            <template v-else-if="resultType === 'multiphenotype'">
              {{ multiphenotypeResult?.method }}多表型联合分析 - {{ multiphenotypeResult?.phenotypeNames?.join(', ') }} - {{ taskId }}
            </template>
            <template v-else-if="resultType === 'enrichment'">
              {{ enrichmentResult?.enrichmentType }}富集分析 - {{ taskId }}
            </template>
            <template v-else-if="resultType === 'finemapping'">
              贝叶斯精细定位 - {{ finemappingResult?.regionChromosome }}:{{ finemappingResult?.regionStart?.toLocaleString() }}-{{ finemappingResult?.regionEnd?.toLocaleString() }} - {{ taskId }}
            </template>
          </p>
        </div>
      </div>
      
      <div class="header-actions">
        <el-dropdown>
          <el-button type="primary" size="large">
            <Download class="btn-icon" />
            下载
            <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item v-if="resultType === 'gwas' || resultType === 'multiphenotype'" @click="downloadFile('manhattan')">
                <Image class="menu-icon" />
                曼哈顿图 (PNG)
              </el-dropdown-item>
              <el-dropdown-item v-if="resultType === 'gwas'" @click="downloadFile('qq')">
                <Image class="menu-icon" />
                QQ图 (PNG)
              </el-dropdown-item>
              <el-dropdown-item @click="downloadFile('snps')">
                <Table class="menu-icon" />
                结果列表 (CSV)
              </el-dropdown-item>
              <el-dropdown-item divided @click="downloadFile('report')">
                <FileText class="menu-icon" />
                完整分析报告 (PDF)
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>
    
    <div v-if="resultType === 'gwas' && gwasResult?.mlmFailed" class="warning-banner">
      <div class="warning-icon-wrapper">
        <AlertCircle class="warning-icon" />
      </div>
      <div class="warning-content">
        <h4 class="warning-title">MLM模型收敛失败，已自动降级到GLM模型</h4>
        <p class="warning-desc">
          由于混合线性模型（MLM）的方差组分估计失败或矩阵非正定，系统已自动切换到广义线性模型（GLM）进行分析。
          建议检查数据质量、样本大小或考虑减少协变量数量。
        </p>
        <div v-if="gwasResult?.warnings && gwasResult.warnings.length > 0" class="warning-details">
          <p class="details-title">详细信息：</p>
          <ul class="warning-list">
            <li v-for="(warning, idx) in gwasResult.warnings" :key="idx" class="warning-item">
              {{ warning }}
            </li>
          </ul>
        </div>
      </div>
    </div>
    
    <div v-else-if="resultType === 'gwas' && gwasResult?.warnings && gwasResult.warnings.length > 0" class="info-banner">
      <div class="info-icon-wrapper">
        <AlertCircle class="info-icon" />
      </div>
      <div class="info-content">
        <h4 class="info-title">分析过程中存在 {{ gwasResult.warnings.length }} 条警告</h4>
        <ul class="warning-list">
          <li v-for="(warning, idx) in gwasResult.warnings" :key="idx" class="warning-item">
            {{ warning }}
          </li>
        </ul>
      </div>
    </div>
    
    <div v-if="isLoading" class="loading-state">
      <Loader2 class="is-loading" :size="40" style="animation: spin 1s linear infinite" />
      <span>加载结果中...</span>
    </div>
    
    <div v-else-if="!result" class="empty-state">
      <AlertCircle class="empty-icon" />
      <p class="empty-title">无法加载结果</p>
      <p class="empty-desc">请检查任务ID是否正确，或任务是否已完成</p>
    </div>
    
    <div v-else class="results-content">
      <div v-if="resultType === 'gwas'" class="overview-cards">
        <div class="stat-card">
          <div class="stat-icon primary">
            <Target class="icon" />
          </div>
          <div class="stat-content">
            <span class="stat-label">显著SNP数量</span>
            <span class="stat-value">{{ gwasResult!.significantSNPCount.toLocaleString() }}</span>
          </div>
        </div>
        
        <div class="stat-card">
          <div class="stat-icon secondary">
            <TrendingUp class="icon" />
          </div>
          <div class="stat-content">
            <span class="stat-label">Inflation Factor (λ)</span>
            <span class="stat-value" :style="{ color: qualityConfig.color }">
              {{ gwasResult!.inflationFactor?.toFixed(3) }}
            </span>
            <span class="quality-badge" :style="{ color: qualityConfig.color, background: qualityConfig.bg }">
              {{ qualityConfig.label }}
            </span>
          </div>
        </div>
        
        <div class="stat-card">
          <div class="stat-icon accent">
            <BarChart3 class="icon" />
          </div>
          <div class="stat-content">
            <span class="stat-label">分析模型</span>
            <span class="stat-value">{{ gwasResult!.model }}</span>
            <span class="stat-hint">{{ gwasResult!.model === 'GLM' ? '广义线性模型' : '混合线性模型' }}</span>
          </div>
        </div>
        
        <div class="stat-card">
          <div class="stat-icon info">
            <Dna class="icon" />
          </div>
          <div class="stat-content">
            <span class="stat-label">分析性状</span>
            <span class="stat-value">{{ gwasResult!.phenotype }}</span>
          </div>
        </div>
      </div>
      
      <div v-else-if="resultType === 'multiphenotype'" class="overview-cards">
        <div class="stat-card">
          <div class="stat-icon primary">
            <Target class="icon" />
          </div>
          <div class="stat-content">
            <span class="stat-label">显著SNP数量</span>
            <span class="stat-value">{{ multiphenotypeResult!.nSignificant.toLocaleString() }}</span>
          </div>
        </div>
        
        <div class="stat-card">
          <div class="stat-icon secondary">
            <GitBranch class="icon" />
          </div>
          <div class="stat-content">
            <span class="stat-label">分析方法</span>
            <span class="stat-value">{{ multiphenotypeResult!.method }}</span>
            <span class="stat-hint">{{ multiphenotypeResult!.method === 'MANOVA' ? '多元方差分析' : '典型相关分析' }}</span>
          </div>
        </div>
        
        <div class="stat-card">
          <div class="stat-icon accent">
            <Dna class="icon" />
          </div>
          <div class="stat-content">
            <span class="stat-label">表型数量</span>
            <span class="stat-value">{{ multiphenotypeResult!.phenotypeNames?.length || 0 }}</span>
          </div>
        </div>
        
        <div class="stat-card">
          <div class="stat-icon info">
            <TrendingUp class="icon" />
          </div>
          <div class="stat-content">
            <span class="stat-label">全局检验P值</span>
            <span class="stat-value">{{ multiphenotypeResult!.globalTest?.pValue?.toExponential(2) }}</span>
          </div>
        </div>
      </div>
      
      <div v-else-if="resultType === 'enrichment'" class="overview-cards">
        <div class="stat-card">
          <div class="stat-icon primary">
            <Target class="icon" />
          </div>
          <div class="stat-content">
            <span class="stat-label">显著富集条目</span>
            <span class="stat-value">{{ enrichmentResult!.significantTermsCount.toLocaleString() }}</span>
          </div>
        </div>
        
        <div class="stat-card">
          <div class="stat-icon secondary">
            <Database class="icon" />
          </div>
          <div class="stat-content">
            <span class="stat-label">富集类型</span>
            <span class="stat-value">{{ enrichmentResult!.enrichmentType }}</span>
            <span class="stat-hint">{{ enrichmentResult!.enrichmentType === 'GO' ? 'Gene Ontology' : 'KEGG Pathway' }}</span>
          </div>
        </div>
        
        <div class="stat-card">
          <div class="stat-icon accent">
            <Dna class="icon" />
          </div>
          <div class="stat-content">
            <span class="stat-label">候选基因数</span>
            <span class="stat-value">{{ enrichmentResult!.candidateGenes?.length || 0 }}</span>
          </div>
        </div>
        
        <div class="stat-card">
          <div class="stat-icon info">
            <BarChart3 class="icon" />
          </div>
          <div class="stat-content">
            <span class="stat-label">分析条目总数</span>
            <span class="stat-value">{{ enrichmentResult!.totalTermsAnalyzed.toLocaleString() }}</span>
          </div>
        </div>
      </div>
      
      <div v-else-if="resultType === 'finemapping'" class="overview-cards">
        <div class="stat-card">
          <div class="stat-icon primary">
            <Target class="icon" />
          </div>
          <div class="stat-content">
            <span class="stat-label">95%可信集合大小</span>
            <span class="stat-value">{{ finemappingResult!.credibleSets?.size_95 || 0 }}</span>
          </div>
        </div>
        
        <div class="stat-card">
          <div class="stat-icon secondary">
            <Crosshair class="icon" />
          </div>
          <div class="stat-content">
            <span class="stat-label">99%可信集合大小</span>
            <span class="stat-value">{{ finemappingResult!.credibleSets?.size_99 || 0 }}</span>
          </div>
        </div>
        
        <div class="stat-card">
          <div class="stat-icon accent">
            <Dna class="icon" />
          </div>
          <div class="stat-content">
            <span class="stat-label">SNP总数</span>
            <span class="stat-value">{{ finemappingResult!.nVariants.toLocaleString() }}</span>
          </div>
        </div>
        
        <div class="stat-card" v-if="leadVariantInfo">
          <div class="stat-icon info">
            <Map class="icon" />
          </div>
          <div class="stat-content">
            <span class="stat-label">Lead SNP</span>
            <span class="stat-value">{{ leadVariantInfo.id }}</span>
            <span class="stat-hint">PIP最高的SNP</span>
          </div>
        </div>
      </div>
      
      <div class="tabs-section">
        <div class="tabs-header">
          <button
            v-for="tab in tabsConfig"
            :key="tab.key"
            :class="['tab-btn', { active: activeTab === tab.key }]"
            @click="activeTab = tab.key"
          >
            <component :is="tab.icon" class="tab-icon" />
            {{ tab.label }}
          </button>
        </div>
        
        <div class="tabs-content">
          <div v-show="activeTab === 'overview'" class="overview-section">
            <div v-if="resultType === 'gwas' || resultType === 'multiphenotype'" class="overview-grid">
              <div class="chart-card">
                <div class="card-header">
                  <h3 class="card-title">曼哈顿图</h3>
                  <el-button text type="primary" @click="activeTab = 'manhattan'">
                    查看详情 <ArrowRight class="arrow-icon" />
                  </el-button>
                </div>
                <ManhattanPlot 
                  v-if="resultType === 'gwas' && gwasResult"
                  :data="gwasResult.manhattanData" 
                  :threshold="5e-8"
                  height="350px"
                  @snp-click="handleSnpClick"
                />
                <ManhattanPlot 
                  v-else-if="resultType === 'multiphenotype' && multiphenotypeResult"
                  :data="multiphenotypeResult.manhattanData" 
                  :threshold="5e-8"
                  height="350px"
                  @snp-click="handleSnpClick"
                />
              </div>
              
              <div class="chart-card" v-if="resultType === 'gwas'">
                <div class="card-header">
                  <h3 class="card-title">QQ图</h3>
                  <el-button text type="primary" @click="activeTab = 'qq'">
                    查看详情 <ArrowRight class="arrow-icon" />
                  </el-button>
                </div>
                <QQPlot 
                  :data="gwasResult!.qqData" 
                  :inflation-factor="gwasResult!.inflationFactor"
                  height="350px"
                />
              </div>
              
              <div class="chart-card" v-else-if="resultType === 'multiphenotype' && multiphenotypeResult?.ccaResult">
                <div class="card-header">
                  <h3 class="card-title">典型相关系数</h3>
                  <el-button text type="primary" @click="activeTab = 'cca'">
                    查看详情 <ArrowRight class="arrow-icon" />
                  </el-button>
                </div>
                <div class="cca-correlation-chart">
                  <div v-for="(corr, idx) in multiphenotypeResult!.ccaResult!.canonicalCorrelations" :key="idx" class="cca-item">
                    <div class="cca-label">CC{{ idx + 1 }}</div>
                    <div class="cca-bar">
                      <div class="cca-fill" :style="{ width: `${corr * 100}%` }"></div>
                    </div>
                    <div class="cca-value">{{ corr.toFixed(3) }}</div>
                    <div class="cca-pvalue">P: {{ multiphenotypeResult!.ccaResult!.pValues[idx]?.toExponential(1) }}</div>
                  </div>
                </div>
              </div>
            </div>
            
            <div v-else-if="resultType === 'enrichment'" class="overview-grid">
              <div class="chart-card">
                <div class="card-header">
                  <h3 class="card-title">Top 10 富集条目</h3>
                  <el-button text type="primary" @click="activeTab = 'barplot'">
                    查看详情 <ArrowRight class="arrow-icon" />
                  </el-button>
                </div>
                <div class="enrichment-bars">
                  <div 
                    v-for="(term, idx) in enrichmentResult!.barplotData?.slice(0, 10)" 
                    :key="idx" 
                    class="enrichment-bar-item"
                  >
                    <div class="enrichment-bar-label" :title="term.name">{{ term.name }}</div>
                    <div class="enrichment-bar-track">
                      <div 
                        class="enrichment-bar-fill" 
                        :style="{ width: `${(term.negLog10AdjP / Math.max(...enrichmentResult!.barplotData!.slice(0, 10).map(t => t.negLog10AdjP)) * 100)}%` }"
                      ></div>
                    </div>
                    <div class="enrichment-bar-value">{{ term.negLog10AdjP.toFixed(1) }}</div>
                  </div>
                </div>
              </div>
              
              <div class="chart-card">
                <div class="card-header">
                  <h3 class="card-title">候选基因列表</h3>
                  <el-button text type="primary" @click="activeTab = 'genes'">
                    查看详情 <ArrowRight class="arrow-icon" />
                  </el-button>
                </div>
                <div class="gene-list">
                  <el-tag 
                    v-for="(gene, idx) in enrichmentResult!.candidateGenes?.slice(0, 30)" 
                    :key="idx"
                    type="success"
                    size="small"
                    class="gene-tag"
                  >
                    {{ gene }}
                  </el-tag>
                </div>
              </div>
            </div>
            
            <div v-else-if="resultType === 'finemapping'" class="overview-grid">
              <div class="chart-card">
                <div class="card-header">
                  <h3 class="card-title">PIP图</h3>
                  <el-button text type="primary" @click="activeTab = 'pip'">
                    查看详情 <ArrowRight class="arrow-icon" />
                  </el-button>
                </div>
                <ManhattanPlot 
                  :data="finemappingResult!.manhattanData.map(d => ({ ...d, pip: d.pip }))" 
                  :threshold="0.95"
                  :pip-mode="true"
                  height="350px"
                />
              </div>
              
              <div class="chart-card">
                <div class="card-header">
                  <h3 class="card-title">可信集合SNP</h3>
                  <el-button text type="primary" @click="activeTab = 'credible'">
                    查看详情 <ArrowRight class="arrow-icon" />
                  </el-button>
                </div>
                <div class="credible-snps">
                  <div 
                    v-for="(snp, idx) in finemappingResult!.credibleSetTable?.filter(s => s.in95CredibleSet).slice(0, 10)" 
                    :key="idx" 
                    class="credible-snp-item"
                  >
                    <div class="credible-snp-name">{{ snp.snp }}</div>
                    <div class="credible-snp-pos">{{ (snp.pos / 1e6).toFixed(3) }} Mb</div>
                    <div class="credible-snp-pip">
                      PIP: <strong>{{ snp.pip.toFixed(3) }}</strong>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            
            <div class="top-snps-section" v-if="resultType === 'gwas' || resultType === 'multiphenotype'">
              <div class="card-header">
                <h3 class="card-title">Top 10 显著SNP</h3>
                <el-button text type="primary" @click="activeTab = 'snps'">
                  查看全部 <ArrowRight class="arrow-icon" />
                </el-button>
              </div>
              
              <div class="snps-table-wrapper">
                <el-table :data="topSNPs" stripe size="small">
                  <el-table-column prop="snp" label="SNP ID" width="140" />
                  <el-table-column prop="chr" label="染色体" width="100" align="center" />
                  <el-table-column prop="pos" label="位置" width="120" align="right">
                    <template #default="{ row }">
                      {{ row.pos.toLocaleString() }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="pValue" label="P值" width="140">
                    <template #default="{ row }">
                      {{ row.pValue.toExponential(2) }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="log10P" label="-log10(P)" width="100" align="right">
                    <template #default="{ row }">
                      <span class="log10p-value">{{ row.log10P.toFixed(2) }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column prop="effectSize" label="效应值" width="100" align="right">
                    <template #default="{ row }">
                      {{ row.effectSize?.toFixed(3) || '-' }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="maf" label="MAF" width="100" align="right">
                    <template #default="{ row }">
                      {{ row.maf?.toFixed(3) || '-' }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="gene" label="基因" width="120">
                    <template #default="{ row }">
                      <el-tag v-if="row.gene" type="success" size="small">{{ row.gene }}</el-tag>
                      <span v-else class="text-muted">-</span>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
            </div>
          </div>
          
          <div v-show="activeTab === 'manhattan'" class="manhattan-section">
            <div class="chart-card full-width">
              <div class="card-header">
                <h3 class="card-title">曼哈顿图 (Manhattan Plot)</h3>
                <el-button size="small" @click="downloadFile('manhattan')">
                  <Download class="btn-icon" />
                  下载图片
                </el-button>
              </div>
              <ManhattanPlot 
                v-if="resultType === 'gwas' && gwasResult"
                :data="gwasResult.manhattanData" 
                :threshold="5e-8"
                height="600px"
                @snp-click="handleSnpClick"
              />
              <ManhattanPlot 
                v-else-if="resultType === 'multiphenotype' && multiphenotypeResult"
                :data="multiphenotypeResult.manhattanData" 
                :threshold="5e-8"
                height="600px"
                @snp-click="handleSnpClick"
              />
            </div>
          </div>
          
          <div v-show="activeTab === 'qq'" class="qq-section">
            <div class="chart-card full-width">
              <div class="card-header">
                <h3 class="card-title">QQ图 (Quantile-Quantile Plot)</h3>
                <el-button size="small" @click="downloadFile('qq')">
                  <Download class="btn-icon" />
                  下载图片
                </el-button>
              </div>
              <QQPlot 
                v-if="resultType === 'gwas' && gwasResult"
                :data="gwasResult.qqData" 
                :inflation-factor="gwasResult.inflationFactor"
                height="600px"
              />
            </div>
          </div>
          
          <div v-show="activeTab === 'cca'" class="cca-section">
            <div class="chart-card full-width" v-if="resultType === 'multiphenotype' && multiphenotypeResult?.ccaResult">
              <div class="card-header">
                <h3 class="card-title">典型相关分析 (CCA) 结果</h3>
              </div>
              
              <div class="cca-results">
                <div class="cca-tabs">
                  <button
                    v-for="(corr, idx) in multiphenotypeResult!.ccaResult!.canonicalCorrelations"
                    :key="idx"
                    :class="['cca-tab-btn', { active: ccaComponentIndex === idx }]"
                    @click="ccaComponentIndex = idx"
                  >
                    CC{{ idx + 1 }}
                    <span class="cca-tab-corr">r = {{ corr.toFixed(3) }}</span>
                  </button>
                </div>
                
                <div class="cca-component-results">
                  <div class="cca-stats-grid">
                    <div class="cca-stat-card">
                      <div class="cca-stat-label">相关系数</div>
                      <div class="cca-stat-value">{{ multiphenotypeResult!.ccaResult!.canonicalCorrelations[ccaComponentIndex]?.toFixed(4) }}</div>
                    </div>
                    <div class="cca-stat-card">
                      <div class="cca-stat-label">Wilks' Lambda</div>
                      <div class="cca-stat-value">{{ multiphenotypeResult!.ccaResult!.wilksLambda[ccaComponentIndex]?.toFixed(4) }}</div>
                    </div>
                    <div class="cca-stat-card">
                      <div class="cca-stat-label">P值</div>
                      <div class="cca-stat-value">{{ multiphenotypeResult!.ccaResult!.pValues[ccaComponentIndex]?.toExponential(3) }}</div>
                    </div>
                    <div class="cca-stat-card">
                      <div class="cca-stat-label">方差解释 (X)</div>
                      <div class="cca-stat-value">{{ (multiphenotypeResult!.ccaResult!.varianceExplainedX[ccaComponentIndex] * 100).toFixed(2) }}%</div>
                    </div>
                    <div class="cca-stat-card">
                      <div class="cca-stat-label">方差解释 (Y)</div>
                      <div class="cca-stat-value">{{ (multiphenotypeResult!.ccaResult!.varianceExplainedY[ccaComponentIndex] * 100).toFixed(2) }}%</div>
                    </div>
                  </div>
                  
                  <div class="cca-loadings-grid">
                    <div class="cca-loadings-card">
                      <h4 class="card-subtitle">基因型载荷 (X)</h4>
                      <div class="loadings-list">
                        <div 
                          v-for="(loading, idx) in multiphenotypeResult!.ccaResult!.xLoadings[ccaComponentIndex]?.slice(0, 20)" 
                          :key="idx"
                          class="loading-item"
                        >
                          <div class="loading-name">SNP {{ idx + 1 }}</div>
                          <div class="loading-bar-track">
                            <div 
                              class="loading-bar-fill" 
                              :class="{ positive: loading >= 0, negative: loading < 0 }"
                              :style="{ 
                                width: `${Math.abs(loading) * 100}%`,
                                marginLeft: loading >= 0 ? '50%' : `${50 - Math.abs(loading) * 50}%`
                              }"
                            ></div>
                          </div>
                          <div class="loading-value">{{ loading.toFixed(3) }}</div>
                        </div>
                      </div>
                    </div>
                    
                    <div class="cca-loadings-card">
                      <h4 class="card-subtitle">表型载荷 (Y)</h4>
                      <div class="loadings-list">
                        <div 
                          v-for="(loading, idx) in multiphenotypeResult!.ccaResult!.yLoadings[ccaComponentIndex]" 
                          :key="idx"
                          class="loading-item"
                        >
                          <div class="loading-name">{{ multiphenotypeResult!.phenotypeNames[idx] }}</div>
                          <div class="loading-bar-track">
                            <div 
                              class="loading-bar-fill" 
                              :class="{ positive: loading >= 0, negative: loading < 0 }"
                              :style="{ 
                                width: `${Math.abs(loading) * 100}%`,
                                marginLeft: loading >= 0 ? '50%' : `${50 - Math.abs(loading) * 50}%`
                              }"
                            ></div>
                          </div>
                          <div class="loading-value">{{ loading.toFixed(3) }}</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
          
          <div v-show="activeTab === 'snps'" class="snps-section">
            <div class="chart-card full-width">
              <div class="card-header">
                <h3 class="card-title">显著SNP列表</h3>
                <div class="card-actions">
                  <div class="filter-group">
                    <Filter class="filter-icon" />
                    <el-select
                      v-model="snpFilter.chr"
                      placeholder="染色体"
                      clearable
                      size="small"
                      style="width: 120px"
                    >
                      <el-option
                        v-for="chr in chromosomes"
                        :key="chr"
                        :label="chr"
                        :value="chr"
                      />
                    </el-select>
                    <el-input-number
                      v-model="snpFilter.minLog10P"
                      :min="0"
                      :max="30"
                      :step="1"
                      placeholder="最小-log10(P)"
                      size="small"
                      style="width: 150px"
                    />
                  </div>
                  <el-button size="small" @click="downloadFile('snps')">
                    <Download class="btn-icon" />
                    导出CSV
                  </el-button>
                </div>
              </div>
              
              <div class="snps-table-wrapper">
                <el-table 
                  :data="snpList" 
                  stripe 
                  size="default"
                  v-loading="isLoading"
                >
                  <el-table-column prop="snp" label="SNP ID" width="140" fixed="left" />
                  <el-table-column prop="chr" label="Chr" width="80" align="center" />
                  <el-table-column prop="pos" label="Position" width="120" align="right">
                    <template #default="{ row }">
                      {{ row.pos.toLocaleString() }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="ref" label="Ref" width="80" align="center" />
                  <el-table-column prop="alt" label="Alt" width="80" align="center" />
                  <el-table-column prop="pValue" label="P-value" width="140">
                    <template #default="{ row }">
                      <span class="p-value">{{ row.pValue.toExponential(2) }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column prop="log10P" label="-log10(P)" width="110" align="right">
                    <template #default="{ row }">
                      <span class="log10p-value high">{{ row.log10P.toFixed(2) }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column prop="effectSize" label="Effect" width="100" align="right">
                    <template #default="{ row }">
                      {{ row.effectSize?.toFixed(3) || '-' }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="maf" label="MAF" width="90" align="right">
                    <template #default="{ row }">
                      {{ row.maf?.toFixed(3) || '-' }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="gene" label="Gene" width="120">
                    <template #default="{ row }">
                      <el-tag v-if="row.gene" type="success" size="small">{{ row.gene }}</el-tag>
                      <span v-else class="text-muted">-</span>
                    </template>
                  </el-table-column>
                  <el-table-column prop="annotation" label="Annotation" min-width="150">
                    <template #default="{ row }">
                      <span v-if="row.annotation">{{ row.annotation }}</span>
                      <span v-else class="text-muted">-</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="120" fixed="right" align="center">
                    <template #default="{ row }">
                      <el-button type="primary" link size="small" @click="handleSnpClick(row)">
                        LD分析
                      </el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
              
              <div class="pagination-wrapper" v-if="resultType === 'gwas'">
                <el-pagination
                  v-model:current-page="snpPage"
                  v-model:page-size="snpPageSize"
                  :total="snpTotal"
                  :page-sizes="[20, 50, 100, 200]"
                  layout="total, sizes, prev, pager, next, jumper"
                />
              </div>
            </div>
          </div>
          
          <div v-show="activeTab === 'barplot'" class="barplot-section">
            <div class="chart-card full-width" v-if="resultType === 'enrichment' && enrichmentResult">
              <div class="card-header">
                <h3 class="card-title">{{ enrichmentResult.enrichmentType }} 富集分析条形图</h3>
              </div>
              <div class="enrichment-barplot-container">
                <div 
                  v-for="(term, idx) in enrichmentResult.barplotData" 
                  :key="idx" 
                  class="enrichment-barplot-item"
                >
                  <div class="enrichment-barplot-label" :title="term.name">
                    <span class="term-id">{{ term.id }}</span>
                    {{ term.name }}
                  </div>
                  <div class="enrichment-barplot-track">
                    <div 
                      class="enrichment-barplot-fill" 
                      :style="{ 
                        width: `${(term.negLog10AdjP / Math.max(...enrichmentResult.barplotData!.map(t => t.negLog10AdjP)) * 100)}%`,
                        background: `linear-gradient(90deg, #165DFF, #00B42A)`
                      }"
                    ></div>
                  </div>
                  <div class="enrichment-barplot-meta">
                    <span class="gene-count">{{ term.geneCount }} genes</span>
                    <span class="enrichment-ratio">ER: {{ term.enrichmentRatio.toFixed(1) }}x</span>
                    <span class="adj-p">P: {{ term.adjPValue.toExponential(2) }}</span>
                    <span class="neglogp">-log10P: {{ term.negLog10AdjP.toFixed(1) }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
          
          <div v-show="activeTab === 'network'" class="network-section">
            <div class="chart-card full-width" v-if="resultType === 'enrichment' && enrichmentResult?.networkData">
              <div class="card-header">
                <h3 class="card-title">基因-概念网络</h3>
              </div>
              <div class="network-container">
                <div class="network-legend">
                  <div class="legend-item">
                    <div class="legend-dot term"></div>
                    <span>功能条目</span>
                  </div>
                  <div class="legend-item">
                    <div class="legend-dot gene"></div>
                    <span>基因</span>
                  </div>
                </div>
                <div class="network-graph-placeholder">
                  <Network class="network-icon" />
                  <p class="network-hint">交互式网络图将在后续版本中支持</p>
                  <p class="network-stats">
                    包含 {{ enrichmentResult.networkData.nodes.length }} 个节点和 {{ enrichmentResult.networkData.links.length }} 条边
                  </p>
                </div>
              </div>
            </div>
          </div>
          
          <div v-show="activeTab === 'genes'" class="genes-section">
            <div class="chart-card full-width" v-if="resultType === 'enrichment' && enrichmentResult">
              <div class="card-header">
                <h3 class="card-title">候选基因列表 ({{ enrichmentResult.candidateGenes?.length || 0 }}个)</h3>
              </div>
              <div class="candidate-genes-grid">
                <div 
                  v-for="(gene, idx) in enrichmentResult.candidateGenes" 
                  :key="idx"
                  class="candidate-gene-card"
                >
                  <Dna class="gene-icon" />
                  <span class="gene-name">{{ gene }}</span>
                  <div class="gene-snps">
                    <small>相关SNP: {{ enrichmentResult.snpGeneMapping?.[gene]?.length || 'N/A' }}个</small>
                  </div>
                </div>
              </div>
              
              <div class="enrichment-terms-table" style="margin-top: 32px;">
                <h4 class="card-subtitle">富集分析详细结果</h4>
                <el-table :data="paginatedEnrichmentTerms" stripe size="default">
                  <el-table-column prop="id" label="条目ID" width="140" />
                  <el-table-column prop="name" label="名称" min-width="250" />
                  <el-table-column prop="category" label="分类" width="120" v-if="enrichmentResult.enrichmentType === 'GO'" />
                  <el-table-column prop="geneCount" label="基因数" width="100" align="center" />
                  <el-table-column prop="enrichmentRatio" label="富集倍数" width="100" align="right">
                    <template #default="{ row }">{{ row.enrichmentRatio.toFixed(2) }}x</template>
                  </el-table-column>
                  <el-table-column prop="pValue" label="P值" width="140">
                    <template #default="{ row }">{{ row.pValue.toExponential(2) }}</template>
                  </el-table-column>
                  <el-table-column prop="adjPValue" label="校正P值" width="140">
                    <template #default="{ row }">
                      <span :class="{ 'high-significance': row.adjPValue < 0.01 }">
                        {{ row.adjPValue.toExponential(2) }}
                      </span>
                    </template>
                  </el-table-column>
                </el-table>
                
                <div class="pagination-wrapper">
                  <el-pagination
                    v-model:current-page="enrichmentPage"
                    v-model:page-size="enrichmentPageSize"
                    :total="enrichmentResult.enrichmentData?.length || 0"
                    :page-sizes="[20, 50, 100]"
                    layout="total, sizes, prev, pager, next, jumper"
                  />
                </div>
              </div>
            </div>
          </div>
          
          <div v-show="activeTab === 'pip'" class="pip-section">
            <div class="chart-card full-width" v-if="resultType === 'finemapping' && finemappingResult">
              <div class="card-header">
                <h3 class="card-title">后验包含概率 (PIP) 图</h3>
              </div>
              <ManhattanPlot 
                :data="finemappingResult.manhattanData.map(d => ({ ...d, pip: d.pip }))" 
                :threshold="0.95"
                :pip-mode="true"
                height="600px"
              />
            </div>
          </div>
          
          <div v-show="activeTab === 'credible'" class="credible-section">
            <div class="chart-card full-width" v-if="resultType === 'finemapping' && finemappingResult">
              <div class="card-header">
                <h3 class="card-title">可信集合SNP列表</h3>
                <div class="credible-summary">
                  <el-tag type="success" size="large">
                    95%可信集合: {{ finemappingResult.credibleSets?.size_95 || 0 }}个SNP
                  </el-tag>
                  <el-tag type="warning" size="large" style="margin-left: 12px;">
                    99%可信集合: {{ finemappingResult.credibleSets?.size_99 || 0 }}个SNP
                  </el-tag>
                </div>
              </div>
              
              <div class="snps-table-wrapper">
                <el-table :data="finemappingResult.credibleSetTable" stripe size="default">
                  <el-table-column prop="snp" label="SNP ID" width="160" fixed="left" />
                  <el-table-column prop="pos" label="位置 (bp)" width="140" align="right">
                    <template #default="{ row }">{{ row.pos.toLocaleString() }}</template>
                  </el-table-column>
                  <el-table-column prop="pValue" label="P值" width="140">
                    <template #default="{ row }">{{ row.pValue.toExponential(2) }}</template>
                  </el-table-column>
                  <el-table-column prop="log10P" label="-log10(P)" width="110" align="right">
                    <template #default="{ row }">
                      <span class="log10p-value high">{{ row.log10P.toFixed(2) }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column prop="pip" label="PIP" width="120" align="right">
                    <template #default="{ row }">
                      <span 
                        class="pip-value"
                        :class="{ 'high-pip': row.pip >= 0.95, 'medium-pip': row.pip >= 0.5 && row.pip < 0.95 }"
                      >
                        {{ row.pip.toFixed(4) }}
                      </span>
                    </template>
                  </el-table-column>
                  <el-table-column label="95%可信集合" width="120" align="center">
                    <template #default="{ row }">
                      <el-tag v-if="row.in95CredibleSet" type="success" size="small">是</el-tag>
                      <span v-else class="text-muted">-</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="99%可信集合" width="120" align="center">
                    <template #default="{ row }">
                      <el-tag v-if="row.in99CredibleSet" type="warning" size="small">是</el-tag>
                      <span v-else class="text-muted">-</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="Lead SNP" width="100" align="center">
                    <template #default="{ row }">
                      <el-tag v-if="row.isLead" type="danger" size="small">是</el-tag>
                      <span v-else class="text-muted">-</span>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
            </div>
          </div>
          
          <div v-show="activeTab === 'ld'" class="ld-section">
            <div class="chart-card full-width">
              <div class="card-header">
                <h3 class="card-title">连锁不平衡热图 (LD Heatmap)</h3>
                <div class="card-actions">
                  <div class="region-input">
                    <el-select
                      v-model="ldRegion.chr"
                      placeholder="染色体"
                      size="small"
                      style="width: 100px"
                    >
                      <el-option
                        v-for="chr in chromosomes"
                        :key="chr"
                        :label="chr"
                        :value="chr"
                      />
                    </el-select>
                    <el-input-number
                      v-model="ldRegion.start"
                      :min="0"
                      placeholder="起始"
                      size="small"
                      style="width: 150px"
                    />
                    <span class="range-sep">-</span>
                    <el-input-number
                      v-model="ldRegion.end"
                      :min="0"
                      placeholder="终止"
                      size="small"
                      style="width: 150px"
                    />
                    <el-button 
                      type="primary" 
                      size="small" 
                      :loading="ldLoading"
                      :disabled="!ldRegion.chr || !ldRegion.end"
                      @click="calculateLDHeatmap"
                    >
                      <Play class="btn-icon" />
                      计算LD
                    </el-button>
                  </div>
                  <el-button 
                    v-if="ldResult" 
                    size="small" 
                    @click="downloadFile('manhattan')"
                  >
                    <Download class="btn-icon" />
                    下载图片
                  </el-button>
                </div>
              </div>
              
              <div v-if="!ldResult && !ldLoading" class="empty-ld">
                <Dna class="empty-icon" />
                <p class="empty-text">选择染色体区域并点击"计算LD"按钮分析连锁不平衡</p>
                <p class="empty-hint">提示：可以从曼哈顿图或SNP列表点击SNP快速定位到LD分析</p>
              </div>
              
              <LDHeatmap
                v-if="ldResult"
                :snp-names="ldResult.snpNames"
                :positions="ldResult.positions"
                :ld-matrix="ldResult.ldMatrix"
                :hap-blocks="ldResult.hapBlocks"
                height="600px"
              />
              
              <div v-if="ldLoading" class="loading-ld">
                <Loader2 class="is-loading" :size="32" style="animation: spin 1s linear infinite" />
                <span>正在计算LD矩阵...</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.warning-banner {
  display: flex;
  gap: 16px;
  padding: 20px;
  background: linear-gradient(135deg, rgba(245, 63, 63, 0.1) 0%, rgba(255, 125, 0, 0.1) 100%);
  border: 1px solid rgba(245, 63, 63, 0.3);
  border-radius: 12px;
  margin-bottom: 24px;
  animation: slideDown 0.3s ease-out;
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.warning-icon-wrapper {
  width: 48px;
  height: 48px;
  flex-shrink: 0;
  background: rgba(245, 63, 63, 0.2);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.warning-icon {
  width: 24px;
  height: 24px;
  color: #F53F3F;
}

.warning-content {
  flex: 1;
}

.warning-title {
  color: #F53F3F;
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 8px 0;
}

.warning-desc {
  color: #F8BA97;
  font-size: 14px;
  line-height: 1.6;
  margin: 0 0 12px 0;
}

.warning-details {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  padding: 12px 16px;
}

.details-title {
  color: #F8BA97;
  font-size: 13px;
  font-weight: 500;
  margin: 0 0 8px 0;
}

.info-banner {
  display: flex;
  gap: 16px;
  padding: 16px 20px;
  background: rgba(22, 93, 255, 0.1);
  border: 1px solid rgba(22, 93, 255, 0.3);
  border-radius: 12px;
  margin-bottom: 24px;
}

.info-icon-wrapper {
  width: 40px;
  height: 40px;
  flex-shrink: 0;
  background: rgba(22, 93, 255, 0.2);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.info-icon {
  width: 20px;
  height: 20px;
  color: #165DFF;
}

.info-content {
  flex: 1;
}

.info-title {
  color: #4C9AFF;
  font-size: 14px;
  font-weight: 600;
  margin: 0 0 8px 0;
}

.warning-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.warning-item {
  color: #CBD5E1;
  font-size: 13px;
  line-height: 1.8;
  padding-left: 16px;
  position: relative;
}

.warning-item::before {
  content: '•';
  position: absolute;
  left: 0;
  color: #F53F3F;
}

.info-banner .warning-item::before {
  color: #165DFF;
}

.results-page {
  max-width: 1600px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.back-btn {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: rgba(30, 41, 59, 0.8);
  border: 1px solid #334155;
  color: #94A3B8;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.back-btn:hover {
  color: #FFFFFF;
  border-color: #165DFF;
}

.back-icon {
  width: 20px;
  height: 20px;
}

.page-title {
  font-size: 28px;
  font-weight: 700;
  color: #FFFFFF;
  margin: 0 0 4px 0;
  display: flex;
  align-items: center;
  gap: 12px;
}

.status-tag {
  margin-left: 12px;
}

.page-desc {
  font-size: 14px;
  color: #94A3B8;
  margin: 0;
  font-family: 'JetBrains Mono', monospace;
}

.btn-icon {
  margin-right: 6px;
}

.menu-icon {
  width: 16px;
  height: 16px;
  margin-right: 8px;
}

.loading-state,
.empty-state {
  text-align: center;
  padding: 80px 20px;
  color: #94A3B8;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.empty-icon {
  width: 64px;
  height: 64px;
  color: #475569;
  margin-bottom: 16px;
}

.empty-title {
  font-size: 18px;
  font-weight: 600;
  color: #E2E8F0;
  margin: 0 0 8px 0;
}

.empty-desc {
  font-size: 14px;
  color: #64748B;
  margin: 0;
}

.overview-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  margin-bottom: 32px;
}

.stat-card {
  background: rgba(30, 41, 59, 0.5);
  border: 1px solid #334155;
  border-radius: 16px;
  padding: 24px;
  display: flex;
  gap: 16px;
  transition: all 0.2s ease;
}

.stat-card:hover {
  border-color: #165DFF;
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
}

.stat-icon {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-icon.primary {
  background: linear-gradient(135deg, rgba(22, 93, 255, 0.2), rgba(114, 46, 209, 0.2));
}

.stat-icon.secondary {
  background: linear-gradient(135deg, rgba(0, 180, 42, 0.2), rgba(20, 201, 201, 0.2));
}

.stat-icon.accent {
  background: linear-gradient(135deg, rgba(255, 125, 0, 0.2), rgba(245, 63, 63, 0.2));
}

.stat-icon.info {
  background: linear-gradient(135deg, rgba(100, 116, 139, 0.2), rgba(71, 85, 105, 0.2));
}

.stat-icon .icon {
  width: 28px;
  height: 28px;
}

.stat-icon.primary .icon { color: #165DFF; }
.stat-icon.secondary .icon { color: #00B42A; }
.stat-icon.accent .icon { color: #FF7D00; }
.stat-icon.info .icon { color: #64748B; }

.stat-content {
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.stat-label {
  font-size: 13px;
  color: #94A3B8;
  margin-bottom: 4px;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #FFFFFF;
  line-height: 1.2;
}

.stat-hint {
  font-size: 11px;
  color: #64748B;
  margin-top: 4px;
}

.quality-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  margin-left: 8px;
}

.tabs-section {
  background: rgba(30, 41, 59, 0.3);
  border: 1px solid #334155;
  border-radius: 16px;
  overflow: hidden;
}

.tabs-header {
  display: flex;
  gap: 4px;
  padding: 12px 16px;
  background: rgba(15, 23, 42, 0.6);
  border-bottom: 1px solid #334155;
  overflow-x: auto;
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
  white-space: nowrap;
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

.tabs-content {
  padding: 24px;
}

.overview-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  margin-bottom: 32px;
}

.chart-card {
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid #334155;
  border-radius: 12px;
  overflow: hidden;
}

.chart-card.full-width {
  grid-column: 1 / -1;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #1E293B;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: #FFFFFF;
  margin: 0;
}

.card-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.arrow-icon {
  width: 14px;
  height: 14px;
}

.top-snps-section,
.snps-table-wrapper {
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid #334155;
  border-radius: 12px;
  overflow: hidden;
}

.top-snps-section .card-header {
  padding: 16px 20px;
}

.snps-table-wrapper {
  padding: 0;
  border: none;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-icon {
  width: 16px;
  height: 16px;
  color: #64748B;
}

.p-value {
  font-family: 'JetBrains Mono', monospace;
  color: #F87171;
  font-weight: 500;
}

.log10p-value {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 600;
}

.log10p-value.high {
  color: #FED7AA;
}

.text-muted {
  color: #64748B;
}

.region-input {
  display: flex;
  align-items: center;
  gap: 8px;
}

.range-sep {
  color: #64748B;
}

.empty-ld,
.loading-ld {
  text-align: center;
  padding: 80px 20px;
}

.empty-ld .empty-icon,
.loading-ld .is-loading {
  width: 48px;
  height: 48px;
  color: #475569;
  margin-bottom: 16px;
}

.empty-text,
.loading-ld span {
  font-size: 14px;
  color: #94A3B8;
  display: block;
  margin-bottom: 8px;
}

.empty-hint {
  font-size: 12px;
  color: #64748B;
  margin: 0;
}

.pagination-wrapper {
  display: flex;
  justify-content: center;
  padding: 20px;
  border-top: 1px solid #1E293B;
}

:deep(.el-table) {
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-header-bg-color: #1E293B;
  --el-table-border-color: #334155;
  --el-table-text-color: #E2E8F0;
  --el-table-header-text-color: #94A3B8;
  --el-table-row-hover-bg-color: rgba(22, 93, 255, 0.05);
  --el-table-striped-odd-row-bg-color: rgba(15, 23, 42, 0.3);
}

:deep(.el-table th) {
  background: #1E293B;
  font-weight: 600;
}

:deep(.el-table .el-table__row:hover > td) {
  background-color: rgba(22, 93, 255, 0.05);
}

:deep(.el-pagination) {
  --el-pagination-bg-color: rgba(30, 41, 59, 0.8);
  --el-pagination-text-color: #94A3B8;
  --el-pagination-hover-text-color: #FFFFFF;
}

:deep(.el-pager li) {
  background: rgba(30, 41, 59, 0.8);
  border: 1px solid #334155;
}

:deep(.el-pager li.is-active) {
  background: linear-gradient(135deg, #165DFF, #00B42A);
  border-color: transparent;
}

@media (max-width: 1024px) {
  .overview-cards {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .overview-grid {
    grid-template-columns: 1fr;
  }
}

.cca-correlation-chart {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
}

.cca-item {
  display: flex;
  align-items: center;
  gap: 16px;
}

.cca-label {
  width: 60px;
  font-weight: 600;
  color: #E2E8F0;
}

.cca-bar {
  flex: 1;
  height: 24px;
  background: rgba(30, 41, 59, 0.8);
  border-radius: 12px;
  overflow: hidden;
}

.cca-fill {
  height: 100%;
  background: linear-gradient(90deg, #165DFF, #00B42A);
  border-radius: 12px;
  transition: width 0.5s ease;
}

.cca-value {
  width: 80px;
  font-weight: 600;
  color: #165DFF;
  text-align: right;
}

.cca-pvalue {
  width: 120px;
  color: #94A3B8;
  font-size: 12px;
}

.enrichment-bars {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
}

.enrichment-bar-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.enrichment-bar-label {
  width: 200px;
  font-size: 12px;
  color: #E2E8F0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.enrichment-bar-track {
  flex: 1;
  height: 20px;
  background: rgba(30, 41, 59, 0.8);
  border-radius: 10px;
  overflow: hidden;
}

.enrichment-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #165DFF, #00B42A);
  border-radius: 10px;
}

.enrichment-bar-value {
  width: 60px;
  font-weight: 600;
  color: #165DFF;
  text-align: right;
}

.gene-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 16px;
  max-height: 300px;
  overflow-y: auto;
}

.gene-tag {
  margin: 0;
}

.credible-snps {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
  max-height: 300px;
  overflow-y: auto;
}

.credible-snp-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  background: rgba(30, 41, 59, 0.5);
  border-radius: 8px;
  border-left: 3px solid #00B42A;
}

.credible-snp-name {
  font-weight: 600;
  color: #E2E8F0;
}

.credible-snp-pos {
  color: #94A3B8;
  font-size: 12px;
}

.credible-snp-pip {
  color: #00B42A;
  font-size: 12px;
}

.cca-results {
  padding: 20px;
}

.cca-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
  border-bottom: 2px solid #1E293B;
}

.cca-tab-btn {
  padding: 12px 20px;
  background: transparent;
  border: none;
  color: #94A3B8;
  font-weight: 500;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: all 0.2s ease;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.cca-tab-btn:hover {
  color: #E2E8F0;
}

.cca-tab-btn.active {
  color: #165DFF;
  border-bottom-color: #165DFF;
}

.cca-tab-corr {
  font-size: 11px;
  color: #94A3B8;
}

.cca-stats-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
  margin-bottom: 32px;
}

.cca-stat-card {
  background: rgba(30, 41, 59, 0.5);
  border: 1px solid #334155;
  border-radius: 12px;
  padding: 16px;
  text-align: center;
}

.cca-stat-label {
  font-size: 12px;
  color: #94A3B8;
  margin-bottom: 8px;
}

.cca-stat-value {
  font-size: 20px;
  font-weight: 700;
  color: #165DFF;
}

.cca-loadings-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}

.cca-loadings-card {
  background: rgba(30, 41, 59, 0.3);
  border-radius: 12px;
  padding: 20px;
}

.card-subtitle {
  font-size: 14px;
  font-weight: 600;
  color: #E2E8F0;
  margin: 0 0 16px 0;
}

.loadings-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 400px;
  overflow-y: auto;
}

.loading-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.loading-name {
  width: 120px;
  font-size: 12px;
  color: #E2E8F0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.loading-bar-track {
  flex: 1;
  height: 16px;
  background: rgba(30, 41, 59, 0.8);
  border-radius: 8px;
  position: relative;
  overflow: hidden;
}

.loading-bar-track::before {
  content: '';
  position: absolute;
  left: 50%;
  top: 0;
  width: 1px;
  height: 100%;
  background: #334155;
}

.loading-bar-fill {
  height: 100%;
  border-radius: 8px;
  transition: all 0.3s ease;
}

.loading-bar-fill.positive {
  background: #165DFF;
}

.loading-bar-fill.negative {
  background: #FF7D00;
}

.loading-value {
  width: 70px;
  font-size: 12px;
  color: #94A3B8;
  text-align: right;
}

.enrichment-barplot-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 20px;
  max-height: 800px;
  overflow-y: auto;
}

.enrichment-barplot-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px;
  background: rgba(30, 41, 59, 0.3);
  border-radius: 8px;
}

.enrichment-barplot-label {
  width: 300px;
  font-size: 13px;
  color: #E2E8F0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.term-id {
  color: #165DFF;
  font-weight: 600;
  margin-right: 8px;
}

.enrichment-barplot-track {
  flex: 1;
  height: 24px;
  background: rgba(30, 41, 59, 0.8);
  border-radius: 12px;
  overflow: hidden;
}

.enrichment-barplot-fill {
  height: 100%;
  border-radius: 12px;
}

.enrichment-barplot-meta {
  display: flex;
  gap: 16px;
  min-width: 300px;
  justify-content: flex-end;
}

.enrichment-barplot-meta span {
  font-size: 11px;
  color: #94A3B8;
}

.gene-count {
  color: #00B42A;
  font-weight: 600;
}

.enrichment-ratio {
  color: #FF7D00;
  font-weight: 600;
}

.adj-p {
  color: #F53F3F;
  font-weight: 600;
}

.neglogp {
  color: #165DFF;
  font-weight: 600;
}

.network-container {
  padding: 20px;
}

.network-legend {
  display: flex;
  gap: 24px;
  margin-bottom: 20px;
  justify-content: center;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #94A3B8;
  font-size: 13px;
}

.legend-dot {
  width: 16px;
  height: 16px;
  border-radius: 50%;
}

.legend-dot.term {
  background: #165DFF;
}

.legend-dot.gene {
  background: #00B42A;
}

.network-graph-placeholder {
  text-align: center;
  padding: 60px 20px;
  background: rgba(30, 41, 59, 0.3);
  border-radius: 12px;
  border: 2px dashed #334155;
}

.network-icon {
  width: 64px;
  height: 64px;
  color: #475569;
  margin-bottom: 16px;
}

.network-hint {
  font-size: 14px;
  color: #94A3B8;
  margin: 0 0 8px 0;
}

.network-stats {
  font-size: 12px;
  color: #64748B;
  margin: 0;
}

.candidate-genes-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
  padding: 20px;
  max-height: 500px;
  overflow-y: auto;
}

.candidate-gene-card {
  background: rgba(30, 41, 59, 0.5);
  border: 1px solid #334155;
  border-radius: 12px;
  padding: 16px;
  text-align: center;
  transition: all 0.2s ease;
}

.candidate-gene-card:hover {
  border-color: #165DFF;
  transform: translateY(-2px);
}

.gene-icon {
  width: 32px;
  height: 32px;
  color: #00B42A;
  margin-bottom: 8px;
}

.gene-name {
  font-weight: 600;
  color: #E2E8F0;
  display: block;
  margin-bottom: 4px;
}

.gene-snps {
  color: #64748B;
  font-size: 11px;
}

.high-significance {
  color: #00B42A;
  font-weight: 600;
}

.credible-summary {
  display: flex;
  align-items: center;
}

.pip-value {
  font-family: 'Courier New', monospace;
}

.pip-value.high-pip {
  color: #00B42A;
  font-weight: 700;
}

.pip-value.medium-pip {
  color: #FF7D00;
  font-weight: 600;
}

.enrichment-terms-table {
  border-top: 1px solid #1E293B;
  padding-top: 20px;
}
</style>
