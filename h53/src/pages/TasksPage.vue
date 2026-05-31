<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import { 
  ListTodo, 
  Play, 
  CheckCircle2, 
  XCircle, 
  Clock, 
  RefreshCw,
  Trash2,
  Eye,
  RotateCcw,
  BarChart3,
  FlaskConical,
  Dna,
  AlertCircle,
  Pause
} from 'lucide-vue-next';
import { useTaskStore } from '@/stores';
import { taskAPI, resultAPI } from '@/services/api';
import type { AnalysisTask, TaskStatus, TaskType } from '@/types';

const router = useRouter();
const taskStore = useTaskStore();

const activeFilter = ref<TaskStatus | 'all'>('all');
const typeFilter = ref<TaskType | 'all'>('all');
const currentPage = ref(1);
const pageSize = ref(20);
const total = ref(0);
const isLoading = ref(false);
let pollInterval: number | null = null;

const statusFilters: { value: TaskStatus | 'all'; label: string; color: string }[] = [
  { value: 'all', label: '全部', color: '#94A3B8' },
  { value: 'queued', label: '排队中', color: '#165DFF' },
  { value: 'running', label: '运行中', color: '#FF7D00' },
  { value: 'completed', label: '已完成', color: '#00B42A' },
  { value: 'failed', label: '失败', color: '#F53F3F' },
  { value: 'cancelled', label: '已取消', color: '#64748B' },
];

const typeFilters: { value: TaskType | 'all'; label: string; icon: any }[] = [
  { value: 'all', label: '全部', icon: ListTodo },
  { value: 'gwas_glm', label: 'GLM分析', icon: BarChart3 },
  { value: 'gwas_mlm', label: 'MLM分析', icon: FlaskConical },
  { value: 'pca', label: 'PCA分析', icon: BarChart3 },
  { value: 'ld_heatmap', label: 'LD热图', icon: Dna },
];

const loadTasks = async () => {
  try {
    isLoading.value = true;
    const status = activeFilter.value === 'all' ? undefined : activeFilter.value;
    const type = typeFilter.value === 'all' ? undefined : typeFilter.value;
    
    const response = await taskAPI.listTasks(currentPage.value, pageSize.value, status, type);
    taskStore.setTasks(response.tasks);
    total.value = response.total;
  } catch (e) {
    console.error('Failed to load tasks:', e);
  } finally {
    isLoading.value = false;
  }
};

const loadStats = async () => {
  try {
    const stats = await taskAPI.getStats();
    taskStore.setStats(stats);
  } catch (e) {
    console.error('Failed to load stats:', e);
  }
};

const startPolling = () => {
  if (pollInterval) return;
  pollInterval = window.setInterval(() => {
    const hasRunningTasks = taskStore.tasks.some(t => t.status === 'running' || t.status === 'queued');
    if (hasRunningTasks) {
      loadTasks();
    }
    loadStats();
  }, 3000);
};

const stopPolling = () => {
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
};

const getStatusConfig = (status: TaskStatus) => {
  const configs: Record<TaskStatus, { label: string; color: string; bgColor: string; icon: any }> = {
    queued: { label: '排队中', color: '#165DFF', bgColor: 'rgba(22, 93, 255, 0.15)', icon: Clock },
    running: { label: '运行中', color: '#FF7D00', bgColor: 'rgba(255, 125, 0, 0.15)', icon: Play },
    completed: { label: '已完成', color: '#00B42A', bgColor: 'rgba(0, 180, 42, 0.15)', icon: CheckCircle2 },
    failed: { label: '失败', color: '#F53F3F', bgColor: 'rgba(245, 63, 63, 0.15)', icon: XCircle },
    cancelled: { label: '已取消', color: '#64748B', bgColor: 'rgba(100, 116, 139, 0.15)', icon: Pause },
  };
  return configs[status];
};

const getTypeLabel = (type: TaskType) => {
  const labels: Record<TaskType, string> = {
    pca: 'PCA分析',
    gwas_glm: 'GLM关联分析',
    gwas_mlm: 'MLM关联分析',
    ld_heatmap: 'LD热图分析',
    finemapping: '贝叶斯精细定位',
    multiphenotype_manova: '多表型MANOVA',
    multiphenotype_cca: '多表型CCA',
    enrichment_go: 'GO富集分析',
    enrichment_kegg: 'KEGG富集分析',
  };
  return labels[type] || type;
};

const handleViewResult = async (task: AnalysisTask) => {
  if (task.taskType.startsWith('gwas_') || 
      task.taskType.startsWith('multiphenotype_') ||
      task.taskType.startsWith('enrichment_') ||
      task.taskType === 'finemapping') {
    router.push(`/results/${task.id}`);
  } else {
    try {
      const result = await resultAPI.getResult(task.id);
      console.log('Task result:', result);
      ElMessage.info('该类型任务结果查看功能开发中');
    } catch (e) {
      console.error('Failed to get result:', e);
    }
  }
};

const handleCancelTask = async (task: AnalysisTask) => {
  try {
    await ElMessageBox.confirm(
      `确定要取消任务吗？`,
      '确认取消',
      {
        confirmButtonText: '取消任务',
        cancelButtonText: '继续运行',
        type: 'warning',
      }
    );
    
    await taskAPI.cancelTask(task.id);
    taskStore.updateTask(task.id, { status: 'cancelled' });
    ElMessage.success('任务已取消');
  } catch (e) {
    if (e !== 'cancel') {
      console.error('Failed to cancel task:', e);
    }
  }
};

const handleRestartTask = async (task: AnalysisTask) => {
  try {
    const response = await taskAPI.restartTask(task.id);
    taskStore.addTask(response.task);
    ElMessage.success('任务已重新提交');
  } catch (e) {
    console.error('Failed to restart task:', e);
  }
};

const handleDeleteTask = async (task: AnalysisTask) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除任务吗？相关结果也将被删除。`,
      '确认删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    );
    
    await taskAPI.cancelTask(task.id);
    taskStore.setTasks(taskStore.tasks.filter(t => t.id !== task.id));
    ElMessage.success('任务已删除');
  } catch (e) {
    if (e !== 'cancel') {
      console.error('Failed to delete task:', e);
    }
  }
};

const formatDate = (dateStr: string) => {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const formatDuration = (start: string, end: string) => {
  if (!start || !end) return '-';
  const diff = new Date(end).getTime() - new Date(start).getTime();
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);
  
  if (days > 0) return `${days}天${hours % 24}小时`;
  if (hours > 0) return `${hours}小时${minutes % 60}分钟`;
  return `${minutes}分钟`;
};

const filteredTasks = computed(() => taskStore.tasks);

onMounted(() => {
  loadTasks();
  loadStats();
  startPolling();
});

onUnmounted(() => {
  stopPolling();
});
</script>

<template>
  <div class="tasks-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">任务队列</h2>
        <p class="page-desc">查看和管理所有分析任务的状态</p>
      </div>
      <div class="header-actions">
        <el-button @click="loadTasks" :loading="isLoading">
          <RefreshCw class="btn-icon" />
          刷新
        </el-button>
      </div>
    </div>
    
    <div class="stats-cards">
      <div class="stat-card total">
        <div class="stat-icon">
          <ListTodo class="icon" />
        </div>
        <div class="stat-content">
          <span class="stat-value">{{ taskStore.stats.total }}</span>
          <span class="stat-label">全部任务</span>
        </div>
      </div>
      <div class="stat-card running">
        <div class="stat-icon">
          <Play class="icon" />
        </div>
        <div class="stat-content">
          <span class="stat-value">{{ taskStore.stats.running }}</span>
          <span class="stat-label">运行中</span>
        </div>
      </div>
      <div class="stat-card completed">
        <div class="stat-icon">
          <CheckCircle2 class="icon" />
        </div>
        <div class="stat-content">
          <span class="stat-value">{{ taskStore.stats.completed }}</span>
          <span class="stat-label">已完成</span>
        </div>
      </div>
      <div class="stat-card failed">
        <div class="stat-icon">
          <XCircle class="icon" />
        </div>
        <div class="stat-content">
          <span class="stat-value">{{ taskStore.stats.failed }}</span>
          <span class="stat-label">失败</span>
        </div>
      </div>
    </div>
    
    <div class="filters-section">
      <div class="filter-group">
        <span class="filter-label">状态筛选:</span>
        <div class="filter-tabs">
          <button
            v-for="filter in statusFilters"
            :key="filter.value"
            :class="['filter-tab', { active: activeFilter === filter.value }]"
            :style="{ '--filter-color': filter.color }"
            @click="activeFilter = filter.value; currentPage = 1; loadTasks()"
          >
            {{ filter.label }}
          </button>
        </div>
      </div>
      
      <div class="filter-group">
        <span class="filter-label">类型筛选:</span>
        <div class="filter-tabs type-tabs">
          <button
            v-for="filter in typeFilters"
            :key="filter.value"
            :class="['filter-tab', { active: typeFilter === filter.value }]"
            @click="typeFilter = filter.value; currentPage = 1; loadTasks()"
          >
            <component :is="filter.icon" class="tab-icon" />
            {{ filter.label }}
          </button>
        </div>
      </div>
    </div>
    
    <div class="tasks-list">
      <div v-if="isLoading" class="loading-state">
        <el-icon class="is-loading" :size="32"><RefreshCw /></el-icon>
        <span>加载中...</span>
      </div>
      
      <div v-else-if="filteredTasks.length === 0" class="empty-state">
        <ListTodo class="empty-icon" />
        <p class="empty-title">暂无任务</p>
        <p class="empty-desc">去<a href="/analysis/config" class="link">分析配置</a>页面创建新的分析任务</p>
      </div>
      
      <div v-else class="tasks-grid">
        <div
          v-for="task in filteredTasks"
          :key="task.id"
          class="task-card"
          :class="task.status"
        >
          <div class="task-header">
            <div class="task-type">
              <Dna v-if="task.taskType === 'ld_heatmap'" class="type-icon" />
              <BarChart3 v-else class="type-icon" />
              <span class="type-label">{{ getTypeLabel(task.taskType) }}</span>
            </div>
            <el-tag 
              :type="task.status === 'completed' ? 'success' : task.status === 'failed' ? 'danger' : task.status === 'running' ? 'warning' : 'info'"
              size="small"
              effect="light"
            >
              <component :is="getStatusConfig(task.status).icon" class="status-icon" />
              {{ getStatusConfig(task.status).label }}
            </el-tag>
          </div>
          
          <div class="task-info">
            <div class="task-params">
              <div class="param-item">
                <span class="param-label">模型:</span>
                <span class="param-value">
                  {{ task.parameters.model || task.taskType.toUpperCase() }}
                </span>
              </div>
              <div v-if="task.parameters.phenotype_name" class="param-item">
                <span class="param-label">性状:</span>
                <span class="param-value">{{ task.parameters.phenotype_name }}</span>
              </div>
            </div>
          </div>
          
          <div v-if="task.status === 'running' || task.status === 'queued'" class="task-progress">
            <div class="progress-header">
              <span class="progress-label">{{ task.currentStage || '处理中...' }}</span>
              <span class="progress-value">{{ Math.round(task.progress * 100) }}%</span>
            </div>
            <el-progress 
              :percentage="Math.round(task.progress * 100)" 
              :show-text="false"
              :stroke-width="6"
              :color="task.status === 'running' ? '#FF7D00' : '#165DFF'"
            />
          </div>
          
          <div v-if="task.status === 'failed' && task.errorMessage" class="task-error">
            <AlertCircle class="error-icon" />
            <div class="error-text" :title="task.errorMessage">
              {{ task.errorMessage.split('\n')[0] }}
            </div>
          </div>
          
          <div class="task-meta">
            <div class="meta-item">
              <Clock class="meta-icon" />
              <span>{{ formatDate(task.createdAt) }}</span>
            </div>
            <div v-if="task.startedAt && task.completedAt" class="meta-item">
              <span class="duration">
                耗时: {{ formatDuration(task.startedAt, task.completedAt) }}
              </span>
            </div>
          </div>
          
          <div class="task-actions">
            <el-button
              v-if="task.status === 'completed' && task.taskType.startsWith('gwas_')"
              type="primary"
              size="small"
              @click="handleViewResult(task)"
            >
              <Eye class="btn-icon" />
              查看结果
            </el-button>
            
            <el-button
              v-if="task.status === 'queued' || task.status === 'running'"
              size="small"
              @click="handleCancelTask(task)"
            >
              <XCircle class="btn-icon" />
              取消
            </el-button>
            
            <el-button
              v-if="task.status === 'failed' || task.status === 'cancelled' || task.status === 'completed'"
              size="small"
              @click="handleRestartTask(task)"
            >
              <RotateCcw class="btn-icon" />
              重新运行
            </el-button>
            
            <el-button
              size="small"
              type="danger"
              text
              @click="handleDeleteTask(task)"
            >
              <Trash2 class="btn-icon" />
            </el-button>
          </div>
        </div>
      </div>
    </div>
    
    <div v-if="total > pageSize" class="pagination-wrapper">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadTasks"
        @current-change="loadTasks"
      />
    </div>
  </div>
</template>

<style scoped>
.tasks-page {
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

.stats-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 28px;
}

.stat-card {
  background: rgba(30, 41, 59, 0.5);
  border: 1px solid #334155;
  border-radius: 14px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  transition: all 0.2s ease;
}

.stat-card:hover {
  transform: translateY(-2px);
}

.stat-card.total {
  border-color: rgba(148, 163, 184, 0.3);
}

.stat-card.running {
  border-color: rgba(255, 125, 0, 0.3);
  background: rgba(255, 125, 0, 0.05);
}

.stat-card.completed {
  border-color: rgba(0, 180, 42, 0.3);
  background: rgba(0, 180, 42, 0.05);
}

.stat-card.failed {
  border-color: rgba(245, 63, 63, 0.3);
  background: rgba(245, 63, 63, 0.05);
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.stat-card.total .stat-icon {
  background: rgba(148, 163, 184, 0.15);
}

.stat-card.running .stat-icon {
  background: rgba(255, 125, 0, 0.15);
}

.stat-card.completed .stat-icon {
  background: rgba(0, 180, 42, 0.15);
}

.stat-card.failed .stat-icon {
  background: rgba(245, 63, 63, 0.15);
}

.stat-icon .icon {
  width: 24px;
  height: 24px;
}

.stat-card.total .icon { color: #94A3B8; }
.stat-card.running .icon { color: #FF7D00; }
.stat-card.completed .icon { color: #00B42A; }
.stat-card.failed .icon { color: #F53F3F; }

.stat-content {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #FFFFFF;
  line-height: 1.2;
}

.stat-label {
  font-size: 13px;
  color: #94A3B8;
}

.filters-section {
  background: rgba(30, 41, 59, 0.5);
  border: 1px solid #334155;
  border-radius: 14px;
  padding: 20px 24px;
  margin-bottom: 24px;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.filter-group:last-child {
  margin-bottom: 0;
}

.filter-label {
  font-size: 14px;
  font-weight: 500;
  color: #94A3B8;
  width: 70px;
  flex-shrink: 0;
}

.filter-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.filter-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid #334155;
  border-radius: 8px;
  color: #94A3B8;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.filter-tab:hover {
  color: #FFFFFF;
  border-color: #475569;
}

.filter-tab.active {
  color: var(--filter-color, #165DFF);
  border-color: var(--filter-color, #165DFF);
  background: rgba(22, 93, 255, 0.1);
}

.type-tabs .filter-tab.active {
  background: linear-gradient(135deg, rgba(22, 93, 255, 0.15), rgba(0, 180, 42, 0.1));
  border-color: #165DFF;
  color: #FFFFFF;
}

.tab-icon {
  width: 16px;
  height: 16px;
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

.link {
  color: #165DFF;
  text-decoration: underline;
}

.tasks-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: 16px;
}

.task-card {
  background: rgba(30, 41, 59, 0.5);
  border: 1px solid #334155;
  border-radius: 14px;
  padding: 20px;
  transition: all 0.2s ease;
}

.task-card:hover {
  border-color: #165DFF;
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
}

.task-card.running {
  border-color: rgba(255, 125, 0, 0.5);
}

.task-card.completed {
  border-color: rgba(0, 180, 42, 0.5);
}

.task-card.failed {
  border-color: rgba(245, 63, 63, 0.5);
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.task-type {
  display: flex;
  align-items: center;
  gap: 8px;
}

.type-icon {
  width: 20px;
  height: 20px;
  color: #165DFF;
}

.type-label {
  font-size: 15px;
  font-weight: 600;
  color: #FFFFFF;
}

.status-icon {
  width: 14px;
  height: 14px;
  margin-right: 4px;
}

.task-info {
  margin-bottom: 16px;
}

.task-params {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.param-item {
  display: flex;
  gap: 8px;
  font-size: 13px;
}

.param-label {
  color: #64748B;
  flex-shrink: 0;
}

.param-value {
  color: #E2E8F0;
  font-weight: 500;
}

.task-progress {
  margin-bottom: 16px;
  padding: 12px;
  background: rgba(15, 23, 42, 0.6);
  border-radius: 8px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.progress-label {
  font-size: 12px;
  color: #94A3B8;
}

.progress-value {
  font-size: 12px;
  font-weight: 600;
  color: #FF7D00;
}

.task-error {
  display: flex;
  gap: 8px;
  padding: 12px;
  background: rgba(245, 63, 63, 0.1);
  border: 1px solid rgba(245, 63, 63, 0.3);
  border-radius: 8px;
  margin-bottom: 16px;
}

.error-icon {
  width: 18px;
  height: 18px;
  color: #F53F3F;
  flex-shrink: 0;
  margin-top: 1px;
}

.error-text {
  font-size: 12px;
  color: #FCA5A5;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-top: 1px solid #1E293B;
  margin-bottom: 16px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #64748B;
}

.meta-icon {
  width: 14px;
  height: 14px;
}

.duration {
  background: rgba(22, 93, 255, 0.1);
  color: #165DFF;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 500;
}

.task-actions {
  display: flex;
  gap: 8px;
}

.task-actions .el-button {
  flex: 1;
}

.pagination-wrapper {
  display: flex;
  justify-content: center;
  margin-top: 32px;
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
  .stats-cards {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .tasks-grid {
    grid-template-columns: 1fr;
  }
}
</style>
