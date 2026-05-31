export class HRVDetection {
  private audioContext: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private microphoneStream: MediaStream | null = null;
  private isRunning: boolean = false;
  private animationFrameId: number | null = null;

  private lastPeakTime: number = 0;
  private beatIntervals: number[] = [];
  private readonly MAX_INTERVALS = 30;
  private readonly MIN_BPM = 40;
  private readonly MAX_BPM = 200;
  private readonly PEAK_THRESHOLD = 0.15;
  private readonly REFRACTORY_PERIOD = 300;

  private onHeartRateUpdate: (hr: number, hrv: number, confidence: number) => void;
  private onBeatDetected: () => void;

  constructor(
    onHeartRateUpdate: (hr: number, hrv: number, confidence: number) => void,
    onBeatDetected: () => void
  ) {
    this.onHeartRateUpdate = onHeartRateUpdate;
    this.onBeatDetected = onBeatDetected;
  }

  async start(): Promise<boolean> {
    try {
      this.microphoneStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
          sampleRate: 44100
        }
      });

      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
      this.audioContext = new AudioContextClass();

      const source = this.audioContext.createMediaStreamSource(this.microphoneStream);

      const highpassFilter = this.audioContext.createBiquadFilter();
      highpassFilter.type = 'highpass';
      highpassFilter.frequency.value = 20;

      const lowpassFilter = this.audioContext.createBiquadFilter();
      lowpassFilter.type = 'lowpass';
      lowpassFilter.frequency.value = 40;

      const gainNode = this.audioContext.createGain();
      gainNode.gain.value = 20;

      this.analyser = this.audioContext.createAnalyser();
      this.analyser.fftSize = 2048;
      this.analyser.smoothingTimeConstant = 0.3;

      source.connect(highpassFilter);
      highpassFilter.connect(lowpassFilter);
      lowpassFilter.connect(gainNode);
      gainNode.connect(this.analyser);

      this.isRunning = true;
      this.beatIntervals = [];
      this.lastPeakTime = performance.now();

      this.analyze();

      return true;
    } catch (error) {
      console.error('HRV检测启动失败:', error);
      return false;
    }
  }

  stop(): void {
    this.isRunning = false;

    if (this.animationFrameId) {
      cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }

    if (this.microphoneStream) {
      this.microphoneStream.getTracks().forEach(track => track.stop());
      this.microphoneStream = null;
    }

    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }

    this.analyser = null;
  }

  private analyze = (): void => {
    if (!this.isRunning || !this.analyser) return;

    const bufferLength = this.analyser.fftSize;
    const dataArray = new Uint8Array(bufferLength);
    this.analyser.getByteTimeDomainData(dataArray);

    let maxAmplitude = 0;
    let maxIndex = 0;

    for (let i = 0; i < bufferLength; i++) {
      const value = (dataArray[i] - 128) / 128;
      const absValue = Math.abs(value);
      if (absValue > maxAmplitude) {
        maxAmplitude = absValue;
        maxIndex = i;
      }
    }

    const now = performance.now();
    const timeSinceLastPeak = now - this.lastPeakTime;
    const minInterval = (60 / this.MAX_BPM) * 1000;

    if (maxAmplitude > this.PEAK_THRESHOLD && timeSinceLastPeak > this.REFRACTORY_PERIOD) {
      if (timeSinceLastPeak >= minInterval) {
        const interval = timeSinceLastPeak;
        this.beatIntervals.push(interval);

        if (this.beatIntervals.length > this.MAX_INTERVALS) {
          this.beatIntervals.shift();
        }

        const bpm = 60000 / this.calculateAverage(this.beatIntervals);
        const hrv = this.calculateHRV(this.beatIntervals);
        const confidence = this.calculateConfidence(this.beatIntervals);

        if (bpm >= this.MIN_BPM && bpm <= this.MAX_BPM) {
          this.onHeartRateUpdate(bpm, hrv, confidence);
          this.onBeatDetected();
        }

        this.lastPeakTime = now;
      }
    }

    this.animationFrameId = requestAnimationFrame(this.analyze);
  };

  private calculateAverage(arr: number[]): number {
    if (arr.length === 0) return 0;
    return arr.reduce((sum, val) => sum + val, 0) / arr.length;
  }

  private calculateSD(arr: number[]): number {
    if (arr.length < 2) return 0;
    const avg = this.calculateAverage(arr);
    const squaredDiffs = arr.map(val => Math.pow(val - avg, 2));
    return Math.sqrt(this.calculateAverage(squaredDiffs));
  }

  private calculateHRV(intervals: number[]): number {
    if (intervals.length < 2) return 0;

    const successiveDiffs = [];
    for (let i = 1; i < intervals.length; i++) {
      successiveDiffs.push(Math.abs(intervals[i] - intervals[i - 1]));
    }

    const rMSSD = Math.sqrt(this.calculateAverage(successiveDiffs.map(d => d * d)));
    return Math.min(100, rMSSD);
  }

  private calculateConfidence(intervals: number[]): number {
    if (intervals.length < 5) return 0;

    const cv = this.calculateSD(intervals) / this.calculateAverage(intervals);
    const countFactor = Math.min(1, intervals.length / this.MAX_INTERVALS);
    const cvFactor = Math.max(0, 1 - cv * 2);

    return countFactor * cvFactor;
  }

  getBeatIntervals(): number[] {
    return [...this.beatIntervals];
  }

  isActive(): boolean {
    return this.isRunning;
  }
}
