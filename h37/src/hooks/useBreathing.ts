import { useEffect, useState, useRef, useCallback } from 'react';
import { useAudioStore } from '../store/useAudioStore';
import type { BreathingPhase } from '../types/audio';

export const useBreathing = () => {
  const { breathing } = useAudioStore();
  const [phase, setPhase] = useState<BreathingPhase>('inhale');
  const [progress, setProgress] = useState(0);
  const animationRef = useRef<number | null>(null);
  const startTimeRef = useRef<number>(0);
  const phaseIndexRef = useRef<number>(0);

  const phases: BreathingPhase[] = ['inhale', 'hold', 'exhale', 'rest'];

  const getPhaseDuration = useCallback((phaseType: BreathingPhase): number => {
    switch (phaseType) {
      case 'inhale': return breathing.inhaleTime * 1000;
      case 'hold': return breathing.holdTime * 1000;
      case 'exhale': return breathing.exhaleTime * 1000;
      case 'rest': return breathing.restTime * 1000;
    }
  }, [breathing]);

  const getTotalCycleTime = useCallback((): number => {
    return phases.reduce((total, p) => total + getPhaseDuration(p), 0);
  }, [getPhaseDuration]);

  useEffect(() => {
    if (!breathing.enabled) {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
        animationRef.current = null;
      }
      return;
    }

    startTimeRef.current = performance.now();
    phaseIndexRef.current = 0;

    const animate = (currentTime: number) => {
      const elapsed = currentTime - startTimeRef.current;
      const totalCycle = getTotalCycleTime();
      const cycleProgress = (elapsed % totalCycle) / totalCycle;

      let accumulatedTime = 0;
      let currentPhaseIndex = 0;
      let phaseProgress = 0;

      for (let i = 0; i < phases.length; i++) {
        const phaseDuration = getPhaseDuration(phases[i]) / totalCycle;
        if (cycleProgress < accumulatedTime + phaseDuration) {
          currentPhaseIndex = i;
          phaseProgress = (cycleProgress - accumulatedTime) / phaseDuration;
          break;
        }
        accumulatedTime += phaseDuration;
      }

      if (phaseIndexRef.current !== currentPhaseIndex) {
        phaseIndexRef.current = currentPhaseIndex;
        setPhase(phases[currentPhaseIndex]);
      }

      setProgress(phaseProgress);
      animationRef.current = requestAnimationFrame(animate);
    };

    animationRef.current = requestAnimationFrame(animate);

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [breathing.enabled, getPhaseDuration, getTotalCycleTime]);

  const getPhaseText = (): string => {
    switch (phase) {
      case 'inhale': return '吸气';
      case 'hold': return '屏息';
      case 'exhale': return '呼气';
      case 'rest': return '停顿';
    }
  };

  return {
    phase,
    progress,
    getPhaseText,
    isEnabled: breathing.enabled
  };
};
