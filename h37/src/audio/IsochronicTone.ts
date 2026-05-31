export class IsochronicTone {
  private audioContext: AudioContext;
  private carrierOscillator: OscillatorNode;
  private lfoOscillator: OscillatorNode;
  private lfoGain: GainNode;
  private carrierGain: GainNode;
  private masterGain: GainNode;
  private isPlaying: boolean = false;
  private carrierFrequency: number = 200;
  private beatFrequency: number = 10;
  private modulationDepth: number = 0.5;

  constructor(audioContext: AudioContext) {
    this.audioContext = audioContext;

    this.carrierOscillator = audioContext.createOscillator();
    this.lfoOscillator = audioContext.createOscillator();

    this.carrierOscillator.type = 'sine';
    this.lfoOscillator.type = 'sine';

    this.lfoGain = audioContext.createGain();
    this.carrierGain = audioContext.createGain();
    this.masterGain = audioContext.createGain();
    this.masterGain.gain.value = 0;

    this.carrierOscillator.connect(this.carrierGain);
    this.lfoOscillator.connect(this.lfoGain);
    this.lfoGain.connect(this.carrierGain.gain);
    this.carrierGain.connect(this.masterGain);
  }

  setFrequencies(carrier: number, beat: number): void {
    this.carrierFrequency = carrier;
    this.beatFrequency = beat;

    const now = this.audioContext.currentTime;
    this.carrierOscillator.frequency.setTargetAtTime(carrier, now, 0.01);
    this.lfoOscillator.frequency.setTargetAtTime(beat, now, 0.01);
  }

  setBeatFrequency(beat: number): void {
    this.beatFrequency = beat;
    this.lfoOscillator.frequency.setTargetAtTime(beat, this.audioContext.currentTime, 0.01);
  }

  setCarrierFrequency(carrier: number): void {
    this.carrierFrequency = carrier;
    this.carrierOscillator.frequency.setTargetAtTime(carrier, this.audioContext.currentTime, 0.01);
  }

  setModulationDepth(depth: number): void {
    this.modulationDepth = depth;
    const now = this.audioContext.currentTime;
    this.lfoGain.gain.setTargetAtTime(depth, now, 0.01);
    this.carrierGain.gain.setTargetAtTime(1 - depth, now, 0.01);
  }

  setVolume(volume: number): void {
    this.masterGain.gain.setTargetAtTime(volume, this.audioContext.currentTime, 0.1);
  }

  start(): void {
    if (this.isPlaying) return;

    const now = this.audioContext.currentTime;
    this.carrierOscillator.start(now);
    this.lfoOscillator.start(now);
    this.isPlaying = true;
  }

  stop(): void {
    if (!this.isPlaying) return;

    const now = this.audioContext.currentTime;
    this.carrierOscillator.stop(now);
    this.lfoOscillator.stop(now);
    this.isPlaying = false;
  }

  connect(destination: AudioNode): void {
    this.masterGain.connect(destination);
  }

  disconnect(): void {
    this.masterGain.disconnect();
  }

  getOutputNode(): AudioNode {
    return this.masterGain;
  }

  destroy(): void {
    this.stop();
    this.disconnect();
  }
}
