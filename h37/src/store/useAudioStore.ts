import { create } from 'zustand';
import type {
  AudioStore,
  BrainwaveBand,
  AudioMode,
  BackgroundSoundId,
  BreathingSettings,
  Preset,
  HRVSettings,
  HapticSettings,
  AdaptiveAISettings,
  AIFeedback
} from '../types/audio';
import { DEFAULT_BAND } from '../data/brainwaveBands';

const FFT_SIZE = 2048;

const defaultHRV: HRVSettings = {
  enabled: false,
  followHeartRate: false,
  currentHeartRate: 0,
  averageHeartRate: 0,
  hrvValue: 0,
  isDetecting: false,
  beatIntervals: [],
  lastBeatTime: 0,
  confidence: 0
};

const defaultHaptic: HapticSettings = {
  enabled: false,
  intensity: 0.5,
  pattern: 'beat',
  isConnected: false,
  lastVibrateTime: 0
};

const defaultAdaptiveAI: AdaptiveAISettings = {
  enabled: false,
  currentPhase: 'warmup',
  startTime: 0,
  feedbackHistory: [],
  adaptationLog: [],
  recommendedBand: null,
  recommendedFrequency: null,
  userMood: 0.5,
  sessionProgress: 0
};

export const useAudioStore = create<AudioStore>((set, get) => ({
  isPlaying: false,
  currentBand: DEFAULT_BAND,
  beatFrequency: DEFAULT_BAND.defaultFrequency,
  carrierFrequency: 200,
  modulationDepth: 0.5,
  masterVolume: 0.5,
  channelBalance: 0,
  audioMode: 'binaural',
  backgroundSounds: {
    rain: { enabled: false, volume: 0.3 },
    whiteNoise: { enabled: false, volume: 0.2 },
    pinkNoise: { enabled: false, volume: 0.2 },
    brownNoise: { enabled: false, volume: 0.2 }
  },
  breathing: {
    enabled: false,
    inhaleTime: 4,
    holdTime: 4,
    exhaleTime: 8,
    restTime: 4
  },
  frequencyData: new Uint8Array(FFT_SIZE / 2),
  timeDataLeft: new Float32Array(FFT_SIZE),
  timeDataRight: new Float32Array(FFT_SIZE),
  phaseDifference: 0,
  averageAmplitude: 0,
  hrv: defaultHRV,
  haptic: defaultHaptic,
  adaptiveAI: defaultAdaptiveAI,

  togglePlay: () => set((state) => ({ isPlaying: !state.isPlaying })),

  setBand: (band: BrainwaveBand) => set({
    currentBand: band,
    beatFrequency: band.defaultFrequency
  }),

  setBeatFrequency: (freq: number) => set({ beatFrequency: freq }),

  setCarrierFrequency: (freq: number) => set({ carrierFrequency: freq }),

  setModulationDepth: (depth: number) => set({ modulationDepth: depth }),

  setMasterVolume: (volume: number) => set({ masterVolume: volume }),

  setChannelBalance: (balance: number) => set({ channelBalance: balance }),

  setAudioMode: (mode: AudioMode) => set({ audioMode: mode }),

  toggleBackgroundSound: (id: BackgroundSoundId) => set((state) => ({
    backgroundSounds: {
      ...state.backgroundSounds,
      [id]: {
        ...state.backgroundSounds[id],
        enabled: !state.backgroundSounds[id].enabled
      }
    }
  })),

  setBackgroundVolume: (id: BackgroundSoundId, volume: number) => set((state) => ({
    backgroundSounds: {
      ...state.backgroundSounds,
      [id]: {
        ...state.backgroundSounds[id],
        volume
      }
    }
  })),

  setBreathing: (settings: Partial<BreathingSettings>) => set((state) => ({
    breathing: {
      ...state.breathing,
      ...settings
    }
  })),

  updateAudioData: (data: Partial<AudioStore>) => set(data),

  loadPreset: (preset: Preset) => set((state) => {
    const settings = preset.settings;
    return {
      ...state,
      ...settings,
      backgroundSounds: settings.backgroundSounds || state.backgroundSounds,
      breathing: settings.breathing || state.breathing
    };
  }),

  setHRV: (settings: Partial<HRVSettings>) => set((state) => ({
    hrv: {
      ...state.hrv,
      ...settings
    }
  })),

  setHaptic: (settings: Partial<HapticSettings>) => set((state) => ({
    haptic: {
      ...state.haptic,
      ...settings
    }
  })),

  setAdaptiveAI: (settings: Partial<AdaptiveAISettings>) => set((state) => ({
    adaptiveAI: {
      ...state.adaptiveAI,
      ...settings
    }
  })),

  addAIFeedback: (feedback: AIFeedback) => set((state) => {
    const newHistory = [...state.adaptiveAI.feedbackHistory, {
      time: Date.now(),
      feedback
    }];
    if (newHistory.length > 50) newHistory.shift();
    return {
      adaptiveAI: {
        ...state.adaptiveAI,
        feedbackHistory: newHistory
      }
    };
  }),

  triggerHaptic: (duration: number = 100) => {
    const state = get();
    if (!state.haptic.enabled) return;

    const gamepads = navigator.getGamepads();
    gamepads.forEach((gamepad) => {
      if (gamepad?.vibrationActuator) {
        gamepad.vibrationActuator.playEffect('dual-rumble', {
          duration,
          strongMagnitude: 0.5 * state.haptic.intensity,
          weakMagnitude: 0.3 * state.haptic.intensity
        });
      }
    });
  }
}));
