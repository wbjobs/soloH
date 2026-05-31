import { useEffect, useRef, useCallback } from 'react';
import { BinauralBeat } from '../audio/BinauralBeat';
import { IsochronicTone } from '../audio/IsochronicTone';
import { BackgroundNoise } from '../audio/BackgroundNoise';
import { useAudioStore } from '../store/useAudioStore';
import type { BackgroundSoundId } from '../types/audio';

const FFT_SIZE = 2048;

export const useAudioEngine = () => {
  const audioContextRef = useRef<AudioContext | null>(null);
  const binauralBeatRef = useRef<BinauralBeat | null>(null);
  const isochronicToneRef = useRef<IsochronicTone | null>(null);
  const masterGainRef = useRef<GainNode | null>(null);
  const compressorRef = useRef<DynamicsCompressorNode | null>(null);
  const analyserLeftRef = useRef<AnalyserNode | null>(null);
  const analyserRightRef = useRef<AnalyserNode | null>(null);
  const splitterRef = useRef<ChannelSplitterNode | null>(null);
  const backgroundNoisesRef = useRef<Map<BackgroundSoundId, BackgroundNoise>>(new Map());
  const animationFrameRef = useRef<number | null>(null);
  const isInitializedRef = useRef(false);
  const lastAnalysisTimeRef = useRef(0);

  const {
    isPlaying,
    beatFrequency,
    carrierFrequency,
    modulationDepth,
    masterVolume,
    channelBalance,
    audioMode,
    backgroundSounds,
    updateAudioData,
    currentBand,
    hrv,
    haptic,
    setBeatFrequency,
    triggerHaptic
  } = useAudioStore();

  const initAudioContext = useCallback(() => {
    if (isInitializedRef.current) return;

    const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
    audioContextRef.current = new AudioContextClass();

    const ctx = audioContextRef.current;

    binauralBeatRef.current = new BinauralBeat(ctx);
    isochronicToneRef.current = new IsochronicTone(ctx);

    masterGainRef.current = ctx.createGain();
    masterGainRef.current.gain.value = 0;

    compressorRef.current = ctx.createDynamicsCompressor();
    compressorRef.current.threshold.value = -24;
    compressorRef.current.knee.value = 30;
    compressorRef.current.ratio.value = 4;
    compressorRef.current.attack.value = 0.005;
    compressorRef.current.release.value = 0.25;

    splitterRef.current = ctx.createChannelSplitter(2);

    analyserLeftRef.current = ctx.createAnalyser();
    analyserRightRef.current = ctx.createAnalyser();
    analyserLeftRef.current.fftSize = FFT_SIZE;
    analyserRightRef.current.fftSize = FFT_SIZE;
    analyserLeftRef.current.smoothingTimeConstant = 0.8;
    analyserRightRef.current.smoothingTimeConstant = 0.8;
    analyserLeftRef.current.minDecibels = -90;
    analyserRightRef.current.minDecibels = -90;
    analyserLeftRef.current.maxDecibels = -10;
    analyserRightRef.current.maxDecibels = -10;

    binauralBeatRef.current.connect(masterGainRef.current);
    isochronicToneRef.current.connect(masterGainRef.current);

    masterGainRef.current.connect(compressorRef.current);
    compressorRef.current.connect(splitterRef.current);
    splitterRef.current.connect(analyserLeftRef.current, 0);
    splitterRef.current.connect(analyserRightRef.current, 1);

    compressorRef.current.connect(ctx.destination);

    const noiseTypes: { id: BackgroundSoundId; type: 'white' | 'pink' | 'brown' | 'rain' }[] = [
      { id: 'rain', type: 'rain' },
      { id: 'whiteNoise', type: 'white' },
      { id: 'pinkNoise', type: 'pink' },
      { id: 'brownNoise', type: 'brown' }
    ];

    noiseTypes.forEach(({ id, type }) => {
      const noise = new BackgroundNoise(ctx, type === 'rain' ? 'pink' : type);
      noise.generateBuffer(type);
      noise.connect(masterGainRef.current!);
      backgroundNoisesRef.current.set(id, noise);
    });

    isInitializedRef.current = true;
  }, []);

  const updateAudioAnalysis = useCallback(() => {
    if (!analyserLeftRef.current || !analyserRightRef.current) return;

    const now = performance.now();
    if (now - lastAnalysisTimeRef.current < 16) return;
    lastAnalysisTimeRef.current = now;

    const bufferLength = analyserLeftRef.current.frequencyBinCount;
    const timeDataLeft = new Float32Array(FFT_SIZE);
    const timeDataRight = new Float32Array(FFT_SIZE);
    const avgFreqData = new Uint8Array(bufferLength);
    const leftFreqData = new Uint8Array(bufferLength);
    const rightFreqData = new Uint8Array(bufferLength);

    analyserLeftRef.current.getFloatTimeDomainData(timeDataLeft);
    analyserRightRef.current.getFloatTimeDomainData(timeDataRight);
    analyserLeftRef.current.getByteFrequencyData(leftFreqData);
    analyserRightRef.current.getByteFrequencyData(rightFreqData);

    for (let i = 0; i < bufferLength; i++) {
      avgFreqData[i] = (leftFreqData[i] + rightFreqData[i]) / 2;
    }

    let sum = 0;
    for (let i = 0; i < bufferLength; i++) {
      sum += avgFreqData[i];
    }
    const averageAmplitude = sum / bufferLength / 255;

    const maxLag = Math.min(256, FFT_SIZE / 4);
    let sumLeft = 0, sumRight = 0, sumSqLeft = 0, sumSqRight = 0;
    for (let i = 0; i < FFT_SIZE; i++) {
      sumLeft += timeDataLeft[i];
      sumRight += timeDataRight[i];
      sumSqLeft += timeDataLeft[i] * timeDataLeft[i];
      sumSqRight += timeDataRight[i] * timeDataRight[i];
    }
    const meanLeft = sumLeft / FFT_SIZE;
    const meanRight = sumRight / FFT_SIZE;
    const varLeft = sumSqLeft / FFT_SIZE - meanLeft * meanLeft;
    const varRight = sumSqRight / FFT_SIZE - meanRight * meanRight;
    const stdLeft = Math.sqrt(Math.max(varLeft, 1e-10));
    const stdRight = Math.sqrt(Math.max(varRight, 1e-10));
    const normFactor = FFT_SIZE * stdLeft * stdRight;

    let maxCorrelation = -Infinity;
    let bestLag = 0;

    for (let lag = -maxLag; lag <= maxLag; lag++) {
      let correlation = 0;
      const startIdx = Math.max(0, lag);
      const endIdx = Math.min(FFT_SIZE, FFT_SIZE + lag);

      for (let i = startIdx; i < endIdx; i++) {
        const leftVal = timeDataLeft[i] - meanLeft;
        const rightVal = timeDataRight[i - lag] - meanRight;
        correlation += leftVal * rightVal;
      }

      const normalizedCorrelation = correlation / normFactor;
      if (normalizedCorrelation > maxCorrelation) {
        maxCorrelation = normalizedCorrelation;
        bestLag = lag;
      }
    }

    const sampleRate = audioContextRef.current?.sampleRate || 44100;
    const phaseDifference = (bestLag / sampleRate) * beatFrequency * Math.PI * 2;

    updateAudioData({
      frequencyData: avgFreqData,
      timeDataLeft,
      timeDataRight,
      phaseDifference,
      averageAmplitude
    });
  }, [updateAudioData, beatFrequency]);

  const animate = useCallback(() => {
    updateAudioAnalysis();
    animationFrameRef.current = requestAnimationFrame(animate);
  }, [updateAudioAnalysis]);

  useEffect(() => {
    if (!isInitializedRef.current) return;

    if (isPlaying) {
      if (audioContextRef.current?.state === 'suspended') {
        audioContextRef.current.resume();
      }

      if (audioMode === 'binaural') {
        binauralBeatRef.current?.start();
        isochronicToneRef.current?.stop();
      } else {
        isochronicToneRef.current?.start();
        binauralBeatRef.current?.stop();
      }

      masterGainRef.current?.gain.setTargetAtTime(masterVolume, audioContextRef.current.currentTime, 0.1);

      if (audioMode === 'binaural') {
        binauralBeatRef.current?.setFrequencies(carrierFrequency, beatFrequency);
        binauralBeatRef.current?.setChannelBalance(channelBalance);
      } else {
        isochronicToneRef.current?.setFrequencies(carrierFrequency, beatFrequency);
        isochronicToneRef.current?.setModulationDepth(modulationDepth);
      }

      (Object.keys(backgroundSounds) as BackgroundSoundId[]).forEach((id) => {
        const noise = backgroundNoisesRef.current.get(id);
        const soundState = backgroundSounds[id];
        if (noise && soundState.enabled) {
          noise.start();
          noise.setVolume(soundState.volume);
        } else if (noise) {
          noise.stop();
        }
      });

      if (!animationFrameRef.current) {
        animate();
      }
    } else {
      binauralBeatRef.current?.stop();
      isochronicToneRef.current?.stop();
      masterGainRef.current?.gain.setTargetAtTime(0, audioContextRef.current?.currentTime || 0, 0.1);

      backgroundNoisesRef.current.forEach((noise) => {
        noise.stop();
      });

      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
    }
  }, [isPlaying, audioMode, beatFrequency, carrierFrequency, modulationDepth, masterVolume, channelBalance, backgroundSounds, animate]);

  useEffect(() => {
    if (!isInitializedRef.current || !isPlaying) return;

    const ctx = audioContextRef.current;
    if (!ctx) return;

    if (audioMode === 'binaural') {
      binauralBeatRef.current?.setBeatFrequency(beatFrequency);
      binauralBeatRef.current?.setCarrierFrequency(carrierFrequency);
      binauralBeatRef.current?.setChannelBalance(channelBalance);
    } else {
      isochronicToneRef.current?.setBeatFrequency(beatFrequency);
      isochronicToneRef.current?.setCarrierFrequency(carrierFrequency);
      isochronicToneRef.current?.setModulationDepth(modulationDepth);
    }

    masterGainRef.current?.gain.setTargetAtTime(masterVolume, ctx.currentTime, 0.1);
  }, [isPlaying, audioMode, beatFrequency, carrierFrequency, modulationDepth, masterVolume, channelBalance]);

  useEffect(() => {
    if (!isInitializedRef.current) return;

    (Object.keys(backgroundSounds) as BackgroundSoundId[]).forEach((id) => {
      const noise = backgroundNoisesRef.current.get(id);
      const soundState = backgroundSounds[id];
      if (noise) {
        if (soundState.enabled && isPlaying) {
          noise.start();
          noise.setVolume(soundState.volume);
        } else {
          noise.stop();
        }
      }
    });
  }, [backgroundSounds, isPlaying]);

  useEffect(() => {
    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }

      binauralBeatRef.current?.destroy();
      isochronicToneRef.current?.destroy();
      backgroundNoisesRef.current.forEach((noise) => noise.destroy());
      backgroundNoisesRef.current.clear();

      if (masterGainRef.current) {
        masterGainRef.current.disconnect();
        masterGainRef.current = null;
      }
      if (compressorRef.current) {
        compressorRef.current.disconnect();
        compressorRef.current = null;
      }
      if (splitterRef.current) {
        splitterRef.current.disconnect();
        splitterRef.current = null;
      }
      if (analyserLeftRef.current) {
        analyserLeftRef.current.disconnect();
        analyserLeftRef.current = null;
      }
      if (analyserRightRef.current) {
        analyserRightRef.current.disconnect();
        analyserRightRef.current = null;
      }
      if (audioContextRef.current) {
        audioContextRef.current.close();
        audioContextRef.current = null;
      }

      isInitializedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (!isPlaying) return;

    if (hrv.followHeartRate && hrv.currentHeartRate > 0) {
      const targetFreq = hrv.currentHeartRate / 60;
      const minFreq = currentBand.frequencyRange[0];
      const maxFreq = currentBand.frequencyRange[1];
      const clampedFreq = Math.max(minFreq, Math.min(maxFreq, targetFreq));

      if (Math.abs(clampedFreq - beatFrequency) > 0.05) {
        setBeatFrequency(clampedFreq);
      }
    }
  }, [hrv.followHeartRate, hrv.currentHeartRate, currentBand, beatFrequency, setBeatFrequency, isPlaying]);

  useEffect(() => {
    if (hrv.lastBeatTime > 0 && haptic.enabled) {
      triggerHaptic(80);
    }
  }, [hrv.lastBeatTime, haptic.enabled, triggerHaptic]);

  useEffect(() => {
    if (!isPlaying || !haptic.enabled || !isInitializedRef.current) return;

    if (haptic.pattern === 'beat') {
      const intervalMs = 1000 / beatFrequency;
      const interval = setInterval(() => {
        triggerHaptic(80);
      }, intervalMs);

      return () => clearInterval(interval);
    }
  }, [beatFrequency, haptic.pattern, haptic.enabled, isPlaying, triggerHaptic]);

  return { initAudioContext };
};
