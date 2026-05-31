import { useState, useEffect } from 'react';
import { X, Check, Info } from 'lucide-react';
import type { JianziEditorProps, JianziComponents } from '@/types';
import { cn } from '@/lib/utils';

export default function JianziEditor({
  jianzi,
  dictionary,
  onUpdate,
  onClose,
}: JianziEditorProps) {
  const [tempComponents, setTempComponents] = useState<JianziComponents | null>(null);
  const [hasChanges, setHasChanges] = useState(false);

  useEffect(() => {
    if (jianzi) {
      setTempComponents({ ...jianzi.components });
      setHasChanges(false);
    } else {
      setTempComponents(null);
    }
  }, [jianzi]);

  if (!jianzi || !tempComponents) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-tanmu/60 bg-xuanzhi">
        <Info className="w-12 h-12 mb-4 opacity-50" />
        <p className="text-lg font-kai">请选择一个减字进行编辑</p>
        <p className="text-sm mt-2">点击左侧谱面中的检测框</p>
      </div>
    );
  }

  const handleComponentChange = (
    key: keyof JianziComponents,
    value: string
  ) => {
    setTempComponents((prev) => {
      if (!prev) return prev;
      const newComponents = { ...prev, [key]: value };
      setHasChanges(
        newComponents.finger !== jianzi.components.finger ||
          newComponents.string !== jianzi.components.string ||
          newComponents.hui !== jianzi.components.hui
      );
      return newComponents;
    });
  };

  const handleConfirm = () => {
    if (!tempComponents || !hasChanges) return;
    onUpdate(jianzi.id, { components: tempComponents });
    setHasChanges(false);
  };

  const handleCancel = () => {
    setTempComponents({ ...jianzi.components });
    setHasChanges(false);
  };

  const fingerOptions = Object.entries(dictionary.fingers);
  const stringOptions = Object.entries(dictionary.strings);
  const huiOptions = Object.entries(dictionary.hui_positions);

  const getGongche = () => {
    const stringInfo = dictionary.strings[tempComponents.string];
    if (!stringInfo?.tuning) return '—';

    let baseNote = stringInfo.tuning;
    const huiInfo = dictionary.hui_positions[tempComponents.hui];

    if (huiInfo?.semitones) {
      const noteNames = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
      const baseIndex = noteNames.indexOf(baseNote[0]);
      const octave = parseInt(baseNote[1] || '4');
      const newIndex = (baseIndex + huiInfo.semitones) % 12;
      const newOctave = octave + Math.floor((baseIndex + huiInfo.semitones) / 12);
      baseNote = noteNames[newIndex] + newOctave;
    }

    return dictionary.gongche_map[baseNote] || baseNote;
  };

  const getFingerDescription = () => {
    const finger = dictionary.fingers[tempComponents.finger];
    if (!finger) return '';
    const typeText = finger.type === 'right' ? '右手' : finger.type === 'left' ? '左手' : '';
    return `${typeText}${finger.description || ''}`;
  };

  return (
    <div className="h-full flex flex-col bg-xuanzhi">
      <div className="flex items-center justify-between px-4 py-3 bg-tanmu text-xuanzhi border-b-2 border-tanmu-dark">
        <h3 className="text-lg font-kai font-bold">减字编辑</h3>
        <button
          onClick={onClose}
          className="p-1 hover:bg-tanmu-light rounded transition-colors"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <div className="bg-xuanzhi-dark rounded-lg p-4 border border-tanmu/20">
          <h4 className="text-sm font-semibold text-tanmu mb-3 font-kai">位置信息</h4>
          <div className="grid grid-cols-2 gap-2 text-sm text-tanmu">
            <div className="flex justify-between">
              <span className="text-tanmu/70">X:</span>
              <span className="font-mono">{jianzi.bbox.x.toFixed(0)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-tanmu/70">Y:</span>
              <span className="font-mono">{jianzi.bbox.y.toFixed(0)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-tanmu/70">宽度:</span>
              <span className="font-mono">{jianzi.bbox.width.toFixed(0)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-tanmu/70">高度:</span>
              <span className="font-mono">{jianzi.bbox.height.toFixed(0)}</span>
            </div>
          </div>
          <div className="mt-2 pt-2 border-t border-tanmu/10">
            <div className="flex justify-between text-sm">
              <span className="text-tanmu/70">置信度:</span>
              <span
                className={cn(
                  'font-mono font-semibold',
                  jianzi.confidence >= 0.9
                    ? 'text-green-600'
                    : jianzi.confidence >= 0.7
                      ? 'text-yellow-600'
                      : 'text-zhusha'
                )}
              >
                {(jianzi.confidence * 100).toFixed(1)}%
              </span>
            </div>
          </div>
        </div>

        <div className="bg-xuanzhi-dark rounded-lg p-4 border border-tanmu/20">
          <h4 className="text-sm font-semibold text-tanmu mb-3 font-kai">减字组件</h4>

          <div className="space-y-4">
            <div>
              <label className="block text-sm text-tanmu/70 mb-1">指法</label>
              <select
                value={tempComponents.finger}
                onChange={(e) => handleComponentChange('finger', e.target.value)}
                className="w-full px-3 py-2 bg-xuanzhi border border-tanmu/30 rounded text-tanmu focus:outline-none focus:ring-2 focus:ring-zhusha/50"
              >
                {fingerOptions.map(([key, value]) => (
                  <option key={key} value={key}>
                    {key} — {value.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm text-tanmu/70 mb-1">弦序</label>
              <select
                value={tempComponents.string}
                onChange={(e) => handleComponentChange('string', e.target.value)}
                className="w-full px-3 py-2 bg-xuanzhi border border-tanmu/30 rounded text-tanmu focus:outline-none focus:ring-2 focus:ring-zhusha/50"
              >
                {stringOptions.map(([key, value]) => (
                  <option key={key} value={key}>
                    {key} — {value.name} ({value.tuning})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm text-tanmu/70 mb-1">徽位</label>
              <select
                value={tempComponents.hui}
                onChange={(e) => handleComponentChange('hui', e.target.value)}
                className="w-full px-3 py-2 bg-xuanzhi border border-tanmu/30 rounded text-tanmu focus:outline-none focus:ring-2 focus:ring-zhusha/50"
              >
                {huiOptions.map(([key, value]) => (
                  <option key={key} value={key}>
                    {key}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        <div className="bg-xuanzhi-dark rounded-lg p-4 border border-tanmu/20">
          <h4 className="text-sm font-semibold text-tanmu mb-3 font-kai">解析结果</h4>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-tanmu/70 text-sm">工尺谱字:</span>
              <span className="text-3xl font-kai text-zhusha font-bold">
                {getGongche()}
              </span>
            </div>
            <div className="pt-2 border-t border-tanmu/10">
              <span className="text-tanmu/70 text-sm block mb-1">指法说明:</span>
              <p className="text-tanmu text-sm font-kai leading-relaxed">
                {getFingerDescription()}
              </p>
            </div>
            {dictionary.hui_positions[tempComponents.hui] && (
              <div className="pt-2 border-t border-tanmu/10">
                <span className="text-tanmu/70 text-sm block mb-1">音高:</span>
                <p className="text-tanmu text-sm font-mono">
                  {dictionary.strings[tempComponents.string]?.tuning || '—'}
                  {' + '}
                  {dictionary.hui_positions[tempComponents.hui]?.semitones || 0}半音
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="p-4 bg-xuanzhi-dark border-t border-tanmu/20">
        <div className="flex gap-2">
          <button
            onClick={handleCancel}
            disabled={!hasChanges}
            className={cn(
              'flex-1 py-2 px-4 rounded border transition-colors flex items-center justify-center gap-2',
              hasChanges
                ? 'border-tanmu/50 text-tanmu hover:bg-tanmu/10'
                : 'border-tanmu/20 text-tanmu/40 cursor-not-allowed'
            )}
          >
            <X className="w-4 h-4" />
            取消
          </button>
          <button
            onClick={handleConfirm}
            disabled={!hasChanges}
            className={cn(
              'flex-1 py-2 px-4 rounded transition-colors flex items-center justify-center gap-2',
              hasChanges
                ? 'bg-zhusha text-xuanzhi hover:bg-zhusha-light'
                : 'bg-tanmu/30 text-xuanzhi/50 cursor-not-allowed'
            )}
          >
            <Check className="w-4 h-4" />
            确认
          </button>
        </div>
        {hasChanges && (
          <p className="text-center text-xs text-zhusha mt-2">
            有未保存的修改
          </p>
        )}
      </div>
    </div>
  );
}
