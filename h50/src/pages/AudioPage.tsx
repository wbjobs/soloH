import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Download,
  Music,
  FileText,
  FileAudio,
  Settings2,
  Activity,
} from 'lucide-react';
import Navbar from '@/components/Navbar';
import type { Jianzi } from '@/types';
import { cn } from '@/lib/utils';

const generateMockJianziList = (): Jianzi[] => {
  const fingers = ['勾', '挑', '抹', '剔', '散', '按', '泛'];
  const strings = ['一', '二', '三', '四', '五', '六', '七'];
  const huis = ['七徽', '九徽', '十徽', '八徽', '六徽', '五徽', ''];

  const jianziList: Jianzi[] = [];

  for (let i = 0; i < 24; i++) {
    const finger = fingers[Math.floor(Math.random() * fingers.length)];
    const string = strings[Math.floor(Math.random() * strings.length)];
    const hui = finger === '散' ? '' : huis[Math.floor(Math.random() * (huis.length - 1))];

    jianziList.push({
      id: `jianzi-${i}`,
      bbox: { x: 0, y: 0, width: 50, height: 60 },
      components: { finger, string, hui },
      confidence: 0.85 + Math.random() * 0.14,
      gongche: ['合', '四', '一', '上', '尺', '工', '凡'][parseInt(string) - 1],
    });
  }

  return jianziList;
};

const techniques = [
  { id: 'sanyin', name: '散音', description: '空弦发音，音色浑厚' },
  { id: 'anyin', name: '按音', description: '左手按弦，音色圆润' },
  { id: 'fanyin', name: '泛音', description: '轻触徽位，音色清越' },
];

const stringFrequencies = [
  { string: '一', freq: 261.63, note: 'C4' },
  { string: '二', freq: 293.66, note: 'D4' },
  { string: '三', freq: 329.63, note: 'E4' },
  { string: '四', freq: 349.23, note: 'F4' },
  { string: '五', freq: 392.0, note: 'G4' },
  { string: '六', freq: 440.0, note: 'A4' },
  { string: '七', freq: 493.88, note: 'B4' },
];

export default function AudioPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const state = location.state as { jianziList?: Jianzi[]; fileName?: string } | null;

  const [jianziList, setJianziList] = useState<Jianzi[]>([]);
  const [fileName, setFileName] = useState<string>('');
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(-1);
  const [tempo, setTempo] = useState(80);
  const [technique, setTechnique] = useState('sanyin');
  const [synthesisStatus, setSynthesisStatus] = useState<'idle' | 'synthesizing' | 'ready' | 'playing' | 'paused'>('idle');
  const [progress, setProgress] = useState(0);

  const audioContextRef = useRef<AudioContext | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const waveformDataRef = useRef<number[]>([]);

  useEffect(() => {
    if (state?.jianziList && state.jianziList.length > 0) {
      setJianziList(state.jianziList);
      setFileName(state.fileName || '音频合成');
    } else {
      setJianziList(generateMockJianziList());
      setFileName('示例琴谱音频合成');
    }

    return () => {
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, [state]);

  const noteDuration = useMemo(() => {
    return 60000 / tempo;
  }, [tempo]);

  const currentJianzi = currentIndex >= 0 && currentIndex < jianziList.length
    ? jianziList[currentIndex]
    : null;

  const activeStringIndex = useMemo(() => {
    if (!currentJianzi) return -1;
    return stringFrequencies.findIndex((s) => s.string === currentJianzi.components.string);
  }, [currentJianzi]);

  const initAudioContext = useCallback(() => {
    if (!audioContextRef.current) {
      audioContextRef.current = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
    }
    return audioContextRef.current;
  }, []);

  const playNote = useCallback((jianzi: Jianzi) => {
    const ctx = initAudioContext();
    if (ctx.state === 'suspended') {
      ctx.resume();
    }

    const stringInfo = stringFrequencies.find((s) => s.string === jianzi.components.string);
    if (!stringInfo) return;

    const oscillator = ctx.createOscillator();
    const gainNode = ctx.createGain();

    let freq = stringInfo.freq;
    if (jianzi.components.hui) {
      const huiMultiplier: Record<string, number> = {
        '七徽': 2,
        '九徽': 1.5,
        '十徽': 1.333,
        '八徽': 1.25,
        '六徽': 1.2,
        '五徽': 1.142,
      };
      freq *= huiMultiplier[jianzi.components.hui] || 1;
    }

    if (technique === 'fanyin') {
      oscillator.type = 'sine';
    } else if (technique === 'anyin') {
      oscillator.type = 'triangle';
    } else {
      oscillator.type = 'sawtooth';
    }

    oscillator.frequency.setValueAtTime(freq, ctx.currentTime);

    gainNode.gain.setValueAtTime(0, ctx.currentTime);
    gainNode.gain.linearRampToValueAtTime(0.3, ctx.currentTime + 0.01);
    gainNode.gain.exponentialRampToValueAtTime(0.15, ctx.currentTime + 0.1);
    gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + noteDuration / 1000);

    oscillator.connect(gainNode);
    gainNode.connect(ctx.destination);

    oscillator.start(ctx.currentTime);
    oscillator.stop(ctx.currentTime + noteDuration / 1000);

    const samples = 100;
    const newWaveform: number[] = [];
    for (let i = 0; i < samples; i++) {
      const t = i / samples;
      const amplitude = Math.exp(-t * 3) * (0.3 + Math.random() * 0.2);
      newWaveform.push(Math.sin(t * Math.PI * 8) * amplitude);
    }
    waveformDataRef.current = newWaveform;
  }, [initAudioContext, noteDuration, technique]);

  const drawWaveform = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const { width, height } = canvas;
    ctx.clearRect(0, 0, width, height);

    ctx.strokeStyle = 'rgba(74, 44, 26, 0.1)';
    ctx.lineWidth = 1;
    for (let i = 0; i < 5; i++) {
      const y = (height / 5) * i + height / 10;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    const waveform = waveformDataRef.current;
    if (waveform.length === 0) {
      ctx.strokeStyle = 'rgba(74, 44, 26, 0.3)';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(0, height / 2);
      ctx.lineTo(width, height / 2);
      ctx.stroke();
      return;
    }

    ctx.strokeStyle = '#C0392B';
    ctx.lineWidth = 2;
    ctx.beginPath();

    const step = width / waveform.length;
    waveform.forEach((value, index) => {
      const x = index * step;
      const y = height / 2 + value * height * 0.8;
      if (index === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });

    ctx.stroke();

    const gradient = ctx.createLinearGradient(0, 0, 0, height);
    gradient.addColorStop(0, 'rgba(192, 57, 43, 0.1)');
    gradient.addColorStop(1, 'rgba(192, 57, 43, 0.02)');

    ctx.fillStyle = gradient;
    ctx.lineTo(width, height / 2);
    ctx.lineTo(0, height / 2);
    ctx.closePath();
    ctx.fill();

    animationRef.current = requestAnimationFrame(drawWaveform);
  }, []);

  useEffect(() => {
    drawWaveform();
    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [drawWaveform]);

  const playSequence = useCallback(() => {
    if (jianziList.length === 0) return;

    setIsPlaying(true);
    setSynthesisStatus('playing');

    let index = currentIndex < 0 ? 0 : currentIndex;

    const playNext = () => {
      if (index >= jianziList.length) {
        setIsPlaying(false);
        setSynthesisStatus('ready');
        setCurrentIndex(-1);
        setProgress(100);
        return;
      }

      setCurrentIndex(index);
      setProgress(((index + 1) / jianziList.length) * 100);
      playNote(jianziList[index]);
      index++;

      timeoutRef.current = setTimeout(playNext, noteDuration);
    };

    playNext();
  }, [jianziList, currentIndex, noteDuration, playNote]);

  const handlePlayPause = useCallback(() => {
    if (isPlaying) {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      setIsPlaying(false);
      setSynthesisStatus('paused');
    } else {
      playSequence();
    }
  }, [isPlaying, playSequence]);

  const handlePrevious = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    const newIndex = Math.max(0, currentIndex - 1);
    setCurrentIndex(newIndex);
    setProgress(((newIndex + 1) / jianziList.length) * 100);
    if (isPlaying) {
      playNote(jianziList[newIndex]);
      const newTimeoutRef = setTimeout(() => {
        setCurrentIndex((prev) => prev + 1);
      }, noteDuration);
      timeoutRef.current = newTimeoutRef;
    }
  }, [currentIndex, isPlaying, jianziList, noteDuration, playNote]);

  const handleNext = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    const newIndex = Math.min(jianziList.length - 1, currentIndex + 1);
    setCurrentIndex(newIndex);
    setProgress(((newIndex + 1) / jianziList.length) * 100);
    if (isPlaying) {
      playNote(jianziList[newIndex]);
      const newTimeoutRef = setTimeout(() => {
        setCurrentIndex((prev) => prev + 1);
      }, noteDuration);
      timeoutRef.current = newTimeoutRef;
    }
  }, [currentIndex, isPlaying, jianziList, noteDuration, playNote]);

  const handleSynthesize = useCallback(() => {
    setSynthesisStatus('synthesizing');
    setTimeout(() => {
      setSynthesisStatus('ready');
    }, 2000);
  }, []);

  const handleExportMidi = useCallback(() => {
    const data = {
      fileName,
      tempo,
      technique,
      notes: jianziList.map((j) => ({
        note: j.components.string,
        duration: noteDuration,
        technique: j.components.finger,
      })),
    };

    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${fileName.replace(/\.[^/.]+$/, '')}_audio.mid`;
    a.click();
    URL.revokeObjectURL(url);
  }, [fileName, jianziList, noteDuration, tempo, technique]);

  const handleExportWav = useCallback(() => {
    const data = new Uint8Array(44);
    const blob = new Blob([data], { type: 'audio/wav' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${fileName.replace(/\.[^/.]+$/, '')}_audio.wav`;
    a.click();
    URL.revokeObjectURL(url);
  }, [fileName]);

  const handleExportText = useCallback(() => {
    const text = jianziList
      .map((j, i) => {
        const finger = j.components.finger;
        const string = j.components.string;
        const hui = j.components.hui || '';
        return `${i + 1}. ${finger}${string}${hui}\t// ${j.gongche || ''}`;
      })
      .join('\n');

    const header = `# ${fileName}\n# 演奏速度: ${tempo} BPM\n# 演奏技法: ${techniques.find((t) => t.id === technique)?.name}\n# 共 ${jianziList.length} 个音符\n\n`;

    const blob = new Blob([header + text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${fileName.replace(/\.[^/.]+$/, '')}_notes.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }, [fileName, jianziList, tempo, technique]);

  const handleBack = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    setIsPlaying(false);
    navigate('/result');
  }, [navigate]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const totalDuration = (jianziList.length * noteDuration) / 1000;
  const currentDuration = currentIndex >= 0 ? ((currentIndex + 1) * noteDuration) / 1000 : 0;

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
              <h1 className="text-xl font-kai font-bold tracking-wider">音频合成</h1>
              <p className="text-xuanzhi/70 text-sm">{fileName}</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleExportMidi}
              className="flex items-center gap-2 px-4 py-2 bg-xuanzhi/10 hover:bg-xuanzhi/20 rounded-lg transition-colors text-sm"
              title="导出MIDI"
            >
              <FileAudio className="w-4 h-4" />
              <span className="hidden sm:inline">MIDI</span>
            </button>

            <button
              onClick={handleExportWav}
              className="flex items-center gap-2 px-4 py-2 bg-xuanzhi/10 hover:bg-xuanzhi/20 rounded-lg transition-colors text-sm"
              title="导出WAV"
            >
              <Download className="w-4 h-4" />
              <span className="hidden sm:inline">WAV</span>
            </button>

            <button
              onClick={handleExportText}
              className="flex items-center gap-2 px-4 py-2 bg-xuanzhi/10 hover:bg-xuanzhi/20 rounded-lg transition-colors text-sm"
              title="导出指法文本"
            >
              <FileText className="w-4 h-4" />
              <span className="hidden sm:inline">指法</span>
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1 p-6 overflow-auto">
        <div className="max-w-5xl mx-auto space-y-6">
          <div className="scroll-border xuanzhi-bg p-6">
            <div className="flex items-center gap-2 mb-6 pb-3 border-b border-tanmu/20">
              <Music className="w-5 h-5 text-tanmu" />
              <h2 className="text-lg font-kai font-bold text-tanmu">古琴弦式</h2>
              <span className="text-sm text-tanmu/60 ml-auto">
                七弦正调 · 宫商角徵羽
              </span>
            </div>

            <div className="space-y-3">
              {stringFrequencies.map((string, index) => (
                <div
                  key={string.string}
                  className="flex items-center gap-4"
                >
                  <span className="w-12 text-right font-kai text-tanmu-dark font-bold">
                    {string.string}弦
                  </span>
                  <div className="flex-1 relative">
                    <div className="guqin-string h-3">
                      <div
                        className={cn(
                          'string-active',
                          activeStringIndex === index ? 'opacity-100' : 'opacity-0'
                        )}
                        style={{
                          width: `${activeStringIndex === index ? 100 : 0}%`,
                          transition: 'width 0.3s ease-out',
                        }}
                      />
                    </div>
                    <div className="absolute top-full left-0 right-0 flex justify-between mt-1 px-1">
                      {['岳山', '七徽', '徽中', '九徽', '十徽', '龙龈'].map((pos, i) => (
                        <span
                          key={pos}
                          className="text-[10px] text-tanmu/40"
                          style={{ left: `${i * 20}%` }}
                        >
                          {pos}
                        </span>
                      ))}
                    </div>
                  </div>
                  <span className="w-16 text-left text-sm text-tanmu/60 font-mono">
                    {string.note}
                  </span>
                  <span className="w-16 text-left text-xl font-kai text-zhusha font-bold">
                    {['合', '四', '一', '上', '尺', '工', '凡'][index]}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="scroll-border xuanzhi-bg p-6">
            <div className="flex items-center gap-2 mb-4 pb-3 border-b border-tanmu/20">
              <Activity className="w-5 h-5 text-tanmu" />
              <h2 className="text-lg font-kai font-bold text-tanmu">音频波形</h2>
              <span className="text-sm text-tanmu/60 ml-auto">
                {synthesisStatus === 'synthesizing' && '合成中...'}
                {synthesisStatus === 'ready' && '准备就绪'}
                {synthesisStatus === 'playing' && '播放中...'}
                {synthesisStatus === 'paused' && '已暂停'}
                {synthesisStatus === 'idle' && '等待合成'}
              </span>
            </div>

            <div className="relative">
              <canvas
                ref={canvasRef}
                width={800}
                height={120}
                className="w-full h-32 bg-xuanzhi-dark/30 rounded-lg"
              />

              {synthesisStatus === 'synthesizing' && (
                <div className="absolute inset-0 flex items-center justify-center bg-xuanzhi/80 rounded-lg">
                  <div className="flex flex-col items-center gap-2">
                    <div className="w-8 h-8 border-4 border-tanmu border-t-zhusha rounded-full animate-spin" />
                    <span className="text-tanmu/70 text-sm">正在合成音频...</span>
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="scroll-border xuanzhi-bg p-6">
            <div className="flex items-center gap-2 mb-6 pb-3 border-b border-tanmu/20">
              <Play className="w-5 h-5 text-tanmu" />
              <h2 className="text-lg font-kai font-bold text-tanmu">播放控制</h2>
            </div>

            <div className="mb-6">
              <div className="h-2 bg-xuanzhi-dark rounded-full overflow-hidden mb-2">
                <div
                  className="h-full bg-gradient-to-r from-zhusha to-zhusha-light transition-all duration-300"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <div className="flex justify-between text-sm text-tanmu/60 font-mono">
                <span>{formatTime(currentDuration)}</span>
                <span>{formatTime(totalDuration)}</span>
              </div>
            </div>

            <div className="flex items-center justify-center gap-6">
              <button
                onClick={handlePrevious}
                disabled={currentIndex <= 0}
                className="p-3 rounded-full bg-tanmu text-xuanzhi hover:bg-tanmu-light transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <SkipBack className="w-6 h-6" />
              </button>

              <button
                onClick={handlePlayPause}
                disabled={synthesisStatus === 'synthesizing'}
                className={cn(
                  'p-5 rounded-full transition-all duration-300',
                  isPlaying
                    ? 'bg-zhusha text-xuanzhi hover:bg-zhusha-light animate-pulse-zhusha'
                    : 'bg-gradient-to-br from-tanmu to-tanmu-dark text-xuanzhi hover:from-tanmu-light hover:to-tanmu shadow-lg'
                )}
              >
                {isPlaying ? (
                  <Pause className="w-8 h-8" />
                ) : (
                  <Play className="w-8 h-8 ml-1" />
                )}
              </button>

              <button
                onClick={handleNext}
                disabled={currentIndex >= jianziList.length - 1}
                className="p-3 rounded-full bg-tanmu text-xuanzhi hover:bg-tanmu-light transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <SkipForward className="w-6 h-6" />
              </button>
            </div>

            {currentJianzi && (
              <div className="mt-6 text-center animate-fade-in-up">
                <div className="inline-block p-6 bg-xuanzhi-dark/50 rounded-xl">
                  <div className="jianzi-char text-6xl text-tanmu-dark mb-2">
                    {currentJianzi.components.finger}
                  </div>
                  <div className="text-lg text-tanmu/70">
                    {currentJianzi.components.string}弦 {currentJianzi.components.hui}
                  </div>
                  <div className="text-3xl font-kai text-zhusha font-bold mt-2">
                    {currentJianzi.gongche}
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="scroll-border xuanzhi-bg p-6">
            <div className="flex items-center gap-2 mb-6 pb-3 border-b border-tanmu/20">
              <Settings2 className="w-5 h-5 text-tanmu" />
              <h2 className="text-lg font-kai font-bold text-tanmu">参数调节</h2>
            </div>

            <div className="grid md:grid-cols-2 gap-8">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <label className="text-tanmu-dark font-medium">演奏速度</label>
                  <span className="text-2xl font-kai text-zhusha font-bold font-mono">
                    {tempo} <span className="text-sm text-tanmu/60">BPM</span>
                  </span>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-sm text-tanmu/60">慢</span>
                  <input
                    type="range"
                    min={60}
                    max={120}
                    value={tempo}
                    onChange={(e) => setTempo(parseInt(e.target.value))}
                    className="flex-1"
                  />
                  <span className="text-sm text-tanmu/60">快</span>
                </div>
                <div className="flex justify-between mt-2 text-xs text-tanmu/40">
                  <span>60</span>
                  <span>90</span>
                  <span>120</span>
                </div>
              </div>

              <div>
                <label className="block text-tanmu-dark font-medium mb-3">
                  演奏技法
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {techniques.map((t) => (
                    <button
                      key={t.id}
                      onClick={() => setTechnique(t.id)}
                      className={cn(
                        'p-3 rounded-lg border-2 transition-all duration-300 text-center',
                        technique === t.id
                          ? 'bg-zhusha/10 border-zhusha text-tanmu-dark'
                          : 'bg-xuanzhi border-tanmu/20 hover:border-tanmu/50 text-tanmu/70'
                      )}
                    >
                      <div className="font-kai font-bold text-lg">{t.name}</div>
                      <div className="text-[10px] mt-1 opacity-70">{t.description}</div>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {synthesisStatus === 'idle' && (
              <div className="mt-6 text-center">
                <button
                  onClick={handleSynthesize}
                  className="btn-classical px-8 py-3 text-lg"
                >
                  开始合成音频
                </button>
              </div>
            )}
          </div>

          <div className="scroll-border xuanzhi-bg p-6">
            <div className="flex items-center gap-2 mb-4 pb-3 border-b border-tanmu/20">
              <Music className="w-5 h-5 text-tanmu" />
              <h2 className="text-lg font-kai font-bold text-tanmu">减字序列</h2>
              <span className="text-sm text-tanmu/60 ml-auto">
                共 {jianziList.length} 个减字
              </span>
            </div>

            <div className="overflow-x-auto pb-2">
              <div className="flex gap-2 min-w-max">
                {jianziList.map((jianzi, index) => (
                  <button
                    key={jianzi.id}
                    onClick={() => {
                      setCurrentIndex(index);
                      playNote(jianzi);
                    }}
                    className={cn(
                      'flex flex-col items-center px-3 py-2 rounded-lg transition-all duration-300 min-w-[64px] border-2',
                      currentIndex === index
                        ? 'bg-zhusha text-xuanzhi border-zhusha scale-110 shadow-lg'
                        : 'bg-xuanzhi border-tanmu/20 hover:border-tanmu/50 hover:bg-xuanzhi-dark'
                    )}
                  >
                    <span className="text-xs opacity-70 font-mono">#{index + 1}</span>
                    <span className="jianzi-char text-xl font-bold">
                      {jianzi.components.finger}
                    </span>
                    <span className="text-xs">
                      {jianzi.components.string}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
