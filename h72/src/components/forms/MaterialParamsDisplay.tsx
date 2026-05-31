import { qdMaterials, transportLayerMaterials, electrodeMaterials } from '../../data/materials';
import type { QDMaterial, TransportLayerMaterial, ElectrodeMaterial } from '../../types';

interface MaterialParamsDisplayProps {
  material: string;
  type: 'qd' | 'transport' | 'electrode';
}

export function MaterialParamsDisplay({ material, type }: MaterialParamsDisplayProps) {
  let params;
  if (type === 'qd') {
    params = qdMaterials[material as QDMaterial];
  } else if (type === 'transport') {
    params = transportLayerMaterials[material as TransportLayerMaterial];
  } else {
    params = electrodeMaterials[material as ElectrodeMaterial];
  }

  if (!params) return null;

  return (
    <div className="mt-3 p-3 bg-space-900/50 rounded-lg border border-slate-500/10">
      <p className="text-xs font-medium text-quantum-400 mb-2">材料参数</p>
      <div className="grid grid-cols-2 gap-2 text-xs">
        {'bandGap' in params && (
          <>
            <div>
              <span className="text-slate-500">带隙:</span>
              <span className="text-slate-300 font-mono ml-1">{params.bandGap} eV</span>
            </div>
            <div>
              <span className="text-slate-500">电子亲和能:</span>
              <span className="text-slate-300 font-mono ml-1">{params.electronAffinity} eV</span>
            </div>
            <div>
              <span className="text-slate-500">有效质量(mₑ):</span>
              <span className="text-slate-300 font-mono ml-1">{params.electronMass} m₀</span>
            </div>
            <div>
              <span className="text-slate-500">有效质量(mₕ):</span>
              <span className="text-slate-300 font-mono ml-1">{params.holeMass} m₀</span>
            </div>
            <div>
              <span className="text-slate-500">介电常数:</span>
              <span className="text-slate-300 font-mono ml-1">{params.permittivity} εᵣ</span>
            </div>
            <div>
              <span className="text-slate-500">折射率:</span>
              <span className="text-slate-300 font-mono ml-1">{params.refractiveIndex}</span>
            </div>
          </>
        )}
        {'workFunction' in params && (
          <>
            <div>
              <span className="text-slate-500">功函数:</span>
              <span className="text-slate-300 font-mono ml-1">{params.workFunction} eV</span>
            </div>
            <div>
              <span className="text-slate-500">电导率:</span>
              <span className="text-slate-300 font-mono ml-1">{params.conductivity.toExponential(2)} S/m</span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
