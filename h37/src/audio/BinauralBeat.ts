export class BinauralBeat {
  private audioContext: AudioContext;
  private leftOscillator: OscillatorNode;
  private rightOscillator: OscillatorNode;
  private leftGain: GainNode;
  private rightGain: GainNode;
  private masterGain: GainNode;
  private splitter: ChannelSplitterNode;
  private merger: ChannelMergerNode;
  private isPlaying: boolean = false;
  private carrierFrequency: number = 200;
  private beatFrequency: number = 10;

  constructor(audioContext: AudioContext) {
    this.audioContext = audioContext;

    this.leftOscillator = audioContext.createOscillator();
    this.rightOscillator = audioContext.createOscillator();

    this.leftOscillator.type = 'sine';
    this.rightOscillator.type = 'sine';

    this.leftGain = audioContext.createGain();
    this.rightGain = audioContext.createGain();
    this.masterGain = audioContext.createGain();
    this.masterGain.gain.value = 0;

    this.splitter = audioContext.createChannelSplitter(2);
    this.merger = audioContext.createChannelMerger(2);

    this.leftOscillator.connect(this.leftGain);
    this.rightOscillator.connect(this.rightGain);

    this.leftGain.connect(this.merger, 0, 0);
    this.rightGain.connect(this.merger, 0, 1);

    this.merger.connect(this.masterGain);
  }

  setFrequencies(carrier: number, beat: number): void {
    this.carrierFrequency = carrier;
    this.beatFrequency = beat;

    const now = this.audioContext.currentTime;
    this.leftOscillator.frequency.setTargetAtTime(carrier - beat / 2, now, 0.01);
    this.rightOscillator.frequency.setTargetAtTime(carrier + beat / 2, now, 0.01);
  }

  setBeatFrequency(beat: number): void {
    this.beatFrequency = beat;
    const now = this.audioContext.currentTime;
    this.leftOscillator.frequency.setTargetAtTime(this.carrierFrequency - beat / 2, now, 0.01);
    this.rightOscillator.frequency.setTargetAtTime(this.carrierFrequency + beat / 2, now, 0.01);
  }

  setCarrierFrequency(carrier: number): void {
    this.carrierFrequency = carrier;
    const now = this.audioContext.currentTime;
    this.leftOscillator.frequency.setTargetAtTime(carrier - this.beatFrequency / 2, now, 0.01);
    this.rightOscillator.frequency.setTargetAtTime(carrier + this.beatFrequency / 2, now, 0.01);
  }

  setVolume(volume: number): void {
    this.masterGain.gain.setTargetAtTime(volume, this.audioContext.currentTime, 0.1);
  }

  setChannelBalance(balance: number): void {
    const now = this.audioContext.currentTime;
    this.leftGain.gain.setTargetAtTime(0.5 * (1 - balance), now, 0.1);
    this.rightGain.gain.setTargetAtTime(0.5 * (1 + balance), now, 0.1);
  }

  start(): void {
    if (this.isPlaying) return;

    const now = this.audioContext.currentTime;
    this.leftOscillator.start(now);
    this.rightOscillator.start(now);
    this.isPlaying = true;
  }

  stop(): void {
    if (!this.isPlaying) return;

    const now = this.audioContext.currentTime;
    this.leftOscillator.stop(now);
    this.rightOscillator.stop(now);
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
