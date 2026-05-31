import React from 'react';
import { Flame, Plus, Trash2, X } from 'lucide-react';
import { useAppStore } from '../../store/useAppStore';
import { CollapsiblePanel } from '../common/CollapsiblePanel';
import { NumberInput } from '../common/NumberInput';
import { radToDeg, degToRad } from '../../engine/math/vector';
import type { SourceType } from '../../types';

const sourceTypeLabels: Record<SourceType, string> = {
  point: '点源',
  small_face: '小平面源',
  extended: '扩展源',
};

export const SourceConfigPanel: React.FC = () => {
  const {
    sources,
    setSourceType,
    setSourcePosition,
    setSourceOrientation,
    setSourcePower,
    setSourceEmissionCoefficient,
    addSource,
    removeSource,
  } = useAppStore();

  return (
    <CollapsiblePanel title="蒸发源配置" icon={<Flame className="w-4 h-4" />}>
      <div className="space-y-4">
        {sources.map((source, index) => (
          <div
            key={source.id}
            className="p-3 rounded-lg bg-slate-900/50 border border-slate-700"
          >
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-orange-500/20 text-orange-400 flex items-center justify-center text-xs font-bold">
                  {index + 1}
                </span>
                <span className="text-sm font-medium text-slate-200">蒸发源</span>
              </div>
              {sources.length > 1 && (
                <button
                  onClick={() => removeSource(source.id)}
                  className="p-1 text-slate-500 hover:text-red-400 transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              )}
            </div>

            <div className="mb-3">
              <label className="text-xs text-slate-400 mb-1 block">源类型</label>
              <div className="flex gap-1">
                {(Object.keys(sourceTypeLabels) as SourceType[]).map((type) => (
                  <button
                    key={type}
                    onClick={() => setSourceType(source.id, type)}
                    className={`flex-1 px-2 py-1.5 text-xs rounded transition-colors ${
                      source.type === type
                        ? 'bg-cyan-600 text-white'
                        : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                    }`}
                  >
                    {sourceTypeLabels[type]}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-3 gap-2 mb-3">
              <NumberInput
                label="X 位置"
                value={source.position.x}
                onChange={(v) => setSourcePosition(source.id, { x: v })}
                step={1}
                unit="mm"
              />
              <NumberInput
                label="Y 位置"
                value={source.position.y}
                onChange={(v) => setSourcePosition(source.id, { y: v })}
                step={1}
                unit="mm"
              />
              <NumberInput
                label="Z 位置"
                value={source.position.z}
                onChange={(v) => setSourcePosition(source.id, { z: v })}
                step={1}
                unit="mm"
              />
            </div>

            <div className="grid grid-cols-3 gap-2 mb-3">
              <NumberInput
                label="X 旋转"
                value={radToDeg(source.orientation.x)}
                onChange={(v) => setSourceOrientation(source.id, { x: degToRad(v) })}
                step={1}
                min={-180}
                max={180}
                unit="°"
              />
              <NumberInput
                label="Y 旋转"
                value={radToDeg(source.orientation.y)}
                onChange={(v) => setSourceOrientation(source.id, { y: degToRad(v) })}
                step={1}
                min={-180}
                max={180}
                unit="°"
              />
              <NumberInput
                label="Z 旋转"
                value={radToDeg(source.orientation.z)}
                onChange={(v) => setSourceOrientation(source.id, { z: degToRad(v) })}
                step={1}
                min={-180}
                max={180}
                unit="°"
              />
            </div>

            <div className="grid grid-cols-2 gap-2">
              <NumberInput
                label="蒸发功率"
                value={source.power}
                onChange={(v) => setSourcePower(source.id, v)}
                step={0.1}
                min={0}
              />
              <NumberInput
                label="发射系数"
                value={source.emissionCoefficient}
                onChange={(v) => setSourceEmissionCoefficient(source.id, v)}
                step={0.1}
                min={1}
                max={10}
              />
            </div>
          </div>
        ))}

        <button
          onClick={addSource}
          className="w-full py-2 flex items-center justify-center gap-2 text-sm text-cyan-400 border border-dashed border-cyan-600/50 rounded-lg hover:bg-cyan-600/10 transition-colors"
        >
          <Plus className="w-4 h-4" />
          添加蒸发源
        </button>
      </div>
    </CollapsiblePanel>
  );
};
