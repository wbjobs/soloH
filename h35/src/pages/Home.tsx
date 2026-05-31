import React, { useEffect } from 'react';
import { Sparkles, Github, BookOpen } from 'lucide-react';
import { ControlPanel } from '../components/ControlPanel';
import { ResultsPanel } from '../components/ResultsPanel';
import { useSimulationStore } from '../store/simulationStore';

export default function Home() {
  const { calculateAll, isCalculating } = useSimulationStore();

  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
        if (!isCalculating) {
          calculateAll();
        }
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [calculateAll, isCalculating]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-white">
      <header className="fixed top-0 left-0 right-0 z-50 bg-slate-900/80 backdrop-blur-lg border-b border-white/10">
        <div className="flex items-center justify-between px-6 py-3">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-gradient-to-br from-cyan-500 to-blue-600 rounded-lg">
              <Sparkles className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
                非线性光学相位匹配仿真平台
              </h1>
              <p className="text-xs text-gray-500">
                Nonlinear Optics Phase Matching Simulator
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="hidden md:flex items-center gap-2 text-xs text-gray-500">
              <kbd className="px-2 py-1 bg-gray-800 rounded border border-gray-700">
                Ctrl
              </kbd>
              <span>+</span>
              <kbd className="px-2 py-1 bg-gray-800 rounded border border-gray-700">
                Enter
              </kbd>
              <span className="ml-1">快速计算</span>
            </div>

            <a
              href="#"
              className="p-2 text-gray-400 hover:text-white transition-colors rounded-lg hover:bg-gray-800"
            >
              <BookOpen size={20} />
            </a>
            <a
              href="#"
              className="p-2 text-gray-400 hover:text-white transition-colors rounded-lg hover:bg-gray-800"
            >
              <Github size={20} />
            </a>
          </div>
        </div>
      </header>

      <main className="pt-16 h-screen flex">
        <aside className="w-80 flex-shrink-0 border-r border-white/10 bg-slate-900/50 p-4 overflow-hidden">
          <ControlPanel />
        </aside>

        <section className="flex-1 overflow-hidden">
          <ResultsPanel />
        </section>
      </main>

      <footer className="fixed bottom-0 left-0 right-0 bg-slate-900/80 backdrop-blur-lg border-t border-white/10 px-6 py-2">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <div className="flex items-center gap-4">
            <span>
              基于 WebAssembly + WebGL 的纯前端数值仿真平台
            </span>
          </div>
          <div className="flex items-center gap-4">
            <span>RK4 数值积分</span>
            <span>•</span>
            <span>FFT 频谱分析</span>
            <span>•</span>
            <span>三波混频耦合波方程</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
