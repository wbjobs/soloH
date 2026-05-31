import { useState, useEffect, useCallback, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Download,
  FileJson,
  FileText,
  Edit3,
  BookOpen,
  Music,
} from 'lucide-react';
import Navbar from '@/components/Navbar';
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

const gongcheTable = [
  { jianzi: '散一', gongche: '合', note: 'C4', description: '散音第一弦，宫音' },
  { jianzi: '散二', gongche: '四', note: 'D4', description: '散音第二弦，商音' },
  { jianzi: '散三', gongche: '一', note: 'E4', description: '散音第三弦，角音' },
  { jianzi: '散四', gongche: '上', note: 'F4', description: '散音第四弦，清角' },
  { jianzi: '散五', gongche: '尺', note: 'G4', description: '散音第五弦，徵音' },
  { jianzi: '散六', gongche: '工', note: 'A4', description: '散音第六弦，羽音' },
  { jianzi: '散七', gongche: '凡', note: 'B4', description: '散音第七弦，变宫' },
  { jianzi: '按七徽', gongche: '六', note: 'C5', description: '按音七徽，高八度宫' },
  { jianzi: '按九徽', gongche: '五', note: 'D5', description: '按音九徽，高八度商' },
  { jianzi: '按十徽', gongche: '乙', note: 'E5', description: '按音十徽，高八度角' },
  { jianzi: '泛七徽', gongche: '六', note: 'C5', description: '泛音七徽，清越宫音' },
  { jianzi: '泛九徽', gongche: '工', note: 'A4', description: '泛音九徽，清越羽音' },
];

const generateMockJianziList = (): Jianzi[] => {
  const fingers = ['勾', '挑', '抹', '剔', '散', '按', '泛'];
  const strings = ['一', '二', '三', '四', '五', '六', '七'];
  const huis = ['七徽', '九徽', '十徽', '八徽', '六徽', '五徽', ''];

  const jianziList: Jianzi[] = [];
  const totalCount = 48;

  for (let i = 0; i < totalCount; i++) {
    const finger = fingers[Math.floor(Math.random() * fingers.length)];
    const string = strings[Math.floor(Math.random() * strings.length)];
    const hui = finger === '散' ? '' : huis[Math.floor(Math.random() * (huis.length - 1))];

    const noteIndex = parseInt(string) - 1;
    const notes = ['C4', 'D4', 'E4', 'F4', 'G4', 'A4', 'B4'];
    const gongche = mockDictionary.gongche_map[notes[noteIndex]] || '';

    const fingerDesc = mockDictionary.fingers[finger]?.description || '';
    const stringDesc = mockDictionary.strings[string]?.name || '';
    const huiDesc = hui ? mockDictionary.hui_positions[hui]?.name || '' : '';
    const description = `${fingerDesc}${stringDesc}${huiDesc ? '于' + huiDesc : ''}`;

    jianziList.push({
      id: `jianzi-${i}`,
      bbox: {
        x: 100 + Math.random() * 200,
        y: 100 + Math.random() * 300,
        width: 50 + Math.random() * 15,
        height: 60 + Math.random() * 15,
      },
      components: {
        finger,
        string,
        hui,
      },
      confidence: 0.65 + Math.random() * 0.33,
      gongche,
      description,
    });
  }

  return jianziList;
};

export default function ResultPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const state = location.state as { jianziList?: Jianzi[]; fileName?: string } | null;

  const [jianziList, setJianziList] = useState<Jianzi[]>([]);
  const [fileName, setFileName] = useState<string>('');
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    if (state?.jianziList && state.jianziList.length > 0) {
      setJianziList(state.jianziList);
      setFileName(state.fileName || '识别结果');
    } else {
      setJianziList(generateMockJianziList());
      setFileName('示例琴谱识别结果');
    }
  }, [state]);

  const verticalColumns = useMemo(() => {
    const cols: Jianzi[][] = [];
    const itemsPerCol = Math.ceil(jianziList.length / 6);

    for (let col = 0; col < 6; col++) {
      const colItems: Jianzi[] = [];
      for (let row = 0; row < itemsPerCol; row++) {
        const index = col * itemsPerCol + row;
        if (index < jianziList.length) {
          colItems.push(jianziList[index]);
        }
      }
      cols.push(colItems);
    }

    return cols.reverse();
  }, [jianziList]);

  const selectedJianzi = jianziList.find((j) => j.id === selectedId);

  const handleBack = useCallback(() => {
    navigate('/editor');
  }, [navigate]);

  const handleEditJianzi = useCallback((jianzi: Jianzi) => {
    navigate('/editor', { state: { selectedJianziId: jianzi.id } });
  }, [navigate]);

  const handleExportGongche = useCallback(() => {
    const gongcheText = jianziList
      .map((j, i) => `${i + 1}. ${j.gongche || ''}\t// ${j.components.finger}${j.components.string}${j.components.hui}`)
      .join('\n');

    const header = `# ${fileName}\n# 工尺谱转译\n# 共 ${jianziList.length} 个减字\n# 导出时间: ${new Date().toLocaleString()}\n\n`;

    const blob = new Blob([header + gongcheText], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${fileName.replace(/\.[^/.]+$/, '')}_gongche.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }, [fileName, jianziList]);

  const handleExportJson = useCallback(() => {
    const data = {
      fileName,
      exportedAt: new Date().toISOString(),
      totalCount: jianziList.length,
      jianziList: jianziList.map((j) => ({
        id: j.id,
        components: j.components,
        confidence: j.confidence,
        gongche: j.gongche,
        description: j.description,
      })),
    };

    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${fileName.replace(/\.[^/.]+$/, '')}_result.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [fileName, jianziList]);

  const fullTranslation = useMemo(() => {
    return jianziList
      .map((j) => {
        const fingerName = mockDictionary.fingers[j.components.finger]?.name || j.components.finger;
        const stringName = mockDictionary.strings[j.components.string]?.name || j.components.string;
        const huiName = j.components.hui ? mockDictionary.hui_positions[j.components.hui]?.name || j.components.hui : '';

        if (j.components.finger === '散') {
          return `${fingerName}${stringName}`;
        }
        return `${fingerName}${stringName}${huiName ? '于' + huiName : ''}`;
      })
      .join('，') + '。';
  }, [jianziList]);

  const stats = {
    total: jianziList.length,
    highConfidence: jianziList.filter((j) => j.confidence >= 0.9).length,
    mediumConfidence: jianziList.filter((j) => j.confidence >= 0.7 && j.confidence < 0.9).length,
    lowConfidence: jianziList.filter((j) => j.confidence < 0.7).length,
  };

  return (
    <div className="min-h-screen flex flex-col bg-xuanzhi">
      <Navbar />

      <header className="bg-gradient-to-r from-tanmu to-tanmu-light text-xuanzhi px-6 py-4 border-b border-tanmu shadow-md">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={handleBack}
              className="p-2 hover:bg-tanmu-light rounded-lg transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-xl font-kai font-bold tracking-wider">识别结果</h1>
              <p className="text-xuanzhi/70 text-sm">{fileName}</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden lg:flex items-center gap-4 mr-4 text-sm text-xuanzhi/80">
              <span>总计: <strong className="text-xuanzhi">{stats.total}</strong></span>
              <span className="text-green-300">高置信: <strong>{stats.highConfidence}</strong></span>
              <span className="text-yellow-300">中置信: <strong>{stats.mediumConfidence}</strong></span>
              <span className="text-red-300">低置信: <strong>{stats.lowConfidence}</strong></span>
            </div>

            <button
              onClick={handleExportGongche}
              className="flex items-center gap-2 px-4 py-2 bg-xuanzhi/10 hover:bg-xuanzhi/20 rounded-lg transition-colors text-sm"
            >
              <FileText className="w-4 h-4" />
              <span className="hidden sm:inline">工尺谱</span>
            </button>

            <button
              onClick={handleExportJson}
              className="flex items-center gap-2 px-4 py-2 bg-xuanzhi/10 hover:bg-xuanzhi/20 rounded-lg transition-colors text-sm"
            >
              <FileJson className="w-4 h-4" />
              <span className="hidden sm:inline">JSON</span>
            </button>

            <button
              onClick={() => navigate('/audio', { state: { jianziList, fileName } })}
              className="flex items-center gap-2 px-4 py-2 bg-zhusha hover:bg-zhusha-light rounded-lg transition-colors text-sm font-semibold"
            >
              <Music className="w-4 h-4" />
              <span className="hidden sm:inline">合成音频</span>
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1 p-6 overflow-auto">
        <div className="max-w-7xl mx-auto">
          <div className="flex flex-col lg:flex-row gap-6">
            <div className="flex-1">
              <div className="scroll-border xuanzhi-bg p-6">
                <div className="flex items-center gap-2 mb-4 pb-3 border-b border-tanmu/20">
                  <BookOpen className="w-5 h-5 text-tanmu" />
                  <h2 className="text-lg font-kai font-bold text-tanmu">减字列表</h2>
                  <span className="text-sm text-tanmu/60 ml-auto">
                    竖排阅读 · 从右至左
                  </span>
                </div>

                <div className="flex gap-4 justify-center overflow-x-auto py-4">
                  {verticalColumns.map((column, colIndex) => (
                    <div
                      key={`col-${colIndex}`}
                      className="flex flex-col gap-3 flex-shrink-0"
                    >
                      {column.map((jianzi) => (
                        <div
                          key={jianzi.id}
                          onClick={() => setSelectedId(jianzi.id)}
                          className={cn(
                            'relative w-20 cursor-pointer transition-all duration-300 p-3 rounded-lg border-2 text-center',
                            selectedId === jianzi.id
                              ? 'bg-zhusha/10 border-zhusha shadow-lg scale-105'
                              : 'bg-xuanzhi border-tanmu/20 hover:border-tanmu/50 hover:shadow-md'
                          )}
                        >
                          <div className="jianzi-char text-2xl text-tanmu-dark mb-2">
                            {jianzi.components.finger}
                          </div>
                          <div className="text-xs text-tanmu/70 flex flex-col items-center gap-0.5">
                            <span>{jianzi.components.string}弦</span>
                            {jianzi.components.hui && (
                              <span className="text-[10px]">{jianzi.components.hui}</span>
                            )}
                          </div>

                          {jianzi.gongche && (
                            <div className="mt-2 pt-2 border-t border-tanmu/10">
                              <span className="text-xl font-kai text-zhusha font-bold">
                                {jianzi.gongche}
                              </span>
                            </div>
                          )}

                          <div
                            className={cn(
                              'absolute -top-2 -right-2 px-1.5 py-0.5 rounded text-[10px] font-mono',
                              jianzi.confidence >= 0.9
                                ? 'bg-green-500 text-white'
                                : jianzi.confidence >= 0.7
                                  ? 'bg-yellow-500 text-white'
                                  : 'bg-red-500 text-white'
                            )}
                          >
                            {(jianzi.confidence * 100).toFixed(0)}%
                          </div>

                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleEditJianzi(jianzi);
                            }}
                            className="absolute -bottom-2 -left-2 p-1 bg-tanmu text-xuanzhi rounded-full opacity-0 group-hover:opacity-100 transition-opacity hover:bg-tanmu-light"
                            title="跳转到编辑器"
                          >
                            <Edit3 className="w-3 h-3" />
                          </button>
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="w-full lg:w-96 flex-shrink-0 space-y-6">
              <div className="scroll-border xuanzhi-bg p-6">
                <div className="flex items-center gap-2 mb-4 pb-3 border-b border-tanmu/20">
                  <Music className="w-5 h-5 text-tanmu" />
                  <h2 className="text-lg font-kai font-bold text-tanmu">工尺谱对照表</h2>
                </div>

                <div className="grid grid-cols-2 gap-x-4 gap-y-2">
                  {gongcheTable.map((item, index) => (
                    <div
                      key={index}
                      className="flex items-center gap-2 p-2 rounded-lg bg-xuanzhi-dark/50 hover:bg-xuanzhi-dark transition-colors"
                    >
                      <span className="jianzi-char text-lg text-tanmu-dark w-12 text-center">
                        {item.jianzi}
                      </span>
                      <span className="text-xl font-kai text-zhusha font-bold w-8 text-center">
                        {item.gongche}
                      </span>
                      <span className="text-xs text-tanmu/60 flex-1 truncate" title={item.description}>
                        {item.description}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {selectedJianzi && (
                <div className="scroll-border xuanzhi-bg p-6 animate-fade-in-up">
                  <div className="flex items-center gap-2 mb-4 pb-3 border-b border-tanmu/20">
                    <Edit3 className="w-5 h-5 text-tanmu" />
                    <h2 className="text-lg font-kai font-bold text-tanmu">减字详情</h2>
                  </div>

                  <div className="text-center mb-4">
                    <div className="inline-block p-4 bg-xuanzhi-dark/50 rounded-xl">
                      <div className="jianzi-char text-5xl text-tanmu-dark">
                        {selectedJianzi.components.finger}
                      </div>
                      <div className="text-sm text-tanmu/70 mt-2">
                        {selectedJianzi.components.string}弦 {selectedJianzi.components.hui}
                      </div>
                    </div>
                  </div>

                  <div className="space-y-3">
                    <div className="flex justify-between items-center p-2 bg-xuanzhi-dark/30 rounded-lg">
                      <span className="text-tanmu/70 text-sm">工尺谱</span>
                      <span className="text-2xl font-kai text-zhusha font-bold">
                        {selectedJianzi.gongche || '-'}
                      </span>
                    </div>
                    <div className="flex justify-between items-center p-2 bg-xuanzhi-dark/30 rounded-lg">
                      <span className="text-tanmu/70 text-sm">指法</span>
                      <span className="text-tanmu-dark font-medium">
                        {mockDictionary.fingers[selectedJianzi.components.finger]?.name || selectedJianzi.components.finger}
                      </span>
                    </div>
                    <div className="flex justify-between items-center p-2 bg-xuanzhi-dark/30 rounded-lg">
                      <span className="text-tanmu/70 text-sm">弦序</span>
                      <span className="text-tanmu-dark font-medium">
                        {mockDictionary.strings[selectedJianzi.components.string]?.name || selectedJianzi.components.string}
                      </span>
                    </div>
                    {selectedJianzi.components.hui && (
                      <div className="flex justify-between items-center p-2 bg-xuanzhi-dark/30 rounded-lg">
                        <span className="text-tanmu/70 text-sm">徽位</span>
                        <span className="text-tanmu-dark font-medium">
                          {mockDictionary.hui_positions[selectedJianzi.components.hui]?.name || selectedJianzi.components.hui}
                        </span>
                      </div>
                    )}
                    <div className="flex justify-between items-center p-2 bg-xuanzhi-dark/30 rounded-lg">
                      <span className="text-tanmu/70 text-sm">置信度</span>
                      <span className={cn(
                        'font-mono font-medium',
                        selectedJianzi.confidence >= 0.9 ? 'text-green-600' :
                        selectedJianzi.confidence >= 0.7 ? 'text-yellow-600' : 'text-red-600'
                      )}>
                        {(selectedJianzi.confidence * 100).toFixed(1)}%
                      </span>
                    </div>
                  </div>

                  <button
                    onClick={() => handleEditJianzi(selectedJianzi)}
                    className="w-full mt-4 btn-classical flex items-center justify-center gap-2"
                  >
                    <Edit3 className="w-4 h-4" />
                    跳转到编辑器修改
                  </button>
                </div>
              )}
            </div>
          </div>

          <div className="mt-6 scroll-border xuanzhi-bg p-6">
            <div className="flex items-center gap-2 mb-4 pb-3 border-b border-tanmu/20">
              <FileText className="w-5 h-5 text-tanmu" />
              <h2 className="text-lg font-kai font-bold text-tanmu">白话文翻译</h2>
            </div>
            <div className="text-tanmu-dark leading-loose text-justify indent-8 font-kai text-lg">
              {fullTranslation}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
