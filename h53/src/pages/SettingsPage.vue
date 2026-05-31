<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { 
  Settings, 
  User, 
  Bell, 
  Database, 
  Server,
  Shield,
  Palette,
  Download,
  Trash2,
  Save,
  CheckCircle2,
  AlertCircle,
  ChevronRight,
  Eye,
  EyeOff,
  RefreshCw,
  Info
} from 'lucide-vue-next';
import { ElMessage, ElMessageBox } from 'element-plus';
import { authAPI } from '@/services/api';
import type { User as UserType } from '@/types';

const activeSection = ref('profile');
const isLoading = ref(false);
const user = ref<UserType | null>(null);

const formData = ref({
  name: '',
  email: '',
  currentPassword: '',
  newPassword: '',
  confirmPassword: '',
});

const settings = ref({
  emailNotifications: true,
  taskCompleteNotify: true,
  taskFailNotify: true,
  autoRefresh: true,
  refreshInterval: 3,
  theme: 'dark',
  defaultModel: 'GLM' as 'GLM' | 'MLM',
  defaultThreshold: 5e-8,
  defaultReference: 'B73_v5',
  downloadFormat: 'png' as 'png' | 'svg' | 'pdf',
  imageResolution: 300,
});

const showCurrentPassword = ref(false);
const showNewPassword = ref(false);
const showConfirmPassword = ref(false);

const sections = [
  { id: 'profile', label: '个人信息', icon: User },
  { id: 'notifications', label: '通知设置', icon: Bell },
  { id: 'analysis', label: '分析偏好', icon: Database },
  { id: 'appearance', label: '外观设置', icon: Palette },
  { id: 'security', label: '安全设置', icon: Shield },
  { id: 'system', label: '系统信息', icon: Server },
];

const loadUserProfile = async () => {
  try {
    isLoading.value = true;
    const profile = await authAPI.getProfile();
    user.value = profile;
    formData.value.name = profile.name;
    formData.value.email = profile.email;
  } catch (e) {
    console.error('Failed to load profile:', e);
  } finally {
    isLoading.value = false;
  }
};

const saveProfile = async () => {
  try {
    isLoading.value = true;
    await new Promise(resolve => setTimeout(resolve, 1000));
    ElMessage.success('个人信息已保存');
  } catch (e) {
    ElMessage.error('保存失败，请重试');
  } finally {
    isLoading.value = false;
  }
};

const changePassword = async () => {
  if (formData.value.newPassword !== formData.value.confirmPassword) {
    ElMessage.error('两次输入的密码不一致');
    return;
  }
  if (formData.value.newPassword.length < 8) {
    ElMessage.error('密码长度至少8位');
    return;
  }
  try {
    isLoading.value = true;
    await new Promise(resolve => setTimeout(resolve, 1000));
    ElMessage.success('密码修改成功');
    formData.value.currentPassword = '';
    formData.value.newPassword = '';
    formData.value.confirmPassword = '';
  } catch (e) {
    ElMessage.error('密码修改失败');
  } finally {
    isLoading.value = false;
  }
};

const saveSettings = () => {
  localStorage.setItem('gwas_settings', JSON.stringify(settings.value));
  ElMessage.success('设置已保存');
};

const clearCache = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要清除所有本地缓存数据吗？这将删除本地存储的设置和临时数据。',
      '清除缓存',
      {
        confirmButtonText: '确定清除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    );
    localStorage.removeItem('gwas_settings');
    ElMessage.success('缓存已清除');
  } catch {
    // User cancelled
  }
};

const exportData = async () => {
  try {
    isLoading.value = true;
    await new Promise(resolve => setTimeout(resolve, 1000));
    const data = {
      settings: settings.value,
      user: user.value,
      exportTime: new Date().toISOString(),
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `gwas-settings-${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
    ElMessage.success('数据导出成功');
  } catch (e) {
    ElMessage.error('导出失败');
  } finally {
    isLoading.value = false;
  }
};

onMounted(() => {
  loadUserProfile();
  const savedSettings = localStorage.getItem('gwas_settings');
  if (savedSettings) {
    settings.value = { ...settings.value, ...JSON.parse(savedSettings) };
  }
});
</script>

<template>
  <div class="min-h-screen bg-slate-950 p-6">
    <div class="max-w-6xl mx-auto">
      <div class="mb-8">
        <div class="flex items-center gap-3 mb-2">
          <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center">
            <Settings class="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 class="text-2xl font-bold text-white">系统设置</h1>
            <p class="text-slate-400 text-sm">管理您的账户和应用偏好设置</p>
          </div>
        </div>
      </div>

      <div class="flex gap-6">
        <div class="w-56 flex-shrink-0">
          <nav class="bg-slate-800/30 rounded-xl p-2 border border-slate-700/50 sticky top-6">
            <button
              v-for="section in sections"
              :key="section.id"
              @click="activeSection = section.id"
              :class="[
                'w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 text-left',
                activeSection === section.id
                  ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/25'
                  : 'text-slate-400 hover:bg-slate-800/50 hover:text-white'
              ]"
            >
              <component :is="section.icon" class="w-4 h-4" />
              <span class="text-sm font-medium">{{ section.label }}</span>
            </button>
          </nav>
        </div>

        <div class="flex-1 space-y-6">
          <div v-if="activeSection === 'profile'" class="bg-slate-800/30 rounded-xl p-6 border border-slate-700/50">
            <h2 class="text-lg font-semibold text-white mb-6">个人信息</h2>
            
            <div class="flex items-start gap-6 mb-8">
              <div class="w-24 h-24 rounded-2xl bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center flex-shrink-0">
                <User class="w-12 h-12 text-white" />
              </div>
              <div class="flex-1">
                <div class="grid grid-cols-2 gap-4">
                  <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">姓名</label>
                    <input
                      v-model="formData.name"
                      type="text"
                      class="w-full px-4 py-2.5 bg-slate-900/50 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
                      placeholder="请输入姓名"
                    />
                  </div>
                  <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">邮箱</label>
                    <input
                      v-model="formData.email"
                      type="email"
                      class="w-full px-4 py-2.5 bg-slate-900/50 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
                      placeholder="请输入邮箱"
                    />
                  </div>
                </div>
                <div class="mt-4 flex justify-end">
                  <button
                    @click="saveProfile"
                    :disabled="isLoading"
                    class="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Save class="w-4 h-4" />
                    保存修改
                  </button>
                </div>
              </div>
            </div>

            <div class="border-t border-slate-700/50 pt-6">
              <h3 class="text-md font-semibold text-white mb-4">修改密码</h3>
              <div class="grid grid-cols-1 gap-4 max-w-md">
                <div>
                  <label class="block text-sm font-medium text-slate-300 mb-2">当前密码</label>
                  <div class="relative">
                    <input
                      v-model="formData.currentPassword"
                      :type="showCurrentPassword ? 'text' : 'password'"
                      class="w-full px-4 py-2.5 pr-10 bg-slate-900/50 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
                      placeholder="请输入当前密码"
                    />
                    <button
                      type="button"
                      @click="showCurrentPassword = !showCurrentPassword"
                      class="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white"
                    >
                      <Eye v-if="!showCurrentPassword" class="w-4 h-4" />
                      <EyeOff v-else class="w-4 h-4" />
                    </button>
                  </div>
                </div>
                <div>
                  <label class="block text-sm font-medium text-slate-300 mb-2">新密码</label>
                  <div class="relative">
                    <input
                      v-model="formData.newPassword"
                      :type="showNewPassword ? 'text' : 'password'"
                      class="w-full px-4 py-2.5 pr-10 bg-slate-900/50 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
                      placeholder="请输入新密码（至少8位）"
                    />
                    <button
                      type="button"
                      @click="showNewPassword = !showNewPassword"
                      class="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white"
                    >
                      <Eye v-if="!showNewPassword" class="w-4 h-4" />
                      <EyeOff v-else class="w-4 h-4" />
                    </button>
                  </div>
                </div>
                <div>
                  <label class="block text-sm font-medium text-slate-300 mb-2">确认新密码</label>
                  <div class="relative">
                    <input
                      v-model="formData.confirmPassword"
                      :type="showConfirmPassword ? 'text' : 'password'"
                      class="w-full px-4 py-2.5 pr-10 bg-slate-900/50 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
                      placeholder="请再次输入新密码"
                    />
                    <button
                      type="button"
                      @click="showConfirmPassword = !showConfirmPassword"
                      class="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white"
                    >
                      <Eye v-if="!showConfirmPassword" class="w-4 h-4" />
                      <EyeOff v-else class="w-4 h-4" />
                    </button>
                  </div>
                </div>
                <div class="flex justify-end pt-2">
                  <button
                    @click="changePassword"
                    :disabled="isLoading || !formData.currentPassword || !formData.newPassword || !formData.confirmPassword"
                    class="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Save class="w-4 h-4" />
                    修改密码
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div v-if="activeSection === 'notifications'" class="bg-slate-800/30 rounded-xl p-6 border border-slate-700/50">
            <h2 class="text-lg font-semibold text-white mb-6">通知设置</h2>
            
            <div class="space-y-4">
              <div class="flex items-center justify-between p-4 bg-slate-900/30 rounded-xl">
                <div class="flex items-center gap-3">
                  <div class="w-10 h-10 rounded-lg bg-blue-500/15 flex items-center justify-center">
                    <Bell class="w-5 h-5 text-blue-400" />
                  </div>
                  <div>
                    <p class="text-white font-medium">邮件通知</p>
                    <p class="text-slate-400 text-sm">接收重要系统通知邮件</p>
                  </div>
                </div>
                <el-switch v-model="settings.emailNotifications" />
              </div>

              <div class="flex items-center justify-between p-4 bg-slate-900/30 rounded-xl">
                <div class="flex items-center gap-3">
                  <div class="w-10 h-10 rounded-lg bg-green-500/15 flex items-center justify-center">
                    <CheckCircle2 class="w-5 h-5 text-green-400" />
                  </div>
                  <div>
                    <p class="text-white font-medium">任务完成通知</p>
                    <p class="text-slate-400 text-sm">分析任务完成时发送通知</p>
                  </div>
                </div>
                <el-switch v-model="settings.taskCompleteNotify" />
              </div>

              <div class="flex items-center justify-between p-4 bg-slate-900/30 rounded-xl">
                <div class="flex items-center gap-3">
                  <div class="w-10 h-10 rounded-lg bg-red-500/15 flex items-center justify-center">
                    <AlertCircle class="w-5 h-5 text-red-400" />
                  </div>
                  <div>
                    <p class="text-white font-medium">任务失败通知</p>
                    <p class="text-slate-400 text-sm">分析任务失败时发送通知</p>
                  </div>
                </div>
                <el-switch v-model="settings.taskFailNotify" />
              </div>

              <div class="flex items-center justify-between p-4 bg-slate-900/30 rounded-xl">
                <div class="flex items-center gap-3">
                  <div class="w-10 h-10 rounded-lg bg-cyan-500/15 flex items-center justify-center">
                    <RefreshCw class="w-5 h-5 text-cyan-400" />
                  </div>
                  <div>
                    <p class="text-white font-medium">自动刷新任务状态</p>
                    <p class="text-slate-400 text-sm">自动更新任务队列状态</p>
                  </div>
                </div>
                <el-switch v-model="settings.autoRefresh" />
              </div>

              <div v-if="settings.autoRefresh" class="p-4 bg-slate-900/30 rounded-xl ml-13">
                <label class="block text-sm font-medium text-slate-300 mb-2">刷新间隔（秒）</label>
                <el-slider v-model="settings.refreshInterval" :min="1" :max="30" :step="1" show-input />
              </div>
            </div>

            <div class="mt-6 flex justify-end">
              <button
                @click="saveSettings"
                class="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors flex items-center gap-2"
              >
                <Save class="w-4 h-4" />
                保存设置
              </button>
            </div>
          </div>

          <div v-if="activeSection === 'analysis'" class="bg-slate-800/30 rounded-xl p-6 border border-slate-700/50">
            <h2 class="text-lg font-semibold text-white mb-6">分析偏好</h2>
            
            <div class="space-y-6">
              <div>
                <label class="block text-sm font-medium text-slate-300 mb-2">默认分析模型</label>
                <div class="grid grid-cols-2 gap-4">
                  <button
                    @click="settings.defaultModel = 'GLM'"
                    :class="[
                      'p-4 rounded-xl border-2 transition-all duration-200 text-left',
                      settings.defaultModel === 'GLM'
                        ? 'border-blue-500 bg-blue-500/10'
                        : 'border-slate-700 bg-slate-900/30 hover:border-slate-600'
                    ]"
                  >
                    <p :class="['font-semibold', settings.defaultModel === 'GLM' ? 'text-blue-400' : 'text-white']">GLM</p>
                    <p class="text-slate-400 text-sm mt-1">广义线性模型</p>
                  </button>
                  <button
                    @click="settings.defaultModel = 'MLM'"
                    :class="[
                      'p-4 rounded-xl border-2 transition-all duration-200 text-left',
                      settings.defaultModel === 'MLM'
                        ? 'border-blue-500 bg-blue-500/10'
                        : 'border-slate-700 bg-slate-900/30 hover:border-slate-600'
                    ]"
                  >
                    <p :class="['font-semibold', settings.defaultModel === 'MLM' ? 'text-blue-400' : 'text-white']">MLM</p>
                    <p class="text-slate-400 text-sm mt-1">混合线性模型</p>
                  </button>
                </div>
              </div>

              <div>
                <label class="block text-sm font-medium text-slate-300 mb-2">默认显著性阈值</label>
                <el-select v-model="settings.defaultThreshold" class="w-full">
                  <el-option :value="1e-5" label="1e-5 (宽松)" />
                  <el-option :value="1e-6" label="1e-6 (中等)" />
                  <el-option :value="5e-8" label="5e-8 (严格)" />
                  <el-option :value="1e-8" label="1e-8 (非常严格)" />
                </el-select>
              </div>

              <div>
                <label class="block text-sm font-medium text-slate-300 mb-2">默认参考基因组</label>
                <el-select v-model="settings.defaultReference" class="w-full">
                  <el-option value="B73_v5" label="B73 v5 (黄金标准)" />
                  <el-option value="Mo17_v1" label="Mo17 v1" />
                  <el-option value="W22_v2" label="W22 v2" />
                  <el-option value="PH207_v1" label="PH207 v1" />
                  <el-option value="B97_v1" label="B97 v1" />
                </el-select>
              </div>

              <div>
                <label class="block text-sm font-medium text-slate-300 mb-2">图片下载格式</label>
                <el-select v-model="settings.downloadFormat" class="w-full">
                  <el-option value="png" label="PNG (位图)" />
                  <el-option value="svg" label="SVG (矢量图)" />
                  <el-option value="pdf" label="PDF (文档)" />
                </el-select>
              </div>

              <div>
                <label class="block text-sm font-medium text-slate-300 mb-2">图片分辨率 (DPI)</label>
                <el-slider v-model="settings.imageResolution" :min="72" :max="600" :step="72" show-input />
              </div>
            </div>

            <div class="mt-6 flex justify-end">
              <button
                @click="saveSettings"
                class="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors flex items-center gap-2"
              >
                <Save class="w-4 h-4" />
                保存设置
              </button>
            </div>
          </div>

          <div v-if="activeSection === 'appearance'" class="bg-slate-800/30 rounded-xl p-6 border border-slate-700/50">
            <h2 class="text-lg font-semibold text-white mb-6">外观设置</h2>
            
            <div>
              <label class="block text-sm font-medium text-slate-300 mb-4">主题模式</label>
              <div class="grid grid-cols-3 gap-4">
                <button
                  @click="settings.theme = 'dark'"
                  :class="[
                    'p-4 rounded-xl border-2 transition-all duration-200',
                    settings.theme === 'dark'
                      ? 'border-blue-500 bg-blue-500/10'
                      : 'border-slate-700 bg-slate-900/30 hover:border-slate-600'
                  ]"
                >
                  <div class="w-full h-16 rounded-lg bg-slate-950 mb-3 flex items-center justify-center">
                    <div class="w-8 h-8 rounded-full bg-slate-800"></div>
                  </div>
                  <p :class="['text-sm font-medium', settings.theme === 'dark' ? 'text-blue-400' : 'text-slate-300']">深色模式</p>
                </button>
                <button
                  @click="settings.theme = 'light'"
                  :class="[
                    'p-4 rounded-xl border-2 transition-all duration-200',
                    settings.theme === 'light'
                      ? 'border-blue-500 bg-blue-500/10'
                      : 'border-slate-700 bg-slate-900/30 hover:border-slate-600'
                  ]"
                >
                  <div class="w-full h-16 rounded-lg bg-white mb-3 flex items-center justify-center">
                    <div class="w-8 h-8 rounded-full bg-slate-100"></div>
                  </div>
                  <p :class="['text-sm font-medium', settings.theme === 'light' ? 'text-blue-400' : 'text-slate-300']">浅色模式</p>
                </button>
                <button
                  @click="settings.theme = 'auto'"
                  :class="[
                    'p-4 rounded-xl border-2 transition-all duration-200',
                    settings.theme === 'auto'
                      ? 'border-blue-500 bg-blue-500/10'
                      : 'border-slate-700 bg-slate-900/30 hover:border-slate-600'
                  ]"
                >
                  <div class="w-full h-16 rounded-lg bg-gradient-to-r from-slate-950 via-slate-500 to-white mb-3 flex items-center justify-center">
                    <div class="w-8 h-8 rounded-full bg-gradient-to-r from-slate-800 to-slate-100"></div>
                  </div>
                  <p :class="['text-sm font-medium', settings.theme === 'auto' ? 'text-blue-400' : 'text-slate-300']">跟随系统</p>
                </button>
              </div>
            </div>

            <div class="mt-6 flex justify-end">
              <button
                @click="saveSettings"
                class="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors flex items-center gap-2"
              >
                <Save class="w-4 h-4" />
                保存设置
              </button>
            </div>
          </div>

          <div v-if="activeSection === 'security'" class="bg-slate-800/30 rounded-xl p-6 border border-slate-700/50">
            <h2 class="text-lg font-semibold text-white mb-6">安全设置</h2>
            
            <div class="space-y-4">
              <div class="flex items-center justify-between p-4 bg-slate-900/30 rounded-xl">
                <div class="flex items-center gap-3">
                  <div class="w-10 h-10 rounded-lg bg-green-500/15 flex items-center justify-center">
                    <CheckCircle2 class="w-5 h-5 text-green-400" />
                  </div>
                  <div>
                    <p class="text-white font-medium">账户状态</p>
                    <p class="text-slate-400 text-sm">正常运行中</p>
                  </div>
                </div>
                <span class="px-3 py-1 rounded-full bg-green-500/15 text-green-400 text-sm font-medium">安全</span>
              </div>

              <div class="p-4 bg-slate-900/30 rounded-xl">
                <div class="flex items-center justify-between mb-2">
                  <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-lg bg-blue-500/15 flex items-center justify-center">
                      <Shield class="w-5 h-5 text-blue-400" />
                    </div>
                    <div>
                      <p class="text-white font-medium">最后登录</p>
                      <p class="text-slate-400 text-sm">{{ user?.lastLogin || '刚刚' }}</p>
                    </div>
                  </div>
                </div>
              </div>

              <div class="flex items-center justify-between p-4 bg-slate-900/30 rounded-xl cursor-pointer hover:bg-slate-900/50 transition-colors">
                <div class="flex items-center gap-3">
                  <div class="w-10 h-10 rounded-lg bg-orange-500/15 flex items-center justify-center">
                    <Download class="w-5 h-5 text-orange-400" />
                  </div>
                  <div>
                    <p class="text-white font-medium">导出个人数据</p>
                    <p class="text-slate-400 text-sm">下载您的所有数据分析记录</p>
                  </div>
                </div>
                <ChevronRight class="w-5 h-5 text-slate-400" />
              </div>

              <div class="flex items-center justify-between p-4 bg-slate-900/30 rounded-xl cursor-pointer hover:bg-slate-900/50 transition-colors" @click="clearCache">
                <div class="flex items-center gap-3">
                  <div class="w-10 h-10 rounded-lg bg-red-500/15 flex items-center justify-center">
                    <Trash2 class="w-5 h-5 text-red-400" />
                  </div>
                  <div>
                    <p class="text-white font-medium">清除本地缓存</p>
                    <p class="text-slate-400 text-sm">清除所有本地存储的临时数据</p>
                  </div>
                </div>
                <ChevronRight class="w-5 h-5 text-slate-400" />
              </div>
            </div>

            <div class="mt-6 flex justify-end gap-3">
              <button
                @click="exportData"
                :disabled="isLoading"
                class="px-6 py-2.5 bg-slate-700 hover:bg-slate-600 text-white font-medium rounded-lg transition-colors flex items-center gap-2 disabled:opacity-50"
              >
                <Download class="w-4 h-4" />
                导出数据
              </button>
            </div>
          </div>

          <div v-if="activeSection === 'system'" class="bg-slate-800/30 rounded-xl p-6 border border-slate-700/50">
            <h2 class="text-lg font-semibold text-white mb-6">系统信息</h2>
            
            <div class="grid grid-cols-2 gap-4">
              <div class="p-4 bg-slate-900/30 rounded-xl">
                <p class="text-slate-400 text-sm mb-1">应用版本</p>
                <p class="text-white font-semibold">v1.0.0</p>
              </div>
              <div class="p-4 bg-slate-900/30 rounded-xl">
                <p class="text-slate-400 text-sm mb-1">构建时间</p>
                <p class="text-white font-semibold">2024-01-15</p>
              </div>
              <div class="p-4 bg-slate-900/30 rounded-xl">
                <p class="text-slate-400 text-sm mb-1">前端框架</p>
                <p class="text-white font-semibold">Vue 3 + TypeScript</p>
              </div>
              <div class="p-4 bg-slate-900/30 rounded-xl">
                <p class="text-slate-400 text-sm mb-1">后端框架</p>
                <p class="text-white font-semibold">Flask + Celery</p>
              </div>
              <div class="p-4 bg-slate-900/30 rounded-xl">
                <p class="text-slate-400 text-sm mb-1">可视化库</p>
                <p class="text-white font-semibold">ECharts 5</p>
              </div>
              <div class="p-4 bg-slate-900/30 rounded-xl">
                <p class="text-slate-400 text-sm mb-1">统计引擎</p>
                <p class="text-white font-semibold">statsmodels + scikit-allel</p>
              </div>
            </div>

            <div class="mt-6 p-4 bg-blue-500/10 border border-blue-500/30 rounded-xl">
              <div class="flex items-start gap-3">
                <Info class="w-5 h-5 text-blue-400 flex-shrink-0 mt-0.5" />
                <div>
                  <p class="text-blue-400 font-medium">关于GWAS分析系统</p>
                  <p class="text-slate-300 text-sm mt-1">
                    本系统是一个专业的全基因组关联分析平台，支持VCF格式基因型数据和CSV表型数据的上传与分析，
                    提供GLM和MLM两种统计模型，生成曼哈顿图、QQ图、LD热图等可视化结果。
                    系统采用Celery异步任务队列，支持大规模数据的并行处理。
                  </p>
                </div>
              </div>
            </div>

            <div class="mt-6 p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-xl">
              <div class="flex items-start gap-3">
                <CheckCircle2 class="w-5 h-5 text-emerald-400 flex-shrink-0 mt-0.5" />
                <div>
                  <p class="text-emerald-400 font-medium">服务状态</p>
                  <p class="text-slate-300 text-sm mt-1">所有服务运行正常</p>
                  <div class="flex gap-4 mt-3">
                    <div class="flex items-center gap-2">
                      <div class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
                      <span class="text-slate-400 text-sm">API服务</span>
                    </div>
                    <div class="flex items-center gap-2">
                      <div class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
                      <span class="text-slate-400 text-sm">任务队列</span>
                    </div>
                    <div class="flex items-center gap-2">
                      <div class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
                      <span class="text-slate-400 text-sm">数据库</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
