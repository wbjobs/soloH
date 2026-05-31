import { useState } from 'react';
import { X, Plus, Edit2, Trash2, Check, ChevronDown, ChevronUp } from 'lucide-react';
import { useAppStore, useAllMaterials } from '@/store/useAppStore';
import type { Material } from '@/types';
import { BUILTIN_MATERIALS } from '@/data/materials';

export function MaterialDatabaseModal() {
  const { showMaterialModal, setShowMaterialModal, customMaterials, addCustomMaterial, updateCustomMaterial, deleteCustomMaterial } = useAppStore();
  const allMaterials = useAllMaterials();
  
  const [editingMaterial, setEditingMaterial] = useState<Partial<Material> | null>(null);
  const [isAdding, setIsAdding] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (!showMaterialModal) return null;

  const handleAddNew = () => {
    setEditingMaterial({
      name: '',
      formula: '',
      bandgap: 1.0,
      bandgapTempCoeff: -0.0003,
      electronAffinity: 4.0,
      effectiveMassElectron: 0.1,
      effectiveMassHole: 0.5,
      refractiveIndex: 3.0,
      augerCoefficient: 1e-30,
      radiativeCoeff: 1e-10,
      mobilityElectron: 1000,
      mobilityHole: 100,
    });
    setIsAdding(true);
  };

  const handleEdit = (material: Material) => {
    setEditingMaterial(material);
    setIsAdding(false);
  };

  const handleSave = () => {
    if (!editingMaterial || !editingMaterial.name || !editingMaterial.formula) return;

    if (isAdding) {
      addCustomMaterial(editingMaterial as Omit<Material, 'id' | 'createdAt' | 'isCustom'>);
    } else if (editingMaterial.id) {
      updateCustomMaterial(editingMaterial.id, editingMaterial);
    }

    setEditingMaterial(null);
  };

  const handleDelete = (id: string) => {
    if (confirm('确定要删除这个材料吗？')) {
      deleteCustomMaterial(id);
    }
  };

  const materialFields = [
    { key: 'bandgap', label: '带隙 (eV)', type: 'number', step: '0.01' },
    { key: 'bandgapTempCoeff', label: '带隙温度系数 (eV/K)', type: 'number', step: '0.00001' },
    { key: 'electronAffinity', label: '电子亲和能 (eV)', type: 'number', step: '0.01' },
    { key: 'effectiveMassElectron', label: '电子有效质量 (m0)', type: 'number', step: '0.001' },
    { key: 'effectiveMassHole', label: '空穴有效质量 (m0)', type: 'number', step: '0.001' },
    { key: 'refractiveIndex', label: '折射率', type: 'number', step: '0.01' },
    { key: 'augerCoefficient', label: '俄歇系数 (cm⁶/s)', type: 'number', step: '1e-32' },
    { key: 'radiativeCoeff', label: '辐射复合系数 (cm³/s)', type: 'number', step: '1e-11' },
    { key: 'mobilityElectron', label: '电子迁移率 (cm²/Vs)', type: 'number', step: '1' },
    { key: 'mobilityHole', label: '空穴迁移率 (cm²/Vs)', type: 'number', step: '1' },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
      <div className="glass-card w-full max-w-4xl max-h-[85vh] flex flex-col animate-slide-in">
        <div className="flex items-center justify-between p-5 border-b border-dark-600">
          <h2 className="font-display text-xl font-bold text-dark-100">材料数据库</h2>
          <div className="flex items-center gap-3">
            <button
              onClick={handleAddNew}
              className="btn-primary px-4 py-2 text-sm flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              添加自定义材料
            </button>
            <button
              onClick={() => setShowMaterialModal(false)}
              className="p-2 rounded-lg hover:bg-dark-700 transition-colors text-dark-300 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto scrollbar-thin p-5">
          {(editingMaterial) ? (
            <div className="bg-dark-700/50 rounded-xl p-5 border border-primary-500/30">
              <h3 className="font-semibold text-dark-100 mb-4">
                {isAdding ? '添加新材料' : '编辑材料'}
              </h3>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-dark-300 mb-1">材料名称</label>
                  <input
                    type="text"
                    value={editingMaterial.name || ''}
                    onChange={(e) => setEditingMaterial({ ...editingMaterial, name: e.target.value })}
                    className="input-field"
                    placeholder="例如：铟镓砷"
                  />
                </div>
                <div>
                  <label className="block text-sm text-dark-300 mb-1">化学式</label>
                  <input
                    type="text"
                    value={editingMaterial.formula || ''}
                    onChange={(e) => setEditingMaterial({ ...editingMaterial, formula: e.target.value })}
                    className="input-field"
                    placeholder="例如：InGaAs"
                  />
                </div>
                {materialFields.map((field) => (
                  <div key={field.key}>
                    <label className="block text-sm text-dark-300 mb-1">{field.label}</label>
                    <input
                      type={field.type}
                      step={field.step}
                      value={(editingMaterial as any)[field.key] ?? ''}
                      onChange={(e) => setEditingMaterial({ 
                        ...editingMaterial, 
                        [field.key]: Number(e.target.value) 
                      })}
                      className="input-field"
                    />
                  </div>
                ))}
              </div>
              <div className="flex gap-3 mt-6">
                <button
                  onClick={handleSave}
                  className="btn-primary px-4 py-2 text-sm flex items-center gap-2"
                >
                  <Check className="w-4 h-4" />
                  保存
                </button>
                <button
                  onClick={() => setEditingMaterial(null)}
                  className="btn-secondary px-4 py-2 text-sm"
                >
                  取消
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="text-sm text-dark-400 mb-2">内置材料</div>
              {BUILTIN_MATERIALS.map((mat) => (
                <div
                  key={mat.id}
                  className="bg-dark-800/50 rounded-xl border border-dark-600 overflow-hidden transition-all hover:border-primary-500/30"
                >
                  <div
                    className="flex items-center justify-between p-4 cursor-pointer"
                    onClick={() => setExpandedId(expandedId === mat.id ? null : mat.id)}
                  >
                    <div>
                      <span className="font-semibold text-dark-100">{mat.name}</span>
                      <span className="ml-2 text-sm text-dark-400 font-mono">{mat.formula}</span>
                    </div>
                    <div className="flex items-center gap-4">
                      <span className="text-sm text-primary-400 font-mono">{mat.bandgap} eV</span>
                      <ChevronDown className={`w-5 h-5 text-dark-400 transition-transform ${expandedId === mat.id ? 'rotate-180' : ''}`} />
                    </div>
                  </div>
                  {expandedId === mat.id && (
                    <div className="px-4 pb-4 pt-2 border-t border-dark-700 grid grid-cols-3 gap-3 text-xs">
                      {materialFields.slice(0, 6).map((field) => (
                        <div key={field.key}>
                          <span className="text-dark-400">{field.label.split(' ')[0]}:</span>
                          <span className="ml-1 text-dark-200 font-mono">{(mat as any)[field.key]}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}

              {customMaterials.length > 0 && (
                <>
                  <div className="text-sm text-dark-400 mb-2 mt-6">自定义材料</div>
                  {customMaterials.map((mat) => (
                    <div
                      key={mat.id}
                      className="bg-dark-800/50 rounded-xl border border-accent-500/30 overflow-hidden transition-all hover:border-accent-500/50"
                    >
                      <div
                        className="flex items-center justify-between p-4 cursor-pointer"
                        onClick={() => setExpandedId(expandedId === mat.id ? null : mat.id)}
                      >
                        <div className="flex items-center gap-3">
                          <span className="px-2 py-0.5 bg-accent-500/20 text-accent-400 text-xs rounded-full">自定义</span>
                          <span className="font-semibold text-dark-100">{mat.name}</span>
                          <span className="ml-2 text-sm text-dark-400 font-mono">{mat.formula}</span>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="text-sm text-primary-400 font-mono">{mat.bandgap} eV</span>
                          <div className="flex items-center gap-1">
                            <button
                              onClick={(e) => { e.stopPropagation(); handleEdit(mat); }}
                              className="p-1.5 rounded-lg hover:bg-dark-700 text-dark-400 hover:text-primary-400 transition-colors"
                            >
                              <Edit2 className="w-4 h-4" />
                            </button>
                            <button
                              onClick={(e) => { e.stopPropagation(); handleDelete(mat.id); }}
                              className="p-1.5 rounded-lg hover:bg-dark-700 text-dark-400 hover:text-red-400 transition-colors"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                            <ChevronDown className={`w-5 h-5 text-dark-400 transition-transform ${expandedId === mat.id ? 'rotate-180' : ''}`} />
                          </div>
                        </div>
                      </div>
                      {expandedId === mat.id && (
                        <div className="px-4 pb-4 pt-2 border-t border-dark-700 grid grid-cols-3 gap-3 text-xs">
                          {materialFields.slice(0, 6).map((field) => (
                            <div key={field.key}>
                              <span className="text-dark-400">{field.label.split(' ')[0]}:</span>
                              <span className="ml-1 text-dark-200 font-mono">{(mat as any)[field.key]}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
