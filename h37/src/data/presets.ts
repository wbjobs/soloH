import type { Preset } from '../types/audio';

export const PRESETS: Preset[] = [
  {
    id: 'deep-relaxation',
    name: '深度放松',
    description: '从Alpha慢慢过渡到Theta，释放压力，进入深度放松状态',
    icon: 'moon',
    duration: 20,
    settings: {
      audioMode: 'binaural',
      carrierFrequency: 200,
      modulationDepth: 0.5,
      masterVolume: 0.5,
      breathing: {
        enabled: true,
        inhaleTime: 4,
        holdTime: 4,
        exhaleTime: 8,
        restTime: 4
      }
    },
    bandProgression: [
      { time: 0, band: 'alpha' },
      { time: 300, band: 'theta' }
    ]
  },
  {
    id: 'focus',
    name: '专注学习',
    description: 'Beta频段，提升专注力和思维清晰度，适合学习和工作',
    icon: 'brain',
    duration: 25,
    settings: {
      audioMode: 'isochronic',
      beatFrequency: 18,
      carrierFrequency: 300,
      modulationDepth: 0.7,
      masterVolume: 0.4,
      breathing: {
        enabled: false,
        inhaleTime: 4,
        holdTime: 2,
        exhaleTime: 4,
        restTime: 2
      }
    },
    bandProgression: [
      { time: 0, band: 'beta' }
    ]
  },
  {
    id: 'meditation',
    name: '冥想入定',
    description: 'Alpha/Theta边界，适合深度冥想、内观和正念练习',
    icon: 'flower-2',
    duration: 15,
    settings: {
      audioMode: 'binaural',
      beatFrequency: 7.5,
      carrierFrequency: 150,
      modulationDepth: 0.4,
      masterVolume: 0.35,
      backgroundSounds: {
        rain: { enabled: true, volume: 0.15 },
        whiteNoise: { enabled: false, volume: 0 },
        pinkNoise: { enabled: false, volume: 0 },
        brownNoise: { enabled: false, volume: 0 }
      },
      breathing: {
        enabled: true,
        inhaleTime: 6,
        holdTime: 6,
        exhaleTime: 12,
        restTime: 6
      }
    },
    bandProgression: [
      { time: 0, band: 'alpha' },
      { time: 180, band: 'theta' }
    ]
  }
];
