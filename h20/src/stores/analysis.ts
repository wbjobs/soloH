import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { AddressCluster, SuspiciousPattern, ClusteringResult } from '../types'
import { analysisApi } from '../api'

export interface ClusteringParams {
  algorithm: string
  minClusterSize?: number
  maxClusters?: number
  similarityThreshold?: number
  includeTransactions?: boolean
}

export const useAnalysisStore = defineStore('analysis', () => {
  const clusters = ref<AddressCluster[]>([])
  const patterns = ref<SuspiciousPattern[]>([])
  const selectedCluster = ref<AddressCluster | null>(null)
  const clusteringProgress = ref(0)
  const analysisParams = ref<ClusteringParams>({
    algorithm: 'common_input'
  })
  const loading = ref(false)
  const error = ref<string | null>(null)
  const clusteringResult = ref<ClusteringResult | null>(null)

  const hasSelectedCluster = computed(() => selectedCluster.value !== null)
  const isClustering = computed(() => clusteringProgress.value > 0 && clusteringProgress.value < 100)

  async function fetchClusters(params?: { algorithm?: string; page?: number; pageSize?: number }) {
    loading.value = true
    error.value = null
    try {
      const response = await analysisApi.getClusteringResults({
        ...analysisParams.value,
        ...params
      })
      clusters.value = response.data.clusters
      clusteringResult.value = response.data
      return response
    } catch (e) {
      error.value = e instanceof Error ? e.message : '获取聚类结果失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchPatterns(params?: {
    patternType?: string
    minSeverity?: string
    page?: number
    pageSize?: number
  }) {
    loading.value = true
    error.value = null
    try {
      const response = await analysisApi.getSuspiciousPatterns(params)
      patterns.value = response.data.items
      return response
    } catch (e) {
      error.value = e instanceof Error ? e.message : '获取可疑模式失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function runClustering(params?: Partial<ClusteringParams>) {
    loading.value = true
    error.value = null
    clusteringProgress.value = 0
    try {
      const mergedParams = { ...analysisParams.value, ...params }
      const response = await analysisApi.runClustering(mergedParams)
      
      const progressInterval = setInterval(() => {
        if (clusteringProgress.value < 90) {
          clusteringProgress.value += 10
        }
      }, 500)

      const result = await response
      clusteringProgress.value = 100
      clearInterval(progressInterval)
      
      clusters.value = result.data.clusters
      clusteringResult.value = result.data
      
      setTimeout(() => {
        clusteringProgress.value = 0
      }, 2000)
      
      return result
    } catch (e) {
      clusteringProgress.value = 0
      error.value = e instanceof Error ? e.message : '执行聚类失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function analyzeAddress(address: string) {
    loading.value = true
    error.value = null
    try {
      const response = await analysisApi.analyzeAddress(address)
      return response
    } catch (e) {
      error.value = e instanceof Error ? e.message : '分析地址失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  function selectCluster(cluster: AddressCluster | null) {
    selectedCluster.value = cluster
  }

  function setAnalysisParams(params: Partial<ClusteringParams>) {
    analysisParams.value = { ...analysisParams.value, ...params }
  }

  function clearSelectedCluster() {
    selectedCluster.value = null
  }

  function clearClusters() {
    clusters.value = []
    clusteringResult.value = null
  }

  function clearPatterns() {
    patterns.value = []
  }

  return {
    clusters,
    patterns,
    selectedCluster,
    clusteringProgress,
    analysisParams,
    loading,
    error,
    clusteringResult,
    hasSelectedCluster,
    isClustering,
    fetchClusters,
    fetchPatterns,
    runClustering,
    analyzeAddress,
    selectCluster,
    setAnalysisParams,
    clearSelectedCluster,
    clearClusters,
    clearPatterns
  }
})
