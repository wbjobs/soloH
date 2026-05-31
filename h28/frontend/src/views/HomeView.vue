<template>
  <div class="home-view">
    <section class="hero-section">
      <div class="hero-content">
        <h1 class="hero-title">古籍文字识别</h1>
        <p class="hero-subtitle">传承中华文化 · 智能文献数字化</p>
        <p class="hero-description">
          基于深度学习的古籍OCR系统，支持繁体中文识别，
          高精度文字检测与识别，助力古籍数字化保护与研究。
        </p>
        <div class="hero-actions">
          <el-button type="primary" size="large" @click="scrollToUpload">
            开始识别
          </el-button>
          <el-button size="large" @click="$router.push('/tasks')">
            查看任务
          </el-button>
        </div>
      </div>
      <div class="hero-decoration">
        <div class="scroll-pattern"></div>
      </div>
    </section>

    <section id="upload-section" class="upload-section">
      <div class="section-header">
        <h2 class="section-title">上传古籍图片</h2>
        <p class="section-subtitle">支持单张图片或PDF文档上传</p>
      </div>
      <UploadArea @upload-start="handleUploadStart" @upload-success="handleUploadSuccess" />
      <ProgressPanel v-if="uploadingTaskId" :task-id="uploadingTaskId" @completed="handleUploadCompleted" />
    </section>

    <section class="features-section">
      <div class="section-header">
        <h2 class="section-title">核心功能</h2>
        <p class="section-subtitle">专业的古籍数字化解决方案</p>
      </div>
      <div class="features-grid">
        <div class="feature-card">
          <div class="feature-icon">
            <icon-park theme="outline" size="48" name="scan" :fill="['#C41E3A']" />
          </div>
          <h3 class="feature-title">高精度识别</h3>
          <p class="feature-desc">
            针对古籍文献特点训练的深度学习模型，支持繁、简、异体字识别，准确率达98%以上。
          </p>
        </div>
        <div class="feature-card">
          <div class="feature-icon">
            <icon-park theme="outline" size="48" name="edit" :fill="['#C41E3A']" />
          </div>
          <h3 class="feature-title">智能校对</h3>
          <p class="feature-desc">
            左右双栏校对编辑器，左图右文对照，点击文字即可修改，候选词智能推荐。
          </p>
        </div>
        <div class="feature-card">
          <div class="feature-icon">
            <icon-park theme="outline" size="48" name="text" :fill="['#C41E3A']" />
          </div>
          <h3 class="feature-title">竖排支持</h3>
          <p class="feature-desc">
            支持传统竖排版式检测与识别，保留原文献阅读顺序和版式结构。
          </p>
        </div>
        <div class="feature-card">
          <div class="feature-icon">
            <icon-park theme="outline" size="48" name="download" :fill="['#C41E3A']" />
          </div>
          <h3 class="feature-title">多格式导出</h3>
          <p class="feature-desc">
            支持TXT、DOCX、PDF、JSON等多种格式导出，满足不同研究需求。
          </p>
        </div>
        <div class="feature-card">
          <div class="feature-icon">
            <icon-park theme="outline" size="48" name="web-page" :fill="['#C41E3A']" />
          </div>
          <h3 class="feature-title">批量处理</h3>
          <p class="feature-desc">
            支持PDF多页文档批量上传与处理，实时进度推送，高效处理大型文献。
          </p>
        </div>
        <div class="feature-card">
          <div class="feature-icon">
            <icon-park theme="outline" size="48" name="offline" :fill="['#C41E3A']" />
          </div>
          <h3 class="feature-title">离线识别</h3>
          <p class="feature-desc">
            内置Tesseract.js降级方案，网络不畅时也可在浏览器端完成OCR识别。
          </p>
        </div>
      </div>
    </section>

    <section class="workflow-section">
      <div class="section-header">
        <h2 class="section-title">使用流程</h2>
        <p class="section-subtitle">三步完成古籍数字化</p>
      </div>
      <div class="workflow-steps">
        <div class="step-item">
          <div class="step-number">1</div>
          <div class="step-content">
            <h3>上传文件</h3>
            <p>上传古籍扫描图片或PDF文档</p>
          </div>
        </div>
        <div class="step-arrow">→</div>
        <div class="step-item">
          <div class="step-number">2</div>
          <div class="step-content">
            <h3>AI识别</h3>
            <p>系统自动进行版式分析与文字识别</p>
          </div>
        </div>
        <div class="step-arrow">→</div>
        <div class="step-item">
          <div class="step-number">3</div>
          <div class="step-content">
            <h3>校对导出</h3>
            <p>在线校对编辑，导出所需格式</p>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import UploadArea from '../components/UploadArea.vue';
import ProgressPanel from '../components/ProgressPanel.vue';
import { useTaskStore } from '../stores/task';
import type { UploadResponse } from '../types';

const router = useRouter();
const taskStore = useTaskStore();
const uploadingTaskId = ref<string | null>(null);

const scrollToUpload = () => {
  const el = document.getElementById('upload-section');
  el?.scrollIntoView({ behavior: 'smooth' });
};

const handleUploadStart = (taskId: string) => {
  uploadingTaskId.value = taskId;
};

const handleUploadSuccess = (response: UploadResponse) => {
  ElMessage.success('上传成功，开始识别...');
  taskStore.subscribeToTask(response.taskId);
};

const handleUploadCompleted = (taskId: string) => {
  ElMessage.success('识别完成！');
  setTimeout(() => {
    router.push(`/task/${taskId}`);
  }, 1000);
};
</script>

<style lang="scss" scoped>
.home-view {
  min-height: 100vh;
}

.hero-section {
  position: relative;
  padding: 80px 40px 100px;
  background: linear-gradient(135deg, #F5F0E6 0%, #EDE4D3 100%);
  overflow: hidden;

  &::before {
    content: '';
    position: absolute;
    top: -50%;
    right: -10%;
    width: 600px;
    height: 600px;
    background: radial-gradient(circle, rgba(196, 30, 58, 0.08) 0%, transparent 70%);
    border-radius: 50%;
  }
}

.hero-content {
  position: relative;
  max-width: 800px;
  z-index: 1;
}

.hero-title {
  font-family: 'Noto Serif SC', 'Source Han Serif SC', serif;
  font-size: 56px;
  font-weight: 700;
  color: #2C1810;
  margin: 0 0 16px 0;
  letter-spacing: 8px;
}

.hero-subtitle {
  font-size: 20px;
  color: #C41E3A;
  margin: 0 0 24px 0;
  letter-spacing: 4px;
}

.hero-description {
  font-size: 16px;
  line-height: 1.8;
  color: #5C4033;
  margin: 0 0 40px 0;
  max-width: 600px;
}

.hero-actions {
  display: flex;
  gap: 16px;

  .el-button {
    min-width: 140px;
    height: 48px;
    font-size: 16px;
  }

  .el-button--primary {
    background-color: #C41E3A;
    border-color: #C41E3A;

    &:hover {
      background-color: #A0182E;
      border-color: #A0182E;
    }
  }
}

.hero-decoration {
  position: absolute;
  top: 40px;
  right: 80px;
  width: 300px;
  height: 400px;
  opacity: 0.1;
}

.scroll-pattern {
  width: 100%;
  height: 100%;
  background-image: 
    repeating-linear-gradient(
      0deg,
      #C41E3A,
      #C41E3A 2px,
      transparent 2px,
      transparent 20px
    );
  border-radius: 8px;
}

.upload-section,
.features-section,
.workflow-section {
  padding: 80px 40px;
}

.upload-section {
  background: #FFF;
}

.features-section {
  background: #FAF7F2;
}

.workflow-section {
  background: #FFF;
}

.section-header {
  text-align: center;
  margin-bottom: 48px;
}

.section-title {
  font-family: 'Noto Serif SC', 'Source Han Serif SC', serif;
  font-size: 36px;
  font-weight: 600;
  color: #2C1810;
  margin: 0 0 12px 0;
}

.section-subtitle {
  font-size: 16px;
  color: #8B7355;
  margin: 0;
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 32px;
  max-width: 1200px;
  margin: 0 auto;
}

.feature-card {
  background: #FFF;
  padding: 32px;
  border-radius: 12px;
  border: 1px solid #E8DFD0;
  transition: all 0.3s ease;

  &:hover {
    transform: translateY(-4px);
    box-shadow: 0 12px 32px rgba(196, 30, 58, 0.1);
    border-color: #C41E3A;
  }
}

.feature-icon {
  width: 80px;
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #FDF5E6;
  border-radius: 12px;
  margin-bottom: 20px;
}

.feature-title {
  font-family: 'Noto Serif SC', serif;
  font-size: 20px;
  font-weight: 600;
  color: #2C1810;
  margin: 0 0 12px 0;
}

.feature-desc {
  font-size: 14px;
  line-height: 1.7;
  color: #6B5B4F;
  margin: 0;
}

.workflow-steps {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 24px;
  max-width: 1000px;
  margin: 0 auto;
  flex-wrap: wrap;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 16px;
  background: #FAF7F2;
  padding: 24px 32px;
  border-radius: 12px;
  border: 1px solid #E8DFD0;
}

.step-number {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #C41E3A;
  color: #FFF;
  font-size: 24px;
  font-weight: 700;
  border-radius: 50%;
  font-family: 'Noto Serif SC', serif;
}

.step-content h3 {
  font-family: 'Noto Serif SC', serif;
  font-size: 18px;
  font-weight: 600;
  color: #2C1810;
  margin: 0 0 4px 0;
}

.step-content p {
  font-size: 14px;
  color: #8B7355;
  margin: 0;
}

.step-arrow {
  font-size: 32px;
  color: #C41E3A;
  font-weight: 300;
}

@media (max-width: 768px) {
  .hero-section {
    padding: 40px 20px 60px;
  }

  .hero-title {
    font-size: 36px;
    letter-spacing: 4px;
  }

  .hero-subtitle {
    font-size: 16px;
  }

  .upload-section,
  .features-section,
  .workflow-section {
    padding: 48px 20px;
  }

  .section-title {
    font-size: 28px;
  }

  .workflow-steps {
    flex-direction: column;
  }

  .step-arrow {
    transform: rotate(90deg);
  }
}
</style>
