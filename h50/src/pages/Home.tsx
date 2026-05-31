import { useNavigate } from 'react-router-dom';
import { Upload, Music2, FileText, Edit3, ArrowRight } from 'lucide-react';

export default function Home() {
  const navigate = useNavigate();

  const features = [
    {
      icon: <Upload className="w-8 h-8" />,
      title: '谱图上传',
      description: '支持竖排减字谱扫描图上传，自动预处理与版式识别',
      color: 'from-tanmu to-tanmu-light'
    },
    {
      icon: <Edit3 className="w-8 h-8" />,
      title: '智能识别',
      description: '基于深度学习的减字检测与组件识别，支持人工校对',
      color: 'from-zhusha to-zhusha-light'
    },
    {
      icon: <Music2 className="w-8 h-8" />,
      title: '音频合成',
      description: '基于采样的古琴音色合成，支持散音、按音、泛音三种技法',
      color: 'from-tanmu to-tanmu-light'
    },
    {
      icon: <FileText className="w-8 h-8" />,
      title: '多格式导出',
      description: '支持MIDI、音频、工尺谱对照、指法说明等多种格式导出',
      color: 'from-zhusha to-zhusha-light'
    }
  ];

  const steps = [
    { step: 1, title: '上传谱图', desc: '上传竖排减字谱扫描图像' },
    { step: 2, title: '智能识别', desc: 'AI自动检测分割并识别减字' },
    { step: 3, title: '人工校对', desc: '在谱面编辑器中修正识别结果' },
    { step: 4, title: '合成导出', desc: '合成古琴音频并导出所需格式' }
  ];

  return (
    <div className="min-h-screen xuanzhi-bg">
      <nav className="px-8 py-4 flex items-center justify-between border-b border-tanmu/20">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-tanmu to-tanmu-light flex items-center justify-center">
            <Music2 className="w-5 h-5 text-xuanzhi" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-tanmu-dark">古琴减字谱智能识别系统</h1>
            <p className="text-xs text-tanmu/60">Guqin Jianzi Notation Recognition</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/upload')}
            className="btn-classical text-sm"
          >
            开始使用
          </button>
        </div>
      </nav>

      <section className="px-8 py-20">
        <div className="max-w-6xl mx-auto">
          <div className="grid md:grid-cols-2 gap-12 items-center">
            <div className="animate-fade-in-up">
              <div className="inline-block px-4 py-1 rounded-full bg-tanmu/10 text-tanmu text-sm mb-6">
                🎵 传承千年古琴文化
              </div>
              <h2 className="text-4xl md:text-5xl font-bold text-tanmu-dark mb-6 leading-tight">
                让古老的减字谱<br />
                <span className="text-zhusha">奏响现代之声</span>
              </h2>
              <p className="text-lg text-tanmu/70 mb-8 leading-relaxed">
                上传您的减字谱扫描图，系统将自动识别减字、合成古琴音频，
                并提供工尺谱对照与详细指法说明，让古琴学习更加简单直观。
              </p>
              <div className="flex items-center gap-4">
                <button
                  onClick={() => navigate('/upload')}
                  className="btn-zhusha flex items-center gap-2 text-base px-8 py-3"
                >
                  立即开始 <ArrowRight className="w-5 h-5" />
                </button>
                <button
                  onClick={() => navigate('/editor')}
                  className="btn-outline flex items-center gap-2 text-base px-8 py-3"
                >
                  查看演示
                </button>
              </div>
            </div>

            <div className="relative animate-fade-in-up" style={{ animationDelay: '0.2s' }}>
              <div className="scroll-border p-8 bg-xuanzhi">
                <div className="aspect-[3/4] bg-gradient-to-br from-xuanzhi to-xuanzhi-dark rounded-lg flex flex-col items-center justify-center relative overflow-hidden">
                  <div className="absolute inset-0 opacity-10">
                    <div className="absolute top-8 left-8 text-6xl font-bold text-tanmu jianzi-char">散</div>
                    <div className="absolute top-8 right-8 text-6xl font-bold text-tanmu jianzi-char">勾</div>
                    <div className="absolute bottom-8 left-8 text-6xl font-bold text-tanmu jianzi-char">挑</div>
                    <div className="absolute bottom-8 right-8 text-6xl font-bold text-tanmu jianzi-char">按</div>
                  </div>
                  
                  <div className="relative z-10 text-center">
                    <div className="text-8xl mb-4 jianzi-char text-tanmu-dark">琴</div>
                    <p className="text-tanmu/60 text-lg">减字谱识别 · 音频合成</p>
                  </div>

                  <div className="absolute bottom-4 left-4 right-4 flex justify-between text-xs text-tanmu/50">
                    <span>七弦</span>
                    <span>十三徽</span>
                    <span>五音</span>
                  </div>
                </div>
              </div>
              
              <div className="absolute -top-4 -right-4 w-24 h-24 bg-zhusha/10 rounded-full blur-2xl"></div>
              <div className="absolute -bottom-4 -left-4 w-32 h-32 bg-tanmu/10 rounded-full blur-2xl"></div>
            </div>
          </div>
        </div>
      </section>

      <section className="px-8 py-16 bg-xuanzhi-dark/50">
        <div className="max-w-6xl mx-auto">
          <h3 className="text-2xl font-bold text-center text-tanmu-dark mb-4">核心功能</h3>
          <p className="text-center text-tanmu/60 mb-12">智能识别 · 精准合成 · 便捷导出</p>
          
          <div className="grid md:grid-cols-4 gap-6">
            {features.map((feature, index) => (
              <div
                key={index}
                className="card-classical text-center group hover:-translate-y-2"
                style={{ animationDelay: `${index * 0.1}s` }}
              >
                <div className={`w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br ${feature.color} flex items-center justify-center text-white shadow-lg group-hover:scale-110 transition-transform duration-300`}>
                  {feature.icon}
                </div>
                <h4 className="text-lg font-bold text-tanmu-dark mb-2">{feature.title}</h4>
                <p className="text-sm text-tanmu/60 leading-relaxed">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="px-8 py-16">
        <div className="max-w-6xl mx-auto">
          <h3 className="text-2xl font-bold text-center text-tanmu-dark mb-4">使用流程</h3>
          <p className="text-center text-tanmu/60 mb-12">四步完成减字谱数字化</p>
          
          <div className="flex flex-wrap justify-center items-start gap-4">
            {steps.map((item, index) => (
              <div key={index} className="flex items-center">
                <div className="flex flex-col items-center text-center w-48">
                  <div className="w-14 h-14 rounded-full bg-gradient-to-br from-tanmu to-tanmu-light flex items-center justify-center text-xuanzhi text-2xl font-bold mb-3 shadow-lg">
                    {item.step}
                  </div>
                  <h4 className="font-bold text-tanmu-dark mb-1">{item.title}</h4>
                  <p className="text-sm text-tanmu/60">{item.desc}</p>
                </div>
                {index < steps.length - 1 && (
                  <ArrowRight className="w-6 h-6 text-tanmu/30 mx-2 hidden md:block" />
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="px-8 py-16 bg-gradient-to-b from-tanmu to-tanmu-dark">
        <div className="max-w-4xl mx-auto text-center">
          <h3 className="text-2xl font-bold text-xuanzhi mb-4">准备好开始了吗？</h3>
          <p className="text-xuanzhi/70 mb-8">上传您的第一张减字谱，体验智能识别的魅力</p>
          <button
            onClick={() => navigate('/upload')}
            className="bg-xuanzhi text-tanmu-dark px-10 py-3 rounded-lg font-bold hover:bg-xuanzhi-dark transition-colors flex items-center gap-2 mx-auto"
          >
            <Upload className="w-5 h-5" />
            上传谱图
          </button>
        </div>
      </section>

      <footer className="px-8 py-6 border-t border-tanmu/10">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <p className="text-sm text-tanmu/50">
            © 2024 古琴减字谱智能识别系统 · 传承千年古琴文化
          </p>
          <div className="flex items-center gap-6 text-sm text-tanmu/50">
            <span className="hover:text-tanmu cursor-pointer transition-colors">使用帮助</span>
            <span className="hover:text-tanmu cursor-pointer transition-colors">关于我们</span>
            <span className="hover:text-tanmu cursor-pointer transition-colors">联系方式</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
