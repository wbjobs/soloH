import type { AudioState } from '../types/audio';

export class WavExporter {
  private sampleRate: number = 44100;
  private numChannels: number = 2;
  private bitDepth: number = 16;

  constructor(sampleRate: number = 44100) {
    this.sampleRate = sampleRate;
  }

  private generateSineWave(frequency: number, duration: number, phase: number = 0): Float32Array {
    const length = Math.floor(this.sampleRate * duration);
    const buffer = new Float32Array(length);
    const angularFrequency = 2 * Math.PI * frequency;

    for (let i = 0; i < length; i++) {
      const time = i / this.sampleRate;
      buffer[i] = Math.sin(angularFrequency * time + phase);
    }

    return buffer;
  }

  private generateBinauralBeat(
    carrierFreq: number,
    beatFreq: number,
    duration: number
  ): [Float32Array, Float32Array] {
    const length = Math.floor(this.sampleRate * duration);
    const leftChannel = new Float32Array(length);
    const rightChannel = new Float32Array(length);

    const leftFreq = carrierFreq - beatFreq / 2;
    const rightFreq = carrierFreq + beatFreq / 2;

    const leftAngular = 2 * Math.PI * leftFreq;
    const rightAngular = 2 * Math.PI * rightFreq;

    for (let i = 0; i < length; i++) {
      const time = i / this.sampleRate;
      leftChannel[i] = Math.sin(leftAngular * time);
      rightChannel[i] = Math.sin(rightAngular * time);
    }

    return [leftChannel, rightChannel];
  }

  private generateIsochronicTone(
    carrierFreq: number,
    beatFreq: number,
    modulationDepth: number,
    duration: number
  ): [Float32Array, Float32Array] {
    const length = Math.floor(this.sampleRate * duration);
    const leftChannel = new Float32Array(length);
    const rightChannel = new Float32Array(length);

    const carrierAngular = 2 * Math.PI * carrierFreq;
    const lfoAngular = 2 * Math.PI * beatFreq;

    for (let i = 0; i < length; i++) {
      const time = i / this.sampleRate;
      const carrier = Math.sin(carrierAngular * time);
      const lfo = (Math.sin(lfoAngular * time) + 1) / 2;
      const envelope = (1 - modulationDepth) + modulationDepth * lfo;
      const sample = carrier * envelope;
      leftChannel[i] = sample;
      rightChannel[i] = sample;
    }

    return [leftChannel, rightChannel];
  }

  private generatePinkNoise(duration: number): [Float32Array, Float32Array] {
    const length = Math.floor(this.sampleRate * duration);
    const leftChannel = new Float32Array(length);
    const rightChannel = new Float32Array(length);

    for (let channel = 0; channel < 2; channel++) {
      const data = channel === 0 ? leftChannel : rightChannel;
      let b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0;

      for (let i = 0; i < length; i++) {
        const white = Math.random() * 2 - 1;
        b0 = 0.99886 * b0 + white * 0.0555179;
        b1 = 0.99332 * b1 + white * 0.0750759;
        b2 = 0.96900 * b2 + white * 0.1538520;
        b3 = 0.86650 * b3 + white * 0.3104856;
        b4 = 0.55000 * b4 + white * 0.5329522;
        b5 = -0.7616 * b5 - white * 0.0168980;
        data[i] = (b0 + b1 + b2 + b3 + b4 + b5 + b6 + white * 0.5362) * 0.11;
        b6 = white * 0.115926;
      }
    }

    return [leftChannel, rightChannel];
  }

  private floatTo16BitPCM(view: DataView, offset: number, input: Float32Array): void {
    for (let i = 0; i < input.length; i++, offset += 2) {
      const s = Math.max(-1, Math.min(1, input[i]));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    }
  }

  private writeString(view: DataView, offset: number, string: string): void {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i));
    }
  }

  private encodeWAV(leftChannel: Float32Array, rightChannel: Float32Array): ArrayBuffer {
    const length = leftChannel.length;
    const buffer = new ArrayBuffer(44 + length * this.numChannels * 2);
    const view = new DataView(buffer);

    this.writeString(view, 0, 'RIFF');
    view.setUint32(4, 36 + length * this.numChannels * 2, true);
    this.writeString(view, 8, 'WAVE');
    this.writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, this.numChannels, true);
    view.setUint32(24, this.sampleRate, true);
    view.setUint32(28, this.sampleRate * this.numChannels * 2, true);
    view.setUint16(32, this.numChannels * 2, true);
    view.setUint16(34, this.bitDepth, true);
    this.writeString(view, 36, 'data');
    view.setUint32(40, length * this.numChannels * 2, true);

    let offset = 44;
    for (let i = 0; i < length; i++) {
      view.setInt16(offset, leftChannel[i] * 0x7fff, true);
      offset += 2;
      view.setInt16(offset, rightChannel[i] * 0x7fff, true);
      offset += 2;
    }

    return buffer;
  }

  async exportWAV(settings: AudioState, duration: number): Promise<Blob> {
    let leftChannel: Float32Array;
    let rightChannel: Float32Array;

    if (settings.audioMode === 'binaural') {
      [leftChannel, rightChannel] = this.generateBinauralBeat(
        settings.carrierFrequency,
        settings.beatFrequency,
        duration
      );
    } else {
      [leftChannel, rightChannel] = this.generateIsochronicTone(
        settings.carrierFrequency,
        settings.beatFrequency,
        settings.modulationDepth,
        duration
      );
    }

    const masterVolume = settings.masterVolume;
    for (let i = 0; i < leftChannel.length; i++) {
      leftChannel[i] *= masterVolume;
      rightChannel[i] *= masterVolume;
    }

    const leftGain = (1 - settings.channelBalance) * 0.5;
    const rightGain = (1 + settings.channelBalance) * 0.5;
    for (let i = 0; i < leftChannel.length; i++) {
      leftChannel[i] *= leftGain;
      rightChannel[i] *= rightGain;
    }

    if (settings.backgroundSounds.rain.enabled ||
        settings.backgroundSounds.whiteNoise.enabled ||
        settings.backgroundSounds.pinkNoise.enabled ||
        settings.backgroundSounds.brownNoise.enabled) {
      const [noiseLeft, noiseRight] = this.generatePinkNoise(duration);
      let noiseVolume = 0;
      if (settings.backgroundSounds.rain.enabled) noiseVolume += settings.backgroundSounds.rain.volume;
      if (settings.backgroundSounds.whiteNoise.enabled) noiseVolume += settings.backgroundSounds.whiteNoise.volume;
      if (settings.backgroundSounds.pinkNoise.enabled) noiseVolume += settings.backgroundSounds.pinkNoise.volume;
      if (settings.backgroundSounds.brownNoise.enabled) noiseVolume += settings.backgroundSounds.brownNoise.volume;
      
      for (let i = 0; i < leftChannel.length; i++) {
        leftChannel[i] += noiseLeft[i] * noiseVolume;
        rightChannel[i] += noiseRight[i] * noiseVolume;
      }
    }

    const wavBuffer = this.encodeWAV(leftChannel, rightChannel);
    return new Blob([wavBuffer], { type: 'audio/wav' });
  }

  async downloadWAV(settings: AudioState, duration: number, filename: string): Promise<void> {
    const blob = await this.exportWAV(settings, duration);
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }
}
