import { useState, useCallback, useRef } from 'react';
import { X, Upload, Sliders, Mountain, Building2, Droplets, RotateCcw, TreeDeciduous, Layers } from 'lucide-react';
import { useParameterStore } from '../../store/useParameterStore';
import { useSimulationStore } from '../../store/useSimulationStore';
import { loadDEMFromFile } from '../../utils/demLoader';
import { loadOBJFromFile } from '../../utils/objLoader';
import * as THREE from 'three';

interface ControlPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

interface SliderControlProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  unit: string;
  onChange: (value: number) => void;
  description?: string;
}

function SliderControl({ label, value, min, max, step, unit, onChange, description }: SliderControlProps) {
  return (
    <div className="mb-4">
      <div className="flex justify-between items-center mb-1">
        <label className="text-sm font-medium text-slate-300">{label}</label>
        <span className="text-sm font-mono text-cyan-400">
          {value.toFixed(step < 1 ? 2 : 0)} {unit}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-cyan-500"
      />
      {description && (
        <p className="text-xs text-slate-500 mt-1">{description}</p>
      )}
    </div>
  );
}

function SectionHeader({ icon: Icon, title }: { icon: any; title: string }) {
  return (
    <div className="flex items-center gap-2 mb-4 pb-2 border-b border-slate-700">
      <Icon size={18} className="text-cyan-400" />
      <h3 className="text-lg font-semibold text-white">{title}</h3>
    </div>
  );
}

export function ControlPanel({ isOpen, onClose }: ControlPanelProps) {
  const {
    sphParams,
    terrainParams,
    bridgeParams,
    updateSPHParams,
    updateTerrainParams,
    updateBridgeParams,
    resetToDefaults
  } = useParameterStore();
  
  const { getEngine } = useSimulationStore();
  const [activeSection, setActiveSection] = useState<'fluid' | 'grain' | 'vegetation' | 'terrain' | 'bridge'>('fluid');
  const demFileInputRef = useRef<HTMLInputElement>(null);
  const objFileInputRef = useRef<HTMLInputElement>(null);
  const [loadStatus, setLoadStatus] = useState<{ type: string; message: string } | null>(null);

  const handleSPHParamChange = useCallback((key: keyof typeof sphParams, value: number) => {
    updateSPHParams({ [key]: value });
    const engine = getEngine();
    if (engine) {
      engine.updateParameters({ [key]: value });
    }
  }, [updateSPHParams, getEngine]);

  const handleTerrainParamChange = useCallback((key: keyof typeof terrainParams, value: number) => {
    updateTerrainParams({ [key]: value });
  }, [updateTerrainParams]);

  const handleBridgeParamChange = useCallback((key: keyof typeof bridgeParams, value: number, axis?: 'x' | 'y' | 'z') => {
    if (axis && key === 'position') {
      updateBridgeParams({
        position: { ...bridgeParams.position, [axis]: value }
      });
    } else if (axis && key === 'scale') {
      updateBridgeParams({
        scale: { ...bridgeParams.scale, [axis]: value }
      });
    }
  }, [updateBridgeParams, bridgeParams]);

  const handleVegetationParamChange = useCallback((key: keyof typeof sphParams.vegetation, value: any) => {
    updateSPHParams({
      vegetation: { ...sphParams.vegetation, [key]: value }
    });
    const engine = getEngine();
    if (engine) {
      engine.updateParameters({ vegetation: { ...sphParams.vegetation, [key]: value } });
    }
  }, [updateSPHParams, getEngine, sphParams.vegetation]);

  const handleGrainSizeParamChange = useCallback((key: keyof typeof sphParams.grainSize, value: number) => {
    updateSPHParams({
      grainSize: { ...sphParams.grainSize, [key]: value }
    });
    const engine = getEngine();
    if (engine) {
      engine.updateParameters({ grainSize: { ...sphParams.grainSize, [key]: value } });
    }
  }, [updateSPHParams, getEngine, sphParams.grainSize]);

  const handleVegetationZoneChange = useCallback((key: 'startZ' | 'endZ' | 'startX' | 'endX', value: number) => {
    updateSPHParams({
      vegetation: {
        ...sphParams.vegetation,
        vegetationZone: { ...sphParams.vegetation.vegetationZone, [key]: value }
      }
    });
  }, [updateSPHParams, sphParams.vegetation]);

  const handleDEMUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setLoadStatus({ type: 'loading', message: '正在加载DEM文件...' });
    try {
      const demData = await loadDEMFromFile(file);
      setLoadStatus({ type: 'success', message: `DEM加载成功: ${demData.resolution}x${demData.resolution}` });
      
      const engine = getEngine();
      if (engine) {
        engine.setTerrain(demData.heights, {
          width: demData.width,
          depth: demData.height,
          resolution: demData.resolution
        });
      }
      
      setTimeout(() => setLoadStatus(null), 3000);
    } catch (error) {
      setLoadStatus({ type: 'error', message: `DEM加载失败: ${error}` });
      setTimeout(() => setLoadStatus(null), 5000);
    }
  }, [getEngine]);

  const handleOBJUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setLoadStatus({ type: 'loading', message: '正在加载OBJ文件...' });
    try {
      const position = new THREE.Vector3(bridgeParams.position.x, bridgeParams.position.y, bridgeParams.position.z);
      const scale = new THREE.Vector3(bridgeParams.scale.x, bridgeParams.scale.y, bridgeParams.scale.z);
      const loaded = await loadOBJFromFile(file, scale, position);
      setLoadStatus({ type: 'success', message: 'OBJ模型加载成功' });
      
      const engine = getEngine();
      if (engine) {
        engine.setBridgeMesh(loaded.mesh);
      }
      
      setTimeout(() => setLoadStatus(null), 3000);
    } catch (error) {
      setLoadStatus({ type: 'error', message: `OBJ加载失败: ${error}` });
      setTimeout(() => setLoadStatus(null), 5000);
    }
  }, [getEngine, bridgeParams]);

  if (!isOpen) return null;

  return (
    <div className="absolute left-0 top-16 bottom-12 w-80 bg-slate-900/95 backdrop-blur-sm border-r border-cyan-500/20 overflow-y-auto z-20">
      <div className="p-4">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold text-cyan-400">参数控制面板</h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-700 rounded-md transition-colors"
          >
            <X size={20} className="text-slate-400" />
          </button>
        </div>

        <div className="flex flex-wrap gap-1 mb-4">
          {[
            { key: 'fluid', label: '流体', icon: Droplets },
            { key: 'grain', label: '粒级配', icon: Layers },
            { key: 'vegetation', label: '植被', icon: TreeDeciduous },
            { key: 'terrain', label: '地形', icon: Mountain },
            { key: 'bridge', label: '桥墩', icon: Building2 }
          ].map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setActiveSection(key as any)}
              className={`flex-1 min-w-[60px] flex items-center justify-center gap-1 py-2 px-2 rounded-md text-xs font-medium transition-all ${
                activeSection === key
                  ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/50'
                  : 'bg-slate-700/50 text-slate-400 hover:bg-slate-700'
              }`}
            >
              <Icon size={14} />
              {label}
            </button>
          ))}
        </div>

        {loadStatus && (
          <div className={`mb-4 p-3 rounded-md text-sm ${
            loadStatus.type === 'loading' ? 'bg-blue-500/20 text-blue-400' :
            loadStatus.type === 'success' ? 'bg-green-500/20 text-green-400' :
            'bg-red-500/20 text-red-400'
          }`}>
            {loadStatus.message}
          </div>
        )}

        {activeSection === 'fluid' && (
          <div>
            <SectionHeader icon={Droplets} title="流体参数" />
            
            <SliderControl
              label="参考密度"
              value={sphParams.density0}
              min={1000}
              max={3000}
              step={50}
              unit="kg/m³"
              onChange={(v) => handleSPHParamChange('density0', v)}
              description="泥石流的参考密度，水为1000，泥石流通常为1500-2500"
            />

            <SliderControl
              label="动力粘度"
              value={sphParams.viscosity}
              min={0.01}
              max={2}
              step={0.01}
              unit="Pa·s"
              onChange={(v) => handleSPHParamChange('viscosity', v)}
              description="控制流体的粘性阻力，值越大流动越慢"
            />

            <SliderControl
              label="屈服应力"
              value={sphParams.yieldStress}
              min={0}
              max={500}
              step={5}
              unit="Pa"
              onChange={(v) => handleSPHParamChange('yieldStress', v)}
              description="Bingham模型关键参数，使流体需要超过此应力才会流动"
            />

            <SliderControl
              label="平滑核半径"
              value={sphParams.smoothingLength}
              min={0.2}
              max={1.5}
              step={0.05}
              unit="m"
              onChange={(v) => handleSPHParamChange('smoothingLength', v)}
              description="SPH核函数的影响半径，影响粒子间相互作用范围"
            />

            <SliderControl
              label="粒子质量"
              value={sphParams.particleMass}
              min={0.05}
              max={1}
              step={0.05}
              unit="kg"
              onChange={(v) => handleSPHParamChange('particleMass', v)}
              description="单个粒子的质量，影响整体惯性"
            />

            <SliderControl
              label="刚度系数"
              value={sphParams.stiffness}
              min={500}
              max={5000}
              step={100}
              unit=""
              onChange={(v) => handleSPHParamChange('stiffness', v)}
              description="状态方程刚度，控制不可压缩性"
            />

            <SliderControl
              label="最大粒子数"
              value={sphParams.maxParticles}
              min={500}
              max={5000}
              step={100}
              unit="个"
              onChange={(v) => handleSPHParamChange('maxParticles', v)}
              description="模拟的最大粒子数量，影响性能和精度"
            />

            <SliderControl
              label="时间步长"
              value={sphParams.timeStep}
              min={0.001}
              max={0.02}
              step={0.001}
              unit="s"
              onChange={(v) => handleSPHParamChange('timeStep', v)}
              description="物理模拟的时间步长，越小越稳定但越慢"
            />
          </div>
        )}

        {activeSection === 'grain' && (
          <div>
            <SectionHeader icon={Layers} title="粒级配参数" />
            
            <SliderControl
              label="细颗粒比例"
              value={sphParams.grainSize.fineFraction}
              min={0}
              max={1}
              step={0.05}
              unit=""
              onChange={(v) => handleGrainSizeParamChange('fineFraction', v)}
              description="细颗粒占总质量的比例，与粗颗粒比例之和应为1"
            />

            <SliderControl
              label="粗颗粒比例"
              value={sphParams.grainSize.coarseFraction}
              min={0}
              max={1}
              step={0.05}
              unit=""
              onChange={(v) => handleGrainSizeParamChange('coarseFraction', v)}
              description="粗颗粒占总质量的比例"
            />

            <SliderControl
              label="细颗粒半径"
              value={sphParams.grainSize.fineRadius}
              min={0.05}
              max={0.3}
              step={0.01}
              unit="m"
              onChange={(v) => handleGrainSizeParamChange('fineRadius', v)}
              description="细颗粒（泥沙/黏土）的平均半径"
            />

            <SliderControl
              label="粗颗粒半径"
              value={sphParams.grainSize.coarseRadius}
              min={0.2}
              max={1}
              step={0.05}
              unit="m"
              onChange={(v) => handleGrainSizeParamChange('coarseRadius', v)}
              description="粗颗粒（砾石/块石）的平均半径"
            />

            <SliderControl
              label="细颗粒密度"
              value={sphParams.grainSize.fineDensity}
              min={1500}
              max={2500}
              step={50}
              unit="kg/m³"
              onChange={(v) => handleGrainSizeParamChange('fineDensity', v)}
              description="细颗粒的真实密度"
            />

            <SliderControl
              label="粗颗粒密度"
              value={sphParams.grainSize.coarseDensity}
              min={2000}
              max={3500}
              step={50}
              unit="kg/m³"
              onChange={(v) => handleGrainSizeParamChange('coarseDensity', v)}
              description="粗颗粒的真实密度"
            />

            <SliderControl
              label="分离速度"
              value={sphParams.grainSize.segregationVelocity}
              min={0}
              max={2}
              step={0.05}
              unit="m/s"
              onChange={(v) => handleGrainSizeParamChange('segregationVelocity', v)}
              description="不同粒径颗粒的分离速度系数"
            />

            <SliderControl
              label="湍流扩散"
              value={sphParams.grainSize.turbulentDiffusion}
              min={0}
              max={0.1}
              step={0.005}
              unit="m²/s"
              onChange={(v) => handleGrainSizeParamChange('turbulentDiffusion', v)}
              description="湍流引起的颗粒混合扩散系数"
            />
          </div>
        )}

        {activeSection === 'vegetation' && (
          <div>
            <SectionHeader icon={TreeDeciduous} title="植被阻力参数" />
            
            <div className="mb-4 flex items-center justify-between">
              <label className="text-sm font-medium text-slate-300">启用植被阻力</label>
              <button
                onClick={() => handleVegetationParamChange('enabled', !sphParams.vegetation.enabled)}
                className={`w-12 h-6 rounded-full transition-colors ${
                  sphParams.vegetation.enabled ? 'bg-cyan-500' : 'bg-slate-600'
                }`}
              >
                <div
                  className={`w-5 h-5 bg-white rounded-full shadow-md transform transition-transform ${
                    sphParams.vegetation.enabled ? 'translate-x-6' : 'translate-x-0.5'
                  }`}
                />
              </button>
            </div>

            <SliderControl
              label="植被密度"
              value={sphParams.vegetation.density}
              min={0}
              max={200}
              step={5}
              unit="株/100m²"
              onChange={(v) => handleVegetationParamChange('density', v)}
              description="单位面积内的植被茎干数量"
            />

            <SliderControl
              label="茎干直径"
              value={sphParams.vegetation.stemDiameter}
              min={0.02}
              max={0.5}
              step={0.01}
              unit="m"
              onChange={(v) => handleVegetationParamChange('stemDiameter', v)}
              description="植被茎干的平均直径"
            />

            <SliderControl
              label="茎干高度"
              value={sphParams.vegetation.stemHeight}
              min={0.5}
              max={10}
              step={0.1}
              unit="m"
              onChange={(v) => handleVegetationParamChange('stemHeight', v)}
              description="植被茎干的平均高度"
            />

            <SliderControl
              label="阻力系数"
              value={sphParams.vegetation.dragCoefficient}
              min={0.5}
              max={3}
              step={0.1}
              unit=""
              onChange={(v) => handleVegetationParamChange('dragCoefficient', v)}
              description="植被的气动阻力系数，圆柱形约1.2"
            />

            <SliderControl
              label="抗弯刚度"
              value={sphParams.vegetation.bendingStiffness}
              min={100}
              max={10000}
              step={100}
              unit="N·m²"
              onChange={(v) => handleVegetationParamChange('bendingStiffness', v)}
              description="植被茎干的抗弯刚度，影响变形吸能"
            />

            <div className="mb-4 p-3 bg-slate-700/30 rounded-md">
              <label className="text-sm font-medium text-slate-300 mb-2 block">植被区域范围</label>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-xs text-slate-400">X起始</label>
                  <input
                    type="number"
                    value={sphParams.vegetation.vegetationZone.startX}
                    onChange={(e) => handleVegetationZoneChange('startX', parseFloat(e.target.value))}
                    className="w-full px-2 py-1 bg-slate-700 border border-slate-600 rounded text-sm text-white"
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-400">X结束</label>
                  <input
                    type="number"
                    value={sphParams.vegetation.vegetationZone.endX}
                    onChange={(e) => handleVegetationZoneChange('endX', parseFloat(e.target.value))}
                    className="w-full px-2 py-1 bg-slate-700 border border-slate-600 rounded text-sm text-white"
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-400">Z起始</label>
                  <input
                    type="number"
                    value={sphParams.vegetation.vegetationZone.startZ}
                    onChange={(e) => handleVegetationZoneChange('startZ', parseFloat(e.target.value))}
                    className="w-full px-2 py-1 bg-slate-700 border border-slate-600 rounded text-sm text-white"
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-400">Z结束</label>
                  <input
                    type="number"
                    value={sphParams.vegetation.vegetationZone.endZ}
                    onChange={(e) => handleVegetationZoneChange('endZ', parseFloat(e.target.value))}
                    className="w-full px-2 py-1 bg-slate-700 border border-slate-600 rounded text-sm text-white"
                  />
                </div>
              </div>
            </div>
          </div>
        )}

        {activeSection === 'terrain' && (
          <div>
            <SectionHeader icon={Mountain} title="地形参数" />

            <div className="mb-4">
              <label className="block text-sm font-medium text-slate-300 mb-2">导入DEM文件</label>
              <input
                ref={demFileInputRef}
                type="file"
                accept=".asc,.txt,.tif,.tiff"
                onChange={handleDEMUpload}
                className="hidden"
              />
              <button
                onClick={() => demFileInputRef.current?.click()}
                className="w-full flex items-center justify-center gap-2 py-3 bg-slate-700/50 hover:bg-slate-700 border border-dashed border-slate-600 rounded-md text-slate-300 transition-colors"
              >
                <Upload size={18} />
                选择DEM文件 (.asc, .tif)
              </button>
            </div>

            <SliderControl
              label="地形宽度"
              value={terrainParams.width}
              min={50}
              max={150}
              step={5}
              unit="m"
              onChange={(v) => handleTerrainParamChange('width', v)}
            />

            <SliderControl
              label="地形深度"
              value={terrainParams.depth}
              min={50}
              max={200}
              step={5}
              unit="m"
              onChange={(v) => handleTerrainParamChange('depth', v)}
            />

            <SliderControl
              label="地形分辨率"
              value={terrainParams.resolution}
              min={32}
              max={256}
              step={16}
              unit="像素"
              onChange={(v) => handleTerrainParamChange('resolution', v)}
            />

            <SliderControl
              label="地形起伏幅度"
              value={terrainParams.amplitude}
              min={2}
              max={20}
              step={1}
              unit="m"
              onChange={(v) => handleTerrainParamChange('amplitude', v)}
            />

            <SliderControl
              label="地形粗糙度"
              value={terrainParams.roughness}
              min={5}
              max={100}
              step={5}
              unit=""
              onChange={(v) => handleTerrainParamChange('roughness', v)}
            />

            <SliderControl
              label="河床坡度"
              value={terrainParams.slope}
              min={0}
              max={50}
              step={1}
              unit="°"
              onChange={(v) => handleTerrainParamChange('slope', v)}
            />

            <SliderControl
              label="随机种子"
              value={terrainParams.seed}
              min={1}
              max={99999}
              step={1}
              unit=""
              onChange={(v) => handleTerrainParamChange('seed', v)}
            />
          </div>
        )}

        {activeSection === 'bridge' && (
          <div>
            <SectionHeader icon={Building2} title="桥墩参数" />

            <div className="mb-4">
              <label className="block text-sm font-medium text-slate-300 mb-2">导入OBJ模型</label>
              <input
                ref={objFileInputRef}
                type="file"
                accept=".obj"
                onChange={handleOBJUpload}
                className="hidden"
              />
              <button
                onClick={() => objFileInputRef.current?.click()}
                className="w-full flex items-center justify-center gap-2 py-3 bg-slate-700/50 hover:bg-slate-700 border border-dashed border-slate-600 rounded-md text-slate-300 transition-colors"
              >
                <Upload size={18} />
                选择OBJ文件
              </button>
            </div>

            <div className="mb-4">
              <label className="text-sm font-medium text-slate-300 mb-2 block">位置</label>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { axis: 'x', label: 'X', value: bridgeParams.position.x, min: -50, max: 50 },
                  { axis: 'y', label: 'Y', value: bridgeParams.position.y, min: 0, max: 30 },
                  { axis: 'z', label: 'Z', value: bridgeParams.position.z, min: -50, max: 100 }
                ].map(({ axis, label, value, min, max }) => (
                  <div key={axis}>
                    <label className="text-xs text-slate-400">{label}</label>
                    <input
                      type="number"
                      value={value.toFixed(1)}
                      min={min}
                      max={max}
                      step={0.5}
                      onChange={(e) => handleBridgeParamChange('position', parseFloat(e.target.value), axis as any)}
                      className="w-full px-2 py-1 bg-slate-700 border border-slate-600 rounded text-sm text-white"
                    />
                  </div>
                ))}
              </div>
            </div>

            <div className="mb-4">
              <label className="text-sm font-medium text-slate-300 mb-2 block">缩放</label>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { axis: 'x', label: 'X', value: bridgeParams.scale.x },
                  { axis: 'y', label: 'Y', value: bridgeParams.scale.y },
                  { axis: 'z', label: 'Z', value: bridgeParams.scale.z }
                ].map(({ axis, label, value }) => (
                  <div key={axis}>
                    <label className="text-xs text-slate-400">{label}</label>
                    <input
                      type="number"
                      value={value.toFixed(2)}
                      min={0.1}
                      max={5}
                      step={0.1}
                      onChange={(e) => handleBridgeParamChange('scale', parseFloat(e.target.value), axis as any)}
                      className="w-full px-2 py-1 bg-slate-700 border border-slate-600 rounded text-sm text-white"
                    />
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        <div className="mt-6 pt-4 border-t border-slate-700">
          <button
            onClick={resetToDefaults}
            className="w-full flex items-center justify-center gap-2 py-2 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-md transition-colors"
          >
            <RotateCcw size={16} />
            重置为默认参数
          </button>
        </div>
      </div>
    </div>
  );
}
