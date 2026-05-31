<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { 
  FlaskConical, 
  Settings2, 
  Play, 
  BarChart2, 
  Layers, 
  Target,
  ChevronRight,
  Dna,
  FileText,
  Users,
  AlertCircle,
  CheckCircle2,
  GitBranch,
  Network,
  Crosshair,
  Database
} from 'lucide-vue-next';
import { useFileStore, useTaskStore } from '@/stores';
import { analysisAPI, referenceAPI, multiphenotypeAPI, enrichmentAPI, finemappingAPI, taskAPI } from '@/services/api';
import type { MaizeInbredLine, CovariateConfig, AnalysisTask } from '@/types';

const router = useRouter();
const fileStore = useFileStore();
const taskStore = useTaskStore();

const analysisType = ref<'gwas' | 'multiphenotype' | 'enrichment' | 'finemapping'>('gwas');
const selectedModel = ref<'GLM' | 'MLM'>('GLM');
const significanceThreshold = ref(5e-8);
const selectedReference = ref('B73_v5');
const pcaComponents = ref<number[]>([1, 2, 3]);
const customCovariateFileId = ref<string | undefined>(undefined);
const customCovariateNames = ref<string[]>([]);
const pcaTaskId = ref<string | null>(null);
const pcaResult = ref<any>(null);
const pcaLoading = ref(false);
const gwasLoading = ref(false);
const maizeLines = ref<MaizeInbredLine[]>([]);
const completedTasks = ref<AnalysisTask[]>([]);

const selectedPhenotypeNames = ref<string[]>([]);
const multiphenotypeMethod = ref<'MANOVA' | 'CCA'>('MANOVA');
const nComponents = ref(3);
const mafThreshold = ref(0.01);

const enrichmentType = ref<'GO' | 'KEGG'>('GO');
const enrichmentPValueThreshold = ref(0.05);
const enrichmentWindowSize = ref(50000);
const selectedResultTaskId = ref<string | undefined>(undefined);

const finemappingChr = ref<string>('1');
const finemappingStart = ref<number>(0);
const finemappingEnd = ref<number>(1000000);
const numCausalConfig = ref<number[]>([1, 2, 3]);
const priorCausal = ref(1e-4);

const analysisTypes = [
  {
    id: 'gwas',
    name: '单表型GWAS',
    description: '经典全基因组关联分析，逐个SNP分析与单一表型的关联',
    icon: FlaskConical,
  },
  {
    id: 'multiphenotype',
    name: '多表型联合分析',
    description: 'MANOVA/CCA多变量分析，同时检验多个表型的遗传关联',
    icon: GitBranch,
  },
  {
    id: 'enrichment',
    name: '基因集富集分析',
    description: 'GO/KEGG通路富集，识别显著位点相关的生物功能',
    icon: Network,
  },
  {
    id: 'finemapping',
    name: '贝叶斯精细定位',
    description: 'CAVIAR算法精细定位显著位点，识别因果变异',
    icon: Crosshair,
  },
];

const models = [
  {
    id: 'GLM',
    name: '广义线性模型',
    nameEn: 'Generalized Linear Model',
    description: '适用于样本无明显亲缘关系的群体',
    icon: BarChart2,
    features: ['计算速度快', '适合大样本', '无亲缘关系假设'],
  },
  {
    id: 'MLM',
    name: '混合线性模型',
    nameEn: 'Mixed Linear Model',
    description: '控制群体结构和亲缘关系，假阳性率低',
    icon: Layers,
    features: ['亲缘关系校正', '群体结构控制', '适合家系数据'],
  },
];

const multiphenotypeMethods = [
  {
    id: 'MANOVA',
    name: '多元方差分析',
    nameEn: 'Multivariate Analysis of Variance',
    description: '检验每个SNP与多个表型的联合显著性',
    features: ['逐个SNP检验', '多表型联合效应', '统计功效高'],
  },
  {
    id: 'CCA',
    name: '典型相关分析',
    nameEn: 'Canonical Correlation Analysis',
    description: '识别基因型矩阵与表型矩阵之间的相关模式',
    features: ['整体关联模式', '典型相关系数', '多维可视化'],
  },
];

const enrichmentTypes = [
  {
    id: 'GO',
    name: 'Gene Ontology',
    description: '基因本体富集，包括生物过程、细胞组分、分子功能',
  },
  {
    id: 'KEGG',
    name: 'KEGG Pathway',
    description: '京都基因与基因组百科全书通路富集分析',
  },
];

const thresholdOptions = [
  { value: 1e-5, label: '1e-5 (宽松)' },
  { value: 1e-6, label: '1e-6' },
  { value: 5e-8, label: '5e-8 (标准)' },
  { value: 1e-8, label: '1e-8 (严格)' },
];

const windowSizeOptions = [
  { value: 10000, label: '10 kb' },
  { value: 50000, label: '50 kb (推荐)' },
  { value: 100000, label: '100 kb' },
  { value: 200000, label: '200 kb' },
];

const canRunAnalysis = computed(() => {
  if (analysisType.value === 'gwas') {
    return fileStore.selectedVCF && 
           fileStore.selectedPhenotype && 
           fileStore.selectedPhenotypeName;
  } else if (analysisType.value === 'multiphenotype') {
    return fileStore.selectedVCF && 
           fileStore.selectedPhenotype && 
           selectedPhenotypeNames.value.length >= 2;
  } else if (analysisType.value === 'enrichment') {
    return selectedResultTaskId.value;
  } else if (analysisType.value === 'finemapping') {
    return fileStore.selectedVCF && 
           finemappingChr.value && 
           finemappingStart.value >= 0 && 
           finemappingEnd.value > finemappingStart.value;
  }
  return false;
});

const phenotypeOptions = computed(() => {
  if (!fileStore.selectedPhenotype?.phenotypeNames) return [];
  return fileStore.selectedPhenotype.phenotypeNames;
});

const chromosomeOptions = computed(() => {
  if (!fileStore.selectedVCF?.chromosomes) return [];
  return fileStore.selectedVCF.chromosomes.map(chr => ({
    value: chr,
    label: `染色体 ${chr}`,
  }));
});

const gwasTaskOptions = computed(() => {
  return completedTasks.value
    .filter(t => ['gwas_glm', 'gwas_mlm', 'multiphenotype_manova', 'multiphenotype_cca'].includes(t.taskType))
    .map(t => ({
      value: t.id,
      label: `${t.parameters.phenotypeName || '多表型分析'} - ${t.taskType} (${new Date(t.createdAt).toLocaleString()})`,
    }));
});

const selectedPCAComponents = computed({
  get: () => pcaComponents.value,
  set: (val: number[]) => {
    pcaComponents.value = val.sort((a, b) => a - b);
  },
});

const loadMaizeLines = async () => {
  try {
    maizeLines.value = await referenceAPI.getMaizeInbredLines();
  } catch (e) {
    console.error('Failed to load maize lines:', e);
  }
};

const loadCompletedTasks = async () => {
  try {
    const response = await taskAPI.listTasks(1, 100);
    completedTasks.value = response.tasks.filter((t: AnalysisTask) => t.status === 'completed');
  } catch (e) {
    console.error('Failed to load tasks:', e);
  }
};

const runPCA = async () => {
  if (!fileStore.selectedVCF) {
    ElMessage.warning('请先选择VCF文件');
    return;
  }
  
  try {
    pcaLoading.value = true;
    const response = await analysisAPI.runPCA(fileStore.selectedVCF.fileId, 10);
    pcaTaskId.value = response.taskId;
    ElMessage.success('PCA分析任务已提交');
  } catch (e) {
    console.error('PCA failed:', e);
  } finally {
    pcaLoading.value = false;
  }
};

const runGWAS = async () => {
  if (!canRunAnalysis.value) {
    ElMessage.warning('请先选择VCF文件、表型文件和表型性状');
    return;
  }
  
  try {
    gwasLoading.value = true;
    
    const covariates: CovariateConfig = {
      pcaComponents: pcaComponents.value,
      customCovariateFileId: customCovariateFileId.value,
      customCovariateNames: customCovariateNames.value,
    };
    
    const response = await analysisAPI.runGWAS({
      vcfFileId: fileStore.selectedVCF!.fileId,
      phenotypeFileId: fileStore.selectedPhenotype!.fileId,
      phenotypeName: fileStore.selectedPhenotypeName,
      model: selectedModel.value,
      covariates,
      significanceThreshold: significanceThreshold.value,
      referenceGenome: selectedReference.value,
    });
    
    taskStore.addTask({
      id: response.taskId,
      taskType: `gwas_${selectedModel.value.toLowerCase()}` as any,
      status: 'queued',
      progress: 0,
      parameters: {},
      createdAt: response.createdAt,
    });
    
    ElMessage.success(`${selectedModel.value}分析任务已提交`);
    router.push('/tasks');
  } catch (e) {
    console.error('GWAS failed:', e);
  } finally {
    gwasLoading.value = false;
  }
};

const runMultiPhenotype = async () => {
  if (!canRunAnalysis.value) {
    ElMessage.warning('请先选择VCF文件、表型文件和至少2个表型性状');
    return;
  }
  
  try {
    gwasLoading.value = true;
    
    const covariates: CovariateConfig = {
      pcaComponents: pcaComponents.value,
      customCovariateFileId: customCovariateFileId.value,
      customCovariateNames: customCovariateNames.value,
    };
    
    const apiMethod = multiphenotypeMethod.value === 'MANOVA' 
      ? multiphenotypeAPI.runMANOVA 
      : multiphenotypeAPI.runCCA;
    
    const response = await apiMethod({
      vcfFileId: fileStore.selectedVCF!.fileId,
      phenotypeFileId: fileStore.selectedPhenotype!.fileId,
      phenotypeNames: selectedPhenotypeNames.value,
      method: multiphenotypeMethod.value,
      covariates,
      significanceThreshold: significanceThreshold.value,
      nComponents: nComponents.value,
      mafThreshold: mafThreshold.value,
      referenceGenome: selectedReference.value,
    });
    
    taskStore.addTask({
      id: response.taskId,
      taskType: `multiphenotype_${multiphenotypeMethod.value.toLowerCase()}` as any,
      status: 'queued',
      progress: 0,
      parameters: {},
      createdAt: response.createdAt,
    });
    
    ElMessage.success(`${multiphenotypeMethod.value}多表型联合分析任务已提交`);
    router.push('/tasks');
  } catch (e) {
    console.error('Multi-phenotype analysis failed:', e);
  } finally {
    gwasLoading.value = false;
  }
};

const runEnrichment = async () => {
  if (!canRunAnalysis.value) {
    ElMessage.warning('请先选择要分析的GWAS结果任务');
    return;
  }
  
  try {
    gwasLoading.value = true;
    
    const apiMethod = enrichmentType.value === 'GO' 
      ? enrichmentAPI.runGO 
      : enrichmentAPI.runKEGG;
    
    const response = await apiMethod({
      resultTaskId: selectedResultTaskId.value!,
      enrichmentType: enrichmentType.value,
      pValueThreshold: enrichmentPValueThreshold.value,
      windowSize: enrichmentWindowSize.value,
      referenceGenome: selectedReference.value,
    });
    
    taskStore.addTask({
      id: response.taskId,
      taskType: `enrichment_${enrichmentType.value.toLowerCase()}` as any,
      status: 'queued',
      progress: 0,
      parameters: {},
      createdAt: response.createdAt,
    });
    
    ElMessage.success(`${enrichmentType.value}富集分析任务已提交`);
    router.push('/tasks');
  } catch (e) {
    console.error('Enrichment analysis failed:', e);
  } finally {
    gwasLoading.value = false;
  }
};

const runFineMapping = async () => {
  if (!canRunAnalysis.value) {
    ElMessage.warning('请选择VCF文件并指定有效的基因组区域');
    return;
  }
  
  try {
    gwasLoading.value = true;
    
    const response = await finemappingAPI.run({
      vcfFileId: fileStore.selectedVCF!.fileId,
      chr: finemappingChr.value,
      start: finemappingStart.value,
      end: finemappingEnd.value,
      numCausalConfig: numCausalConfig.value,
      priorCausal: priorCausal.value,
      referenceGenome: selectedReference.value,
    });
    
    taskStore.addTask({
      id: response.taskId,
      taskType: 'finemapping' as any,
      status: 'queued',
      progress: 0,
      parameters: {},
      createdAt: response.createdAt,
    });
    
    ElMessage.success('贝叶斯精细定位任务已提交');
    router.push('/tasks');
  } catch (e) {
    console.error('Fine-mapping failed:', e);
  } finally {
    gwasLoading.value = false;
  }
};

const startAnalysis = () => {
  if (analysisType.value === 'gwas') {
    runGWAS();
  } else if (analysisType.value === 'multiphenotype') {
    runMultiPhenotype();
  } else if (analysisType.value === 'enrichment') {
    runEnrichment();
  } else if (analysisType.value === 'finemapping') {
    runFineMapping();
  }
};

const handleCustomCovariateChange = () => {
  if (customCovariateFileId.value) {
    const covFile = fileStore.covariateFiles.find(f => f.fileId === customCovariateFileId.value);
    if (covFile?.metadata?.covariate_names) {
      customCovariateNames.value = [];
    }
  } else {
    customCovariateNames.value = [];
  }
};

const pcaOptions = computed(() => {
  if (!pcaResult.value?.explainedVarianceRatio) return [];
  return pcaResult.value.explainedVarianceRatio.map((ratio: number, index: number) => ({
    value: index + 1,
    label: `PC${index + 1} (${(ratio * 100).toFixed(1)}%)`,
  }));
});

watch(customCovariateFileId, handleCustomCovariateChange);
watch(fileStore.selectedPhenotype, () => {
  selectedPhenotypeNames.value = [];
});
watch(analysisType, () => {
  if (analysisType.value === 'enrichment') {
    loadCompletedTasks();
  }
});

onMounted(() => {
  loadMaizeLines();
});
</script>

<template>
  <div class="analysis-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">分析配置</h2>
        <p class="page-desc">选择分析类型，配置参数，运行遗传分析</p>
      </div>
      <div class="header-actions">
        <el-button 
          type="primary" 
          size="large"
          :loading="gwasLoading"
          :disabled="!canRunAnalysis"
          @click="startAnalysis"
        >
          <Play class="btn-icon" />
          开始分析
        </el-button>
      </div>
    </div>
    
    <div class="config-section">
      <div class="section-header">
        <div class="section-icon">
          <Settings2 class="icon" />
        </div>
        <div>
          <h3 class="section-title">选择分析类型</h3>
          <p class="section-desc">根据您的研究目标选择合适的分析方法</p>
        </div>
      </div>
      
      <div class="analysis-type-cards">
        <div
          v-for="atype in analysisTypes"
          :key="atype.id"
          :class="['analysis-type-card', { selected: analysisType === atype.id }]"
          @click="analysisType = atype.id as any"
        >
          <div class="analysis-type-icon">
            <component :is="atype.icon" class="icon" />
          </div>
          <h4 class="analysis-type-name">{{ atype.name }}</h4>
          <p class="analysis-type-desc">{{ atype.description }}</p>
          <div v-if="analysisType === atype.id" class="selected-indicator">
            <CheckCircle2 class="selected-icon" />
            已选择
          </div>
        </div>
      </div>
    </div>
    
    <div class="config-steps" v-if="analysisType !== 'enrichment'">
      <div class="step-item" :class="{ active: canRunAnalysis }">
        <div class="step-number">1</div>
        <div class="step-content">
          <h3 class="step-title">数据选择</h3>
          <div class="selected-files">
            <div class="file-preview" :class="{ selected: fileStore.selectedVCF }">
              <Dna class="file-icon" />
              <div class="file-info">
                <span class="file-label">基因型数据</span>
                <span class="file-name">
                  {{ fileStore.selectedVCF?.fileName || '未选择VCF文件' }}
                </span>
              </div>
              <CheckCircle2 v-if="fileStore.selectedVCF" class="check-icon" />
            </div>
            
            <template v-if="analysisType !== 'finemapping'">
              <ChevronRight class="arrow-icon" />
              
              <div class="file-preview" :class="{ selected: fileStore.selectedPhenotype }">
                <FileText class="file-icon" />
                <div class="file-info">
                  <span class="file-label">表型数据</span>
                  <span class="file-name">
                    {{ fileStore.selectedPhenotype?.fileName || '未选择表型文件' }}
                  </span>
                </div>
                <CheckCircle2 v-if="fileStore.selectedPhenotype" class="check-icon" />
              </div>
              
              <ChevronRight class="arrow-icon" />
              
              <div class="file-preview" :class="{ selected: (analysisType === 'gwas' && fileStore.selectedPhenotypeName) || (analysisType === 'multiphenotype' && selectedPhenotypeNames.length >= 2) }">
                <Target class="file-icon" />
                <div class="file-info">
                  <span class="file-label">{{ analysisType === 'multiphenotype' ? '目标表型' : '目标性状' }}</span>
                  <span class="file-name">
                    <template v-if="analysisType === 'gwas'">
                      {{ fileStore.selectedPhenotypeName || '请选择题型性状' }}
                    </template>
                    <template v-else-if="analysisType === 'multiphenotype'">
                      {{ selectedPhenotypeNames.length >= 2 ? `已选${selectedPhenotypeNames.length}个性状` : '请选择至少2个性状' }}
                    </template>
                  </span>
                </div>
                <CheckCircle2 v-if="(analysisType === 'gwas' && fileStore.selectedPhenotypeName) || (analysisType === 'multiphenotype' && selectedPhenotypeNames.length >= 2)" class="check-icon" />
              </div>
            </template>
          </div>
        </div>
      </div>
    </div>
    
    <div v-if="analysisType === 'gwas'" class="config-section">
      <div class="section-header">
        <div class="section-icon">
          <Settings2 class="icon" />
        </div>
        <div>
          <h3 class="section-title">选择分析模型</h3>
          <p class="section-desc">根据您的群体结构选择合适的统计模型</p>
        </div>
      </div>
      
      <div class="model-cards">
        <div
          v-for="model in models"
          :key="model.id"
          :class="['model-card', { selected: selectedModel === model.id }]"
          @click="selectedModel = model.id as 'GLM' | 'MLM'"
        >
          <div class="model-header">
            <div class="model-icon-wrapper">
              <component :is="model.icon" class="model-icon" />
            </div>
            <div class="model-badge">{{ model.id }}</div>
          </div>
          
          <h4 class="model-name">{{ model.name }}</h4>
          <p class="model-name-en">{{ model.nameEn }}</p>
          <p class="model-desc">{{ model.description }}</p>
          
          <ul class="model-features">
            <li v-for="feature in model.features" :key="feature">
              <CheckCircle2 class="feature-icon" />
              {{ feature }}
            </li>
          </ul>
          
          <div v-if="selectedModel === model.id" class="selected-indicator">
            <CheckCircle2 class="selected-icon" />
            已选择
          </div>
        </div>
      </div>
    </div>
    
    <div v-if="analysisType === 'multiphenotype'" class="config-section">
      <div class="section-header">
        <div class="section-icon">
          <GitBranch class="icon" />
        </div>
        <div>
          <h3 class="section-title">多表型分析方法</h3>
          <p class="section-desc">选择多表型联合分析的统计方法</p>
        </div>
      </div>
      
      <div class="model-cards">
        <div
          v-for="method in multiphenotypeMethods"
          :key="method.id"
          :class="['model-card', { selected: multiphenotypeMethod === method.id }]"
          @click="multiphenotypeMethod = method.id as 'MANOVA' | 'CCA'"
        >
          <div class="model-header">
            <div class="model-icon-wrapper">
              <GitBranch class="model-icon" />
            </div>
            <div class="model-badge">{{ method.id }}</div>
          </div>
          
          <h4 class="model-name">{{ method.name }}</h4>
          <p class="model-name-en">{{ method.nameEn }}</p>
          <p class="model-desc">{{ method.description }}</p>
          
          <ul class="model-features">
            <li v-for="feature in method.features" :key="feature">
              <CheckCircle2 class="feature-icon" />
              {{ feature }}
            </li>
          </ul>
          
          <div v-if="multiphenotypeMethod === method.id" class="selected-indicator">
            <CheckCircle2 class="selected-icon" />
            已选择
          </div>
        </div>
      </div>
    </div>
    
    <div v-if="analysisType === 'multiphenotype' && phenotypeOptions.length > 0" class="config-section">
      <div class="section-header">
        <div class="section-icon">
          <Target class="icon" />
        </div>
        <div>
          <h3 class="section-title">选择表型性状</h3>
          <p class="section-desc">请选择至少2个表型性状进行联合分析</p>
        </div>
      </div>
      
      <div class="phenotype-checkboxes">
        <el-checkbox-group v-model="selectedPhenotypeNames">
          <el-checkbox
            v-for="phenotype in phenotypeOptions"
            :key="phenotype"
            :label="phenotype"
            size="large"
          >
            {{ phenotype }}
          </el-checkbox>
        </el-checkbox-group>
      </div>
      
      <div class="config-hint" style="margin-top: 12px;">
        已选择 <strong>{{ selectedPhenotypeNames.length }}</strong> 个性状，需选择至少2个
      </div>
    </div>
    
    <div v-if="analysisType === 'enrichment'" class="config-section">
      <div class="section-header">
        <div class="section-icon">
          <Network class="icon" />
        </div>
        <div>
          <h3 class="section-title">富集分析配置</h3>
          <p class="section-desc">选择要分析的GWAS结果和富集分析类型</p>
        </div>
      </div>
      
      <div class="model-cards">
        <div
          v-for="etype in enrichmentTypes"
          :key="etype.id"
          :class="['model-card', { selected: enrichmentType === etype.id }]"
          @click="enrichmentType = etype.id as 'GO' | 'KEGG'"
        >
          <div class="model-header">
            <div class="model-icon-wrapper">
              <Database class="model-icon" />
            </div>
            <div class="model-badge">{{ etype.id }}</div>
          </div>
          
          <h4 class="model-name">{{ etype.name }}</h4>
          <p class="model-desc">{{ etype.description }}</p>
          
          <div v-if="enrichmentType === etype.id" class="selected-indicator">
            <CheckCircle2 class="selected-icon" />
            已选择
          </div>
        </div>
      </div>
      
      <div class="param-config">
        <div class="config-item">
          <div class="config-label">
            <label>选择GWAS分析结果</label>
            <span class="config-hint">选择已完成的GWAS或多表型分析任务</span>
          </div>
          <div class="config-control">
            <el-select
              v-model="selectedResultTaskId"
              placeholder="选择分析任务"
              size="large"
              style="width: 500px"
            >
              <el-option
                v-for="option in gwasTaskOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </div>
        </div>
        
        <div class="config-item">
          <div class="config-label">
            <label>基因窗口大小</label>
            <span class="config-hint">SNP上下游窗口大小用于定位候选基因</span>
          </div>
          <div class="config-control">
            <el-radio-group v-model="enrichmentWindowSize" size="large">
              <el-radio-button
                v-for="option in windowSizeOptions"
                :key="option.value"
                :value="option.value"
              >
                {{ option.label }}
              </el-radio-button>
            </el-radio-group>
          </div>
        </div>
        
        <div class="config-item">
          <div class="config-label">
            <label>显著性阈值</label>
            <span class="config-hint">富集分析的P值阈值，经过BH-FDR校正</span>
          </div>
          <div class="config-control">
            <el-select v-model="enrichmentPValueThreshold" size="large" style="width: 200px">
              <el-option :value="0.01" label="0.01" />
              <el-option :value="0.05" label="0.05 (推荐)" />
              <el-option :value="0.1" label="0.1" />
            </el-select>
          </div>
        </div>
      </div>
    </div>
    
    <div v-if="analysisType === 'finemapping'" class="config-section">
      <div class="section-header">
        <div class="section-icon">
          <Crosshair class="icon" />
        </div>
        <div>
          <h3 class="section-title">精细定位区域配置</h3>
          <p class="section-desc">指定要进行精细定位的基因组区域</p>
        </div>
      </div>
      
      <div class="param-config">
        <div class="config-item">
          <div class="config-label">
            <label>染色体</label>
            <span class="config-hint">选择目标染色体</span>
          </div>
          <div class="config-control">
            <el-select
              v-model="finemappingChr"
              placeholder="选择染色体"
              size="large"
              style="width: 200px"
            >
              <el-option
                v-for="option in chromosomeOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </div>
        </div>
        
        <div class="config-item">
          <div class="config-label">
            <label>区域范围 (bp)</label>
            <span class="config-hint">输入起始和终止位置，建议100kb-2Mb</span>
          </div>
          <div class="config-control">
            <el-input-number
              v-model="finemappingStart"
              :min="0"
              :step="10000"
              size="large"
              style="width: 200px; margin-right: 16px;"
            />
            <span style="color: #94A3B8; margin: 0 8px;">至</span>
            <el-input-number
              v-model="finemappingEnd"
              :min="finemappingStart + 1000"
              :step="10000"
              size="large"
              style="width: 200px;"
            />
            <span style="margin-left: 16px; color: #94A3B8;">
              {{ finemappingEnd > finemappingStart ? `区域大小: ${((finemappingEnd - finemappingStart) / 1e6).toFixed(2)} Mb` : '' }}
            </span>
          </div>
        </div>
        
        <div class="config-item">
          <div class="config-label">
            <label>因果变异数配置</label>
            <span class="config-hint">CAVIAR算法考虑的因果变异数量</span>
          </div>
          <div class="config-control">
            <el-checkbox-group v-model="numCausalConfig">
              <el-checkbox :label="1" size="large">1个</el-checkbox>
              <el-checkbox :label="2" size="large">2个</el-checkbox>
              <el-checkbox :label="3" size="large">3个</el-checkbox>
              <el-checkbox :label="4" size="large">4个</el-checkbox>
              <el-checkbox :label="5" size="large">5个</el-checkbox>
            </el-checkbox-group>
          </div>
        </div>
        
        <div class="config-item">
          <div class="config-label">
            <label>先验因果概率</label>
            <span class="config-hint">每个SNP成为因果变异的先验概率</span>
          </div>
          <div class="config-control">
            <el-select v-model="priorCausal" size="large" style="width: 200px">
              <el-option :value="1e-5" label="1e-5" />
              <el-option :value="1e-4" label="1e-4 (推荐)" />
              <el-option :value="1e-3" label="1e-3" />
            </el-select>
          </div>
        </div>
      </div>
    </div>
    
    <div v-if="analysisType !== 'enrichment'" class="config-grid">
      <div class="config-section">
        <div class="section-header">
          <div class="section-icon">
            <Users class="icon" />
          </div>
          <div>
            <h3 class="section-title">协变量校正</h3>
            <p class="section-desc">添加协变量以控制群体结构和其他混杂因素</p>
          </div>
        </div>
        
        <div class="covariate-config">
          <div class="config-item">
            <div class="config-label">
              <label>PCA主成分</label>
              <span class="config-hint">选择用于校正群体结构的主成分</span>
            </div>
            <div class="config-control">
              <el-button 
                size="small" 
                @click="runPCA" 
                :loading="pcaLoading"
                :disabled="!fileStore.selectedVCF"
              >
                计算PCA
              </el-button>
            </div>
          </div>
          
          <div v-if="pcaOptions.length > 0" class="config-item">
            <div class="config-label">
              <label>选择主成分</label>
              <span class="config-hint">建议选择方差解释率累计达到80%的主成分</span>
            </div>
            <div class="config-control">
              <el-checkbox-group v-model="selectedPCAComponents">
                <el-checkbox
                  v-for="option in pcaOptions"
                  :key="option.value"
                  :label="option.value"
                  size="large"
                >
                  {{ option.label }}
                </el-checkbox>
              </el-checkbox-group>
            </div>
          </div>
          
          <div class="config-item">
            <div class="config-label">
              <label>自定义协变量文件</label>
              <span class="config-hint">包含其他需要校正的协变量（如性别、环境等）</span>
            </div>
            <div class="config-control">
              <el-select
                v-model="customCovariateFileId"
                placeholder="选择协变量文件"
                style="width: 300px"
                clearable
              >
                <el-option
                  v-for="file in fileStore.covariateFiles"
                  :key="file.fileId"
                  :label="file.fileName"
                  :value="file.fileId"
                />
              </el-select>
            </div>
          </div>
          
          <div v-if="customCovariateFileId && fileStore.covariateFiles.length > 0" class="config-item">
            <div class="config-label">
              <label>选择协变量</label>
              <span class="config-hint">选择需要纳入模型的协变量</span>
            </div>
            <div class="config-control">
              <el-checkbox-group v-model="customCovariateNames">
                <el-checkbox
                  v-for="name in (fileStore.covariateFiles.find(f => f.fileId === customCovariateFileId)?.metadata?.covariate_names || [])"
                  :key="name"
                  :label="name"
                  size="large"
                >
                  {{ name }}
                </el-checkbox>
              </el-checkbox-group>
            </div>
          </div>
        </div>
      </div>
      
      <div class="config-section">
        <div class="section-header">
          <div class="section-icon">
            <Target class="icon" />
          </div>
          <div>
            <h3 class="section-title">分析参数</h3>
            <p class="section-desc">设置显著性阈值和参考基因组版本</p>
          </div>
        </div>
        
        <div class="param-config">
          <div v-if="analysisType === 'gwas' || analysisType === 'multiphenotype'" class="config-item">
            <div class="config-label">
              <label>显著性阈值</label>
              <span class="config-hint">全基因组显著水平，推荐使用5e-8</span>
            </div>
            <div class="config-control">
              <el-radio-group v-model="significanceThreshold" size="large">
                <el-radio-button
                  v-for="option in thresholdOptions"
                  :key="option.value"
                  :value="option.value"
                >
                  {{ option.label }}
                </el-radio-button>
              </el-radio-group>
            </div>
          </div>
          
          <div v-if="analysisType === 'multiphenotype' && multiphenotypeMethod === 'CCA'" class="config-item">
            <div class="config-label">
              <label>CCA成分数</label>
              <span class="config-hint">典型相关分析提取的最大成分数</span>
            </div>
            <div class="config-control">
              <el-input-number
                v-model="nComponents"
                :min="1"
                :max="10"
                size="large"
              />
            </div>
          </div>
          
          <div v-if="analysisType === 'multiphenotype'" class="config-item">
            <div class="config-label">
              <label>MAF过滤阈值</label>
              <span class="config-hint">最小等位基因频率，过滤稀有变异</span>
            </div>
            <div class="config-control">
              <el-select v-model="mafThreshold" size="large" style="width: 200px">
                <el-option :value="0.05" label="0.05" />
                <el-option :value="0.01" label="0.01 (推荐)" />
                <el-option :value="0.001" label="0.001" />
              </el-select>
            </div>
          </div>
          
          <div class="config-item">
            <div class="config-label">
              <label>参考基因组</label>
              <span class="config-hint">选择用于SNP注释的玉米自交系参考基因组</span>
            </div>
            <div class="config-control">
              <el-select v-model="selectedReference" size="large" style="width: 350px">
                <el-option
                  v-for="line in maizeLines"
                  :key="line.id"
                  :label="`${line.name} (${line.version}) - ${line.description}`"
                  :value="line.id"
                >
                  <div class="genome-option">
                    <span class="genome-name">{{ line.name }}</span>
                    <span class="genome-version">{{ line.version }}</span>
                    <span class="genome-size">{{ line.genomeSize }}</span>
                  </div>
                </el-option>
              </el-select>
            </div>
          </div>
        </div>
        
        <div class="genome-info" v-if="maizeLines.length > 0">
          <h4 class="info-title">玉米自交系参考基因组</h4>
          <div class="genome-cards">
            <div
              v-for="line in maizeLines"
              :key="line.id"
              :class="['genome-card', { active: selectedReference === line.id }]"
              @click="selectedReference = line.id"
            >
              <div class="genome-header">
                <Dna class="genome-icon" />
                <span class="genome-badge">{{ line.version }}</span>
              </div>
              <h5 class="genome-name">{{ line.name }}</h5>
              <p class="genome-desc">{{ line.description }}</p>
              <div class="genome-stats">
                <span>{{ line.chromosomeCount }}条染色体</span>
                <span>{{ line.genomeSize }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <div v-if="!canRunAnalysis" class="warning-banner">
      <AlertCircle class="warning-icon" />
      <p class="warning-text">
        <template v-if="analysisType === 'gwas'">
          请先在<a href="/upload" class="link">数据上传</a>页面选择VCF文件、表型文件和目标性状
        </template>
        <template v-else-if="analysisType === 'multiphenotype'">
          请选择VCF文件、表型文件和至少2个表型性状
        </template>
        <template v-else-if="analysisType === 'enrichment'">
          请选择要分析的GWAS分析结果任务
        </template>
        <template v-else-if="analysisType === 'finemapping'">
          请选择VCF文件并指定有效的基因组区域
        </template>
      </p>
    </div>
  </div>
</template>

<style scoped>
.analysis-page {
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

.config-steps {
  margin-bottom: 32px;
}

.step-item {
  background: rgba(30, 41, 59, 0.5);
  border: 1px solid #334155;
  border-radius: 16px;
  padding: 24px;
  display: flex;
  gap: 20px;
}

.step-item.active {
  border-color: #00B42A;
  background: rgba(0, 180, 42, 0.05);
}

.step-number {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, #165DFF, #00B42A);
  color: white;
  font-size: 18px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.step-content {
  flex: 1;
}

.step-title {
  font-size: 16px;
  font-weight: 600;
  color: #FFFFFF;
  margin: 0 0 16px 0;
}

.selected-files {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.file-preview {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 18px;
  background: rgba(15, 23, 42, 0.6);
  border: 2px solid #334155;
  border-radius: 12px;
  min-width: 220px;
}

.file-preview.selected {
  border-color: #00B42A;
  background: rgba(0, 180, 42, 0.08);
}

.file-icon {
  width: 24px;
  height: 24px;
  color: #165DFF;
  flex-shrink: 0;
}

.file-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.file-label {
  font-size: 11px;
  color: #64748B;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.file-name {
  font-size: 13px;
  font-weight: 500;
  color: #E2E8F0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 180px;
}

.check-icon {
  width: 20px;
  height: 20px;
  color: #00B42A;
  flex-shrink: 0;
}

.arrow-icon {
  width: 20px;
  height: 20px;
  color: #475569;
}

.config-section {
  background: rgba(30, 41, 59, 0.5);
  border: 1px solid #334155;
  border-radius: 16px;
  padding: 28px;
  margin-bottom: 24px;
}

.section-header {
  display: flex;
  gap: 16px;
  margin-bottom: 28px;
}

.section-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(22, 93, 255, 0.15), rgba(0, 180, 42, 0.15));
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.section-icon .icon {
  width: 24px;
  height: 24px;
  color: #165DFF;
}

.section-title {
  font-size: 20px;
  font-weight: 600;
  color: #FFFFFF;
  margin: 0 0 4px 0;
}

.section-desc {
  font-size: 14px;
  color: #94A3B8;
  margin: 0;
}

.model-cards {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

.model-card {
  position: relative;
  background: rgba(15, 23, 42, 0.6);
  border: 2px solid #334155;
  border-radius: 16px;
  padding: 28px;
  cursor: pointer;
  transition: all 0.3s ease;
  overflow: hidden;
}

.model-card::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(22, 93, 255, 0.1), transparent);
  opacity: 0;
  transition: opacity 0.3s ease;
}

.model-card:hover {
  border-color: #165DFF;
  transform: translateY(-4px);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.3);
}

.model-card:hover::before {
  opacity: 1;
}

.model-card.selected {
  border-color: #165DFF;
  background: linear-gradient(135deg, rgba(22, 93, 255, 0.08), rgba(0, 180, 42, 0.05));
  box-shadow: 0 0 0 3px rgba(22, 93, 255, 0.2);
}

.model-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.model-icon-wrapper {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  background: linear-gradient(135deg, #165DFF, #00B42A);
  display: flex;
  align-items: center;
  justify-content: center;
}

.model-icon {
  width: 28px;
  height: 28px;
  color: white;
}

.model-badge {
  padding: 6px 12px;
  background: rgba(22, 93, 255, 0.2);
  color: #165DFF;
  font-size: 12px;
  font-weight: 700;
  border-radius: 6px;
  letter-spacing: 0.5px;
}

.model-name {
  font-size: 20px;
  font-weight: 700;
  color: #FFFFFF;
  margin: 0 0 4px 0;
}

.model-name-en {
  font-size: 12px;
  color: #64748B;
  margin: 0 0 12px 0;
  font-style: italic;
}

.model-desc {
  font-size: 14px;
  color: #94A3B8;
  margin: 0 0 20px 0;
  line-height: 1.6;
}

.model-features {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.model-features li {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #E2E8F0;
}

.feature-icon {
  width: 16px;
  height: 16px;
  color: #00B42A;
  flex-shrink: 0;
}

.selected-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid rgba(22, 93, 255, 0.3);
  color: #165DFF;
  font-size: 13px;
  font-weight: 600;
}

.selected-icon {
  width: 16px;
  height: 16px;
}

.config-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}

.config-item {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  padding: 20px 0;
  border-bottom: 1px solid #1E293B;
}

.config-item:last-child {
  border-bottom: none;
}

.config-label {
  flex-shrink: 0;
  max-width: 280px;
}

.config-label label {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: #FFFFFF;
  margin-bottom: 4px;
}

.config-hint {
  font-size: 12px;
  color: #64748B;
  line-height: 1.5;
}

.config-control {
  flex: 1;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

:deep(.el-radio-button__inner) {
  background: rgba(30, 41, 59, 0.8);
  border-color: #334155;
  color: #94A3B8;
}

:deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) {
  background: linear-gradient(135deg, #165DFF, #00B42A);
  border-color: transparent;
  color: white;
}

.genome-option {
  display: flex;
  align-items: center;
  gap: 12px;
}

.genome-option .genome-name {
  font-weight: 600;
  color: #FFFFFF;
}

.genome-option .genome-version {
  font-size: 12px;
  color: #165DFF;
  background: rgba(22, 93, 255, 0.1);
  padding: 2px 8px;
  border-radius: 4px;
}

.genome-option .genome-size {
  font-size: 12px;
  color: #64748B;
}

.info-title {
  font-size: 14px;
  font-weight: 600;
  color: #94A3B8;
  margin: 24px 0 16px 0;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.genome-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.genome-card {
  background: rgba(15, 23, 42, 0.6);
  border: 2px solid #334155;
  border-radius: 12px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.genome-card:hover {
  border-color: #165DFF;
}

.genome-card.active {
  border-color: #00B42A;
  background: rgba(0, 180, 42, 0.08);
}

.genome-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.genome-icon {
  width: 20px;
  height: 20px;
  color: #165DFF;
}

.genome-badge {
  font-size: 10px;
  font-weight: 600;
  color: #64748B;
  background: rgba(100, 116, 139, 0.2);
  padding: 2px 6px;
  border-radius: 4px;
}

.genome-card .genome-name {
  font-size: 16px;
  font-weight: 600;
  color: #FFFFFF;
  margin: 0 0 6px 0;
}

.genome-desc {
  font-size: 11px;
  color: #64748B;
  margin: 0 0 12px 0;
  line-height: 1.4;
  min-height: 30px;
}

.genome-stats {
  display: flex;
  gap: 8px;
  font-size: 10px;
  color: #94A3B8;
}

.genome-stats span {
  background: rgba(30, 41, 59, 0.8);
  padding: 2px 6px;
  border-radius: 4px;
}

.warning-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 24px;
  background: rgba(255, 125, 0, 0.1);
  border: 1px solid rgba(255, 125, 0, 0.3);
  border-radius: 12px;
  margin-top: 24px;
}

.warning-icon {
  width: 24px;
  height: 24px;
  color: #FF7D00;
  flex-shrink: 0;
}

.warning-text {
  font-size: 14px;
  color: #FED7AA;
  margin: 0;
}

.warning-text .link {
  color: #FF7D00;
  text-decoration: underline;
  font-weight: 500;
}

.analysis-type-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  margin-top: 20px;
}

.analysis-type-card {
  background: rgba(30, 41, 59, 0.5);
  border: 2px solid #334155;
  border-radius: 16px;
  padding: 24px;
  cursor: pointer;
  transition: all 0.3s ease;
  position: relative;
}

.analysis-type-card:hover {
  border-color: #165DFF;
  transform: translateY(-2px);
}

.analysis-type-card.selected {
  border-color: #165DFF;
  background: rgba(22, 93, 255, 0.1);
}

.analysis-type-icon {
  width: 48px;
  height: 48px;
  background: linear-gradient(135deg, rgba(22, 93, 255, 0.2), rgba(0, 180, 42, 0.2));
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.analysis-type-icon .icon {
  width: 28px;
  height: 28px;
  color: #165DFF;
}

.analysis-type-name {
  font-size: 16px;
  font-weight: 600;
  color: #FFFFFF;
  margin: 0 0 8px 0;
}

.analysis-type-desc {
  font-size: 13px;
  color: #94A3B8;
  margin: 0;
  line-height: 1.6;
}

.phenotype-checkboxes {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  padding: 16px;
  background: rgba(15, 23, 42, 0.5);
  border-radius: 12px;
  margin-top: 16px;
}

.phenotype-checkboxes :deep(.el-checkbox) {
  margin-right: 16px;
  margin-bottom: 8px;
}

@media (max-width: 1024px) {
  .analysis-type-cards {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .config-grid {
    grid-template-columns: 1fr;
  }
  
  .model-cards {
    grid-template-columns: 1fr;
  }
  
  .selected-files {
    flex-direction: column;
    align-items: stretch;
  }
  
  .arrow-icon {
    transform: rotate(90deg);
    align-self: center;
  }
  
  .config-item {
    flex-direction: column;
    gap: 12px;
  }
}

@media (max-width: 768px) {
  .analysis-type-cards {
    grid-template-columns: 1fr;
  }
}
</style>
