import React from 'react';
import { Shield, Plus, Trash2, Box, Circle, CircleDot } from 'lucide-react';
import { useAppStore } from '../../store/useAppStore';
import { CollapsiblePanel } from '../common/CollapsiblePanel';
import { NumberInput } from '../common/NumberInput';
import type { OccluderShape } from '../../types';

const shapeLabels: Record<OccluderShape, string> = {
  box: '长方体',
  cylinder: '圆柱体',
  sphere: '球体',
};

const shapeIcons: Record<OccluderShape, React.ReactNode> = {
  box: <Box className="w-3 h-3" />,
  cylinder: <Circle className="w-3 h-3" />,
  sphere: <CircleDot className="w-3 h-3" />,
};

export const OccluderConfigPanel: React.FC = () => {
  const {
    occluders,
    addOccluder,
    removeOccluder,
    setOccluderPosition,
    setOccluderOrientation,
    setOccluderShape,
    setOccluderSize,
  } = useAppStore();

  return (
    <CollapsiblePanel
      title="遮挡物"
      icon={<Shield className="w-4 h-4" />}
      defaultOpen={false}
    >
      <div className="space-y-4">
        <button
          onClick={addOccluder}
          className="w-full px-3 py-2 bg-cyan-600 hover:bg-cyan-500 text-white text-sm rounded flex items-center justify-center gap-2 transition-colors"
        >
          <Plus className="w-4 h-4" />
          添加遮挡物
        </button>

        {occluders.length === 0 ? (
          <div className="text-xs text-slate-500 text-center py-4">
            暂无遮挡物，点击上方按钮添加
          </div>
        ) : (
          <div className="space-y-3 max-h-80 overflow-y-auto pr-1">
            {occluders.map((occluder, index) => (
              <div
                key={occluder.id}
                className="border border-slate-600 rounded-lg p-3 bg-slate-900/50"
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    {shapeIcons[occluder.shape]}
                    <span className="text-sm text-slate-200">
                      遮挡物 {index + 1}
                    </span>
                  </div>
                  <button
                    onClick={() => removeOccluder(occluder.id)}
                    className="p-1 text-red-400 hover:text-red-300 hover:bg-red-900/30 rounded"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>

                <div className="mb-3">
                  <label className="text-xs text-slate-400 mb-1 block">形状</label>
                  <div className="flex gap-1">
                    {(Object.keys(shapeLabels) as OccluderShape[]).map((shape) => (
                      <button
                        key={shape}
                        onClick={() => setOccluderShape(occluder.id, shape)}
                        className={`flex-1 px-2 py-1.5 text-xs rounded transition-colors flex items-center justify-center gap-1 ${
                        occluder.shape === shape
                          ? 'bg-cyan-600 text-white'
                          : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                      }`}
                      >
                        {shapeIcons[shape]}
                        {shapeLabels[shape]}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="mb-3">
                  <label className="text-xs text-slate-400 mb-2 block">位置</label>
                  <div className="grid grid-cols-3 gap-2">
                    <NumberInput
                      label="X"
                      value={occluder.position.x}
                      onChange={(v) =>
                        setOccluderPosition(occluder.id, { x: v })
                      }
                      step={1}
                      unit="mm"
                    />
                    <NumberInput
                      label="Y"
                      value={occluder.position.y}
                      onChange={(v) =>
                        setOccluderPosition(occluder.id, { y: v })
                      }
                      step={1}
                      unit="mm"
                    />
                    <NumberInput
                      label="Z"
                      value={occluder.position.z}
                      onChange={(v) =>
                        setOccluderPosition(occluder.id, { z: v })
                      }
                      step={1}
                      unit="mm"
                    />
                  </div>
                </div>

                <div className="mb-3">
                  <label className="text-xs text-slate-400 mb-2 block">
                    旋转角度 (弧度)
                  </label>
                  <div className="grid grid-cols-3 gap-2">
                    <NumberInput
                      label="X"
                      value={occluder.orientation.x}
                      onChange={(v) =>
                        setOccluderOrientation(occluder.id, { x: v })
                      }
                      step={0.1}
                      unit="rad"
                    />
                    <NumberInput
                      label="Y"
                      value={occluder.orientation.y}
                      onChange={(v) =>
                        setOccluderOrientation(occluder.id, { y: v })
                      }
                      step={0.1}
                      unit="rad"
                    />
                    <NumberInput
                      label="Z"
                      value={occluder.orientation.z}
                      onChange={(v) =>
                        setOccluderOrientation(occluder.id, { z: v })
                      }
                      step={0.1}
                      unit="rad"
                    />
                  </div>
                </div>

                {occluder.shape === 'box' && (
                  <div>
                    <label className="text-xs text-slate-400 mb-2 block">
                      尺寸
                    </label>
                    <div className="grid grid-cols-3 gap-2">
                      <NumberInput
                        label="宽"
                        value={occluder.size.width || 20}
                        onChange={(v) =>
                          setOccluderSize(occluder.id, { width: v })
                        }
                        step={1}
                        min={1}
                        unit="mm"
                      />
                      <NumberInput
                        label="高"
                        value={occluder.size.height || 20}
                        onChange={(v) =>
                          setOccluderSize(occluder.id, { height: v })
                        }
                        step={1}
                        min={1}
                        unit="mm"
                      />
                      <NumberInput
                        label="深"
                        value={occluder.size.depth || 20}
                        onChange={(v) =>
                          setOccluderSize(occluder.id, { depth: v })
                        }
                        step={1}
                        min={1}
                        unit="mm"
                      />
                    </div>
                  </div>
                )}

                {occluder.shape === 'cylinder' && (
                  <div>
                    <label className="text-xs text-slate-400 mb-2 block">
                      尺寸
                    </label>
                    <div className="grid grid-cols-2 gap-2">
                      <NumberInput
                        label="半径"
                        value={occluder.size.radius || 10}
                        onChange={(v) =>
                          setOccluderSize(occluder.id, { radius: v })
                        }
                        step={1}
                        min={1}
                        unit="mm"
                      />
                      <NumberInput
                        label="高度"
                        value={occluder.size.height || 20}
                        onChange={(v) =>
                          setOccluderSize(occluder.id, { height: v })
                        }
                        step={1}
                        min={1}
                        unit="mm"
                      />
                    </div>
                  </div>
                )}

                {occluder.shape === 'sphere' && (
                  <NumberInput
                    label="半径"
                    value={occluder.size.radius || 10}
                    onChange={(v) =>
                      setOccluderSize(occluder.id, { radius: v })
                    }
                    step={1}
                    min={1}
                    unit="mm"
                  />
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </CollapsiblePanel>
  );
};
