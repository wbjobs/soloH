import { useState, useCallback, useEffect, useRef } from 'react';
import { Scene3D } from './components/Scene3D/Scene3D';
import { Toolbar } from './components/Toolbar/Toolbar';
import { ControlPanel } from './components/ControlPanel/ControlPanel';
import { DataMonitor } from './components/DataMonitor/DataMonitor';
import { StatusBar } from './components/StatusBar/StatusBar';
import { useSimulationStore } from './store/useSimulationStore';
import { useParameterStore } from './store/useParameterStore';

function App() {
  const [showSettings, setShowSettings] = useState(true);
  const [showMonitor, setShowMonitor] = useState(true);
  const [canvas, setCanvas] = useState<HTMLCanvasElement | null>(null);
  const { initEngine, getEngine, isRunning } = useSimulationStore();
  const { sphParams } = useParameterStore();
  const initializedRef = useRef(false);

  useEffect(() => {
    if (!initializedRef.current) {
      initEngine(sphParams);
      initializedRef.current = true;
    }
  }, [initEngine, sphParams]);

  const handleCanvasReady = useCallback((canvasEl: HTMLCanvasElement) => {
    setCanvas(canvasEl);
  }, []);

  const handleToggleSettings = useCallback(() => {
    setShowSettings(prev => !prev);
  }, []);

  const handleToggleMonitor = useCallback(() => {
    setShowMonitor(prev => !prev);
  }, []);

  const handleCloseSettings = useCallback(() => {
    setShowSettings(false);
  }, []);

  const handleCloseMonitor = useCallback(() => {
    setShowMonitor(false);
  }, []);

  return (
    <div className="w-screen h-screen bg-slate-950 overflow-hidden relative">
      <Scene3D onCanvasReady={handleCanvasReady} />
      
      <Toolbar 
        canvas={canvas}
        onToggleSettings={handleToggleSettings}
        onToggleMonitor={handleToggleMonitor}
      />
      
      <ControlPanel 
        isOpen={showSettings}
        onClose={handleCloseSettings}
      />
      
      <DataMonitor 
        isOpen={showMonitor}
        onClose={handleCloseMonitor}
      />
      
      <StatusBar />

      <div className="absolute bottom-14 left-4 z-10 max-w-md">
        {!isRunning && (
          <div className="bg-slate-900/90 backdrop-blur-sm border border-cyan-500/30 rounded-lg p-4 text-sm">
            <h3 className="text-cyan-400 font-semibold mb-2">使用说明</h3>
            <ul className="text-slate-300 space-y-1 text-xs">
              <li>• 点击 <span className="text-cyan-400 font-mono">"开始"</span> 按钮启动SPH泥石流模拟</li>
              <li>• 鼠标左键拖拽旋转视角，滚轮缩放，右键平移</li>
              <li>• 左侧 <span className="text-cyan-400">参数面板</span> 可调节流体、地形、桥墩参数</li>
              <li>• 右侧 <span className="text-cyan-400">数据监控</span> 查看冲击力和压强实时数据</li>
              <li>• 点击 <span className="text-emerald-400">"导出数据"</span> 导出CSV格式冲击力数据</li>
              <li>• 点击 <span className="text-red-400">"录制视频"</span> 录制模拟过程</li>
              <li>• 粒子颜色表示速度：<span style={{color: '#1e3a5f'}}>蓝</span>→<span style={{color: '#4ecdc4'}}>青</span>→<span style={{color: '#95e619'}}>绿</span>→<span style={{color: '#ffe66d'}}>黄</span>→<span style={{color: '#ff6b35'}}>红</span></li>
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
