import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { Task, TaskResult, ProgressMessage, TaskStatus } from '../types';
import { getTasks, getTask, getTaskResult, deleteTask as apiDeleteTask } from '../api';
import { socketManager } from '../utils/socket';

export const useTaskStore = defineStore('task', () => {
  const tasks = ref<Task[]>([]);
  const currentTask = ref<Task | null>(null);
  const currentTaskResult = ref<TaskResult | null>(null);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const progressMap = ref<Map<string, ProgressMessage>>(new Map());
  const totalCount = ref(0);
  const currentPage = ref(1);
  const pageSize = ref(10);

  const completedTasks = computed(() =>
    tasks.value.filter((t) => t.status === 'completed')
  );

  const processingTasks = computed(() =>
    tasks.value.filter((t) => 
      t.status === 'pending' || 
      t.status === 'preprocessing' ||
      t.status === 'detecting' ||
      t.status === 'recognizing' ||
      t.status === 'postprocessing' ||
      t.status === 'punctuating'
    )
  );

  const failedTasks = computed(() =>
    tasks.value.filter((t) => t.status === 'failed')
  );

  const getTaskById = (id: string) => tasks.value.find((t) => t.id === id);

  const getProgress = (taskId: string) => progressMap.value.get(taskId);

  async function loadTasks(page: number = 1, perPage: number = 10, status?: string) {
    loading.value = true;
    error.value = null;
    try {
      const response = await getTasks(page, perPage, status);
      tasks.value = response.items;
      totalCount.value = response.total;
      currentPage.value = response.page;
      pageSize.value = response.pageSize;
      return response;
    } catch (e) {
      error.value = e instanceof Error ? e.message : '加载任务失败';
      throw e;
    } finally {
      loading.value = false;
    }
  }

  async function loadTask(taskId: string) {
    loading.value = true;
    error.value = null;
    try {
      currentTask.value = await getTask(taskId);
      return currentTask.value;
    } catch (e) {
      error.value = e instanceof Error ? e.message : '加载任务失败';
      throw e;
    } finally {
      loading.value = false;
    }
  }

  async function loadTaskResult(taskId: string) {
    loading.value = true;
    error.value = null;
    try {
      currentTaskResult.value = await getTaskResult(taskId);
      return currentTaskResult.value;
    } catch (e) {
      error.value = e instanceof Error ? e.message : '加载任务结果失败';
      throw e;
    } finally {
      loading.value = false;
    }
  }

  async function deleteTask(taskId: string) {
    try {
      await apiDeleteTask(taskId);
      tasks.value = tasks.value.filter((t) => t.id !== taskId);
      if (currentTask.value?.id === taskId) {
        currentTask.value = null;
        currentTaskResult.value = null;
      }
      progressMap.value.delete(taskId);
    } catch (e) {
      error.value = e instanceof Error ? e.message : '删除任务失败';
      throw e;
    }
  }

  function addTask(task: Task) {
    const index = tasks.value.findIndex((t) => t.id === task.id);
    if (index >= 0) {
      tasks.value[index] = task;
    } else {
      tasks.value.unshift(task);
    }
  }

  function updateTaskStatus(taskId: string, status: TaskStatus, progress?: number) {
    const task = tasks.value.find((t) => t.id === taskId);
    if (task) {
      task.status = status;
      if (progress !== undefined) {
        task.progress = progress;
      }
      if (status === 'completed') {
        task.completedAt = new Date().toISOString();
      }
    }
    if (currentTask.value?.id === taskId) {
      currentTask.value.status = status;
      if (progress !== undefined) {
        currentTask.value.progress = progress;
      }
      if (status === 'completed') {
        currentTask.value.completedAt = new Date().toISOString();
      }
    }
  }

  function handleProgress(message: ProgressMessage) {
    progressMap.value.set(message.taskId, message);
    updateTaskStatus(message.taskId, message.status, message.progress);
    
    const task = tasks.value.find((t) => t.id === message.taskId);
    if (task) {
      task.currentPage = message.currentPage ?? task.currentPage;
      task.pageCount = message.totalPages ?? task.pageCount;
    }
    if (currentTask.value?.id === message.taskId) {
      currentTask.value.currentPage = message.currentPage ?? currentTask.value.currentPage;
      currentTask.value.pageCount = message.totalPages ?? currentTask.value.pageCount;
    }
  }

  function handleCompleted(data: { taskId: string; result: TaskResult }) {
    updateTaskStatus(data.taskId, 'completed', 100);
    
    const task = tasks.value.find((t) => t.id === data.taskId);
    if (task) {
      task.result = data.result;
      task.completedAt = new Date().toISOString();
    }
    
    if (currentTask.value?.id === data.taskId) {
      currentTask.value.result = data.result;
      currentTask.value.completedAt = new Date().toISOString();
      currentTaskResult.value = data.result;
    }
    
    progressMap.value.delete(data.taskId);
  }

  function handleFailed(data: { taskId: string; error: string }) {
    updateTaskStatus(data.taskId, 'failed', 0);
    const task = tasks.value.find((t) => t.id === data.taskId);
    if (task) {
      task.errorMessage = data.error;
      task.completedAt = new Date().toISOString();
    }
    if (currentTask.value?.id === data.taskId) {
      currentTask.value.errorMessage = data.error;
      currentTask.value.completedAt = new Date().toISOString();
    }
    
    progressMap.value.delete(data.taskId);
  }

  function handleTaskCreated(task: Task) {
    addTask(task);
  }

  function handleTaskDeleted(data: { taskId: string }) {
    tasks.value = tasks.value.filter((t) => t.id !== data.taskId);
    if (currentTask.value?.id === data.taskId) {
      currentTask.value = null;
      currentTaskResult.value = null;
    }
  }

  function connectWebSocket() {
    socketManager.connect();
    socketManager.on('progress', handleProgress);
    socketManager.on('completed', handleCompleted);
    socketManager.on('failed', handleFailed);
    socketManager.on('task_created', handleTaskCreated);
    socketManager.on('task_deleted', handleTaskDeleted);
  }

  function disconnectWebSocket() {
    socketManager.disconnect();
    socketManager.off('progress', handleProgress);
    socketManager.off('completed', handleCompleted);
    socketManager.off('failed', handleFailed);
    socketManager.off('task_created', handleTaskCreated);
    socketManager.off('task_deleted', handleTaskDeleted);
  }

  function subscribeToTask(taskId: string) {
    socketManager.joinTask(taskId);
  }

  function unsubscribeFromTask(taskId: string) {
    socketManager.leaveTask(taskId);
  }

  function updateLineContent(pageNumber: number, lineId: string, content: string) {
    if (!currentTaskResult.value) return;
    
    const page = currentTaskResult.value.pages.find((p) => p.pageNumber === pageNumber);
    if (page) {
      const line = page.textLines.find((l) => l.id === lineId);
      if (line) {
        line.content = content;
        line.confidence = 100;
        line.candidates = [content];
        
        if (page.columns && page.columns[line.columnIndex]) {
          const columnLine = page.columns[line.columnIndex].find((l) => l.id === lineId);
          if (columnLine) {
            columnLine.content = content;
            columnLine.confidence = 100;
            columnLine.candidates = [content];
          }
        }
        
        currentTaskResult.value.fullText = currentTaskResult.value.pages
          .flatMap((p) => p.textLines.map((l) => l.content))
          .join('\n');
      }
    }
  }

  function updateBoxText(pageNumber: number, boxId: string, content: string) {
    if (!currentTaskResult.value) return;
    
    const page = currentTaskResult.value.pages.find((p) => p.pageNumber === pageNumber);
    if (page) {
      const line = page.textLines.find((l) => l.textBox.id === boxId);
      if (line) {
        line.content = content;
        line.confidence = 100;
        line.candidates = [content];
        
        if (page.columns && page.columns[line.columnIndex]) {
          const columnLine = page.columns[line.columnIndex].find((l) => l.textBox.id === boxId);
          if (columnLine) {
            columnLine.content = content;
            columnLine.confidence = 100;
            columnLine.candidates = [content];
          }
        }
        
        currentTaskResult.value.fullText = currentTaskResult.value.pages
          .flatMap((p) => p.textLines.map((l) => l.content))
          .join('\n');
      }
    }
  }

  function clearCurrent() {
    currentTask.value = null;
    currentTaskResult.value = null;
  }

  function setError(msg: string | null) {
    error.value = msg;
  }

  return {
    tasks,
    currentTask,
    currentTaskResult,
    loading,
    error,
    progressMap,
    totalCount,
    currentPage,
    pageSize,
    completedTasks,
    processingTasks,
    failedTasks,
    getTaskById,
    getProgress,
    loadTasks,
    loadTask,
    loadTaskResult,
    deleteTask,
    addTask,
    updateTaskStatus,
    handleProgress,
    handleCompleted,
    handleFailed,
    handleTaskCreated,
    handleTaskDeleted,
    connectWebSocket,
    disconnectWebSocket,
    subscribeToTask,
    unsubscribeFromTask,
    updateLineContent,
    updateBoxText,
    clearCurrent,
    setError,
  };
});
