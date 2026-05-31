import { useAppStore } from '../../store';

const layerColors: Record<string, string> = {
  ITO: '#E0E0E0',
  'PEDOT:PSS': '#4CAF50',
  PVK: '#9C27B0',
  TPD: '#FF9800',
  ZnO: '#2196F3',
  TiO2: '#607D8B',
  'PBDB-T': '#FF5722',
  PCBM: '#795548',
  CdSe: '#E91E63',
  InP: '#9C27B0',
  Perovskite: '#FFC107',
  CdS: '#00BCD4',
  ZnS: '#8BC34A',
  Ag: '#C0C0C0',
  Al: '#A0A0A0',
  Au: '#FFD700',
  Ca: '#D3D3D3',
};

export function DeviceStructurePreview() {
  const { inputParams } = useAppStore();
  const ds = inputParams.deviceStructure;

  const layers = [
    { name: ds.anode, thickness: ds.anodeThickness, type: 'anode', material: ds.anode },
    { name: ds.htl, thickness: ds.htlThickness, type: 'htl', material: ds.htl },
    { name: 'QD Layer', thickness: ds.qdLayerThickness, type: 'qdl', material: inputParams.qdMaterial },
    { name: ds.etl, thickness: ds.etlThickness, type: 'etl', material: ds.etl },
    { name: ds.cathode, thickness: ds.cathodeThickness, type: 'cathode', material: ds.cathode },
  ];

  const totalThickness = layers.reduce((sum, l) => sum + l.thickness, 0);
  const maxHeight = 400;

  return (
    <div className="glass-card p-6">
      <h3 className="text-lg font-semibold text-slate-200 mb-4">器件结构预览</h3>
      <div className="flex items-end justify-center gap-4 h-[500px]">
        <div className="flex flex-col-reverse items-center">
          {layers.map((layer, index) => {
            const height = (layer.thickness / totalThickness) * maxHeight;
            const color = layerColors[layer.material] || '#888888';
            return (
              <div
                key={index}
                className="group relative w-48 flex flex-col items-center justify-end transition-all duration-300 hover:scale-105 cursor-pointer"
                style={{ height: `${Math.max(height, 20)}px` }}
              >
                <div
                  className="w-full rounded-t-sm transition-all duration-300 group-hover:shadow-lg"
                  style={{
                    backgroundColor: color,
                    height: '100%',
                    boxShadow: `inset 0 2px 10px rgba(255,255,255,0.2), inset 0 -2px 10px rgba(0,0,0,0.2)`,
                  }}
                />
                <div className="absolute bottom-0 left-full ml-4 opacity-0 group-hover:opacity-100 transition-opacity duration-300 bg-space-900/90 border border-slate-500/30 rounded-lg p-3 min-w-[160px] z-10">
                  <p className="text-sm font-semibold text-slate-200">{layer.name}</p>
                  <p className="text-xs text-slate-400 font-mono">{layer.thickness} nm</p>
                  <p className="text-xs text-slate-500 mt-1">
                    {layer.type === 'anode' && '阳极'}
                    {layer.type === 'htl' && '空穴传输层'}
                    {layer.type === 'qdl' && '量子点发光层'}
                    {layer.type === 'etl' && '电子传输层'}
                    {layer.type === 'cathode' && '阴极'}
                  </p>
                </div>
                <p className="absolute -right-2 top-1/2 -translate-y-1/2 text-xs text-slate-500 font-mono transform translate-x-full">
                  {layer.thickness} nm
                </p>
              </div>
            );
          })}
        </div>
        <div className="flex flex-col justify-between h-[400px] ml-8">
          {layers.map((layer, index) => (
            <div
              key={index}
              className="flex items-center gap-2"
              style={{ height: `${(layer.thickness / totalThickness) * maxHeight}px` }}
            >
              <div
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: layerColors[layer.material] || '#888888' }}
              />
              <span className="text-xs text-slate-400">{layer.name}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="mt-6 text-center">
        <p className="text-sm text-slate-400">
          总厚度: <span className="text-quantum-400 font-mono font-semibold">{totalThickness} nm</span>
        </p>
      </div>
    </div>
  );
}
