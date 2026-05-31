export interface User {
  id: string;
  email: string;
  name: string;
  createdAt: string;
  lastLogin?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  name: string;
}

export interface AuthResponse {
  access_token: string;
  user: User;
}

export interface UploadFile {
  fileId: string;
  fileName: string;
  fileType: 'vcf' | 'phenotype' | 'covariate';
  fileSize: number;
  sampleCount?: number;
  variantCount?: number;
  phenotypeNames?: string[];
  covariateNames?: string[];
  chromosomes?: string[];
  uploadTime: string;
  metadata?: Record<string, any>;
}

export interface FilePreview {
  fileId: string;
  fileType: string;
  preview: {
    headers: string[];
    rows: any[][];
  };
}

export interface SampleMatchResult {
  matchedSamples: string[];
  vcfOnlySamples: string[];
  phenotypeOnlySamples: string[];
  matchCount: number;
  vcfTotal: number;
  phenotypeTotal: number;
}

export interface PCAData {
  sampleId: string;
  PC1: number;
  PC2: number;
  PC3: number;
  [key: string]: number | string;
}

export interface PCAResult {
  taskId: string;
  explainedVarianceRatio: number[];
  pcData: PCAData[];
}

export interface CovariateConfig {
  pcaComponents: number[];
  customCovariateFileId?: string;
  customCovariateNames: string[];
}

export interface GWASRequest {
  vcfFileId: string;
  phenotypeFileId: string;
  phenotypeName: string;
  model: 'GLM' | 'MLM';
  covariates: CovariateConfig;
  significanceThreshold: number;
  referenceGenome: string;
}

export interface GWASResponse {
  taskId: string;
  status: TaskStatus;
  model?: string;
  createdAt: string;
}

export type TaskStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';

export type TaskType = 'pca' | 'gwas_glm' | 'gwas_mlm' | 'ld_heatmap' | 
  'multiphenotype_manova' | 'multiphenotype_cca' | 
  'enrichment_go' | 'enrichment_kegg' | 'finemapping';

export interface AnalysisTask {
  id: string;
  taskType: TaskType;
  status: TaskStatus;
  progress: number;
  currentStage?: string;
  errorMessage?: string;
  parameters: Record<string, any>;
  createdAt: string;
  startedAt?: string;
  completedAt?: string;
}

export interface TaskListResponse {
  total: number;
  page: number;
  pageSize: number;
  tasks: AnalysisTask[];
}

export interface TaskStats {
  total: number;
  queued: number;
  running: number;
  completed: number;
  failed: number;
  cancelled: number;
}

export interface ManhattanPoint {
  chr: string;
  pos: number;
  snp: string;
  pValue: number;
  log10P: number;
  maf?: number;
  effectSize?: number;
  pip?: number;
}

export interface QQPoint {
  expected: number;
  observed: number;
}

export interface SignificantSNP {
  id: string;
  snp: string;
  chr: string;
  pos: number;
  ref: string;
  alt: string;
  pValue: number;
  log10P: number;
  effectSize?: number;
  maf?: number;
  gene?: string;
  annotation?: string;
}

export interface SNPListResponse {
  total: number;
  page: number;
  pageSize: number;
  snps: SignificantSNP[];
}

export interface GWASResult {
  taskId: string;
  model: string;
  phenotype: string;
  inflationFactor: number;
  significantSNPCount: number;
  manhattanData: ManhattanPoint[];
  qqData: QQPoint[];
  significantSNPs: SignificantSNP[];
  visualizationFiles?: VisualizationFile[];
  createdAt: string;
  mlmFailed?: boolean;
  warnings?: string[];
  originalModel?: string;
  notes?: Record<string, any>;
}

export interface VisualizationFile {
  id: string;
  fileType: string;
  file_path: string;
  width?: number;
  height?: number;
  createdAt: string;
}

export interface LDHeatmapRequest {
  vcfFileId: string;
  chr: string;
  start: number;
  end: number;
}

export interface LDHeatmapResponse {
  snpNames: string[];
  positions: number[];
  ldMatrix: number[][];
  hapBlocks?: HaplotypeBlock[];
}

export interface HaplotypeBlock {
  start: number;
  end: number;
  startIdx?: number;
  endIdx?: number;
  n_snps?: number;
  snps: string[];
}

export interface ReferenceGenome {
  id: string;
  name: string;
  species: string;
  version: string;
  description?: string;
  createdAt: string;
}

export interface MaizeInbredLine {
  id: string;
  name: string;
  version: string;
  description: string;
  chromosomeCount: number;
  genomeSize: string;
  annotationVersion: string;
}

export interface GeneAnnotation {
  id: string;
  gene_id: string;
  gene_name?: string;
  chromosome: string;
  start_pos: number;
  end_pos: number;
  strand?: string;
  description?: string;
}

export interface MultiPhenotypeRequest {
  vcfFileId: string;
  phenotypeFileId: string;
  phenotypeNames: string[];
  method: 'MANOVA' | 'CCA';
  covariates: CovariateConfig;
  significanceThreshold: number;
  nComponents?: number;
  mafThreshold?: number;
  referenceGenome: string;
}

export interface MultiPhenotypeResponse {
  taskId: string;
  status: TaskStatus;
  method: string;
  createdAt: string;
}

export interface EnrichmentRequest {
  resultTaskId: string;
  enrichmentType: 'GO' | 'KEGG';
  pValueThreshold?: number;
  windowSize?: number;
  referenceGenome: string;
}

export interface EnrichmentResponse {
  taskId: string;
  status: TaskStatus;
  enrichmentType: string;
  createdAt: string;
}

export interface FineMappingRequest {
  vcfFileId: string;
  chr: string;
  start: number;
  end: number;
  numCausalConfig?: number[];
  priorCausal?: number;
  referenceGenome: string;
}

export interface FineMappingResponse {
  taskId: string;
  status: TaskStatus;
  createdAt: string;
}

export interface Variant {
  id: string;
  chr: string;
  pos: number;
  ref: string;
  alt: string;
  pValue?: number;
  log10P?: number;
  maf?: number;
}

export interface CCAResult {
  canonicalCorrelations: number[];
  wilksLambda: number[];
  pValues: number[];
  xCoefficients: number[][];
  yCoefficients: number[][];
  xLoadings: number[][];
  yLoadings: number[][];
  varianceExplainedX: number[];
  varianceExplainedY: number[];
  nComponents: number;
}

export interface MultiPhenotypeResult {
  taskId: string;
  resultType: 'multiphenotype';
  method: string;
  phenotypeNames: string[];
  nVariants: number;
  nSamples: number;
  nSignificant: number;
  globalTest: {
    statistic: number;
    pValue: number;
  };
  manhattanData: {
    chr: string;
    pos: number;
    snp: string;
    pValue: number;
    log10P: number;
    fStatistic?: number;
    maf?: number;
  }[];
  ccaResult?: CCAResult;
  topVariants: Variant[];
  notes?: Record<string, any>;
  createdAt: string;
}

export interface EnrichmentTerm {
  id: string;
  name: string;
  category?: string;
  description?: string;
  geneCount: number;
  bgGeneCount: number;
  enrichmentRatio: number;
  pValue: number;
  adjPValue: number;
  negLog10AdjP: number;
  genes: string[];
}

export interface EnrichmentResult {
  taskId: string;
  resultType: 'enrichment';
  enrichmentType: string;
  totalTermsAnalyzed: number;
  significantTermsCount: number;
  enrichmentData: EnrichmentTerm[];
  barplotData: {
    name: string;
    id: string;
    geneCount: number;
    enrichmentRatio: number;
    pValue: number;
    adjPValue: number;
    negLog10AdjP: number;
  }[];
  networkData?: {
    nodes: { id: string; name: string; type: 'term' | 'gene'; value?: number }[];
    links: { source: string; target: string }[];
  };
  candidateGenes: string[];
  snpGeneMapping: Record<string, string[]>;
  notes?: Record<string, any>;
  createdAt: string;
}

export interface FineMappingResult {
  taskId: string;
  resultType: 'finemapping';
  regionChromosome: string;
  regionStart: number;
  regionEnd: number;
  nVariants: number;
  leadVariant: Variant | null;
  posteriorInclusionProbs: number[];
  zScores: number[];
  modelPriors: number[];
  modelPosteriors: number[];
  credibleSets: {
    variants_95: number[];
    size_95: number;
    variants_99: number[];
    size_99: number;
    lead_variant: number;
  };
  manhattanData: {
    chr: string;
    pos: number;
    snp: string;
    log10P: number;
    pValue: number;
    pip: number;
  }[];
  credibleSetTable: {
    snp: string;
    pos: number;
    pip: number;
    in95CredibleSet: boolean;
    in99CredibleSet: boolean;
    isLead: boolean;
    pValue: number;
    log10P: number;
  }[];
  notes?: Record<string, any>;
  createdAt: string;
}
