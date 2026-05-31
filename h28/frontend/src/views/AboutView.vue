<template>
  <div class="about-view">
    <section class="about-hero">
      <div class="about-content">
        <h1 class="about-title">关于古籍文字识别</h1>
        <p class="about-subtitle">传承 · 保护 · 研究</p>
      </div>
    </section>

    <div class="about-container">
      <section class="about-section">
        <h2 class="section-title">项目背景</h2>
        <p class="section-text">
          古籍是中华文明的重要载体，承载着数千年的历史与智慧。然而，由于年代久远、保存条件等因素，
          大量古籍文献正面临着老化、损坏的威胁。数字化保护是古籍传承的重要手段，而文字识别技术
          则是古籍数字化的核心环节。
        </p>
        <p class="section-text">
          本系统采用深度学习技术，针对古籍文献的特点（繁体中文、竖排版式、异体字多、背景复杂等）
          进行专项优化，实现高精度的古籍文字自动识别，助力古籍数字化保护与学术研究。
        </p>
      </section>

      <section class="about-section">
        <h2 class="section-title">技术架构</h2>
        <div class="tech-stack">
          <div class="tech-category">
            <h3>前端技术</h3>
            <ul>
              <li><strong>Vue 3</strong> - 渐进式前端框架</li>
              <li><strong>TypeScript</strong> - 类型安全的JavaScript</li>
              <li><strong>Element Plus</strong> - 基于Vue 3的组件库</li>
              <li><strong>Pinia</strong> - 状态管理</li>
              <li><strong>Socket.IO</strong> - 实时通信</li>
              <li><strong>Tesseract.js</strong> - 浏览器端OCR</li>
            </ul>
          </div>
          <div class="tech-category">
            <h3>后端技术</h3>
            <ul>
              <li><strong>Python</strong> - 主要开发语言</li>
              <li><strong>FastAPI</strong> - 高性能Web框架</li>
              <li><strong>PyTorch</strong> - 深度学习框架</li>
              <li><strong>PaddleOCR</strong> - 文字检测与识别</li>
              <li><strong>WebSocket</strong> - 实时进度推送</li>
            </ul>
          </div>
          <div class="tech-category">
            <h3>核心算法</h3>
            <ul>
              <li><strong>DBnet</strong> - 文本检测</li>
              <li><strong>CRNN</strong> - 文本识别</li>
              <li><strong>语言模型</strong> - 候选词推荐</li>
              <li><strong>版面分析</strong> - 版式结构理解</li>
            </ul>
          </div>
        </div>
      </section>

      <section class="about-section">
        <h2 class="section-title">功能特色</h2>
        <div class="features-grid">
          <div class="feature-item">
            <div class="feature-icon">
              <icon-park theme="outline" size="36" name="high-quality" :fill="['#C41E3A']" />
            </div>
            <h3>高精度识别</h3>
            <p>针对古籍优化的深度学习模型，识别准确率达98%以上</p>
          </div>
          <div class="feature-item">
            <div class="feature-icon">
              <icon-park theme="outline" size="36" name="two-columns" :fill="['#C41E3A']" />
            </div>
            <h3>双栏校对</h3>
            <p>左图右文对照编辑，所见即所得的校对体验</p>
          </div>
          <div class="feature-item">
            <div class="feature-icon">
              <icon-park theme="outline" size="36" name="chinese" :fill="['#C41E3A']" />
            </div>
            <h3>繁简支持</h3>
            <p>支持繁体、简体、异体字识别，覆盖各类古籍文献</p>
          </div>
          <div class="feature-item">
            <div class="feature-icon">
              <icon-park theme="outline" size="36" name="web-page" :fill="['#C41E3A']" />
            </div>
            <h3>版式还原</h3>
            <p>支持竖排、横排等多种版式，保留原文阅读顺序</p>
          </div>
          <div class="feature-item">
            <div class="feature-icon">
              <icon-park theme="outline" size="36" name="magic-stick" :fill="['#C41E3A']" />
            </div>
            <h3>智能推荐</h3>
            <p>基于语言模型的候选词推荐，提高校对效率</p>
          </div>
          <div class="feature-item">
            <div class="feature-icon">
              <icon-park theme="outline" size="36" name="offline" :fill="['#C41E3A']" />
            </div>
            <h3>离线可用</h3>
            <p>内置Tesseract.js降级方案，网络不畅也可使用</p>
          </div>
        </div>
      </section>

      <section class="about-section">
        <h2 class="section-title">使用说明</h2>
        <div class="usage-steps">
          <div class="step">
            <div class="step-number">1</div>
            <div class="step-content">
              <h3>上传文件</h3>
              <p>支持JPG、PNG、TIFF等图片格式，以及PDF文档</p>
            </div>
          </div>
          <div class="step">
            <div class="step-number">2</div>
            <div class="step-content">
              <h3>等待识别</h3>
              <p>系统自动进行文字检测与识别，可实时查看进度</p>
            </div>
          </div>
          <div class="step">
            <div class="step-number">3</div>
            <div class="step-content">
              <h3>校对编辑</h3>
              <p>点击文字进行修改，选择候选词快速纠错</p>
            </div>
          </div>
          <div class="step">
            <div class="step-number">4</div>
            <div class="step-content">
              <h3>导出结果</h3>
              <p>支持TXT、DOCX、PDF、JSON等多种格式导出</p>
            </div>
          </div>
        </div>
      </section>

      <section class="about-section contact-section">
        <h2 class="section-title">联系我们</h2>
        <p class="section-text">
          如有问题或建议，欢迎通过以下方式联系我们：
        </p>
        <div class="contact-info">
          <div class="contact-item">
            <icon-park theme="outline" size="24" name="mail" :fill="['#C41E3A']" />
            <span>contact@guji-ocr.example.com</span>
          </div>
          <div class="contact-item">
            <icon-park theme="outline" size="24" name="github" :fill="['#C41E3A']" />
            <span>github.com/guji-ocr</span>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
</script>

<style lang="scss" scoped>
.about-view {
  min-height: 100vh;
  background: #FAF7F2;
}

.about-hero {
  background: linear-gradient(135deg, #F5F0E6 0%, #EDE4D3 100%);
  padding: 80px 40px;
  text-align: center;
}

.about-title {
  font-family: 'Noto Serif SC', serif;
  font-size: 48px;
  font-weight: 700;
  color: #2C1810;
  margin: 0 0 12px 0;
  letter-spacing: 8px;
}

.about-subtitle {
  font-size: 18px;
  color: #C41E3A;
  margin: 0;
  letter-spacing: 4px;
}

.about-container {
  max-width: 1000px;
  margin: 0 auto;
  padding: 40px;
}

.about-section {
  background: #FFF;
  border-radius: 12px;
  padding: 40px;
  margin-bottom: 24px;
  border: 1px solid #E8DFD0;
}

.section-title {
  font-family: 'Noto Serif SC', serif;
  font-size: 24px;
  font-weight: 600;
  color: #2C1810;
  margin: 0 0 20px 0;
  padding-bottom: 12px;
  border-bottom: 2px solid #C41E3A;
  display: inline-block;
}

.section-text {
  font-size: 15px;
  line-height: 1.8;
  color: #5C4033;
  margin: 0 0 16px 0;

  &:last-child {
    margin-bottom: 0;
  }
}

.tech-stack {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 24px;
  margin-top: 24px;
}

.tech-category {
  background: #FAF7F2;
  padding: 24px;
  border-radius: 8px;

  h3 {
    font-family: 'Noto Serif SC', serif;
    font-size: 16px;
    font-weight: 600;
    color: #C41E3A;
    margin: 0 0 16px 0;
  }

  ul {
    list-style: none;
    padding: 0;
    margin: 0;
  }

  li {
    font-size: 14px;
    color: #5C4033;
    padding: 8px 0;
    border-bottom: 1px dashed #E8DFD0;

    &:last-child {
      border-bottom: none;
    }

    strong {
      color: #2C1810;
      margin-right: 8px;
    }
  }
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 20px;
  margin-top: 24px;
}

.feature-item {
  display: flex;
  gap: 16px;
  padding: 20px;
  background: #FAF7F2;
  border-radius: 8px;
  transition: all 0.3s ease;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(196, 30, 58, 0.08);
  }

  h3 {
    font-family: 'Noto Serif SC', serif;
    font-size: 16px;
    font-weight: 600;
    color: #2C1810;
    margin: 0 0 8px 0;
  }

  p {
    font-size: 13px;
    color: #6B5B4F;
    margin: 0;
    line-height: 1.6;
  }
}

.feature-icon {
  flex-shrink: 0;
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #FFF;
  border-radius: 8px;
}

.usage-steps {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 20px;
  margin-top: 24px;
}

.step {
  display: flex;
  gap: 16px;
  padding: 20px;
  background: #FAF7F2;
  border-radius: 8px;
  border-left: 3px solid #C41E3A;
}

.step-number {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #C41E3A;
  color: #FFF;
  font-size: 18px;
  font-weight: 700;
  border-radius: 50%;
  flex-shrink: 0;
  font-family: 'Noto Serif SC', serif;
}

.step-content h3 {
  font-family: 'Noto Serif SC', serif;
  font-size: 16px;
  font-weight: 600;
  color: #2C1810;
  margin: 0 0 8px 0;
}

.step-content p {
  font-size: 13px;
  color: #6B5B4F;
  margin: 0;
  line-height: 1.6;
}

.contact-section {
  text-align: center;
}

.contact-info {
  display: flex;
  justify-content: center;
  gap: 40px;
  margin-top: 24px;
  flex-wrap: wrap;
}

.contact-item {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 15px;
  color: #5C4033;
}

@media (max-width: 768px) {
  .about-hero {
    padding: 48px 20px;
  }

  .about-title {
    font-size: 32px;
    letter-spacing: 4px;
  }

  .about-container {
    padding: 20px;
  }

  .about-section {
    padding: 24px;
  }

  .tech-stack,
  .features-grid,
  .usage-steps {
    grid-template-columns: 1fr;
  }

  .contact-info {
    flex-direction: column;
    gap: 16px;
  }
}
</style>
