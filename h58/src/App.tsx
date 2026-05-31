import React, { useEffect, useState } from 'react';
import { Brush, Info, X, Settings, Grid3X3, Stamp, Framer, Palette } from 'lucide-react';
import { SampleUploader } from './components/SampleUploader';
import { ParameterControls } from './components/ParameterControls';
import { StyleFusion } from './components/StyleFusion';
import { LayoutControls } from './components/LayoutControls';
import { SealSignatureControls } from './components/SealSignatureControls';
import { RubbingControls } from './components/RubbingControls';
import { StrokeVisualization } from './components/StrokeVisualization';
import { TextInput } from './components/TextInput';
import { GenerationPreview } from './components/GenerationPreview';
import { ExportPanel } from './components/ExportPanel';
import { useAppStore } from './store/useAppStore';
import { isTFInitialized } from './utils/ganGenerator';

type ControlTab = 'style' | 'layout' | 'seal' | 'rubbing';

function App() {
  const { samples, selectedSampleId } = useAppStore();
  const [showAbout, setShowAbout] = useState(true);
  const [tfAvailable, setTfAvailable] = useState<boolean | null>(null);
  const [activeControlTab, setActiveControlTab] = useState<ControlTab>('style');

  useEffect(() => {
    const checkTF = async () => {
      try {
        const available = await isTFInitialized();
        setTfAvailable(available);
      } catch {
        setTfAvailable(false);
      }
    };
    checkTF();
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => setShowAbout(false), 8000);
    return () => clearTimeout(timer);
  }, []);

  const controlTabs: { id: ControlTab; label: string; icon: React.ReactNode }[] = [
    { id: 'style', label: '笔触', icon: <Palette className="w-4 h-4" /> },
    { id: 'layout', label: '章法', icon: <Grid3X3 className="w-4 h-4" /> },
    { id: 'seal', label: '落款', icon: <Stamp className="w-4 h-4" /> },
    { id: 'rubbing', label: '拓片', icon: <Framer className="w-4 h-4" /> },
  ];

  const selectedSample = samples.find(s => s.id === selectedSampleId);

  return (
    <div className="min-h-screen bg-[#f5f0e6] paper-texture relative">
      <header className="sticky top-0 z-20 bg-[#1a1a1a] text-[#f5f0e6] py-4 px-6 shadow-lg border-b-4 border-[#c41e3a]">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-[#c41e3a] rounded-full flex items-center justify-center">
              <Brush className="w-6 h-6" />
            </div>
            <div>
              <h1 className="font-calligraphy text-2xl tracking-wide">墨韵</h1>
              <p className="text-xs text-[#b0b0b0]">手写体生成器</p>
            </div>
          </div>
          
          <div className="flex items-center gap-4">
            <div className="hidden md:flex items-center gap-2 text-sm">
              <span className={`w-2 h-2 rounded-full ${tfAvailable ? 'bg-green-500' : 'bg-yellow-500'}`}></span>
              <span className="text-[#b0b0b0]">
                {tfAvailable ? 'TensorFlow.js 已加载' : '使用笔画拼接模式'}
              </span>
            </div>
            <button
              onClick={() => setShowAbout(!showAbout)}
              className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-white/10 transition-colors"
              title="关于"
            >
              <Info className="w-5 h-5" />
            </button>
          </div>
        </div>
      </header>

      {showAbout && (
        <div className="absolute top-20 right-4 z-30 max-w-sm bg-white rounded-lg shadow-xl p-4 border border-[#e8e0cf]">
          <button
            onClick={() => setShowAbout(false)}
            className="absolute top-2 right-2 text-[#6b6b6b] hover:text-[#1a1a1a]"
          >
            <X className="w-4 h-4" />
          </button>
          <h4 className="font-calligraphy text-lg text-[#c41e3a] mb-2">关于墨韵</h4>
          <p className="text-sm text-[#3d3d3d] mb-2">
            上传楷书或行书样本字图片，系统自动提取笔画顺序与轨迹，生成您的专属手写体。
          </p>
          <ul className="text-xs text-[#6b6b6b] space-y-1">
            <li>• 支持多风格融合（加权平均）</li>
            <li>• 笔画粗细、速度、飞白可调</li>
            <li>• 章法布局：字间距、行距、错落</li>
            <li>• 落款印章、拓片效果</li>
            <li>• SVG 矢量导出，逐笔回放</li>
            <li>• 纯前端处理，隐私安全</li>
          </ul>
        </div>
      )}

      <main className="max-w-7xl mx-auto px-4 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-4 space-y-6">
            <SampleUploader />
            
            <div className="bg-white rounded-lg p-1 shadow-md">
              <div className="flex gap-1 mb-4">
                {controlTabs.map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveControlTab(tab.id)}
                    className={`flex-1 py-2 px-2 text-xs rounded flex flex-col items-center gap-1 transition-all ${
                      activeControlTab === tab.id
                        ? 'bg-[#1a1a1a] text-[#f5f0e6]'
                        : 'text-[#6b6b6b] hover:bg-[#e8e0cf]'
                    }`}
                  >
                    {tab.icon}
                    {tab.label}
                  </button>
                ))}
              </div>
              
              <div className="min-h-[300px]">
                {activeControlTab === 'style' && (
                  <div className="space-y-6 p-3">
                    <ParameterControls className="!mb-0" />
                    <StyleFusion className="!mb-0" />
                  </div>
                )}
                {activeControlTab === 'layout' && (
                  <div className="p-3">
                    <LayoutControls className="!mb-0" />
                  </div>
                )}
                {activeControlTab === 'seal' && (
                  <div className="p-3">
                    <SealSignatureControls className="!mb-0" />
                  </div>
                )}
                {activeControlTab === 'rubbing' && (
                  <div className="p-3">
                    <RubbingControls className="!mb-0" />
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="lg:col-span-8 space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <StrokeVisualization />
              <div className="space-y-6">
                <TextInput onGenerate={() => {}} />
                <ExportPanel />
              </div>
            </div>
            
            <GenerationPreview />
          </div>
        </div>
      </main>

      <footer className="mt-12 py-6 bg-[#1a1a1a] text-[#8b8b8b] text-center text-sm">
        <div className="max-w-7xl mx-auto px-4">
          <p className="font-calligraphy text-[#b0b0b0] mb-1">墨韵 · 让每一个字都有温度</p>
          <p>
            Powered by TensorFlow.js · React · TypeScript · Canvas · SVG
          </p>
          <p className="mt-1 text-xs text-[#6b6b6b]">
            纯前端处理，您的图片和数据不会上传到任何服务器
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;
