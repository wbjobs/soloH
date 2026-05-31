import type { AIFeedback, AITreatmentPhase, BrainwaveBandId, AdaptiveAISettings, AudioState } from '../types/audio';
import { BRAINWAVE_BANDS } from '../data/brainwaveBands';

interface AdaptationRule {
  condition: (state: AudioState, feedbackHistory: { time: number; feedback: AIFeedback }[]) => boolean;
  action: (state: AudioState) => { param: string; oldValue: number; newValue: number; reason: string };
}

export class AdaptiveAITherapy {
  private settings: AdaptiveAISettings;
  private getState: () => AudioState;
  private onAdaptation: (param: string, oldValue: number, newValue: number, reason: string) => void;
  private onRecommendation: (band: BrainwaveBandId | null, frequency: number | null) => void;
  private checkIntervalId: number | null = null;
  private readonly CHECK_INTERVAL = 15000;

  private adaptationRules: AdaptationRule[] = [
    {
      condition: (state, history) => {
        const recent = history.slice(-3);
        return recent.length >= 2 &&
               recent.every(f => f.feedback === 'much_better' || f.feedback === 'better');
      },
      action: (state) => ({
        param: 'modulationDepth',
        oldValue: state.modulationDepth,
        newValue: Math.min(1, state.modulationDepth + 0.1),
        reason: '用户反馈良好，增加调制深度增强效果'
      })
    },
    {
      condition: (state, history) => {
        const recent = history.slice(-2);
        return recent.length >= 2 &&
               recent.every(f => f.feedback === 'worse' || f.feedback === 'much_worse');
      },
      action: (state) => ({
        param: 'modulationDepth',
        oldValue: state.modulationDepth,
        newValue: Math.max(0.2, state.modulationDepth - 0.15),
        reason: '用户反馈不佳，降低调制深度减少刺激'
      })
    },
    {
      condition: (state, history) => {
        const recent = history.slice(-3);
        return recent.length >= 2 &&
               recent.every(f => f.feedback === 'better') &&
               state.hrv.hrvValue > 50;
      },
      action: (state) => {
        const currentIdx = BRAINWAVE_BANDS.findIndex(b => b.id === state.currentBand.id);
        if (currentIdx > 0) {
          return {
            param: 'band',
            oldValue: currentIdx,
            newValue: currentIdx - 1,
            reason: 'HRV升高，过渡到更深层的脑波状态'
          };
        }
        return { param: 'none', oldValue: 0, newValue: 0, reason: '' };
      }
    },
    {
      condition: (state, history) => {
        const recent = history.slice(-2);
        return recent.length >= 1 &&
               recent[recent.length - 1].feedback === 'worse' &&
               state.hrv.hrvValue < 20;
      },
      action: (state) => {
        const currentIdx = BRAINWAVE_BANDS.findIndex(b => b.id === state.currentBand.id);
        if (currentIdx < BRAINWAVE_BANDS.length - 1) {
          return {
            param: 'band',
            oldValue: currentIdx,
            newValue: currentIdx + 1,
            reason: 'HRV降低，切换到更活跃的脑波频段'
          };
        }
        return { param: 'none', oldValue: 0, newValue: 0, reason: '' };
      }
    },
    {
      condition: (state, history) => {
        const lastFeedback = history[history.length - 1];
        return lastFeedback?.feedback === 'same' && state.adaptiveAI.sessionProgress > 0.3;
      },
      action: (state) => ({
        param: 'beatFrequency',
        oldValue: state.beatFrequency,
        newValue: Math.min(
          state.currentBand.frequencyRange[1],
          Math.max(
            state.currentBand.frequencyRange[0],
            state.beatFrequency + (Math.random() > 0.5 ? 0.5 : -0.5)
          )
        ),
        reason: '用户反应平淡，微调频率保持新鲜感'
      })
    },
    {
      condition: (state, history) => {
        return state.adaptiveAI.currentPhase === 'warmup' &&
               state.adaptiveAI.sessionProgress > 0.15;
      },
      action: (state) => ({
        param: 'phase',
        oldValue: 0,
        newValue: 1,
        reason: '暖身阶段完成，进入主动治疗阶段'
      })
    },
    {
      condition: (state, history) => {
        return state.adaptiveAI.currentPhase === 'active' &&
               state.adaptiveAI.sessionProgress > 0.8;
      },
      action: (state) => ({
        param: 'phase',
        oldValue: 1,
        newValue: 2,
        reason: '疗程接近完成，进入放松收尾阶段'
      })
    }
  ];

  constructor(
    settings: AdaptiveAISettings,
    getState: () => AudioState,
    onAdaptation: (param: string, oldValue: number, newValue: number, reason: string) => void,
    onRecommendation: (band: BrainwaveBandId | null, frequency: number | null) => void
  ) {
    this.settings = settings;
    this.getState = getState;
    this.onAdaptation = onAdaptation;
    this.onRecommendation = onRecommendation;
  }

  start(): void {
    if (!this.settings.enabled) return;

    this.settings.startTime = Date.now();
    this.settings.currentPhase = 'warmup';
    this.settings.sessionProgress = 0;

    this.checkIntervalId = window.setInterval(() => {
      this.checkAndAdapt();
    }, this.CHECK_INTERVAL);

    this.updateRecommendation();
  }

  stop(): void {
    if (this.checkIntervalId !== null) {
      clearInterval(this.checkIntervalId);
      this.checkIntervalId = null;
    }
  }

  addFeedback(feedback: AIFeedback): void {
    const now = Date.now();
    this.settings.feedbackHistory.push({
      time: now,
      feedback
    });

    if (this.settings.feedbackHistory.length > 50) {
      this.settings.feedbackHistory.shift();
    }

    this.settings.userMood = this.calculateMood();
    this.updateRecommendation();
  }

  private checkAndAdapt(): void {
    if (!this.settings.enabled) return;

    const state = this.getState();
    const now = Date.now();
    const elapsed = (now - this.settings.startTime) / 1000 / 60;
    const targetDuration = 20;
    this.settings.sessionProgress = Math.min(1, elapsed / targetDuration);

    for (const rule of this.adaptationRules) {
      if (rule.condition(state, this.settings.feedbackHistory)) {
        const result = rule.action(state);
        if (result.param !== 'none') {
          this.applyAdaptation(result.param, result.oldValue, result.newValue, result.reason);
          break;
        }
      }
    }

    this.updateRecommendation();
  }

  private applyAdaptation(param: string, oldValue: number, newValue: number, reason: string): void {
    this.settings.adaptationLog.push({
      time: Date.now(),
      param,
      oldValue,
      newValue,
      reason
    });

    if (this.settings.adaptationLog.length > 100) {
      this.settings.adaptationLog.shift();
    }

    this.onAdaptation(param, oldValue, newValue, reason);
  }

  private calculateMood(): number {
    if (this.settings.feedbackHistory.length === 0) return 0.5;

    const feedbackScores: Record<AIFeedback, number> = {
      much_better: 1.0,
      better: 0.75,
      same: 0.5,
      worse: 0.25,
      much_worse: 0.0
    };

    const recent = this.settings.feedbackHistory.slice(-10);
    const weightedSum = recent.reduce((sum, f, i) => {
      const weight = (i + 1) / recent.length;
      return sum + feedbackScores[f.feedback] * weight;
    }, 0);

    const totalWeight = recent.reduce((sum, _, i) => sum + (i + 1) / recent.length, 0);
    return weightedSum / totalWeight;
  }

  private updateRecommendation(): void {
    const state = this.getState();
    const mood = this.settings.userMood;
    const hrv = state.hrv.hrvValue;
    const hr = state.hrv.currentHeartRate;

    let recommendedBand: BrainwaveBandId | null = null;
    let recommendedFrequency: number | null = null;

    if (hr > 90 || hrv < 20) {
      recommendedBand = 'alpha';
      recommendedFrequency = 10;
    } else if (hr < 60 && hrv > 60) {
      recommendedBand = 'theta';
      recommendedFrequency = 6;
    } else if (mood > 0.8) {
      const currentIdx = BRAINWAVE_BANDS.findIndex(b => b.id === state.currentBand.id);
      if (currentIdx > 0) {
        recommendedBand = BRAINWAVE_BANDS[currentIdx - 1].id;
        recommendedFrequency = BRAINWAVE_BANDS[currentIdx - 1].defaultFrequency;
      }
    } else if (mood < 0.3) {
      const currentIdx = BRAINWAVE_BANDS.findIndex(b => b.id === state.currentBand.id);
      if (currentIdx < BRAINWAVE_BANDS.length - 1) {
        recommendedBand = BRAINWAVE_BANDS[currentIdx + 1].id;
        recommendedFrequency = BRAINWAVE_BANDS[currentIdx + 1].defaultFrequency;
      }
    }

    this.settings.recommendedBand = recommendedBand;
    this.settings.recommendedFrequency = recommendedFrequency;

    if (recommendedBand || recommendedFrequency) {
      this.onRecommendation(recommendedBand, recommendedFrequency);
    }
  }

  getAdaptationLog(): { time: number; param: string; oldValue: number; newValue: number; reason: string }[] {
    return [...this.settings.adaptationLog];
  }

  getPhaseName(): string {
    const phases: Record<AITreatmentPhase, string> = {
      warmup: '暖身阶段',
      active: '主动治疗',
      cooldown: '放松收尾',
      complete: '已完成'
    };
    return phases[this.settings.currentPhase];
  }

  updateSettings(settings: Partial<AdaptiveAISettings>): void {
    Object.assign(this.settings, settings);

    if (settings.enabled && !this.checkIntervalId) {
      this.start();
    } else if (!settings.enabled && this.checkIntervalId) {
      this.stop();
    }
  }

  destroy(): void {
    this.stop();
  }
}
