<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useAuthStore, useTaskStore } from '@/stores';
import { taskAPI } from '@/services/api';
import {
  Upload,
  FlaskConical,
  ListTodo,
  BarChart3,
  Dna,
  Settings,
  LogOut,
  ChevronLeft,
  ChevronRight,
  Bell,
  User,
} from 'lucide-vue-next';

const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();
const taskStore = useTaskStore();

const collapsed = ref(false);
const userDropdownVisible = ref(false);

const menuItems = [
  { path: '/upload', name: '数据上传', icon: Upload },
  { path: '/analysis/config', name: '分析配置', icon: FlaskConical },
  { path: '/tasks', name: '任务队列', icon: ListTodo },
  { path: '/tasks', name: '结果可视化', icon: BarChart3 },
  { path: '/reference', name: '参考基因组', icon: Dna },
  { path: '/settings', name: '系统设置', icon: Settings },
];

const activeRoute = computed(() => route.path);

const isActive = (path: string) => {
  if (path === '/tasks') {
    return activeRoute.value.startsWith('/tasks') || activeRoute.value.startsWith('/results');
  }
  return activeRoute.value.startsWith(path);
};

const toggleSidebar = () => {
  collapsed.value = !collapsed.value;
};

const handleLogout = () => {
  authStore.logout();
  router.push('/login');
};

const loadStats = async () => {
  try {
    const stats = await taskAPI.getStats();
    taskStore.setStats(stats);
  } catch (e) {
    console.error('Failed to load stats:', e);
  }
};

onMounted(() => {
  if (!authStore.isAuthenticated) {
    router.push('/login');
    return;
  }
  loadStats();
});
</script>

<template>
  <div class="main-layout">
    <aside :class="['sidebar', { collapsed }]">
      <div class="sidebar-header">
        <div class="logo">
          <Dna class="logo-icon" />
          <span v-if="!collapsed" class="logo-text">GWAS Platform</span>
        </div>
        <button class="toggle-btn" @click="toggleSidebar">
          <ChevronLeft v-if="!collapsed" class="toggle-icon" />
          <ChevronRight v-else class="toggle-icon" />
        </button>
      </div>
      
      <nav class="sidebar-nav">
        <router-link
          v-for="item in menuItems"
          :key="item.path + item.name"
          :to="item.path"
          :class="['nav-item', { active: isActive(item.path) }]"
        >
          <component :is="item.icon" class="nav-icon" />
          <span v-if="!collapsed" class="nav-text">{{ item.name }}</span>
          <span
            v-if="!collapsed && item.path === '/tasks' && item.name === '任务队列' && taskStore.stats.running > 0"
            class="nav-badge"
          >
            {{ taskStore.stats.running }}
          </span>
        </router-link>
      </nav>
      
      <div class="sidebar-footer">
        <div class="stats-grid" v-if="!collapsed">
          <div class="stat-item">
            <span class="stat-value running">{{ taskStore.stats.running }}</span>
            <span class="stat-label">运行中</span>
          </div>
          <div class="stat-item">
            <span class="stat-value completed">{{ taskStore.stats.completed }}</span>
            <span class="stat-label">已完成</span>
          </div>
          <div class="stat-item">
            <span class="stat-value queued">{{ taskStore.stats.queued }}</span>
            <span class="stat-label">排队中</span>
          </div>
        </div>
      </div>
    </aside>
    
    <div class="main-content">
      <header class="top-header">
        <div class="header-left">
          <h1 class="page-title">
            {{ menuItems.find(m => activeRoute.startsWith(m.path))?.name || 'GWAS分析平台' }}
          </h1>
        </div>
        
        <div class="header-right">
          <button class="icon-btn notification-btn">
            <Bell class="icon" />
            <span v-if="taskStore.stats.running > 0" class="notification-dot"></span>
          </button>
          
          <el-dropdown trigger="click" v-model="userDropdownVisible">
            <div class="user-info">
              <div class="user-avatar">
                <User class="avatar-icon" />
              </div>
              <div v-if="!collapsed" class="user-details">
                <span class="user-name">{{ authStore.user?.name }}</span>
                <span class="user-email">{{ authStore.user?.email }}</span>
              </div>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="router.push('/settings')">
                  <Settings class="menu-icon" />
                  个人设置
                </el-dropdown-item>
                <el-dropdown-item divided @click="handleLogout">
                  <LogOut class="menu-icon" />
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>
      
      <main class="content-area">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<style scoped>
.main-layout {
  display: flex;
  min-height: 100vh;
  background: #0F172A;
}

.sidebar {
  width: 260px;
  background: linear-gradient(180deg, #0F172A 0%, #1E293B 100%);
  border-right: 1px solid #1E293B;
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease;
  position: sticky;
  top: 0;
  height: 100vh;
}

.sidebar.collapsed {
  width: 72px;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 16px;
  border-bottom: 1px solid #1E293B;
}

.logo {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo-icon {
  width: 36px;
  height: 36px;
  color: #165DFF;
  flex-shrink: 0;
}

.logo-text {
  font-size: 18px;
  font-weight: 700;
  color: #FFFFFF;
  background: linear-gradient(135deg, #165DFF, #00B42A);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.toggle-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: rgba(30, 41, 59, 0.8);
  border: 1px solid #334155;
  color: #94A3B8;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.toggle-btn:hover {
  background: #334155;
  color: #FFFFFF;
}

.toggle-icon {
  width: 18px;
  height: 18px;
}

.sidebar-nav {
  flex: 1;
  padding: 16px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow-y: auto;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 10px;
  color: #94A3B8;
  text-decoration: none;
  transition: all 0.2s ease;
  position: relative;
  overflow: hidden;
}

.nav-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  width: 3px;
  background: linear-gradient(180deg, #165DFF, #00B42A);
  border-radius: 0 3px 3px 0;
  opacity: 0;
  transition: opacity 0.2s ease;
}

.nav-item:hover {
  background: rgba(30, 41, 59, 0.8);
  color: #FFFFFF;
}

.nav-item.active {
  background: linear-gradient(90deg, rgba(22, 93, 255, 0.15) 0%, transparent 100%);
  color: #165DFF;
}

.nav-item.active::before {
  opacity: 1;
}

.nav-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

.nav-text {
  font-size: 14px;
  font-weight: 500;
  white-space: nowrap;
}

.nav-badge {
  margin-left: auto;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  background: #F53F3F;
  color: white;
  font-size: 11px;
  font-weight: 600;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.sidebar-footer {
  padding: 16px;
  border-top: 1px solid #1E293B;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.stat-value {
  font-size: 18px;
  font-weight: 700;
}

.stat-value.running {
  color: #FF7D00;
}

.stat-value.completed {
  color: #00B42A;
}

.stat-value.queued {
  color: #165DFF;
}

.stat-label {
  font-size: 10px;
  color: #64748B;
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.top-header {
  height: 64px;
  background: rgba(15, 23, 42, 0.9);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid #1E293B;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 32px;
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-left {
  flex: 1;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: #FFFFFF;
  margin: 0;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.icon-btn {
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
  position: relative;
}

.icon-btn:hover {
  color: #FFFFFF;
  border-color: #165DFF;
}

.icon {
  width: 20px;
  height: 20px;
}

.notification-dot {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 8px;
  height: 8px;
  background: #F53F3F;
  border-radius: 50%;
  border: 2px solid #0F172A;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.2s ease;
}

.user-info:hover {
  background: rgba(30, 41, 59, 0.8);
}

.user-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, #165DFF, #00B42A);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.avatar-icon {
  width: 18px;
  height: 18px;
  color: white;
}

.user-details {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.user-name {
  font-size: 14px;
  font-weight: 500;
  color: #FFFFFF;
}

.user-email {
  font-size: 12px;
  color: #64748B;
}

.menu-icon {
  width: 16px;
  height: 16px;
  margin-right: 8px;
}

.content-area {
  flex: 1;
  padding: 24px 32px;
  overflow-y: auto;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.fade-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

@media (max-width: 768px) {
  .sidebar {
    position: fixed;
    left: -260px;
    z-index: 200;
  }
  
  .sidebar:not(.collapsed) {
    left: 0;
  }
  
  .top-header {
    padding: 0 16px;
  }
  
  .content-area {
    padding: 16px;
  }
  
  .user-details {
    display: none;
  }
}
</style>
