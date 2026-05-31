export type BrainwaveBandId = 'delta' | 'theta' | 'alpha' | 'beta' | 'gamma';

export interface BrainwaveBand {
  id: BrainwaveBandId;
  name: string;
  frequencyRange: [number, number];
  defaultFrequency: number;
  color: string;
  glowColor: string;
  description: string;
}

export type AudioMode = 'binaural' | 'isochronic';

export type BackgroundSoundId = 'rain' | 'whiteNoise' | 'pinkNoise' | 'brownNoise';

export interface BackgroundSoundState {
  enabled: boolean;
  volume: number;
}

export interface BackgroundSounds {
  rain: BackgroundSoundState;
  whiteNoise: BackgroundSoundState;
  pinkNoise: BackgroundSoundState;
  brownNoise: BackgroundSoundState;
}

export interface BreathingSettings {
  enabled: boolean;
  inhaleTime: number;
  holdTime: number;
  exhaleTime: number;
  restTime: number;
}

export type BreathingPhase = 'inhale' | 'hold' | 'exhale' | 'rest';

export interface HRVSettings {
  enabled: boolean;
  followHeartRate: boolean;
  currentHeartRate: number;
  averageHeartRate: number;
  hrvValue: number;
  isDetecting: boolean;
  beatIntervals: number[];
  lastBeatTime: number;
  confidence: number;
}

export interface HapticSettings {
  enabled: boolean;
  intensity: number;
  pattern: 'beat' | 'breathing' | 'wave';
  isConnected: boolean;
  lastVibrateTime: number;
}

export type AIFeedback = 'much_better' | 'better' | 'same' | 'worse' | 'much_worse';
export type AITreatmentPhase = 'warmup' | 'active' | 'cooldown' | 'complete';

export interface AdaptiveAISettings {
  enabled: boolean;
  currentPhase: AITreatmentPhase;
  startTime: number;
  feedbackHistory: { time: number; feedback: AIFeedback }[];
  adaptationLog: { time: number; param: string; oldValue: number; newValue: number; reason: string }[];
  recommendedBand: BrainwaveBandId | null;
  recommendedFrequency: number | null;
  userMood: number;
  sessionProgress: number;
}

export interface AudioState {
  isPlaying: boolean;
  currentBand: BrainwaveBand;
  beatFrequency: number;
  carrierFrequency: number;
  modulationDepth: number;
  masterVolume: number;
  channelBalance: number;
  audioMode: AudioMode;
  backgroundSounds: BackgroundSounds;
  breathing: BreathingSettings;
  frequencyData: Uint8Array;
  timeDataLeft: Float32Array;
  timeDataRight: Float32Array;
  phaseDifference: number;
  averageAmplitude: number;
  hrv: HRVSettings;
  haptic: HapticSettings;
  adaptiveAI: AdaptiveAISettings;
}

export interface AudioActions {
  togglePlay: () => void;
  setBand: (band: BrainwaveBand) => void;
  setBeatFrequency: (freq: number) => void;
  setCarrierFrequency: (freq: number) => void;
  setModulationDepth: (depth: number) => void;
  setMasterVolume: (volume: number) => void;
  setChannelBalance: (balance: number) => void;
  setAudioMode: (mode: AudioMode) => void;
  toggleBackgroundSound: (id: BackgroundSoundId) => void;
  setBackgroundVolume: (id: BackgroundSoundId, volume: number) => void;
  setBreathing: (settings: Partial<BreathingSettings>) => void;
  updateAudioData: (data: Partial<AudioState>) => void;
  loadPreset: (preset: Preset) => void;
  setHRV: (settings: Partial<HRVSettings>) => void;
  setHaptic: (settings: Partial<HapticSettings>) => void;
  setAdaptiveAI: (settings: Partial<AdaptiveAISettings>) => void;
  addAIFeedback: (feedback: AIFeedback) => void;
  triggerHaptic: (duration?: number) => void;
}

export interface Preset {
  id: string;
  name: string;
  description: string;
  icon: string;
  duration: number;
  settings: Partial<AudioState>;
  bandProgression?: { time: number; band: BrainwaveBandId }[];
}

export type AudioStore = AudioState & AudioActions;
