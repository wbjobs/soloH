import { Zap, Github, Info } from 'lucide-react';
import { useState } from 'react';

export function Header() {
  const [showInfo, setShowInfo] = useState(false);

  return (
    <>
      <header className="relative z-10 border-b border-dark-700/50 backdrop-blur-xl bg-dark-900/30">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center shadow-lg shadow-primary-500/20 animate-pulse-glow">
                <Zap className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="font-display text-xl font-bold bg-gradient-to-r from-primary-400 to-accent-400 bg-clip-text text-transparent">
                  TPV 电池模拟器
                </h1>
                <p className="text-xs text-dark-400 font-mono">
                  热光伏电池详细平衡模型计算
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <div className="hidden md:flex items-center gap-3 text-xs text-dark-400">
                <span className="px-2 py-1 bg-dark-800/50 rounded-lg font-mono">
                  Web Worker
                </span>
                <span className="px-2 py-1 bg-dark-800/50 rounded-lg font-mono">
                  D3.js 可视化
                </span>
                <span className="px-2 py-1 bg-dark-800/50 rounded-lg font-mono">
                  详细平衡模型
                </span>
              </div>
              <button
                onClick={() => setShowInfo(true)}
                className="p-2 rounded-lg hover:bg-dark-700/50 transition-colors text-dark-400 hover:text-dark-100"
                title="关于"
              >
                <Info className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </header>

      {showInfo && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in" onClick={() => setShowInfo(false)}>
          <div className="glass-card max-w-lg p-6 animate-slide-in" onClick={e => e.stopPropagation()}>
            <h3 className="font-display text-lg font-bold text-dark-100 mb-4">关于 TPV 电池模拟器</h3>
            <div className="space-y-3 text-sm text-dark-300">
              <p>
                这是一个纯前端的热光伏（Thermophotovoltaic, TPV）电池性能仿真工具。
              </p>
              <div className="space-y-2">
                <p className="font-semibold text-dark-200">核心功能：</p>
                <ul className="list-disc list-inside space-y-1 text-xs text-dark-400">
                  <li>黑体辐射谱计算（Planck定律）</li>
                  <li>选择性发射极优化（一维光子晶体/多层膜）</li>
                  <li>详细平衡模型求解（辐射复合、俄歇复合、串联电阻）</li>
                  <li>转换效率、I-V曲线、量子效率输出</li>
                  <li>带隙-效率二维扫描等高线图</li>
                  <li>可自定义的材料数据库</li>
                </ul>
              </div>
              <div className="space-y-2">
                <p className="font-semibold text-dark-200">技术栈：</p>
                <div className="flex flex-wrap gap-2">
                  <span className="px-2 py-1 bg-dark-700/50 rounded text-xs font-mono">React 18</span>
                  <span className="px-2 py-1 bg-dark-700/50 rounded text-xs font-mono">TypeScript</span>
                  <span className="px-2 py-1 bg-dark-700/50 rounded text-xs font-mono">Web Worker</span>
                  <span className="px-2 py-1 bg-dark-700/50 rounded text-xs font-mono">D3.js</span>
                  <span className="px-2 py-1 bg-dark-700/50 rounded text-xs font-mono">Zustand</span>
                  <span className="px-2 py-1 bg-dark-700/50 rounded text-xs font-mono">TailwindCSS</span>
                </div>
              </div>
              <p className="text-xs text-dark-500 pt-2 border-t border-dark-700">
                所有计算均在浏览器本地完成，无需后端服务。
              </p>
            </div>
            <button
              onClick={() => setShowInfo(false)}
              className="btn-primary w-full mt-6 py-2"
            >
              知道了
            </button>
          </div>
        </div>
      )}
    </>
  );
}
