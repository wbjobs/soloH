import { useState, useMemo } from 'react';
import { X, Plus, Trash2, GripVertical, Eye, RotateCcw } from 'lucide-react';
import { useAppStore } from '@/store/useAppStore';
import { DIELECTRIC_MATERIALS } from '@/data/materials';
import { calculateReflectanceSpectrum } from '@/utils/physics/tmm';
import { QuantumEfficiencyChart } from '@/components/charts/QuantumEfficiencyChart';
import type { EmitterLayer } from '@/types';

export function EmitterEditorModal() {
  const { showEmitterModal, setShowEmitterModal, params, setEmitterStructure } = useAppStore();
  const [localStructure, setLocalStructure] = useState<EmitterLayer[]>(params.emitterStructure);

  if (!showEmitterModal) return null;

  const previewReflectance = useMemo(() => {
    return calculateReflectanceSpectrum(localStructure, 200, 5000, 150);
  }, [localStructure]);

  const handleAddLayer = () => {
    const defaultMat = DIELECTRIC_MATERIALS[0];
    setLocalStructure([
      ...localStructure,
      {
        thickness: 100,
        material: defaultMat.name,
        n: defaultMat.n,
        k: defaultMat.k,
        dn_dT: defaultMat.dn_dT,
        dk_dT: defaultMat.dk_dT,
        referenceTemperature: defaultMat.referenceTemperature,
      },
    ]);
  };

  const handleRemoveLayer = (index: number) => {
    if (localStructure.length <= 1) return;
    setLocalStructure(localStructure.filter((_, i) => i !== index));
  };

  const handleUpdateLayer = (index: number, updates: Partial<EmitterLayer>) => {
    setLocalStructure(localStructure.map((layer, i) => 
      i === index ? { ...layer, ...updates } : layer
    ));
  };

  const handleMaterialChange = (index: number, materialName: string) => {
    const mat = DIELECTRIC_MATERIALS.find(m => m.name === materialName);
    if (mat) {
      handleUpdateLayer(index, {
        material: materialName,
        n: mat.n,
        k: mat.k,
        dn_dT: mat.dn_dT,
        dk_dT: mat.dk_dT,
        referenceTemperature: mat.referenceTemperature,
      });
    }
  };

  const handleSave = () => {
    setEmitterStructure(localStructure);
    setShowEmitterModal(false);
  };

  const handleReset = () => {
    setLocalStructure(params.emitterStructure);
  };

  const getLayerColor = (index: number, total: number) => {
    const hue = (index / total) * 60 + 200;
    return `hsl(${hue}, 60%, 50%)`;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
      <div className="glass-card w-full max-w-5xl max-h-[85vh] flex flex-col animate-slide-in">
        <div className="flex items-center justify-between p-5 border-b border-dark-600">
          <h2 className="font-display text-xl font-bold text-dark-100">
            选择性发射极结构编辑器
          </h2>
          <button
            onClick={() => setShowEmitterModal(false)}
            className="p-2 rounded-lg hover:bg-dark-700 transition-colors text-dark-300 hover:text-white"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-hidden flex">
          <div className="w-1/2 p-5 overflow-y-auto scrollbar-thin border-r border-dark-600">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-dark-100">膜层结构</h3>
                <div className="flex gap-2">
                  <button
                    onClick={handleReset}
                    className="btn-secondary px-3 py-1.5 text-xs flex items-center gap-1"
                  >
                    <RotateCcw className="w-3 h-3" />
                    重置
                  </button>
                  <button
                    onClick={handleAddLayer}
                    className="btn-primary px-3 py-1.5 text-xs flex items-center gap-1"
                  >
                    <Plus className="w-3 h-3" />
                    添加层
                  </button>
                </div>
              </div>

              <div className="space-y-2">
                {localStructure.map((layer, index) => (
                  <div
                    key={index}
                    className="bg-dark-700/50 rounded-xl p-4 border border-dark-600 hover:border-primary-500/30 transition-all"
                  >
                    <div className="flex items-center gap-3 mb-3">
                      <GripVertical className="w-4 h-4 text-dark-500" />
                      <div 
                        className="w-3 h-3 rounded-full" 
                        style={{ backgroundColor: getLayerColor(index, localStructure.length) }}
                      />
                      <span className="font-mono text-sm text-dark-200">
                        层 {index + 1}
                      </span>
                      {localStructure.length > 1 && (
                        <button
                          onClick={() => handleRemoveLayer(index)}
                          className="ml-auto p-1.5 rounded-lg hover:bg-dark-600 text-dark-400 hover:text-red-400 transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                    <div className="grid grid-cols-3 gap-3">
                      <div>
                        <label className="block text-xs text-dark-400 mb-1">材料</label>
                        <select
                          value={layer.material}
                          onChange={(e) => handleMaterialChange(index, e.target.value)}
                          className="input-field text-sm py-1.5"
                        >
                          {DIELECTRIC_MATERIALS.map((mat) => (
                            <option key={mat.name} value={mat.name}>
                              {mat.name}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs text-dark-400 mb-1">厚度 (nm)</label>
                        <input
                          type="number"
                          min="5"
                          max="1000"
                          value={layer.thickness}
                          onChange={(e) => handleUpdateLayer(index, { thickness: Number(e.target.value) })}
                          className="input-field text-sm py-1.5"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-dark-400 mb-1">n / k</label>
                        <div className="flex gap-2">
                          <input
                            type="number"
                            step="0.01"
                            value={layer.n}
                            onChange={(e) => handleUpdateLayer(index, { n: Number(e.target.value) })}
                            className="input-field text-sm py-1.5 flex-1"
                          />
                          <input
                            type="number"
                            step="0.01"
                            value={layer.k}
                            onChange={(e) => handleUpdateLayer(index, { k: Number(e.target.value) })}
                            className="input-field text-sm py-1.5 flex-1"
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-4 p-4 bg-dark-900/50 rounded-xl">
                <div className="flex items-center gap-2 text-sm text-dark-300 mb-2">
                  <Eye className="w-4 h-4" />
                  结构预览 (从上到下)
                </div>
                <div className="space-y-1">
                  <div className="h-6 bg-dark-600/50 rounded flex items-center justify-center text-xs text-dark-400">
                    空气 (n=1.0)
                  </div>
                  {[...localStructure].reverse().map((layer, index) => (
                    <div
                      key={index}
                      className="h-8 rounded flex items-center justify-center text-xs font-mono"
                      style={{ 
                        backgroundColor: getLayerColor(localStructure.length - 1 - index, localStructure.length),
                        opacity: 0.6,
                      }}
                    >
                      {layer.material} ({layer.thickness}nm)
                    </div>
                  ))}
                  <div className="h-6 bg-dark-500/50 rounded flex items-center justify-center text-xs text-dark-300">
                    电池基底
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="w-1/2 p-5 overflow-y-auto scrollbar-thin">
            <h3 className="font-semibold text-dark-100 mb-4">反射谱预览</h3>
            <div className="chart-container">
              <QuantumEfficiencyChart
                qeData={[]}
                reflectanceData={previewReflectance}
                width={450}
                height={300}
              />
            </div>

            <div className="mt-4 p-4 bg-dark-800/50 rounded-xl">
              <h4 className="text-sm font-semibold text-dark-200 mb-2">提示</h4>
              <ul className="text-xs text-dark-400 space-y-1">
                <li>• 金属层（W、Pt、Au）用于红外反射</li>
                <li>• 介质层（SiO₂、Si₃N₄）用于干涉滤波</li>
                <li>• 优化后的结构会反射亚带隙光子，提高能量利用率</li>
                <li>• 勾选"优化选择性发射极"可自动优化层厚</li>
              </ul>
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-3 p-5 border-t border-dark-600">
          <button
            onClick={() => setShowEmitterModal(false)}
            className="btn-secondary px-5 py-2"
          >
            取消
          </button>
          <button
            onClick={handleSave}
            className="btn-primary px-5 py-2"
          >
            保存结构
          </button>
        </div>
      </div>
    </div>
  );
}
