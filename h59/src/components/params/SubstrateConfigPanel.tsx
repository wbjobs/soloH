import React, { useRef } from 'react';
import { Square, Upload, RotateCcw, RefreshCw } from 'lucide-react';
import { useAppStore } from '../../store/useAppStore';
import { CollapsiblePanel } from '../common/CollapsiblePanel';
import { NumberInput } from '../common/NumberInput';
import { parseSTL, simplifySTL, getSTLBoundingBox } from '../../engine/stl/parser';
import { radToDeg, degToRad } from '../../engine/math/vector';
import type { SubstrateType, MotionType } from '../../types';

const substrateTypeLabels: Record<SubstrateType, string> = {
  plane: '平板',
  sphere: '球面',
  aspheric: '非球面',
  stl: 'STL文件',
};

const motionTypeLabels: Record<MotionType, string> = {
  none: '无',
  rotation: '旋转',
  tilt: '倾转',
  planetary: '行星运动',
};

const axisLabels: Record<'x' | 'y' | 'z', string> = {
  x: 'X轴',
  y: 'Y轴',
  z: 'Z轴',
};

export const SubstrateConfigPanel: React.FC = () => {
  const {
    substrate,
    setSubstrate,
    setSubstrateSize,
    setSubstrateResolution,
    setSubstrateMotion,
  } = useAppStore();

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      let stlData = await parseSTL(file);
      stlData = simplifySTL(stlData, 10000);
      const bbox = getSTLBoundingBox(stlData);
      const maxDim = Math.max(bbox.size.x, bbox.size.y, bbox.size.z);
      const scale = 200 / maxDim;

      const scaledVertices = new Float32Array(stlData.vertices.length);
      for (let i = 0; i < stlData.vertices.length; i += 3) {
        scaledVertices[i] = (stlData.vertices[i] - bbox.center.x) * scale;
        scaledVertices[i + 1] = (stlData.vertices[i + 1] - bbox.center.y) * scale;
        scaledVertices[i + 2] = (stlData.vertices[i + 2] - bbox.center.z) * scale;
      }

      setSubstrate({
        type: 'stl',
        stlData: {
          ...stlData,
          vertices: scaledVertices,
        },
        size: {
          width: bbox.size.x * scale,
          height: bbox.size.y * scale,
        },
      });
    } catch (error) {
      console.error('STL parse error:', error);
    }
  };

  return (
    <>
      <CollapsiblePanel title="基板配置" icon={<Square className="w-4 h-4" />}>
        <div className="space-y-4">
          <div>
            <label className="text-xs text-slate-400 mb-1 block">基板类型</label>
            <div className="flex flex-wrap gap-1">
              {(Object.keys(substrateTypeLabels) as SubstrateType[]).map((type) => (
                <button
                  key={type}
                  onClick={() => setSubstrate({ type })}
                  className={`px-2 py-1.5 text-xs rounded transition-colors ${
                    substrate.type === type
                      ? 'bg-cyan-600 text-white'
                      : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                  }`}
                >
                  {substrateTypeLabels[type]}
                </button>
              ))}
            </div>
          </div>

        {substrate.type === 'stl' && (
          <div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".stl"
              onChange={handleFileUpload}
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="w-full py-3 flex items-center justify-center gap-2 text-sm text-slate-300 border-2 border-dashed border-slate-600 rounded-lg hover:border-cyan-500 hover:bg-cyan-500/5 transition-colors"
            >
              <Upload className="w-4 h-4" />
              {substrate.stlData ? '重新选择STL文件' : '上传STL文件'}
            </button>
            {substrate.stlData && (
              <p className="text-xs text-green-400 mt-2 text-center">
                ✓ 已加载 {(substrate.stlData.faces.length / 3).toLocaleString()} 个三角形
              </p>
            )}
          </div>
        )}

        <div className="grid grid-cols-3 gap-2">
          <NumberInput
            label="X 位置"
            value={substrate.position.x}
            onChange={(v) => setSubstrate({ position: { ...substrate.position, x: v } })}
            step={1}
            unit="mm"
          />
          <NumberInput
            label="Y 位置"
            value={substrate.position.y}
            onChange={(v) => setSubstrate({ position: { ...substrate.position, y: v } })}
            step={1}
            unit="mm"
          />
          <NumberInput
            label="Z 位置"
            value={substrate.position.z}
            onChange={(v) => setSubstrate({ position: { ...substrate.position, z: v } })}
            step={1}
            unit="mm"
          />
        </div>

        <div className="grid grid-cols-3 gap-2">
          <NumberInput
            label="X 旋转"
            value={radToDeg(substrate.orientation.x)}
            onChange={(v) =>
              setSubstrate({
                orientation: { ...substrate.orientation, x: degToRad(v) },
              })
            }
            step={1}
            min={-180}
            max={180}
            unit="°"
          />
          <NumberInput
            label="Y 旋转"
            value={radToDeg(substrate.orientation.y)}
            onChange={(v) =>
              setSubstrate({
                orientation: { ...substrate.orientation, y: degToRad(v) },
              })
            }
            step={1}
            min={-180}
            max={180}
            unit="°"
          />
          <NumberInput
            label="Z 旋转"
            value={radToDeg(substrate.orientation.z)}
            onChange={(v) =>
              setSubstrate({
                orientation: { ...substrate.orientation, z: degToRad(v) },
              })
            }
            step={1}
            min={-180}
            max={180}
            unit="°"
          />
        </div>

        {(substrate.type === 'plane' || substrate.type === 'aspheric') && (
          <div className="grid grid-cols-2 gap-2">
            <NumberInput
              label="宽度"
              value={substrate.size.width}
              onChange={(v) => setSubstrateSize({ width: v })}
              step={1}
              min={10}
              max={500}
              unit="mm"
            />
            <NumberInput
              label="高度"
              value={substrate.size.height}
              onChange={(v) => setSubstrateSize({ height: v })}
              step={1}
              min={10}
              max={500}
              unit="mm"
            />
          </div>
        )}

        {substrate.type === 'sphere' && (
          <NumberInput
            label="半径"
            value={substrate.size.radius || 100}
            onChange={(v) => setSubstrateSize({ radius: v })}
            step={1}
            min={10}
            max={500}
            unit="mm"
          />
        )}

        {substrate.type === 'aspheric' && (
          <NumberInput
            label="曲率"
            value={substrate.size.curvature || 0.01}
            onChange={(v) => setSubstrateSize({ curvature: v })}
            step={0.001}
            min={0.001}
            max={0.1}
          />
        )}

        <div className="grid grid-cols-2 gap-2">
          <NumberInput
            label="X 分辨率"
            value={substrate.resolution.x}
            onChange={(v) => setSubstrateResolution({ x: Math.round(v) })}
            step={5}
            min={10}
            max={200}
          />
          <NumberInput
            label="Y 分辨率"
            value={substrate.resolution.y}
            onChange={(v) => setSubstrateResolution({ y: Math.round(v) })}
            step={5}
            min={10}
            max={200}
          />
        </div>
      </div>
    </CollapsiblePanel>

    <CollapsiblePanel
      title="基板运动"
      icon={<RefreshCw className="w-4 h-4" />}
      defaultOpen={false}
    >
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-sm text-slate-300">启用运动</span>
          <button
            onClick={() => setSubstrateMotion({ enabled: !substrate.motion.enabled })}
            className={`w-12 h-6 rounded-full transition-colors ${
              substrate.motion.enabled ? 'bg-cyan-500' : 'bg-slate-600'
            }`}
          >
            <div
              className={`w-5 h-5 bg-white rounded-full shadow transition-transform ${
                substrate.motion.enabled ? 'translate-x-6' : 'translate-x-0.5'
              }`}
            />
          </button>
        </div>

        {substrate.motion.enabled && (
          <>
            <div>
              <label className="text-xs text-slate-400 mb-1 block">运动类型</label>
              <div className="flex gap-1">
                {(Object.keys(motionTypeLabels) as MotionType[]).map((type) => (
                  <button
                    key={type}
                    onClick={() => setSubstrateMotion({ type })}
                    className={`flex-1 px-2 py-1.5 text-xs rounded transition-colors ${
                      substrate.motion.type === type
                        ? 'bg-cyan-600 text-white'
                        : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                    }`}
                  >
                    {motionTypeLabels[type]}
                  </button>
                ))}
              </div>
            </div>

            {(substrate.motion.type === 'rotation' || substrate.motion.type === 'planetary') && (
              <>
                <div>
                  <label className="text-xs text-slate-400 mb-1 block">旋转轴</label>
                  <div className="flex gap-1">
                    {(['x', 'y', 'z'] as const).map((axis) => (
                      <button
                        key={axis}
                        onClick={() => setSubstrateMotion({ rotationAxis: axis })}
                        className={`flex-1 px-2 py-1.5 text-xs rounded transition-colors ${
                          substrate.motion.rotationAxis === axis
                            ? 'bg-cyan-600 text-white'
                            : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                        }`}
                      >
                        {axisLabels[axis]}
                      </button>
                    ))}
                  </div>
                </div>

                <NumberInput
                  label="旋转速度"
                  value={substrate.motion.rotationSpeed}
                  onChange={(v) => setSubstrateMotion({ rotationSpeed: v })}
                  step={1}
                  min={1}
                  max={360}
                  unit="°/转"
                />

                <div>
                  <label className="text-xs text-slate-400 mb-2 block">旋转中心</label>
                  <div className="grid grid-cols-3 gap-2">
                    <NumberInput
                      label="X"
                      value={substrate.motion.rotationCenter.x}
                      onChange={(v) =>
                        setSubstrateMotion({
                          rotationCenter: { ...substrate.motion.rotationCenter, x: v },
                        })
                      }
                      step={1}
                      unit="mm"
                    />
                    <NumberInput
                      label="Y"
                      value={substrate.motion.rotationCenter.y}
                      onChange={(v) =>
                        setSubstrateMotion({
                          rotationCenter: { ...substrate.motion.rotationCenter, y: v },
                        })
                      }
                      step={1}
                      unit="mm"
                    />
                    <NumberInput
                      label="Z"
                      value={substrate.motion.rotationCenter.z}
                      onChange={(v) =>
                        setSubstrateMotion({
                          rotationCenter: { ...substrate.motion.rotationCenter, z: v },
                        })
                      }
                      step={1}
                      unit="mm"
                    />
                  </div>
                </div>
              </>
            )}

            {substrate.motion.type === 'tilt' && (
              <>
                <div>
                  <label className="text-xs text-slate-400 mb-1 block">倾转轴</label>
                  <div className="flex gap-1">
                    {(['x', 'y', 'z'] as const).map((axis) => (
                      <button
                        key={axis}
                        onClick={() => setSubstrateMotion({ tiltAxis: axis })}
                        className={`flex-1 px-2 py-1.5 text-xs rounded transition-colors ${
                          substrate.motion.tiltAxis === axis
                            ? 'bg-cyan-600 text-white'
                            : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                        }`}
                      >
                        {axisLabels[axis]}
                      </button>
                    ))}
                  </div>
                </div>

                <NumberInput
                  label="倾摆角度"
                  value={substrate.motion.tiltAngle}
                  onChange={(v) => setSubstrateMotion({ tiltAngle: v })}
                  step={1}
                  min={1}
                  max={90}
                  unit="°"
                />
              </>
            )}

            {substrate.motion.type === 'planetary' && (
              <>
                <NumberInput
                  label="行星半径"
                  value={substrate.motion.planetaryRadius || 50}
                  onChange={(v) => setSubstrateMotion({ planetaryRadius: v })}
                  step={1}
                  min={10}
                  max={300}
                  unit="mm"
                />
                <NumberInput
                  label="行星转速"
                  value={substrate.motion.planetaryRotationSpeed || 60}
                  onChange={(v) => setSubstrateMotion({ planetaryRotationSpeed: v })}
                  step={1}
                  min={1}
                  max={360}
                  unit="°/转"
                />
              </>
            )}

            <NumberInput
              label="积分步数"
              value={substrate.motion.integrationSteps}
              onChange={(v) => setSubstrateMotion({ integrationSteps: Math.round(v) })}
              step={1}
              min={4}
              max={360}
            />
          </>
        )}
      </div>
    </CollapsiblePanel>
    </>
  );
};
