import React from 'react';
import { SourceConfigPanel } from '../components/params/SourceConfigPanel';
import { SubstrateConfigPanel } from '../components/params/SubstrateConfigPanel';
import { CalculationConfigPanel } from '../components/params/CalculationConfigPanel';
import { OccluderConfigPanel } from '../components/params/OccluderConfigPanel';
import { Scene3D } from '../components/viewer3d/Scene3D';
import { ContourPlot, StatisticsPanel } from '../components/results/ContourPlot';
import { ControlBar } from '../components/layout/ControlBar';
import { Layers, Atom } from 'lucide-react';

export default function Home() {
  return (
    <div className="h-screen flex flex-col bg-[#0A1929] overflow-hidden">
      <header className="h-14 bg-slate-900/80 border-b border-slate-700 px-6 flex items-center justify-between backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center">
            <Atom className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-slate-100 tracking-tight">
              真空镀膜膜厚模拟器
            </h1>
            <p className="text-xs text-slate-500">Thin Film Deposition Simulator</p>
          </div>
        </div>
        <div className="flex items-center gap-4 text-xs text-slate-500">
          <span className="flex items-center gap-1">
            <Layers className="w-3 h-3" />
            Web Worker + 数值积分
          </span>
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden">
        <aside className="w-80 bg-slate-900/50 border-r border-slate-700 overflow-y-auto p-3">
          <SourceConfigPanel />
          <SubstrateConfigPanel />
          <OccluderConfigPanel />
          <CalculationConfigPanel />
        </aside>

        <main className="flex-1 flex flex-col overflow-hidden">
          <div className="flex-1 relative">
            <Scene3D />
            <div className="absolute top-4 left-4 px-3 py-1.5 bg-slate-900/80 backdrop-blur-sm rounded-lg text-xs text-slate-400 border border-slate-700">
              3D 视图 - 拖拽旋转，滚轮缩放
            </div>
          </div>
        </main>

        <aside className="w-96 bg-slate-900/50 border-l border-slate-700 overflow-y-auto p-4">
          <div className="h-full flex flex-col">
            <div className="flex-1">
              <ContourPlot />
            </div>
            <div className="mt-4 pt-4 border-t border-slate-700">
              <StatisticsPanel />
            </div>
          </div>
        </aside>
      </div>

      <ControlBar />
    </div>
  );
}
