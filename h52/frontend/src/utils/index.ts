import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import type { EmotionCategory, EmotionProbabilities, EmotionResult, HistoryItem, ModalityResult, AttentionMatrix, TimeSeriesPoint } from '@/types';
import { EMOTION_LABELS, EMOTION_COLORS } from '@/types';

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

export function formatPercent(value: number, decimals = 1): string {
  return `${(value * 100).toFixed(decimals)}%`;
}

export function formatNumber(value: number, decimals = 2): string {
  return value.toFixed(decimals);
}

export function getDominantEmotion(probabilities: EmotionProbabilities): {
  category: EmotionCategory;
  confidence: number;
} {
  const entries = Object.entries(probabilities) as [EmotionCategory, number][];
  let maxCategory: EmotionCategory = 'neutral';
  let maxValue = 0;

  for (const [category, value] of entries) {
    if (value > maxValue) {
      maxValue = value;
      maxCategory = category;
    }
  }

  return { category: maxCategory, confidence: maxValue };
}

export function getEmotionLabel(category: EmotionCategory): string {
  return EMOTION_LABELS[category];
}

export function getEmotionColor(category: EmotionCategory): string {
  return EMOTION_COLORS[category];
}

export function getValenceArousalLabel(valence: number, arousal: number): string {
  const valenceLabel = valence > 0.2 ? '积极' : valence < -0.2 ? '消极' : '中性';
  const arousalLabel = arousal > 0.2 ? '兴奋' : arousal < -0.2 ? '平静' : '中性';
  return `${valenceLabel}·${arousalLabel}`;
}

export function getQuadrant(valence: number, arousal: number): string {
  if (valence >= 0 && arousal >= 0) return 'Q1';
  if (valence < 0 && arousal >= 0) return 'Q2';
  if (valence < 0 && arousal < 0) return 'Q3';
  return 'Q4';
}

export function getQuadrantLabel(quadrant: string): string {
  const labels: Record<string, string> = {
    Q1: '积极·兴奋',
    Q2: '消极·兴奋',
    Q3: '消极·平静',
    Q4: '积极·平静',
  };
  return labels[quadrant] || '未知';
}

export function generateRandomEmotionProbabilities(): EmotionProbabilities {
  const emotions: EmotionProbabilities = {
    anger: 0,
    joy: 0,
    sadness: 0,
    surprise: 0,
    disgust: 0,
    fear: 0,
    neutral: 0,
  };

  const emotionKeys = Object.keys(emotions) as EmotionCategory[];
  const dominantIndex = Math.floor(Math.random() * emotionKeys.length);
  const dominant = emotionKeys[dominantIndex];

  let remaining = 1.0;
  emotions[dominant] = 0.4 + Math.random() * 0.4;
  remaining -= emotions[dominant];

  for (const key of emotionKeys) {
    if (key !== dominant && remaining > 0) {
      const value = Math.random() * remaining * 0.3;
      emotions[key] = value;
      remaining -= value;
    }
  }

  emotions.neutral += remaining;

  return emotions;
}

export function generateMockEmotionResult(): EmotionResult {
  const id = crypto.randomUUID();
  const timestamp = Date.now();
  const probabilities = generateRandomEmotionProbabilities();
  const dominant = getDominantEmotion(probabilities);

  const valence = (Math.random() - 0.5) * 2;
  const arousal = (Math.random() - 0.5) * 2;

  const generateModalityResult = (): ModalityResult => {
    const probs = generateRandomEmotionProbabilities();
    return {
      contribution: Math.random() * 0.5 + 0.2,
      features: Array.from({ length: 128 }, () => Math.random()),
      emotionProbabilities: probs,
    };
  };

  const modalities = {
    audio: generateModalityResult(),
    video: generateModalityResult(),
    text: generateModalityResult(),
  };

  const totalContrib = modalities.audio.contribution + modalities.video.contribution + modalities.text.contribution;
  modalities.audio.contribution /= totalContrib;
  modalities.video.contribution /= totalContrib;
  modalities.text.contribution /= totalContrib;

  const timeSteps = 30;
  const timeSeries: TimeSeriesPoint[] = [];
  for (let i = 0; i < timeSteps; i++) {
    const probs = generateRandomEmotionProbabilities();
    const dom = getDominantEmotion(probs);
    timeSeries.push({
      time: i,
      emotion: dom.category,
      valence: valence + (Math.random() - 0.5) * 0.5,
      arousal: arousal + (Math.random() - 0.5) * 0.5,
      probabilities: probs,
    });
  }

  const attentionWeights: AttentionMatrix = {
    timeSteps,
    modalities: ['audio', 'video', 'text'],
    weights: Array.from({ length: timeSteps }, () => [
      Math.random() * 0.4 + 0.2,
      Math.random() * 0.4 + 0.2,
      Math.random() * 0.4 + 0.2,
    ]),
  };

  const transcripts = [
    '今天天气真不错，我感到非常开心和愉快。工作也很顺利，一切都在朝着好的方向发展。',
    '我对这件事情感到非常愤怒和失望，为什么总是这样不公平？我需要冷静下来好好思考。',
    '最近发生了很多事情，让我感到有些悲伤和难过。不过我相信一切都会好起来的。',
    '太令人惊讶了！我完全没有想到会是这样的结果，真是太棒了！',
    '这种感觉让我很不舒服，有些厌恶和排斥。我需要远离这种环境。',
    '我感到有些恐惧和不安，不知道接下来会发生什么。希望一切都能平安度过。',
    '今天是普通的一天，没有什么特别的事情发生。工作和生活都按部就班地进行着。',
  ];

  return {
    id,
    timestamp,
    emotion: {
      category: dominant.category,
      confidence: dominant.confidence,
      probabilities,
    },
    valenceArousal: { valence, arousal },
    modalities,
    attentionWeights,
    timeSeries,
    transcript: transcripts[Math.floor(Math.random() * transcripts.length)],
  };
}

export function generateMockHistoryItems(count: number): HistoryItem[] {
  const items: HistoryItem[] = [];
  const now = Date.now();

  for (let i = 0; i < count; i++) {
    const probabilities = generateRandomEmotionProbabilities();
    const dominant = getDominantEmotion(probabilities);

    items.push({
      id: `history-${i}`,
      videoId: `video-${i}`,
      createdAt: new Date(now - i * 3600000 * Math.random() * 24 * 7).toISOString(),
      primaryEmotion: dominant.category,
      confidence: dominant.confidence,
      valence: (Math.random() - 0.5) * 2,
      arousal: (Math.random() - 0.5) * 2,
      duration: Math.floor(Math.random() * 30) + 30,
    });
  }

  return items;
}

export function smoothData<T extends number>(
  data: T[],
  windowSize = 3
): number[] {
  if (data.length < windowSize) return data as number[];

  const result: number[] = [];
  for (let i = 0; i < data.length; i++) {
    const start = Math.max(0, i - Math.floor(windowSize / 2));
    const end = Math.min(data.length, i + Math.ceil(windowSize / 2));
    const window = data.slice(start, end);
    const avg = window.reduce((a, b) => a + b, 0) / window.length;
    result.push(avg);
  }
  return result;
}

export function interpolateColor(
  color1: string,
  color2: string,
  factor: number
): string {
  const hex = (x: string) => parseInt(x, 16);
  const r1 = hex(color1.slice(1, 3));
  const g1 = hex(color1.slice(3, 5));
  const b1 = hex(color1.slice(5, 7));
  const r2 = hex(color2.slice(1, 3));
  const g2 = hex(color2.slice(3, 5));
  const b2 = hex(color2.slice(5, 7));

  const r = Math.round(r1 + (r2 - r1) * factor);
  const g = Math.round(g1 + (g2 - g1) * factor);
  const b = Math.round(b1 + (b2 - b1) * factor);

  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
}

export function getHeatmapColor(value: number, min = 0, max = 1): string {
  const normalized = Math.max(0, Math.min(1, (value - min) / (max - min)));

  const colors = [
    { pos: 0.0, color: '#440154' },
    { pos: 0.2, color: '#482878' },
    { pos: 0.4, color: '#3e4989' },
    { pos: 0.6, color: '#31688e' },
    { pos: 0.8, color: '#21918c' },
    { pos: 0.9, color: '#35b779' },
    { pos: 1.0, color: '#fde725' },
  ];

  for (let i = 0; i < colors.length - 1; i++) {
    if (normalized >= colors[i].pos && normalized <= colors[i + 1].pos) {
      const range = colors[i + 1].pos - colors[i].pos;
      const factor = (normalized - colors[i].pos) / range;
      return interpolateColor(colors[i].color, colors[i + 1].color, factor);
    }
  }

  return colors[colors.length - 1].color;
}

export function downloadFile(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function debounce<T extends (...args: unknown[]) => void>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: ReturnType<typeof setTimeout> | null = null;
  return (...args: Parameters<T>) => {
    if (timeout) clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
}

export function throttle<T extends (...args: unknown[]) => void>(
  func: T,
  limit: number
): (...args: Parameters<T>) => void {
  let inThrottle = false;
  return (...args: Parameters<T>) => {
    if (!inThrottle) {
      func(...args);
      inThrottle = true;
      setTimeout(() => {
        inThrottle = false;
      }, limit);
    }
  };
}
