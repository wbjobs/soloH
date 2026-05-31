import { useCallback } from 'react';
import { Header } from '@/components/layout/Header';
import { ParameterPanel } from '@/components/params/ParameterPanel';
import { ResultPanel } from '@/components/results/ResultPanel';
import { MaterialDatabaseModal } from '@/components/materials/MaterialDatabaseModal';
import { EmitterEditorModal } from '@/components/emitter/EmitterEditorModal';
import { useCalculationWorker } from '@/hooks/useCalculationWorker';
import { useAppStore } from '@/store/useAppStore';
import { AlertTriangle } from 'lucide-react';

function App() {
  const { state, startCalculation, cancelCalculation } = useCalculationWorker();
  const { params, customMaterials } = useAppStore();

  const handleStart = useCallback(() => {
    startCalculation(params, customMaterials);
  }, [params, customMaterials, startCalculation]);

  const handleCancel = useCallback(() => {
    cancelCalculation();
  }, [cancelCalculation]);

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      
      <main className="flex-1 container mx-auto px-4 py-6">
        {state.error && (
          <div className="mb-4 p-4 bg-red-500/10 border border-red-500/30 rounded-xl flex items-center gap-3 animate-fade-in">
            <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0" />
            <div>
              <p className="text-sm font-semibold text-red-400">计算出错</p>
              <p className="text-xs text-red-300/80">{state.error}</p>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-4 xl:col-span-3">
            <ParameterPanel
              calculationState={state}
              onStart={handleStart}
              onCancel={handleCancel}
            />
          </div>

          <div className="lg:col-span-8 xl:col-span-9">
            <ResultPanel result={state.result} />
          </div>
        </div>
      </main>

      <footer className="py-6 border-t border-dark-700/30 text-center text-xs text-dark-500">
        <p className="font-mono">
          TPV Battery Simulator v1.0 | 基于详细平衡模型的热光伏电池性能仿真
        </p>
        <p className="mt-1 text-dark-600">
          Planck 黑体辐射 · Shockley-Queisser 极限 · TMM 传输矩阵法 · 遗传算法优化
        </p>
      </footer>

      <MaterialDatabaseModal />
      <EmitterEditorModal />
    </div>
  );
}

export default App;
