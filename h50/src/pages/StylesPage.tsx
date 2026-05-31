import React, { useState, useEffect } from 'react';
import {
  Music2,
  Play,
  Pause,
  Volume2,
  Info,
  ChevronRight,
  Loader2,
  Layers,
} from 'lucide-react';
import { getStyles, getStyleDetail } from '@/services/api';
import type { GuqinStyle } from '@/types/index';

const StylesPage: React.FC = () => {
  const [styles, setStyles] = useState<GuqinStyle[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedStyle, setSelectedStyle] = useState<GuqinStyle | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [playingStyle, setPlayingStyle] = useState<string | null>(null);
  const [audioElement, setAudioElement] = useState<HTMLAudioElement | null>(null);

  useEffect(() => {
    loadStyles();
    return () => {
      if (audioElement) {
        audioElement.pause();
      }
    };
  }, []);

  const loadStyles = async () => {
    try {
      setLoading(true);
      const data = await getStyles();
      setStyles(data);
      if (data.length > 0) {
        handleSelectStyle(data[0].id);
      }
    } catch (error) {
      console.error('Failed to load styles:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectStyle = async (styleId: string) => {
    try {
      setDetailLoading(true);
      const detail = await getStyleDetail(styleId);
      setSelectedStyle(detail);
    } catch (error) {
      console.error('Failed to load style detail:', error);
    } finally {
      setDetailLoading(false);
    }
  };

  const handlePlayDemo = (styleId: string) => {
    if (playingStyle === styleId && audioElement) {
      audioElement.pause();
      setPlayingStyle(null);
      return;
    }

    if (audioElement) {
      audioElement.pause();
    }

    const demoUrls: Record<string, string> = {
      traditional: '/demo/traditional.mp3',
      guangling: '/demo/guangling.mp3',
      yushan: '/demo/yushan.mp3',
      meian: '/demo/meian.mp3',
      zhucheng: '/demo/zhucheng.mp3',
      jiuyi: '/demo/jiuyi.mp3',
      shushan: '/demo/shushan.mp3',
    };

    const audio = new Audio(demoUrls[styleId] || demoUrls.traditional);
    audio.onended = () => setPlayingStyle(null);
    audio.play().catch(() => {
      setPlayingStyle(null);
    });
    setAudioElement(audio);
    setPlayingStyle(styleId);
  };

  const getParamLabel = (key: string) => {
    const labels: Record<string, string> = {
      tempo_modulation: '节奏变化',
      vibrato_intensity: '吟猱强度',
      vibrato_rate: '吟猱频率',
      glissando_smoothness: '滑音流畅度',
      harmonic_emphasis: '泛音强调',
      attack_smoothness: '起音柔和度',
      decay_extension: '余韵延长',
      reverb_amount: '混响量',
      brightness_correction: '音色明暗',
      note_gap: '音间隔',
      rubato: '自由节奏',
    };
    return labels[key] || key;
  };

  const getParamDescription = (key: string) => {
    const descriptions: Record<string, string> = {
      tempo_modulation: '控制演奏时的速度变化程度，数值越大节奏越自由',
      vibrato_intensity: '控制吟猱的幅度大小，影响左手按弦的摇动幅度',
      vibrato_rate: '控制吟猱的频率快慢，影响左手按弦的摇动速度',
      glissando_smoothness: '控制滑音的流畅程度，数值越大过渡越平滑',
      harmonic_emphasis: '控制泛音的突出程度，影响泛音与按音的音量对比',
      attack_smoothness: '控制起音的柔和程度，数值越大起音越平缓',
      decay_extension: '控制余韵的延长时间，数值越大余韵越长',
      reverb_amount: '控制混响效果的强度，模拟不同空间的声学效果',
      brightness_correction: '控制音色的明暗程度，数值越大音色越明亮',
      note_gap: '控制音符之间的间隔时间，影响乐句的连贯性',
      rubato: '控制自由节奏的程度，数值越大节奏弹性越大',
    };
    return descriptions[key] || '';
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#F5F0E6] flex items-center justify-center">
        <Loader2 className="animate-spin text-[#C0392B]" size={48} />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F5F0E6]">
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-[#4A2C1A] mb-2">流派风格</h1>
          <p className="text-[#4A2C1A]/70">探索古琴七大流派的独特艺术风格和演奏特点</p>
        </div>

        <div className="grid grid-cols-4 gap-6">
          <div className="col-span-1">
            <div className="bg-white rounded-xl shadow-md overflow-hidden sticky top-24">
              <div className="bg-[#4A2C1A] text-white px-4 py-3">
                <h3 className="font-semibold flex items-center gap-2">
                  <Layers size={18} />
                  流派列表
                </h3>
              </div>
              <div className="divide-y divide-[#4A2C1A]/10">
                {styles.map((style) => (
                  <button
                    key={style.id}
                    onClick={() => handleSelectStyle(style.id)}
                    className={`w-full text-left px-4 py-3 flex items-center justify-between transition-colors ${
                      selectedStyle?.id === style.id
                        ? 'bg-[#C0392B]/10 text-[#C0392B]'
                        : 'hover:bg-[#4A2C1A]/5 text-[#4A2C1A]'
                    }`}
                  >
                    <span className="font-medium">{style.name}</span>
                    <ChevronRight size={16} />
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="col-span-3 space-y-6">
            {detailLoading ? (
              <div className="flex items-center justify-center py-20">
                <Loader2 className="animate-spin text-[#C0392B]" size={40} />
              </div>
            ) : selectedStyle ? (
              <>
                <div className="bg-white rounded-xl shadow-md overflow-hidden">
                  <div className="bg-gradient-to-r from-[#4A2C1A] to-[#6B3A25] p-8 text-white">
                    <div className="flex items-start justify-between">
                      <div>
                        <h2 className="text-4xl font-bold mb-2">{selectedStyle.name}</h2>
                        <p className="text-white/80 text-lg max-w-2xl leading-relaxed">
                          {selectedStyle.description}
                        </p>
                      </div>
                      <button
                        onClick={() => handlePlayDemo(selectedStyle.id)}
                        className="flex items-center gap-2 bg-white text-[#C0392B] px-6 py-3 rounded-lg hover:bg-white/90 transition-colors font-medium shadow-lg"
                      >
                        {playingStyle === selectedStyle.id ? (
                          <Pause size={20} />
                        ) : (
                          <Play size={20} />
                        )}
                        {playingStyle === selectedStyle.id ? '暂停' : '试听'}
                      </button>
                    </div>
                  </div>
                </div>

                {selectedStyle.params && (
                  <div className="bg-white rounded-xl shadow-md p-6">
                    <h3 className="text-xl font-semibold text-[#4A2C1A] mb-6 flex items-center gap-2">
                      <Info size={20} />
                      风格参数详解
                    </h3>
                    <div className="grid grid-cols-2 gap-4">
                      {Object.entries(selectedStyle.params).map(([key, value]) => (
                        <div
                          key={key}
                          className="bg-[#F5F0E6] rounded-lg p-4 hover:bg-[#4A2C1A]/5 transition-colors"
                        >
                          <div className="flex items-center justify-between mb-2">
                            <span className="font-medium text-[#4A2C1A]">
                              {getParamLabel(key)}
                            </span>
                            <span className="text-lg font-bold text-[#C0392B]">
                              {(value * 100).toFixed(0)}%
                            </span>
                          </div>
                          <div className="h-2 bg-[#4A2C1A]/20 rounded-full overflow-hidden mb-2">
                            <div
                              className="h-full bg-gradient-to-r from-[#4A2C1A] to-[#C0392B] transition-all duration-500"
                              style={{ width: `${value * 100}%` }}
                            />
                          </div>
                          <p className="text-xs text-[#4A2C1A]/60 leading-relaxed">
                            {getParamDescription(key)}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="grid grid-cols-2 gap-6">
                  <div className="bg-white rounded-xl shadow-md p-6">
                    <h3 className="text-lg font-semibold text-[#4A2C1A] mb-4">演奏特点</h3>
                    <div className="space-y-3">
                      {selectedStyle.id === 'guangling' && (
                        <>
                          <div className="flex items-start gap-2">
                            <span className="text-[#C0392B] mt-1">•</span>
                            <p className="text-sm text-[#4A2C1A]/80">
                              跌宕多变，自由洒脱，节奏富于弹性
                            </p>
                          </div>
                          <div className="flex items-start gap-2">
                            <span className="text-[#C0392B] mt-1">•</span>
                            <p className="text-sm text-[#4A2C1A]/80">
                              吟猱幅度大，气韵生动，表现力丰富
                            </p>
                          </div>
                          <div className="flex items-start gap-2">
                            <span className="text-[#C0392B] mt-1">•</span>
                            <p className="text-sm text-[#4A2C1A]/80">
                              滑音流畅，如歌如诉，情感真挚
                            </p>
                          </div>
                        </>
                      )}
                      {selectedStyle.id === 'yushan' && (
                        <>
                          <div className="flex items-start gap-2">
                            <span className="text-[#C0392B] mt-1">•</span>
                            <p className="text-sm text-[#4A2C1A]/80">
                              清微淡远，中正平和，格调高雅
                            </p>
                          </div>
                          <div className="flex items-start gap-2">
                            <span className="text-[#C0392B] mt-1">•</span>
                            <p className="text-sm text-[#4A2C1A]/80">
                              音色温润，节奏沉稳，意境深远
                            </p>
                          </div>
                          <div className="flex items-start gap-2">
                            <span className="text-[#C0392B] mt-1">•</span>
                            <p className="text-sm text-[#4A2C1A]/80">
                              含蓄内敛，韵味悠长，有文人气息
                            </p>
                          </div>
                        </>
                      )}
                      {selectedStyle.id === 'meian' && (
                        <>
                          <div className="flex items-start gap-2">
                            <span className="text-[#C0392B] mt-1">•</span>
                            <p className="text-sm text-[#4A2C1A]/80">
                              刚劲有力，节奏明快，气势磅礴
                            </p>
                          </div>
                          <div className="flex items-start gap-2">
                            <span className="text-[#C0392B] mt-1">•</span>
                            <p className="text-sm text-[#4A2C1A]/80">
                              按音坚实，泛音清亮，对比鲜明
                            </p>
                          </div>
                          <div className="flex items-start gap-2">
                            <span className="text-[#C0392B] mt-1">•</span>
                            <p className="text-sm text-[#4A2C1A]/80">
                              旋律流畅，富于歌唱性，感染力强
                            </p>
                          </div>
                        </>
                      )}
                      {selectedStyle.id === 'zhucheng' && (
                        <>
                          <div className="flex items-start gap-2">
                            <span className="text-[#C0392B] mt-1">•</span>
                            <p className="text-sm text-[#4A2C1A]/80">
                              古朴厚重，刚柔相济，苍劲有力
                            </p>
                          </div>
                          <div className="flex items-start gap-2">
                            <span className="text-[#C0392B] mt-1">•</span>
                            <p className="text-sm text-[#4A2C1A]/80">
                              节奏紧凑，起落分明，结构严谨
                            </p>
                          </div>
                          <div className="flex items-start gap-2">
                            <span className="text-[#C0392B] mt-1">•</span>
                            <p className="text-sm text-[#4A2C1A]/80">
                              音韵铿锵，有金石之声
                            </p>
                          </div>
                        </>
                      )}
                      {selectedStyle.id === 'jiuyi' && (
                        <>
                          <div className="flex items-start gap-2">
                            <span className="text-[#C0392B] mt-1">•</span>
                            <p className="text-sm text-[#4A2C1A]/80">
                              雄健奔放，跌宕起伏，气势宏大
                            </p>
                          </div>
                          <div className="flex items-start gap-2">
                            <span className="text-[#C0392B] mt-1">•</span>
                            <p className="text-sm text-[#4A2C1A]/80">
                              音色饱满，力度变化丰富
                            </p>
                          </div>
                          <div className="flex items-start gap-2">
                            <span className="text-[#C0392B] mt-1">•</span>
                            <p className="text-sm text-[#4A2C1A]/80">
                              讲究气韵，注重意境的营造
                            </p>
                          </div>
                        </>
                      )}
                      {selectedStyle.id === 'shushan' && (
                        <>
                          <div className="flex items-start gap-2">
                            <span className="text-[#C0392B] mt-1">•</span>
                            <p className="text-sm text-[#4A2C1A]/80">
                              细腻婉约，清新雅致，意境幽远
                            </p>
                          </div>
                          <div className="flex items-start gap-2">
                            <span className="text-[#C0392B] mt-1">•</span>
                            <p className="text-sm text-[#4A2C1A]/80">
                              左手技巧丰富，吟猱细腻多变
                            </p>
                          </div>
                          <div className="flex items-start gap-2">
                            <span className="text-[#C0392B] mt-1">•</span>
                            <p className="text-sm text-[#4A2C1A]/80">
                              音色柔美，富于抒情性
                            </p>
                          </div>
                        </>
                      )}
                      {selectedStyle.id === 'traditional' && (
                        <>
                          <div className="flex items-start gap-2">
                            <span className="text-[#C0392B] mt-1">•</span>
                            <p className="text-sm text-[#4A2C1A]/80">
                              传统中立风格，均衡各流派特点
                            </p>
                          </div>
                          <div className="flex items-start gap-2">
                            <span className="text-[#C0392B] mt-1">•</span>
                            <p className="text-sm text-[#4A2C1A]/80">
                              节奏平稳，音色自然，适合初学者
                            </p>
                          </div>
                          <div className="flex items-start gap-2">
                            <span className="text-[#C0392B] mt-1">•</span>
                            <p className="text-sm text-[#4A2C1A]/80">
                              作为基准风格，便于对比其他流派
                            </p>
                          </div>
                        </>
                      )}
                    </div>
                  </div>

                  <div className="bg-white rounded-xl shadow-md p-6">
                    <h3 className="text-lg font-semibold text-[#4A2C1A] mb-4">代表曲目</h3>
                    <div className="space-y-2">
                      {selectedStyle.id === 'guangling' && (
                        <>
                          <div className="flex items-center gap-3 p-3 bg-[#4A2C1A]/5 rounded-lg">
                            <Music2 size={18} className="text-[#C0392B]" />
                            <span className="text-[#4A2C1A]">《广陵散》</span>
                          </div>
                          <div className="flex items-center gap-3 p-3 bg-[#4A2C1A]/5 rounded-lg">
                            <Music2 size={18} className="text-[#C0392B]" />
                            <span className="text-[#4A2C1A]">《平沙落雁》</span>
                          </div>
                          <div className="flex items-center gap-3 p-3 bg-[#4A2C1A]/5 rounded-lg">
                            <Music2 size={18} className="text-[#C0392B]" />
                            <span className="text-[#4A2C1A]">《梅花三弄》</span>
                          </div>
                        </>
                      )}
                      {selectedStyle.id === 'yushan' && (
                        <>
                          <div className="flex items-center gap-3 p-3 bg-[#4A2C1A]/5 rounded-lg">
                            <Music2 size={18} className="text-[#C0392B]" />
                            <span className="text-[#4A2C1A]">《流水》</span>
                          </div>
                          <div className="flex items-center gap-3 p-3 bg-[#4A2C1A]/5 rounded-lg">
                            <Music2 size={18} className="text-[#C0392B]" />
                            <span className="text-[#4A2C1A]">《潇湘水云》</span>
                          </div>
                          <div className="flex items-center gap-3 p-3 bg-[#4A2C1A]/5 rounded-lg">
                            <Music2 size={18} className="text-[#C0392B]" />
                            <span className="text-[#4A2C1A]">《渔樵问答》</span>
                          </div>
                        </>
                      )}
                      {selectedStyle.id === 'meian' && (
                        <>
                          <div className="flex items-center gap-3 p-3 bg-[#4A2C1A]/5 rounded-lg">
                            <Music2 size={18} className="text-[#C0392B]" />
                            <span className="text-[#4A2C1A]">《长门怨》</span>
                          </div>
                          <div className="flex items-center gap-3 p-3 bg-[#4A2C1A]/5 rounded-lg">
                            <Music2 size={18} className="text-[#C0392B]" />
                            <span className="text-[#4A2C1A]">《秋风词》</span>
                          </div>
                          <div className="flex items-center gap-3 p-3 bg-[#4A2C1A]/5 rounded-lg">
                            <Music2 size={18} className="text-[#C0392B]" />
                            <span className="text-[#4A2C1A]">《极乐吟》</span>
                          </div>
                        </>
                      )}
                      {selectedStyle.id === 'zhucheng' && (
                        <>
                          <div className="flex items-center gap-3 p-3 bg-[#4A2C1A]/5 rounded-lg">
                            <Music2 size={18} className="text-[#C0392B]" />
                            <span className="text-[#4A2C1A]">《高山流水》</span>
                          </div>
                          <div className="flex items-center gap-3 p-3 bg-[#4A2C1A]/5 rounded-lg">
                            <Music2 size={18} className="text-[#C0392B]" />
                            <span className="text-[#4A2C1A]">《石上流泉》</span>
                          </div>
                          <div className="flex items-center gap-3 p-3 bg-[#4A2C1A]/5 rounded-lg">
                            <Music2 size={18} className="text-[#C0392B]" />
                            <span className="text-[#4A2C1A]">《春山听杜鹃》</span>
                          </div>
                        </>
                      )}
                      {selectedStyle.id === 'jiuyi' && (
                        <>
                          <div className="flex items-center gap-3 p-3 bg-[#4A2C1A]/5 rounded-lg">
                            <Music2 size={18} className="text-[#C0392B]" />
                            <span className="text-[#4A2C1A]">《胡笳十八拍》</span>
                          </div>
                          <div className="flex items-center gap-3 p-3 bg-[#4A2C1A]/5 rounded-lg">
                            <Music2 size={18} className="text-[#C0392B]" />
                            <span className="text-[#4A2C1A]">《离骚》</span>
                          </div>
                          <div className="flex items-center gap-3 p-3 bg-[#4A2C1A]/5 rounded-lg">
                            <Music2 size={18} className="text-[#C0392B]" />
                            <span className="text-[#4A2C1A]">《秋鸿》</span>
                          </div>
                        </>
                      )}
                      {selectedStyle.id === 'shushan' && (
                        <>
                          <div className="flex items-center gap-3 p-3 bg-[#4A2C1A]/5 rounded-lg">
                            <Music2 size={18} className="text-[#C0392B]" />
                            <span className="text-[#4A2C1A]">《醉渔唱晚》</span>
                          </div>
                          <div className="flex items-center gap-3 p-3 bg-[#4A2C1A]/5 rounded-lg">
                            <Music2 size={18} className="text-[#C0392B]" />
                            <span className="text-[#4A2C1A]">《忆故人》</span>
                          </div>
                          <div className="flex items-center gap-3 p-3 bg-[#4A2C1A]/5 rounded-lg">
                            <Music2 size={18} className="text-[#C0392B]" />
                            <span className="text-[#4A2C1A]">《良宵引》</span>
                          </div>
                        </>
                      )}
                      {selectedStyle.id === 'traditional' && (
                        <>
                          <div className="flex items-center gap-3 p-3 bg-[#4A2C1A]/5 rounded-lg">
                            <Music2 size={18} className="text-[#C0392B]" />
                            <span className="text-[#4A2C1A]">《仙翁操》</span>
                          </div>
                          <div className="flex items-center gap-3 p-3 bg-[#4A2C1A]/5 rounded-lg">
                            <Music2 size={18} className="text-[#C0392B]" />
                            <span className="text-[#4A2C1A]">《秋风词》</span>
                          </div>
                          <div className="flex items-center gap-3 p-3 bg-[#4A2C1A]/5 rounded-lg">
                            <Music2 size={18} className="text-[#C0392B]" />
                            <span className="text-[#4A2C1A]">《湘江怨》</span>
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                </div>

                <div className="bg-white rounded-xl shadow-md p-6">
                  <h3 className="text-lg font-semibold text-[#4A2C1A] mb-4">流派对比</h3>
                  <div className="overflow-x-auto">
                    <table className="w-full border-collapse">
                      <thead>
                        <tr className="bg-[#4A2C1A]/5">
                          <th className="px-4 py-3 text-left text-sm font-medium text-[#4A2C1A] border-b">
                            流派
                          </th>
                          <th className="px-4 py-3 text-center text-sm font-medium text-[#4A2C1A] border-b">
                            节奏
                          </th>
                          <th className="px-4 py-3 text-center text-sm font-medium text-[#4A2C1A] border-b">
                            音色
                          </th>
                          <th className="px-4 py-3 text-center text-sm font-medium text-[#4A2C1A] border-b">
                            吟猱
                          </th>
                          <th className="px-4 py-3 text-center text-sm font-medium text-[#4A2C1A] border-b">
                            滑音
                          </th>
                          <th className="px-4 py-3 text-center text-sm font-medium text-[#4A2C1A] border-b">
                            余韵
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {styles.map((style) => (
                          <tr
                            key={style.id}
                            className={`border-b border-[#4A2C1A]/10 hover:bg-[#4A2C1A]/5 cursor-pointer transition-colors ${
                              selectedStyle?.id === style.id ? 'bg-[#C0392B]/5' : ''
                            }`}
                            onClick={() => handleSelectStyle(style.id)}
                          >
                            <td className="px-4 py-3 text-sm font-medium text-[#4A2C1A]">
                              {style.name}
                            </td>
                            {style.params && (
                              <>
                                <td className="px-4 py-3 text-center">
                                  <div className="flex flex-col items-center gap-1">
                                    <div className="w-16 h-2 bg-[#4A2C1A]/10 rounded-full overflow-hidden">
                                      <div
                                        className="h-full bg-[#C0392B]"
                                        style={{
                                          width: `${style.params.tempo_modulation * 100}%`,
                                        }}
                                      />
                                    </div>
                                    <span className="text-xs text-[#4A2C1A]/60">
                                      {(style.params.tempo_modulation * 100).toFixed(0)}%
                                    </span>
                                  </div>
                                </td>
                                <td className="px-4 py-3 text-center">
                                  <div className="flex flex-col items-center gap-1">
                                    <div className="w-16 h-2 bg-[#4A2C1A]/10 rounded-full overflow-hidden">
                                      <div
                                        className="h-full bg-[#C0392B]"
                                        style={{
                                          width: `${style.params.brightness_correction * 100}%`,
                                        }}
                                      />
                                    </div>
                                    <span className="text-xs text-[#4A2C1A]/60">
                                      {(style.params.brightness_correction * 100).toFixed(0)}%
                                    </span>
                                  </div>
                                </td>
                                <td className="px-4 py-3 text-center">
                                  <div className="flex flex-col items-center gap-1">
                                    <div className="w-16 h-2 bg-[#4A2C1A]/10 rounded-full overflow-hidden">
                                      <div
                                        className="h-full bg-[#C0392B]"
                                        style={{
                                          width: `${style.params.vibrato_intensity * 100}%`,
                                        }}
                                      />
                                    </div>
                                    <span className="text-xs text-[#4A2C1A]/60">
                                      {(style.params.vibrato_intensity * 100).toFixed(0)}%
                                    </span>
                                  </div>
                                </td>
                                <td className="px-4 py-3 text-center">
                                  <div className="flex flex-col items-center gap-1">
                                    <div className="w-16 h-2 bg-[#4A2C1A]/10 rounded-full overflow-hidden">
                                      <div
                                        className="h-full bg-[#C0392B]"
                                        style={{
                                          width: `${style.params.glissando_smoothness * 100}%`,
                                        }}
                                      />
                                    </div>
                                    <span className="text-xs text-[#4A2C1A]/60">
                                      {(style.params.glissando_smoothness * 100).toFixed(0)}%
                                    </span>
                                  </div>
                                </td>
                                <td className="px-4 py-3 text-center">
                                  <div className="flex flex-col items-center gap-1">
                                    <div className="w-16 h-2 bg-[#4A2C1A]/10 rounded-full overflow-hidden">
                                      <div
                                        className="h-full bg-[#C0392B]"
                                        style={{
                                          width: `${style.params.decay_extension * 100}%`,
                                        }}
                                      />
                                    </div>
                                    <span className="text-xs text-[#4A2C1A]/60">
                                      {(style.params.decay_extension * 100).toFixed(0)}%
                                    </span>
                                  </div>
                                </td>
                              </>
                            )}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
};

export default StylesPage;
