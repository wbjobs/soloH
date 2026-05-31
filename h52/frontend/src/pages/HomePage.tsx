import { Link } from 'react-router-dom';
import { Video, Zap, BarChart3, Brain, Sparkles, ArrowRight, Layers, Eye, MessageSquare } from 'lucide-react';

export function HomePage() {
  const features = [
    {
      icon: Video,
      title: '视频情感分析',
      description: '通过WebRTC录制用户视频，自动提取多模态特征进行深度情感分析',
      color: 'from-blue-500 to-cyan-500',
    },
    {
      icon: Layers,
      title: '多模态融合',
      description: '融合语音、面部表情、文本三种模态，使用跨模态注意力提升准确率',
      color: 'from-purple-500 to-pink-500',
    },
    {
      icon: Eye,
      title: '可解释性AI',
      description: '提供注意力权重热图和模态贡献度分析，让AI决策透明可理解',
      color: 'from-green-500 to-emerald-500',
    },
    {
      icon: Zap,
      title: '实时流式预测',
      description: '支持WebSocket实时传输，动态可视化情感时序变化过程',
      color: 'from-yellow-500 to-orange-500',
    },
    {
      icon: BarChart3,
      title: '效价唤醒度',
      description: '输出连续维度的情感度量，超越简单分类的细粒度情感分析',
      color: 'from-red-500 to-rose-500',
    },
    {
      icon: MessageSquare,
      title: 'ASR语音转写',
      description: '自动将语音内容转换为文本，丰富情感分析的上下文信息',
      color: 'from-indigo-500 to-violet-500',
    },
  ];

  const modalities = [
    {
      name: '语音特征',
      icon: '🎵',
      model: 'wav2vec2',
      description: '提取语音韵律、音调、语速等声学特征',
      color: '#667eea',
    },
    {
      name: '面部表情',
      icon: '😊',
      model: 'MediaPipe',
      description: '捕捉面部关键点、肌肉运动、微表情变化',
      color: '#f093fb',
    },
    {
      name: '文本内容',
      icon: '📝',
      model: 'BERT + Whisper',
      description: '语音转写后提取语义情感特征',
      color: '#4facfe',
    },
  ];

  const emotions = [
    { name: '愤怒', emoji: '😠', color: '#e74c3c' },
    { name: '快乐', emoji: '😊', color: '#f1c40f' },
    { name: '悲伤', emoji: '😢', color: '#3498db' },
    { name: '惊讶', emoji: '😮', color: '#e67e22' },
    { name: '厌恶', emoji: '🤢', color: '#27ae60' },
    { name: '恐惧', emoji: '😨', color: '#9b59b6' },
    { name: '中性', emoji: '😐', color: '#95a5a6' },
  ];

  return (
    <div className="min-h-screen">
      <section className="relative py-32 overflow-hidden">
        <div className="absolute inset-0 grid-overlay opacity-50 pointer-events-none" />
        <div className="absolute top-20 left-1/4 w-96 h-96 bg-primary/20 rounded-full blur-3xl animate-pulse-slow" />
        <div className="absolute bottom-20 right-1/4 w-96 h-96 bg-secondary/20 rounded-full blur-3xl animate-pulse-slow" style={{ animationDelay: '1s' }} />

        <div className="container mx-auto px-4 relative z-10">
          <div className="text-center max-w-4xl mx-auto">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/30 mb-8 animate-fade-in">
              <Sparkles className="w-4 h-4 text-primary" />
              <span className="text-sm text-primary">基于Transformer的多模态情感分析</span>
            </div>

            <h1 className="text-5xl md:text-7xl font-bold font-display mb-6 animate-slide-up">
              <span className="text-foreground">理解情感的</span>
              <br />
              <span className="text-gradient">每一个维度</span>
            </h1>

            <p className="text-xl text-muted-foreground mb-10 max-w-2xl mx-auto animate-slide-up" style={{ animationDelay: '100ms' }}>
              融合语音、面部表情、文本三种模态，通过跨模态注意力实现精准的情感识别，
              同时提供完整的可解释性分析。
            </p>

            <div className="flex flex-wrap items-center justify-center gap-4 animate-slide-up" style={{ animationDelay: '200ms' }}>
              <Link to="/record" className="btn-primary flex items-center gap-2 text-lg px-8 py-4">
                <Video className="w-5 h-5" />
                开始录制分析
                <ArrowRight className="w-5 h-5" />
              </Link>
              <Link to="/realtime" className="btn-secondary flex items-center gap-2 text-lg px-8 py-4">
                <Zap className="w-5 h-5" />
                实时分析
              </Link>
            </div>
          </div>

          <div className="mt-20 flex flex-wrap items-center justify-center gap-8 animate-fade-in" style={{ animationDelay: '300ms' }}>
            {emotions.map((emotion, index) => (
              <div
                key={emotion.name}
                className="flex flex-col items-center gap-2 group"
                style={{ animationDelay: `${index * 100}ms` }}
              >
                <div
                  className="w-16 h-16 rounded-full flex items-center justify-center text-3xl transition-all duration-300 group-hover:scale-125 group-hover:animate-breathe"
                  style={{
                    backgroundColor: `${emotion.color}20`,
                    boxShadow: `0 0 30px ${emotion.color}40`,
                  }}
                >
                  {emotion.emoji}
                </div>
                <span className="text-sm text-muted-foreground">{emotion.name}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="py-20">
        <div className="container mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold font-display mb-4">
              技术架构
            </h2>
            <p className="text-muted-foreground max-w-2xl mx-auto">
              采用前沿的深度学习技术，从三个不同模态提取情感特征，通过跨模态Transformer实现高级融合
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6 mb-16">
            {modalities.map((modality, index) => (
              <div
                key={modality.name}
                className="glass-card-hover p-8 text-center animate-slide-up"
                style={{ animationDelay: `${index * 100}ms` }}
              >
                <div
                  className="w-20 h-20 rounded-2xl flex items-center justify-center text-4xl mx-auto mb-6"
                  style={{ backgroundColor: `${modality.color}20` }}
                >
                  {modality.icon}
                </div>
                <h3 className="text-xl font-bold mb-2" style={{ color: modality.color }}>
                  {modality.name}
                </h3>
                <p className="text-sm text-primary font-mono mb-3">
                  {modality.model}
                </p>
                <p className="text-muted-foreground text-sm">
                  {modality.description}
                </p>
              </div>
            ))}
          </div>

          <div className="text-center mb-8">
            <div className="inline-flex items-center gap-3 text-2xl font-bold text-gradient">
              <span>跨模态注意力融合</span>
              <Brain className="w-8 h-8" />
              <span>Transformer</span>
            </div>
            <div className="mt-4 max-w-3xl mx-auto">
              <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                <div className="h-full bg-gradient-primary rounded-full animate-pulse-slow" style={{ width: '100%' }} />
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="py-20 bg-gradient-to-b from-transparent via-primary/5 to-transparent">
        <div className="container mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold font-display mb-4">
              核心功能
            </h2>
            <p className="text-muted-foreground max-w-2xl mx-auto">
              全面的情感分析能力，从数据采集到可视化展示的完整解决方案
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((feature, index) => (
              <div
                key={feature.title}
                className="glass-card-hover p-6 animate-slide-up"
                style={{ animationDelay: `${index * 100}ms` }}
              >
                <div className={`w-14 h-14 rounded-2xl bg-gradient-to-br ${feature.color} flex items-center justify-center mb-4`}>
                  <feature.icon className="w-7 h-7 text-white" />
                </div>
                <h3 className="text-xl font-bold mb-2">{feature.title}</h3>
                <p className="text-muted-foreground text-sm">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="py-20">
        <div className="container mx-auto px-4">
          <div className="glass-card p-8 md:p-12 text-center relative overflow-hidden">
            <div className="absolute inset-0 bg-gradient-primary opacity-10" />
            <div className="relative z-10">
              <h2 className="text-3xl md:text-4xl font-bold font-display mb-6">
                准备好开始分析了吗？
              </h2>
              <p className="text-muted-foreground max-w-xl mx-auto mb-8">
                只需1分钟，录制一段视频，即可获得深度多模态情感分析报告。
                支持7种情感分类、效价唤醒度预测、模态贡献度解释。
              </p>
              <div className="flex flex-wrap items-center justify-center gap-4">
                <Link to="/record" className="btn-primary flex items-center gap-2 px-8 py-4">
                  <Video className="w-5 h-5" />
                  立即体验
                </Link>
                <Link to="/history" className="btn-secondary flex items-center gap-2 px-8 py-4">
                  <BarChart3 className="w-5 h-5" />
                  查看历史记录
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      <footer className="py-8 border-t border-white/10">
        <div className="container mx-auto px-4 text-center text-sm text-muted-foreground">
          <p>EmotionAI © 2024 - 多模态情感分析系统 | 基于 React + FastAPI + PyTorch 构建</p>
        </div>
      </footer>
    </div>
  );
}

export default HomePage;
