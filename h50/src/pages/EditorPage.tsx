import { useState, useEffect, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Play,
  RefreshCw,
  Sliders,
  Music,
  Save,
  FileJson,
} from 'lucide-react';
import ScoreEditor from '@/components/ScoreEditor';
import JianziEditor from '@/components/JianziEditor';
import type { Jianzi, Dictionary } from '@/types';
import { cn } from '@/lib/utils';

const mockDictionary: Dictionary = {
  fingers: {
    散: { name: '散音', type: 'right', description: '右手弹空弦' },
    勾: { name: '勾', type: 'right', description: '右指向内弹' },
    挑: { name: '挑', type: 'right', description: '右指向外弹' },
    抹: { name: '抹', type: 'right', description: '右指向内弹' },
    剔: { name: '剔', type: 'right', description: '右指向外弹' },
    打: { name: '打', type: 'right', description: '右指向内弹' },
    摘: { name: '摘', type: 'right', description: '右指向外弹' },
    托: { name: '托', type: 'right', description: '右指向外弹' },
    擘: { name: '擘', type: 'right', description: '右指向内弹' },
    按: { name: '按音', type: 'left', description: '左手按弦' },
    泛: { name: '泛音', type: 'left', description: '左手轻触徽位' },
  },
  strings: {
    一: { name: '一弦', open_note: 60, tuning: 'C4' },
    二: { name: '二弦', open_note: 62, tuning: 'D4' },
    三: { name: '三弦', open_note: 64, tuning: 'E4' },
    四: { name: '四弦', open_note: 65, tuning: 'F4' },
    五: { name: '五弦', open_note: 67, tuning: 'G4' },
    六: { name: '六弦', open_note: 69, tuning: 'A4' },
    七: { name: '七弦', open_note: 71, tuning: 'B4' },
  },
  hui_positions: {
    一徽: { name: '一徽', position: 1, ratio: 0.0625, semitones: 36 },
    二徽: { name: '二徽', position: 2, ratio: 0.1111, semitones: 31 },
    三徽: { name: '三徽', position: 3, ratio: 0.1667, semitones: 27 },
    四徽: { name: '四徽', position: 4, ratio: 0.25, semitones: 24 },
    五徽: { name: '五徽', position: 5, ratio: 0.3333, semitones: 19 },
    六徽: { name: '六徽', position: 6, ratio: 0.4, semitones: 16 },
    七徽: { name: '七徽', position: 7, ratio: 0.5, semitones: 12 },
    七分六: { name: '七分六', position: 7.6, ratio: 0.5625, semitones: 10 },
    八徽: { name: '八徽', position: 8, ratio: 0.6, semitones: 9 },
    九徽: { name: '九徽', position: 9, ratio: 0.6667, semitones: 7 },
    十徽: { name: '十徽', position: 10, ratio: 0.75, semitones: 5 },
    十一徽: { name: '十一徽', position: 11, ratio: 0.8333, semitones: 4 },
    十二徽: { name: '十二徽', position: 12, ratio: 0.8889, semitones: 2 },
    十三徽: { name: '十三徽', position: 13, ratio: 0.9375, semitones: 1 },
  },
  gongche_map: {
    C4: '合',
    D4: '四',
    E4: '一',
    F4: '上',
    G4: '尺',
    A4: '工',
    B4: '凡',
    C5: '六',
    D5: '五',
    E5: '乙',
    F5: '仩',
    G5: '伬',
    A5: '仜',
    B5: '匚',
    C6: '伍',
  },
};

const generateMockJianziList = (): Jianzi[] => {
  const fingers = ['勾', '挑', '抹', '剔', '散', '按'];
  const strings = ['一', '二', '三', '四', '五', '六', '七'];
  const huis = ['七徽', '九徽', '十徽', '八徽', '六徽', '五徽'];

  const jianziList: Jianzi[] = [];
  const baseX = 80;
  const baseY = 100;
  const colWidth = 100;
  const rowHeight = 80;

  for (let col = 0; col < 6; col++) {
    for (let row = 0; row < 8; row++) {
      const index = col * 8 + row;
      jianziList.push({
        id: `jianzi-${index}`,
        bbox: {
          x: baseX + col * colWidth + (Math.random() - 0.5) * 10,
          y: baseY + row * rowHeight + (Math.random() - 0.5) * 10,
          width: 50 + Math.random() * 15,
          height: 60 + Math.random() * 15,
        },
        components: {
          finger: fingers[Math.floor(Math.random() * fingers.length)],
          string: strings[Math.floor(Math.random() * strings.length)],
          hui: huis[Math.floor(Math.random() * huis.length)],
        },
        confidence: 0.7 + Math.random() * 0.28,
      });
    }
  }

  return jianziList;
};

export default function EditorPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const state = location.state as { imageUrl?: string; fileName?: string } | null;

  const [imageUrl, setImageUrl] = useState<string>('');
  const [fileName, setFileName] = useState<string>('');
  const [jianziList, setJianziList] = useState<Jianzi[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [dictionary] = useState<Dictionary>(mockDictionary);
  const [showPreprocess, setShowPreprocess] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);

  useEffect(() => {
    if (state?.imageUrl) {
      setImageUrl(state.imageUrl);
      setFileName(state.fileName || '未命名');
      setJianziList(generateMockJianziList());
    } else {
      const defaultImage = 'https://images.unsplash.com/photo-1516979187457-637abb4f9353?w=800&h=1000&fit=crop';
      setImageUrl(defaultImage);
      setFileName('示例琴谱');
      setJianziList(generateMockJianziList());
    }
  }, [state]);

  const selectedJianzi = jianziList.find((j) => j.id === selectedId) || null;

  const handleSelect = useCallback((id: string | null) => {
    setSelectedId(id);
  }, []);

  const handleUpdate = useCallback((id: string, updates: Partial<Jianzi>) => {
    setJianziList((prev) =>
      prev.map((j) => (j.id === id ? { ...j, ...updates } : j))
    );
  }, []);

  const handleCloseEditor = useCallback(() => {
    setSelectedId(null);
  }, []);

  const handlePlay = useCallback(() => {
    setIsPlaying(true);
    let index = 0;
    const playNext = () => {
      if (index >= jianziList.length) {
        setIsPlaying(false);
        setSelectedId(null);
        return;
      }
      setSelectedId(jianziList[index].id);
      index++;
      setTimeout(playNext, 400);
    };
    playNext();
  }, [jianziList]);

  const handleReidentify = useCallback(() => {
    setJianziList(generateMockJianziList());
    setSelectedId(null);
  }, []);

  const handleExport = useCallback(() => {
    const data = {
      fileName,
      jianziList,
      exportedAt: new Date().toISOString(),
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${fileName.replace(/\.[^/.]+$/, '')}_jianzi.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [fileName, jianziList]);

  const handleSave = useCallback(() => {
    alert('保存成功！');
  }, []);

  const handleBack = useCallback(() => {
    navigate('/upload');
  }, [navigate]);

  const handleJumpToJianzi = useCallback((id: string) => {
    setSelectedId(id);
  }, []);

  const stats = {
    total: jianziList.length,
    highConfidence: jianziList.filter((j) => j.confidence >= 0.9).length,
    mediumConfidence: jianziList.filter((j) => j.confidence >= 0.7 && j.confidence < 0.9).length,
    lowConfidence: jianziList.filter((j) => j.confidence < 0.7).length,
  };

  return (
    <div className="h-screen flex flex-col bg-tanmu-dark overflow-hidden">
      <header className="bg-tanmu text-xuanzhi px-6 py-3 flex items-center justify-between border-b border-tanmu-light shadow-lg flex-shrink-0">
        <div className="flex items-center gap-4">
          <button
            onClick={handleBack}
            className="p-2 hover:bg-tanmu-light rounded-lg transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-xl font-kai font-bold">谱面编辑器</h1>
            <p className="text-xuanzhi/70 text-sm">{fileName}</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden md:flex items-center gap-4 mr-4 text-sm text-xuanzhi/80">
            <span>总计: <strong className="text-xuanzhi">{stats.total}</strong></span>
            <span className="text-green-400">≥90%: <strong>{stats.highConfidence}</strong></span>
            <span className="text-yellow-400">≥70%: <strong>{stats.mediumConfidence}</strong></span>
            <span className="text-red-400">{'<70%: '}<strong>{stats.lowConfidence}</strong></span>
          </div>

          <button
            onClick={() => setShowPreprocess(!showPreprocess)}
            className={cn(
              'p-2 rounded-lg transition-colors flex items-center gap-2 text-sm',
              showPreprocess ? 'bg-tanmu-light text-xuanzhi' : 'hover:bg-tanmu-light text-xuanzhi/80'
            )}
          >
            <Sliders className="w-5 h-5" />
            <span className="hidden sm:inline">预处理</span>
          </button>

          <button
            onClick={handleReidentify}
            className="p-2 hover:bg-tanmu-light rounded-lg transition-colors text-xuanzhi/80 flex items-center gap-2 text-sm"
          >
            <RefreshCw className="w-5 h-5" />
            <span className="hidden sm:inline">重新识别</span>
          </button>

          <button
            onClick={handlePlay}
            disabled={isPlaying}
            className={cn(
              'p-2 rounded-lg transition-colors flex items-center gap-2 text-sm',
              isPlaying
                ? 'bg-zhusha text-xuanzhi'
                : 'hover:bg-tanmu-light text-xuanzhi/80'
            )}
          >
            <Music className="w-5 h-5" />
            <span className="hidden sm:inline">播放</span>
          </button>

          <button
            onClick={handleExport}
            className="p-2 hover:bg-tanmu-light rounded-lg transition-colors text-xuanzhi/80 flex items-center gap-2 text-sm"
          >
            <FileJson className="w-5 h-5" />
            <span className="hidden sm:inline">导出</span>
          </button>

          <button
            onClick={handleSave}
            className="px-4 py-2 bg-zhusha hover:bg-zhusha-light rounded-lg transition-colors text-xuanzhi flex items-center gap-2 text-sm font-semibold"
          >
            <Save className="w-5 h-5" />
            <span className="hidden sm:inline">保存</span>
          </button>
        </div>
      </header>

      {showPreprocess && (
        <div className="bg-tanmu/50 px-6 py-3 border-b border-tanmu-light flex items-center gap-6 flex-shrink-0">
          <span className="text-xuanzhi/80 text-sm">图像调整:</span>
          <div className="flex items-center gap-2">
            <span className="text-xuanzhi/60 text-sm">亮度</span>
            <input
              type="range"
              className="w-32 accent-zhusha"
              defaultValue={50}
            />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xuanzhi/60 text-sm">对比度</span>
            <input
              type="range"
              className="w-32 accent-zhusha"
              defaultValue={50}
            />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xuanzhi/60 text-sm">阈值</span>
            <input
              type="range"
              className="w-32 accent-zhusha"
              defaultValue={128}
              min={0}
              max={255}
            />
          </div>
          <button
            onClick={handleReidentify}
            className="ml-auto px-4 py-1.5 bg-tanmu-light hover:bg-tanmu text-xuanzhi rounded-lg text-sm transition-colors flex items-center gap-2"
          >
            <Play className="w-4 h-4" />
            应用并重新识别
          </button>
        </div>
      )}

      <div className="flex-1 flex overflow-hidden">
        <div className="flex-1 flex flex-col overflow-hidden">
          <ScoreEditor
            imageUrl={imageUrl}
            jianziList={jianziList}
            selectedId={selectedId}
            onSelect={handleSelect}
          />
        </div>

        <div className="w-80 border-l border-tanmu-light flex-shrink-0 flex flex-col overflow-hidden">
          <JianziEditor
            jianzi={selectedJianzi}
            dictionary={dictionary}
            onUpdate={handleUpdate}
            onClose={handleCloseEditor}
          />
        </div>
      </div>

      <div className="bg-tanmu border-t border-tanmu-light flex-shrink-0">
        <div className="px-4 py-2 border-b border-tanmu-light flex items-center justify-between">
          <h3 className="text-xuanzhi font-kai font-semibold text-sm">减字列表</h3>
          <span className="text-xuanzhi/60 text-xs">
            共 {jianziList.length} 个减字
          </span>
        </div>
        <div className="overflow-x-auto">
          <div className="flex gap-1 p-2 min-w-max">
            {jianziList.map((jianzi, index) => (
              <button
                key={jianzi.id}
                onClick={() => handleJumpToJianzi(jianzi.id)}
                className={cn(
                  'flex flex-col items-center px-3 py-2 rounded-lg transition-all min-w-[70px]',
                  jianzi.id === selectedId
                    ? 'bg-zhusha text-xuanzhi ring-2 ring-zhusha-light'
                    : 'bg-tanmu-light/50 text-xuanzhi/80 hover:bg-tanmu-light hover:text-xuanzhi'
                )}
              >
                <span className="text-lg font-kai font-bold">
                  {jianzi.components.finger}
                </span>
                <div className="text-xs flex items-center gap-1 mt-0.5">
                  <span>{jianzi.components.string}</span>
                  <span className="opacity-60">·</span>
                  <span className="truncate max-w-[40px]">{jianzi.components.hui}</span>
                </div>
                <span
                  className={cn(
                    'text-[10px] mt-0.5 font-mono',
                    jianzi.confidence >= 0.9
                      ? 'text-green-400'
                      : jianzi.confidence >= 0.7
                        ? 'text-yellow-400'
                        : 'text-red-400'
                  )}
                >
                  #{index + 1} {(jianzi.confidence * 100).toFixed(0)}%
                </span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
