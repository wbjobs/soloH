import type { BrainwaveBand } from '../types/audio';

export const BRAINWAVE_BANDS: BrainwaveBand[] = [
  {
    id: 'delta',
    name: 'Delta',
    frequencyRange: [0.5, 4],
    defaultFrequency: 2.5,
    color: '#6366f1',
    glowColor: 'rgba(99, 102, 241, 0.6)',
    description: '深度睡眠、恢复性休息'
  },
  {
    id: 'theta',
    name: 'Theta',
    frequencyRange: [4, 8],
    defaultFrequency: 6,
    color: '#8b5cf6',
    glowColor: 'rgba(139, 92, 246, 0.6)',
    description: '冥想、创造力、浅睡'
  },
  {
    id: 'alpha',
    name: 'Alpha',
    frequencyRange: [8, 13],
    defaultFrequency: 10,
    color: '#3b82f6',
    glowColor: 'rgba(59, 130, 246, 0.6)',
    description: '放松、平静、清醒放松'
  },
  {
    id: 'beta',
    name: 'Beta',
    frequencyRange: [13, 30],
    defaultFrequency: 20,
    color: '#10b981',
    glowColor: 'rgba(16, 185, 129, 0.6)',
    description: '专注、警觉、逻辑思维'
  },
  {
    id: 'gamma',
    name: 'Gamma',
    frequencyRange: [30, 100],
    defaultFrequency: 40,
    color: '#f59e0b',
    glowColor: 'rgba(245, 158, 11, 0.6)',
    description: '高度认知、洞察力、整合'
  }
];

export const getBandById = (id: string): BrainwaveBand | undefined => {
  return BRAINWAVE_BANDS.find(band => band.id === id);
};

export const DEFAULT_BAND = BRAINWAVE_BANDS[2];
