import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { User, UploadFile, AnalysisTask, GWASResult } from '@/types';
import { authAPI } from '@/services/api';

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null);
  const token = ref<string | null>(localStorage.getItem('access_token'));
  const isLoading = ref(false);

  const isAuthenticated = computed(() => !!token.value);

  const setAuth = (accessToken: string, userData: User) => {
    token.value = accessToken;
    user.value = userData;
    localStorage.setItem('access_token', accessToken);
    localStorage.setItem('user', JSON.stringify(userData));
  };

  const clearAuth = () => {
    token.value = null;
    user.value = null;
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');
  };

  const login = async (email: string, password: string) => {
    isLoading.value = true;
    try {
      const response = await authAPI.login({ email, password });
      setAuth(response.access_token, response.user);
      return response;
    } finally {
      isLoading.value = false;
    }
  };

  const register = async (name: string, email: string, password: string) => {
    isLoading.value = true;
    try {
      const response = await authAPI.register({ name, email, password });
      setAuth(response.access_token, response.user);
      return response;
    } finally {
      isLoading.value = false;
    }
  };

  const logout = () => {
    clearAuth();
  };

  const restoreAuth = () => {
    const storedUser = localStorage.getItem('user');
    const storedToken = localStorage.getItem('access_token');
    if (storedUser && storedToken) {
      try {
        user.value = JSON.parse(storedUser);
        token.value = storedToken;
      } catch {
        clearAuth();
      }
    }
  };

  return {
    user,
    token,
    isLoading,
    isAuthenticated,
    login,
    register,
    logout,
    restoreAuth,
  };
});

export const useFileStore = defineStore('files', () => {
  const vcfFiles = ref<UploadFile[]>([]);
  const phenotypeFiles = ref<UploadFile[]>([]);
  const covariateFiles = ref<UploadFile[]>([]);
  const selectedVCF = ref<UploadFile | null>(null);
  const selectedPhenotype = ref<UploadFile | null>(null);
  const selectedPhenotypeName = ref<string>('');

  const setVCFFiles = (files: UploadFile[]) => {
    vcfFiles.value = files;
  };

  const setPhenotypeFiles = (files: UploadFile[]) => {
    phenotypeFiles.value = files;
  };

  const setCovariateFiles = (files: UploadFile[]) => {
    covariateFiles.value = files;
  };

  const addVCFFile = (file: UploadFile) => {
    vcfFiles.value.unshift(file);
  };

  const addPhenotypeFile = (file: UploadFile) => {
    phenotypeFiles.value.unshift(file);
  };

  const addCovariateFile = (file: UploadFile) => {
    covariateFiles.value.unshift(file);
  };

  const removeFile = (fileId: string, fileType: string) => {
    if (fileType === 'vcf') {
      vcfFiles.value = vcfFiles.value.filter(f => f.fileId !== fileId);
      if (selectedVCF.value?.fileId === fileId) {
        selectedVCF.value = null;
      }
    } else if (fileType === 'phenotype') {
      phenotypeFiles.value = phenotypeFiles.value.filter(f => f.fileId !== fileId);
      if (selectedPhenotype.value?.fileId === fileId) {
        selectedPhenotype.value = null;
        selectedPhenotypeName.value = '';
      }
    } else if (fileType === 'covariate') {
      covariateFiles.value = covariateFiles.value.filter(f => f.fileId !== fileId);
    }
  };

  return {
    vcfFiles,
    phenotypeFiles,
    covariateFiles,
    selectedVCF,
    selectedPhenotype,
    selectedPhenotypeName,
    setVCFFiles,
    setPhenotypeFiles,
    setCovariateFiles,
    addVCFFile,
    addPhenotypeFile,
    addCovariateFile,
    removeFile,
  };
});

export const useTaskStore = defineStore('tasks', () => {
  const tasks = ref<AnalysisTask[]>([]);
  const currentTask = ref<AnalysisTask | null>(null);
  const currentResult = ref<GWASResult | null>(null);
  const stats = ref({
    total: 0,
    queued: 0,
    running: 0,
    completed: 0,
    failed: 0,
    cancelled: 0,
  });

  const setTasks = (taskList: AnalysisTask[]) => {
    tasks.value = taskList;
  };

  const addTask = (task: AnalysisTask) => {
    tasks.value.unshift(task);
  };

  const updateTask = (taskId: string, updates: Partial<AnalysisTask>) => {
    const index = tasks.value.findIndex(t => t.id === taskId);
    if (index !== -1) {
      tasks.value[index] = { ...tasks.value[index], ...updates };
    }
    if (currentTask.value?.id === taskId) {
      currentTask.value = { ...currentTask.value, ...updates };
    }
  };

  const setStats = (newStats: typeof stats.value) => {
    stats.value = newStats;
  };

  const setCurrentResult = (result: GWASResult | null) => {
    currentResult.value = result;
  };

  return {
    tasks,
    currentTask,
    currentResult,
    stats,
    setTasks,
    addTask,
    updateTask,
    setStats,
    setCurrentResult,
  };
});
