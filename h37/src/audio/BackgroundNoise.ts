export class BackgroundNoise {
  private audioContext: AudioContext;
  private noiseBuffer: AudioBuffer | null = null;
  private sourceNode: AudioBufferSourceNode | null = null;
  private gainNode: GainNode;
  private noiseType: 'white' | 'pink' | 'brown';
  private isPlaying: boolean = false;

  constructor(audioContext: AudioContext, noiseType: 'white' | 'pink' | 'brown' = 'white') {
    this.audioContext = audioContext;
    this.noiseType = noiseType;
    this.gainNode = audioContext.createGain();
    this.gainNode.gain.value = 0;
  }

  private generateWhiteNoise(): AudioBuffer {
    const bufferSize = 2 * this.audioContext.sampleRate;
    const buffer = this.audioContext.createBuffer(2, bufferSize, this.audioContext.sampleRate);

    for (let channel = 0; channel < 2; channel++) {
      const data = buffer.getChannelData(channel);
      for (let i = 0; i < bufferSize; i++) {
        data[i] = Math.random() * 2 - 1;
      }
    }

    return buffer;
  }

  private generatePinkNoise(): AudioBuffer {
    const bufferSize = 2 * this.audioContext.sampleRate;
    const buffer = this.audioContext.createBuffer(2, bufferSize, this.audioContext.sampleRate);

    for (let channel = 0; channel < 2; channel++) {
      const data = buffer.getChannelData(channel);
      let b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0;

      for (let i = 0; i < bufferSize; i++) {
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

    return buffer;
  }

  private generateBrownNoise(): AudioBuffer {
    const bufferSize = 2 * this.audioContext.sampleRate;
    const buffer = this.audioContext.createBuffer(2, bufferSize, this.audioContext.sampleRate);

    for (let channel = 0; channel < 2; channel++) {
      const data = buffer.getChannelData(channel);
      let lastOut = 0;
      for (let i = 0; i < bufferSize; i++) {
        const white = Math.random() * 2 - 1;
        lastOut = (lastOut + 0.02 * white) / 1.02;
        data[i] = lastOut * 3.5;
      }
    }

    return buffer;
  }

  private generateRainNoise(): AudioBuffer {
    const bufferSize = 2 * this.audioContext.sampleRate;
    const buffer = this.audioContext.createBuffer(2, bufferSize, this.audioContext.sampleRate);

    for (let channel = 0; channel < 2; channel++) {
      const data = buffer.getChannelData(channel);
      let b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0;

      for (let i = 0; i < bufferSize; i++) {
        let white = Math.random() * 2 - 1;
        b0 = 0.99886 * b0 + white * 0.0555179;
        b1 = 0.99332 * b1 + white * 0.0750759;
        b2 = 0.96900 * b2 + white * 0.1538520;
        b3 = 0.86650 * b3 + white * 0.3104856;
        b4 = 0.55000 * b4 + white * 0.5329522;
        b5 = -0.7616 * b5 - white * 0.0168980;
        let pink = (b0 + b1 + b2 + b3 + b4 + b5 + b6 + white * 0.5362) * 0.11;
        b6 = white * 0.115926;

        if (Math.random() < 0.001) {
          white = Math.random() * 0.5;
        } else {
          white = 0;
        }

        data[i] = pink * 0.6 + white * 0.4;
      }
    }

    return buffer;
  }

  generateBuffer(type: 'white' | 'pink' | 'brown' | 'rain'): void {
    this.noiseType = type === 'rain' ? 'pink' : type;
    switch (type) {
      case 'white':
        this.noiseBuffer = this.generateWhiteNoise();
        break;
      case 'pink':
        this.noiseBuffer = this.generatePinkNoise();
        break;
      case 'brown':
        this.noiseBuffer = this.generateBrownNoise();
        break;
      case 'rain':
        this.noiseBuffer = this.generateRainNoise();
        break;
    }
  }

  start(): void {
    if (!this.noiseBuffer || this.isPlaying) return;

    this.sourceNode = this.audioContext.createBufferSource();
    this.sourceNode.buffer = this.noiseBuffer;
    this.sourceNode.loop = true;
    this.sourceNode.connect(this.gainNode);
    this.sourceNode.start();
    this.isPlaying = true;
  }

  stop(): void {
    if (this.sourceNode && this.isPlaying) {
      this.sourceNode.stop();
      this.sourceNode.disconnect();
      this.sourceNode = null;
      this.isPlaying = false;
    }
  }

  setVolume(volume: number): void {
    this.gainNode.gain.setTargetAtTime(volume, this.audioContext.currentTime, 0.1);
  }

  connect(destination: AudioNode): void {
    this.gainNode.connect(destination);
  }

  disconnect(): void {
    this.gainNode.disconnect();
  }

  getGainNode(): GainNode {
    return this.gainNode;
  }

  destroy(): void {
    this.stop();
    this.disconnect();
  }
}
