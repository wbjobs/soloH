import { Atom, Settings, LineChart, Layers } from 'lucide-react';
import { useAppStore } from '../../store';
import type { TabType } from '../../types';

const tabs: { id: TabType; label: string; icon: typeof Atom }[] = [
  { id: 'params', label: '参数设置', icon: Settings },
  { id: 'results', label: '结果分析', icon: LineChart },
  { id: 'visualization', label: '可视化中心', icon: Layers },
];

export function Navbar() {
  const { activeTab, setActiveTab, progress } = useAppStore();

  return (
    <nav className="glass-card border-b border-slate-500/20 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-quantum-400 to-quantum-600 flex items-center justify-center shadow-lg shadow-quantum-400/30">
              <Atom className="w-6 h-6 text-space-950" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-100">量子点器件模拟器</h1>
              <p className="text-xs text-slate-500 font-mono">QD-LED Simulator v1.0</p>
            </div>
          </div>

          <div className="flex items-center gap-2 bg-space-900/50 rounded-xl p-1">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`nav-link flex items-center gap-2 transition-all duration-300 ${
                    isActive ? 'nav-link-active' : ''
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span className="text-sm font-medium">{tab.label}</span>
                </button>
              );
            })}
          </div>

          <div className="flex items-center gap-4">
            {progress.status === 'calculating' && (
              <div className="flex items-center gap-2 text-sm">
                <div className="w-32 h-2 bg-space-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-quantum-400 to-quantum-500 rounded-full transition-all duration-300"
                    style={{ width: `${progress.progress}%` }}
                  />
                </div>
                <span className="text-quantum-400 font-mono text-xs">
                  {progress.progress.toFixed(0)}%
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}
