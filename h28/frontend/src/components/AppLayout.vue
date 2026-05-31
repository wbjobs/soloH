<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useTaskStore } from '../stores/task';
import { socketManager } from '../utils/socket';
import { 
  Home, 
  FileText, 
  Info, 
  Upload, 
  List, 
  Close,
  BookOpen
} from '@icon-park/vue-next';

const router = useRouter();
const route = useRoute();
const taskStore = useTaskStore();

const sidebarOpen = ref(true);
const wsConnected = ref(false);

const menuItems = [
  { path: '/', name: '首页', icon: Home },
  { path: '/tasks', name: '任务列表', icon: FileText },
  { path: '/about', name: '关于', icon: Info },
];

const toggleSidebar = () => {
  sidebarOpen.value = !sidebarOpen.value;
};

const navigateTo = (path: string) => {
  router.push(path);
};

const isActive = (path: string) => route.path === path;

const handleConnect = () => {
  wsConnected.value = true;
};

const handleDisconnect = () => {
  wsConnected.value = false;
};

onMounted(() => {
  taskStore.connectWebSocket();
  taskStore.loadTasks(1, 10);
  
  socketManager.on('connect', handleConnect);
  socketManager.on('disconnect', handleDisconnect);
});

onUnmounted(() => {
  taskStore.disconnectWebSocket();
  
  socketManager.off('connect', handleConnect);
  socketManager.off('disconnect', handleDisconnect);
});
</script>

<template>
  <div class="app-layout">
    <header class="app-header">
      <div class="header-left">
        <button class="menu-btn" @click="toggleSidebar">
          <List v-if="!sidebarOpen" :size="20" />
          <Close v-else :size="20" />
        </button>
        <div class="logo" @click="navigateTo('/')">
          <BookOpen :size="28" class="logo-icon" />
          <span class="logo-text">古籍文字识别系统</span>
        </div>
      </div>
      
      <div class="header-right">
        <div class="ws-status" :class="{ connected: wsConnected }">
          <span class="status-dot"></span>
          <span class="status-text">{{ wsConnected ? '已连接' : '未连接' }}</span>
        </div>
        <button class="upload-btn" @click="navigateTo('/')">
          <Upload :size="18" />
          <span>上传文件</span>
        </button>
      </div>
    </header>

    <div class="app-body">
      <aside class="app-sidebar" :class="{ collapsed: !sidebarOpen }">
        <nav class="sidebar-nav">
          <div 
            v-for="item in menuItems" 
            :key="item.path"
            class="nav-item"
            :class="{ active: isActive(item.path) }"
            @click="navigateTo(item.path)"
          >
            <component :is="item.icon" :size="20" />
            <span v-if="sidebarOpen" class="nav-text">{{ item.name }}</span>
          </div>
        </nav>

        <div v-if="sidebarOpen" class="sidebar-stats">
          <div class="stat-item">
            <span class="stat-label">处理中</span>
            <span class="stat-value processing">{{ taskStore.processingTasks.length }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">已完成</span>
            <span class="stat-value completed">{{ taskStore.completedTasks.length }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">失败</span>
            <span class="stat-value failed">{{ taskStore.failedTasks.length }}</span>
          </div>
        </div>
      </aside>

      <main class="app-main">
        <router-view />
      </main>
    </div>
  </div>
</template>

<style scoped lang="scss">
.app-layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: #F5F0E6;
}

.app-header {
  height: 64px;
  background: linear-gradient(135deg, #C41E3A 0%, #9B162E 100%);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  box-shadow: 0 2px 8px rgba(196, 30, 58, 0.15);
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.menu-btn {
  background: rgba(255, 255, 255, 0.15);
  border: none;
  color: white;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;

  &:hover {
    background: rgba(255, 255, 255, 0.25);
  }
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  color: white;

  .logo-icon {
    color: #FFD700;
  }

  .logo-text {
    font-size: 20px;
    font-weight: 600;
    letter-spacing: 1px;
  }
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.ws-status {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 20px;
  color: rgba(255, 255, 255, 0.8);
  font-size: 13px;

  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #ef4444;
    transition: background-color 0.3s ease;
  }

  &.connected {
    .status-dot {
      background: #22c55e;
      box-shadow: 0 0 8px rgba(34, 197, 94, 0.5);
    }
  }
}

.upload-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: rgba(255, 255, 255, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 8px;
  color: white;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    background: rgba(255, 255, 255, 0.3);
    transform: translateY(-1px);
  }
}

.app-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.app-sidebar {
  width: 240px;
  background: #FFFFFF;
  border-right: 1px solid #E8E0D0;
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.03);

  &.collapsed {
    width: 64px;
  }
}

.sidebar-nav {
  flex: 1;
  padding: 16px 8px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  margin-bottom: 4px;
  border-radius: 8px;
  color: #5D534A;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
  overflow: hidden;

  &:hover {
    background: #F5F0E6;
    color: #C41E3A;
  }

  &.active {
    background: linear-gradient(135deg, rgba(196, 30, 58, 0.1) 0%, rgba(196, 30, 58, 0.05) 100%);
    color: #C41E3A;
    font-weight: 500;

    &::before {
      content: '';
      position: absolute;
      left: 0;
      width: 3px;
      height: 24px;
      background: #C41E3A;
      border-radius: 0 2px 2px 0;
    }
  }
}

.sidebar-stats {
  padding: 16px;
  border-top: 1px solid #E8E0D0;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;

  &:last-child {
    margin-bottom: 0;
  }
}

.stat-label {
  font-size: 13px;
  color: #8B8176;
}

.stat-value {
  font-size: 16px;
  font-weight: 600;

  &.processing {
    color: #E6A23C;
  }

  &.completed {
    color: #67C23A;
  }

  &.failed {
    color: #C41E3A;
  }
}

.app-main {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  background-color: #F5F0E6;
}
</style>
