<template>
  <div class="task-list-view">
    <div class="page-header">
      <div class="header-content">
        <h1 class="page-title">任务列表</h1>
        <p class="page-subtitle">管理您的古籍识别任务</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="$router.push('/')">
          <icon-park theme="outline" size="18" name="add" />
          新建任务
        </el-button>
      </div>
    </div>

    <div class="stats-bar">
      <div class="stat-item">
        <span class="stat-label">全部任务</span>
        <span class="stat-value">{{ totalCount }}</span>
      </div>
      <div class="stat-item processing">
        <span class="stat-label">处理中</span>
        <span class="stat-value">{{ processingTasks.length }}</span>
      </div>
      <div class="stat-item completed">
        <span class="stat-label">已完成</span>
        <span class="stat-value">{{ completedTasks.length }}</span>
      </div>
    </div>

    <div class="filter-bar">
      <el-tabs v-model="activeTab" class="filter-tabs">
        <el-tab-pane label="全部" name="all" />
        <el-tab-pane label="处理中" name="processing" />
        <el-tab-pane label="已完成" name="completed" />
        <el-tab-pane label="失败" name="failed" />
      </el-tabs>
      <el-input
        v-model="searchQuery"
        placeholder="搜索任务名称..."
        clearable
        class="search-input"
        :prefix-icon="Search"
      />
    </div>

    <div class="task-content">
      <template v-if="loading">
        <div class="loading-state">
          <el-icon class="is-loading" :size="48">
            <Loading />
          </el-icon>
          <p>加载中...</p>
        </div>
      </template>

      <template v-else-if="filteredTasks.length === 0">
        <div class="empty-state">
          <icon-park theme="outline" size="80" name="empty" :fill="['#D4C4B0']" />
          <h3>暂无任务</h3>
          <p>点击上方按钮上传您的第一份古籍文档</p>
          <el-button type="primary" @click="$router.push('/')">
            开始识别
          </el-button>
        </div>
      </template>

      <template v-else>
        <div class="task-grid">
          <TaskCard
            v-for="task in filteredTasks"
            :key="task.id"
            :task="task"
            :progress="taskStore.getProgress(task.id)"
            @view="handleViewTask"
            @delete="handleDeleteTask"
            @rerun="handleRerunTask"
          />
        </div>

        <div class="pagination-bar">
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :total="totalCount"
            :page-sizes="[10, 20, 40, 80]"
            layout="total, sizes, prev, pager, next, jumper"
            background
            @size-change="handlePageChange"
            @current-change="handlePageChange"
          />
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Search, Loading } from '@element-plus/icons-vue';
import TaskCard from '../components/TaskCard.vue';
import { useTaskStore } from '../stores/task';
import { rerunTask } from '../api';
import type { Task } from '../types';

const router = useRouter();
const taskStore = useTaskStore();

const activeTab = ref('all');
const searchQuery = ref('');
const currentPage = ref(1);
const pageSize = ref(20);

const loading = computed(() => taskStore.loading);
const totalCount = computed(() => taskStore.totalCount);
const tasks = computed(() => taskStore.tasks);
const processingTasks = computed(() => taskStore.processingTasks);
const completedTasks = computed(() => taskStore.completedTasks);

const processingStatuses: string[] = ['pending', 'preprocessing', 'detecting', 'recognizing', 'postprocessing', 'punctuating'];

const filteredTasks = computed(() => {
  let result = tasks.value;

  if (activeTab.value === 'processing') {
    result = result.filter((t) => processingStatuses.includes(t.status));
  } else if (activeTab.value !== 'all') {
    result = result.filter((t) => t.status === activeTab.value);
  }

  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase();
    result = result.filter((t) =>
      t.fileName.toLowerCase().includes(query)
    );
  }

  return result;
});

const loadTasks = async () => {
  try {
    await taskStore.loadTasks(currentPage.value, pageSize.value);
  } catch (e) {
    ElMessage.error('加载任务列表失败');
  }
};

const handlePageChange = () => {
  loadTasks();
};

const handleViewTask = (task: Task) => {
  router.push(`/task/${task.id}`);
};

const handleDeleteTask = async (task: Task) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除任务 "${task.fileName}" 吗？此操作不可恢复。`,
      '确认删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger',
      }
    );
    await taskStore.deleteTask(task.id);
    ElMessage.success('删除成功');
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败');
    }
  }
};

const handleRerunTask = async (task: Task) => {
  try {
    await ElMessageBox.confirm(
      `确定要重新运行任务 "${task.fileName}" 吗？`,
      '确认重跑',
      {
        confirmButtonText: '重跑',
        cancelButtonText: '取消',
        type: 'info',
      }
    );
    const updatedTask = await rerunTask(task.id);
    taskStore.addTask(updatedTask);
    taskStore.subscribeToTask(updatedTask.id);
    ElMessage.success('已开始重新识别');
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('重跑失败');
    }
  }
};

onMounted(() => {
  taskStore.connectWebSocket();
  loadTasks();
});
</script>

<style lang="scss" scoped>
.task-list-view {
  min-height: 100vh;
  background: #FAF7F2;
  padding-bottom: 40px;
}

.page-header {
  background: linear-gradient(135deg, #F5F0E6 0%, #EDE4D3 100%);
  padding: 48px 40px 32px;
  display: flex;
  justify-content: space-between;
  align-items: flex-end;

  .el-button {
    background: #C41E3A;
    border-color: #C41E3A;

    &:hover {
      background: #A0182E;
      border-color: #A0182E;
    }
  }
}

.page-title {
  font-family: 'Noto Serif SC', serif;
  font-size: 32px;
  font-weight: 600;
  color: #2C1810;
  margin: 0 0 8px 0;
}

.page-subtitle {
  font-size: 14px;
  color: #8B7355;
  margin: 0;
}

.stats-bar {
  display: flex;
  gap: 24px;
  padding: 24px 40px;
  background: #FFF;
  border-bottom: 1px solid #E8DFD0;
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 0 24px;
  border-left: 3px solid #D4C4B0;

  &:first-child {
    border-left-color: #8B7355;
  }

  &.processing {
    border-left-color: #E6A23C;
  }

  &.completed {
    border-left-color: #67C23A;
  }
}

.stat-label {
  font-size: 13px;
  color: #8B7355;
}

.stat-value {
  font-family: 'Noto Serif SC', serif;
  font-size: 28px;
  font-weight: 600;
  color: #2C1810;
}

.filter-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 40px;
  background: #FFF;
  border-bottom: 1px solid #E8DFD0;
}

.filter-tabs {
  :deep(.el-tabs__header) {
    margin: 0;
  }

  :deep(.el-tabs__item) {
    font-size: 14px;
    color: #6B5B4F;

    &.is-active {
      color: #C41E3A;
    }
  }

  :deep(.el-tabs__active-bar) {
    background-color: #C41E3A;
  }
}

.search-input {
  width: 280px;
}

.task-content {
  padding: 24px 40px;
}

.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  color: #8B7355;

  p {
    margin: 16px 0 24px 0;
    font-size: 14px;
  }

  h3 {
    font-family: 'Noto Serif SC', serif;
    font-size: 20px;
    color: #5C4033;
    margin: 16px 0 8px 0;
  }
}

.loading-state .el-icon {
  color: #C41E3A;
}

.task-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
}

.pagination-bar {
  display: flex;
  justify-content: center;
  margin-top: 32px;

  :deep(.el-pagination.is-background .el-pager li.is-active) {
    background-color: #C41E3A;
  }
}

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
    padding: 32px 20px 24px;
  }

  .stats-bar {
    flex-wrap: wrap;
    gap: 16px;
    padding: 16px 20px;
  }

  .filter-bar {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
    padding: 12px 20px;
  }

  .search-input {
    width: 100%;
  }

  .task-content {
    padding: 16px 20px;
  }

  .task-grid {
    grid-template-columns: 1fr;
  }
}
</style>
