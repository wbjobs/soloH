<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { ElMessage } from 'element-plus';
import { User, Lock, LogIn, UserPlus, Dna } from 'lucide-vue-next';
import { useAuthStore } from '@/stores';

const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();

const isLogin = ref(true);
const isLoading = ref(false);

const formData = ref({
  name: '',
  email: '',
  password: '',
  confirmPassword: '',
});

const rules = {
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    {
      validator: (_: any, value: string, callback: any) => {
        if (value !== formData.value.password) {
          callback(new Error('两次密码不一致'));
        } else {
          callback();
        }
      },
      trigger: 'blur',
    },
  ],
};

const redirect = route.query.redirect as string || '/upload';

const toggleMode = () => {
  isLogin.value = !isLogin.value;
};

const handleSubmit = async () => {
  try {
    isLoading.value = true;
    
    if (isLogin.value) {
      await authStore.login(formData.value.email, formData.value.password);
      ElMessage.success('登录成功');
    } else {
      await authStore.register(formData.value.name, formData.value.email, formData.value.password);
      ElMessage.success('注册成功');
    }
    
    router.push(redirect);
  } catch (error) {
    console.error('Auth error:', error);
  } finally {
    isLoading.value = false;
  }
};

const handleDemoLogin = async () => {
  try {
    isLoading.value = true;
    await authStore.login('demo@gwas.com', 'demo123456');
    ElMessage.success('演示账号登录成功');
    router.push(redirect);
  } catch (error) {
    ElMessage.error('演示账号登录失败，请检查后端服务是否启动');
  } finally {
    isLoading.value = false;
  }
};

onMounted(() => {
  if (authStore.isAuthenticated) {
    router.push(redirect);
  }
});
</script>

<template>
  <div class="auth-container">
    <div class="bg-decoration">
      <div class="circle circle-1"></div>
      <div class="circle circle-2"></div>
      <div class="circle circle-3"></div>
    </div>
    
    <div class="auth-card">
      <div class="auth-header">
        <div class="logo">
          <Dna class="logo-icon" />
        </div>
        <h1 class="title">GWAS 分析平台</h1>
        <p class="subtitle">全基因组关联分析系统</p>
      </div>
      
      <div class="auth-tabs">
        <button 
          :class="['tab-btn', { active: isLogin }]"
          @click="isLogin = true"
        >
          登录
        </button>
        <button 
          :class="['tab-btn', { active: !isLogin }]"
          @click="isLogin = false"
        >
          注册
        </button>
      </div>
      
      <el-form
        ref="formRef"
        :model="formData"
        :rules="rules"
        class="auth-form"
        @submit.prevent="handleSubmit"
      >
        <el-form-item v-if="!isLogin" prop="name">
          <el-input
            v-model="formData.name"
            placeholder="请输入姓名"
            size="large"
            :prefix-icon="User"
          />
        </el-form-item>
        
        <el-form-item prop="email">
          <el-input
            v-model="formData.email"
            placeholder="请输入邮箱"
            size="large"
            :prefix-icon="User"
            type="email"
          />
        </el-form-item>
        
        <el-form-item prop="password">
          <el-input
            v-model="formData.password"
            placeholder="请输入密码"
            size="large"
            :prefix-icon="Lock"
            type="password"
            show-password
          />
        </el-form-item>
        
        <el-form-item v-if="!isLogin" prop="confirmPassword">
          <el-input
            v-model="formData.confirmPassword"
            placeholder="请确认密码"
            size="large"
            :prefix-icon="Lock"
            type="password"
            show-password
          />
        </el-form-item>
        
        <el-button
          type="primary"
          size="large"
          class="submit-btn"
          :loading="isLoading"
          @click="handleSubmit"
        >
          <template v-if="isLogin">
            <LogIn class="btn-icon" />
            登录
          </template>
          <template v-else>
            <UserPlus class="btn-icon" />
            注册
          </template>
        </el-button>
      </el-form>
      
      <div class="demo-login">
        <div class="divider">
          <span>或者</span>
        </div>
        <el-button
          size="large"
          class="demo-btn"
          :loading="isLoading"
          @click="handleDemoLogin"
        >
          使用演示账号登录
        </el-button>
        <p class="demo-hint">演示账号: demo@gwas.com / demo123456</p>
      </div>
      
      <div class="auth-footer">
        <p v-if="isLogin">
          还没有账号？
          <span class="link" @click="toggleMode">立即注册</span>
        </p>
        <p v-else>
          已有账号？
          <span class="link" @click="toggleMode">立即登录</span>
        </p>
      </div>
    </div>
    
    <div class="feature-cards">
      <div class="feature-card">
        <div class="feature-icon blue">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/>
            <line x1="16" y1="17" x2="8" y2="17"/>
          </svg>
        </div>
        <h3>VCF数据支持</h3>
        <p>支持标准VCF格式基因型数据上传，自动解析样本信息</p>
      </div>
      
      <div class="feature-card">
        <div class="feature-icon green">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="20" x2="18" y2="10"/>
            <line x1="12" y1="20" x2="12" y2="4"/>
            <line x1="6" y1="20" x2="6" y2="14"/>
          </svg>
        </div>
        <h3>多种统计模型</h3>
        <p>提供GLM和MLM两种模型，支持协变量校正和PCA分析</p>
      </div>
      
      <div class="feature-card">
        <div class="feature-icon orange">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <line x1="2" y1="12" x2="22" y2="12"/>
            <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
          </svg>
        </div>
        <h3>可视化分析</h3>
        <p>曼哈顿图、QQ图、LD热图等多种交互式可视化图表</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.auth-container {
  min-height: 100vh;
  background: linear-gradient(135deg, #0F172A 0%, #1E293B 50%, #0F172A 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  position: relative;
  overflow: hidden;
}

.bg-decoration {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
}

.circle {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.3;
}

.circle-1 {
  width: 500px;
  height: 500px;
  background: linear-gradient(135deg, #165DFF, #722ED1);
  top: -200px;
  right: -100px;
}

.circle-2 {
  width: 400px;
  height: 400px;
  background: linear-gradient(135deg, #00B42A, #14C9C9);
  bottom: -150px;
  left: -100px;
}

.circle-3 {
  width: 300px;
  height: 300px;
  background: linear-gradient(135deg, #FF7D00, #F53F3F);
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}

.auth-card {
  background: rgba(15, 23, 42, 0.9);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(51, 65, 85, 0.8);
  border-radius: 20px;
  padding: 40px;
  width: 100%;
  max-width: 440px;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
  position: relative;
  z-index: 10;
  margin-right: 60px;
}

.auth-header {
  text-align: center;
  margin-bottom: 32px;
}

.logo {
  width: 70px;
  height: 70px;
  margin: 0 auto 16px;
  background: linear-gradient(135deg, #165DFF, #00B42A);
  border-radius: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 10px 30px rgba(22, 93, 255, 0.4);
}

.logo-icon {
  width: 40px;
  height: 40px;
  color: white;
}

.title {
  font-size: 28px;
  font-weight: 700;
  color: #FFFFFF;
  margin: 0 0 8px 0;
  letter-spacing: -0.5px;
}

.subtitle {
  font-size: 14px;
  color: #94A3B8;
  margin: 0;
}

.auth-tabs {
  display: flex;
  background: rgba(30, 41, 59, 0.8);
  border-radius: 12px;
  padding: 4px;
  margin-bottom: 28px;
}

.tab-btn {
  flex: 1;
  padding: 12px;
  border: none;
  background: transparent;
  color: #94A3B8;
  font-size: 15px;
  font-weight: 500;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.tab-btn.active {
  background: linear-gradient(135deg, #165DFF, #00B42A);
  color: white;
  box-shadow: 0 4px 12px rgba(22, 93, 255, 0.3);
}

.auth-form {
  margin-bottom: 20px;
}

:deep(.el-form-item) {
  margin-bottom: 20px;
}

:deep(.el-input__wrapper) {
  background: rgba(30, 41, 59, 0.8);
  border: 1px solid #334155;
  box-shadow: none;
  border-radius: 10px;
  padding: 4px 12px;
}

:deep(.el-input__wrapper:hover) {
  border-color: #165DFF;
}

:deep(.el-input__wrapper.is-focus) {
  border-color: #165DFF;
  box-shadow: 0 0 0 3px rgba(22, 93, 255, 0.15);
}

:deep(.el-input__inner) {
  color: #FFFFFF;
}

:deep(.el-input__inner::placeholder) {
  color: #64748B;
}

:deep(.el-input__prefix-inner) {
  color: #64748B;
}

.submit-btn {
  width: 100%;
  height: 48px;
  font-size: 16px;
  font-weight: 600;
  background: linear-gradient(135deg, #165DFF, #00B42A);
  border: none;
  border-radius: 10px;
  margin-top: 8px;
  transition: all 0.3s ease;
}

.submit-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 25px rgba(22, 93, 255, 0.4);
}

.btn-icon {
  margin-right: 8px;
}

.demo-login {
  margin-top: 24px;
}

.divider {
  display: flex;
  align-items: center;
  margin: 20px 0;
  color: #64748B;
  font-size: 12px;
}

.divider::before,
.divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: #334155;
}

.divider span {
  padding: 0 16px;
}

.demo-btn {
  width: 100%;
  height: 44px;
  font-size: 14px;
  font-weight: 500;
  background: rgba(22, 93, 255, 0.1);
  border: 1px solid rgba(22, 93, 255, 0.3);
  color: #165DFF;
  border-radius: 10px;
  transition: all 0.3s ease;
}

.demo-btn:hover {
  background: rgba(22, 93, 255, 0.2);
  border-color: #165DFF;
}

.demo-hint {
  text-align: center;
  color: #64748B;
  font-size: 12px;
  margin: 12px 0 0 0;
}

.auth-footer {
  text-align: center;
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid #334155;
}

.auth-footer p {
  color: #94A3B8;
  font-size: 14px;
  margin: 0;
}

.link {
  color: #165DFF;
  cursor: pointer;
  font-weight: 500;
  transition: color 0.2s ease;
}

.link:hover {
  color: #3D7FFF;
}

.feature-cards {
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-width: 320px;
}

.feature-card {
  background: rgba(15, 23, 42, 0.8);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(51, 65, 85, 0.5);
  border-radius: 16px;
  padding: 24px;
  transition: all 0.3s ease;
}

.feature-card:hover {
  transform: translateX(5px);
  border-color: rgba(22, 93, 255, 0.5);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
}

.feature-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.feature-icon svg {
  width: 24px;
  height: 24px;
  color: white;
}

.feature-icon.blue {
  background: linear-gradient(135deg, rgba(22, 93, 255, 0.2), rgba(114, 46, 209, 0.2));
  color: #165DFF;
}

.feature-icon.green {
  background: linear-gradient(135deg, rgba(0, 180, 42, 0.2), rgba(20, 201, 201, 0.2));
  color: #00B42A;
}

.feature-icon.orange {
  background: linear-gradient(135deg, rgba(255, 125, 0, 0.2), rgba(245, 63, 63, 0.2));
  color: #FF7D00;
}

.feature-card h3 {
  color: #FFFFFF;
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 8px 0;
}

.feature-card p {
  color: #94A3B8;
  font-size: 13px;
  margin: 0;
  line-height: 1.6;
}

@media (max-width: 1024px) {
  .auth-container {
    flex-direction: column;
    gap: 40px;
  }
  
  .auth-card {
    margin-right: 0;
  }
  
  .feature-cards {
    flex-direction: row;
    max-width: none;
    gap: 16px;
  }
  
  .feature-card {
    flex: 1;
  }
}

@media (max-width: 640px) {
  .auth-card {
    padding: 30px 24px;
  }
  
  .feature-cards {
    flex-direction: column;
    width: 100%;
    max-width: 440px;
  }
}
</style>
