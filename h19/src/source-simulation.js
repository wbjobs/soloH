const { Complex, FFT } = require('./signal-processing');

class SourceSimulator {
  constructor(options = {}) {
    this.sampleRate = options.sampleRate || 48000;
    this.soundSpeed = options.soundSpeed || 343;
    this.noiseLevel = options.noiseLevel || 0.01;
    this._noiseState = this._initNoiseState();
  }

  _initNoiseState() {
    return {
      s: Math.random() * 2 - 1,
      s1: Math.random() * 2 - 1,
      s2: Math.random() * 2 - 1,
      s3: Math.random() * 2 - 1
    };
  }

  generateWhiteNoise(numSamples, amplitude = 1) {
    const noise = new Float64Array(numSamples);
    for (let i = 0; i < numSamples; i++) {
      const u1 = Math.random();
      const u2 = Math.random();
      const z = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
      noise[i] = amplitude * z;
    }
    return noise;
  }

  generatePinkNoise(numSamples, amplitude = 1) {
    const noise = new Float64Array(numSamples);
    let b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0;
    
    for (let i = 0; i < numSamples; i++) {
      const white = (Math.random() * 2 - 1);
      b0 = 0.99886 * b0 + white * 0.0555179;
      b1 = 0.99332 * b1 + white * 0.0750759;
      b2 = 0.96900 * b2 + white * 0.1538520;
      b3 = 0.86650 * b3 + white * 0.3104856;
      b4 = 0.55000 * b4 + white * 0.5329522;
      b5 = -0.7616 * b5 - white * 0.0168980;
      noise[i] = amplitude * (b0 + b1 + b2 + b3 + b4 + b5 + b6 + white * 0.5362) * 0.11;
      b6 = white * 0.115926;
    }
    return noise;
  }

  generateSineWave(numSamples, frequency, amplitude = 1, phase = 0) {
    const signal = new Float64Array(numSamples);
    const dt = 1 / this.sampleRate;
    for (let i = 0; i < numSamples; i++) {
      signal[i] = amplitude * Math.sin(2 * Math.PI * frequency * i * dt + phase);
    }
    return signal;
  }

  generateSweep(numSamples, startFreq, endFreq, amplitude = 1, exponential = true) {
    const signal = new Float64Array(numSamples);
    const dt = 1 / this.sampleRate;
    const T = numSamples * dt;
    
    if (exponential) {
      const k = Math.pow(endFreq / startFreq, 1 / T);
      let phase = 0;
      for (let i = 0; i < numSamples; i++) {
        const t = i * dt;
        const freq = startFreq * Math.pow(k, t);
        phase += 2 * Math.PI * freq * dt;
        signal[i] = amplitude * Math.sin(phase);
      }
    } else {
      const sweepRate = (endFreq - startFreq) / T;
      for (let i = 0; i < numSamples; i++) {
        const t = i * dt;
        const freq = startFreq + sweepRate * t;
        signal[i] = amplitude * Math.sin(Math.PI * sweepRate * t * t + 2 * Math.PI * startFreq * t);
      }
    }
    return signal;
  }

  generateVoiceLike(numSamples, baseFreq = 150, amplitude = 1) {
    const signal = new Float64Array(numSamples);
    const dt = 1 / this.sampleRate;
    
    const harmonics = [1, 2, 3, 4, 5];
    const amplitudes = [1, 0.8, 0.6, 0.4, 0.2];
    
    let pitchVariation = 0;
    for (let i = 0; i < numSamples; i++) {
      const t = i * dt;
      
      pitchVariation = 0.95 * pitchVariation + 0.05 * (Math.random() * 20 - 10);
      const f0 = baseFreq + pitchVariation;
      
      let sample = 0;
      for (let h = 0; h < harmonics.length; h++) {
        const freq = f0 * harmonics[h];
        sample += amplitudes[h] * Math.sin(2 * Math.PI * freq * t);
      }
      
      const envelope = 0.5 + 0.5 * Math.sin(2 * Math.PI * 4 * t);
      signal[i] = amplitude * envelope * sample / harmonics.length;
    }
    
    return signal;
  }

  generatePulse(numSamples, pulseFreq, dutyCycle = 0.1, amplitude = 1) {
    const signal = new Float64Array(numSamples);
    const period = Math.round(this.sampleRate / pulseFreq);
    const pulseLength = Math.round(period * dutyCycle);
    
    for (let i = 0; i < numSamples; i++) {
      const phase = i % period;
      if (phase < pulseLength) {
        signal[i] = amplitude * Math.sin(Math.PI * phase / pulseLength);
      } else {
        signal[i] = 0;
      }
    }
    return signal;
  }

  generateSource(type, numSamples, options = {}) {
    switch (type) {
      case 'white_noise':
        return this.generateWhiteNoise(numSamples, options.amplitude);
      case 'pink_noise':
        return this.generatePinkNoise(numSamples, options.amplitude);
      case 'sine':
        return this.generateSineWave(numSamples, options.frequency, options.amplitude, options.phase);
      case 'sweep':
        return this.generateSweep(numSamples, options.startFreq, options.endFreq, options.amplitude, options.exponential);
      case 'voice':
        return this.generateVoiceLike(numSamples, options.baseFreq, options.amplitude);
      case 'pulse':
        return this.generatePulse(numSamples, options.pulseFreq, options.dutyCycle, options.amplitude);
      default:
        return this.generateWhiteNoise(numSamples, options.amplitude);
    }
  }

  propagateSignals(sourceSignal, arrayPositions, sourcePos, reflectors = []) {
    const numElements = arrayPositions.length;
    const numSamples = sourceSignal.length;
    const microphoneSignals = new Array(numElements);
    
    const dt = 1 / this.sampleRate;
    
    for (let m = 0; m < numElements; m++) {
      const micPos = arrayPositions[m];
      
      const dx = micPos.x - sourcePos.x;
      const dy = micPos.y - sourcePos.y;
      const dz = micPos.z - sourcePos.z;
      const directDist = Math.sqrt(dx * dx + dy * dy + dz * dz);
      const directDelay = directDist / this.soundSpeed;
      const directDelaySamples = Math.round(directDelay / dt);
      const directAttenuation = Math.min(1, 1 / (1 + directDist * 0.5));
      
      microphoneSignals[m] = new Float64Array(numSamples);
      
      for (let i = 0; i < numSamples; i++) {
        let sample = 0;
        
        const directIdx = i - directDelaySamples;
        if (directIdx >= 0 && directIdx < numSamples) {
          sample += directAttenuation * sourceSignal[directIdx];
        }
        
        for (const reflector of reflectors) {
          const refl = this._computeReflection(micPos, sourcePos, reflector);
          if (refl) {
            const reflDelaySamples = Math.round(refl.delay / dt);
            const reflIdx = i - reflDelaySamples;
            if (reflIdx >= 0 && reflIdx < numSamples) {
              sample += refl.attenuation * sourceSignal[reflIdx];
            }
          }
        }
        
        microphoneSignals[m][i] = sample;
      }
      
      if (this.noiseLevel > 0) {
        const noise = this.generateWhiteNoise(numSamples, this.noiseLevel);
        for (let i = 0; i < numSamples; i++) {
          microphoneSignals[m][i] += noise[i];
        }
      }
    }
    
    return microphoneSignals;
  }

  _computeReflection(micPos, sourcePos, reflector) {
    const normal = reflector.normal;
    const planePoint = reflector.position;
    
    const toSource = {
      x: sourcePos.x - planePoint.x,
      y: sourcePos.y - planePoint.y,
      z: sourcePos.z - planePoint.z
    };
    
    const dist = toSource.x * normal.x + toSource.y * normal.y + toSource.z * normal.z;
    
    if (dist < 0.01) return null;
    
    const imageSource = {
      x: sourcePos.x - 2 * dist * normal.x,
      y: sourcePos.y - 2 * dist * normal.y,
      z: sourcePos.z - 2 * dist * normal.z
    };
    
    const dx = micPos.x - imageSource.x;
    const dy = micPos.y - imageSource.y;
    const dz = micPos.z - imageSource.z;
    const totalDist = Math.sqrt(dx * dx + dy * dy + dz * dz);
    
    const attenuation = reflector.reflection * Math.min(1, 1 / (1 + totalDist * 0.5));
    
    return {
      delay: totalDist / this.soundSpeed,
      attenuation: attenuation
    };
  }

  generateMultiSourceSignals(sources, arrayPositions, numSamples, reflectors = []) {
    const numElements = arrayPositions.length;
    const microphoneSignals = new Array(numElements);
    
    for (let m = 0; m < numElements; m++) {
      microphoneSignals[m] = new Float64Array(numSamples);
    }
    
    for (const source of sources) {
      const sourceSignal = this.generateSource(
        source.type,
        numSamples,
        source.options
      );
      
      const propagated = this.propagateSignals(
        sourceSignal,
        arrayPositions,
        source.position,
        reflectors
      );
      
      for (let m = 0; m < numElements; m++) {
        for (let i = 0; i < numSamples; i++) {
          microphoneSignals[m][i] += propagated[m][i];
        }
      }
    }
    
    return microphoneSignals;
  }

  addReverberation(signals, rt60 = 0.3) {
    const numElements = signals.length;
    const numSamples = signals[0].length;
    const dt = 1 / this.sampleRate;
    
    const decay = Math.exp(-3 * dt / rt60);
    const delayLines = [];
    const delayLengths = [173, 259, 331, 419];
    
    for (let m = 0; m < numElements; m++) {
      delayLines[m] = delayLengths.map(len => new Array(len).fill(0));
    }
    
    const output = new Array(numElements);
    for (let m = 0; m < numElements; m++) {
      output[m] = new Float64Array(numSamples);
    }
    
    for (let i = 0; i < numSamples; i++) {
      for (let m = 0; m < numElements; m++) {
        let reverb = 0;
        for (let d = 0; d < delayLines[m].length; d++) {
          const dl = delayLines[m][d];
          const idx = i % dl.length;
          reverb += dl[idx];
          dl[idx] = decay * dl[idx] + 0.25 * signals[m][i];
        }
        output[m][i] = signals[m][i] + 0.3 * reverb / delayLines[m].length;
      }
    }
    
    return output;
  }
}

class WAVReader {
  constructor() {
    this.audioContext = null;
  }

  parseWAVBuffer(buffer) {
    const view = new DataView(buffer);
    
    if (view.getUint32(0, true) !== 0x46464952) {
      throw new Error('Not a valid WAV file');
    }
    
    if (view.getUint32(8, true) !== 0x45564157) {
      throw new Error('Not a valid WAV file');
    }
    
    let offset = 12;
    let fmt = null;
    let data = null;
    let dataOffset = 0;
    
    while (offset < buffer.byteLength) {
      const chunkId = view.getUint32(offset, true);
      const chunkSize = view.getUint32(offset + 4, true);
      
      if (chunkId === 0x20746d66) {
        fmt = {
          audioFormat: view.getUint16(offset + 8, true),
          numChannels: view.getUint16(offset + 10, true),
          sampleRate: view.getUint32(offset + 12, true),
          byteRate: view.getUint32(offset + 16, true),
          blockAlign: view.getUint16(offset + 20, true),
          bitsPerSample: view.getUint16(offset + 22, true)
        };
      } else if (chunkId === 0x61746164) {
        dataOffset = offset + 8;
        data = new DataView(buffer, dataOffset, chunkSize);
      }
      
      offset += 8 + chunkSize;
      if (chunkSize % 2) offset++;
    }
    
    if (!fmt || !data) {
      throw new Error('Invalid WAV format');
    }
    
    return { fmt, data, dataOffset };
  }

  extractChannels(buffer, numChannelsNeeded) {
    const { fmt, data } = this.parseWAVBuffer(buffer);
    const bytesPerSample = fmt.bitsPerSample / 8;
    const totalSamples = data.byteLength / (fmt.numChannels * bytesPerSample);
    
    const channels = new Array(numChannelsNeeded);
    for (let c = 0; c < numChannelsNeeded; c++) {
      channels[c] = new Float64Array(totalSamples);
    }
    
    const maxVal = Math.pow(2, fmt.bitsPerSample - 1);
    let sampleIdx = 0;
    
    for (let i = 0; i < data.byteLength; i += fmt.numChannels * bytesPerSample) {
      for (let c = 0; c < Math.min(fmt.numChannels, numChannelsNeeded); c++) {
        let val;
        const byteOffset = i + c * bytesPerSample;
        
        switch (fmt.bitsPerSample) {
          case 16:
            val = data.getInt16(byteOffset, true) / maxVal;
            break;
          case 24:
            val = (data.getInt8(byteOffset + 2) << 16 | 
                   data.getUint8(byteOffset + 1) << 8 | 
                   data.getUint8(byteOffset)) / (maxVal * 256);
            break;
          case 32:
            val = data.getInt32(byteOffset, true) / maxVal;
            break;
          default:
            val = data.getInt8(byteOffset) / 128;
        }
        
        channels[c][sampleIdx] = val;
      }
      
      for (let c = fmt.numChannels; c < numChannelsNeeded; c++) {
        channels[c][sampleIdx] = channels[0][sampleIdx];
      }
      
      sampleIdx++;
    }
    
    return {
      sampleRate: fmt.sampleRate,
      numSamples: totalSamples,
      channels: channels
    };
  }

  resample(signals, fromRate, toRate) {
    if (fromRate === toRate) return signals;
    
    const ratio = toRate / fromRate;
    const numChannels = signals.length;
    const numSamples = Math.floor(signals[0].length * ratio);
    
    const resampled = new Array(numChannels);
    for (let c = 0; c < numChannels; c++) {
      resampled[c] = new Float64Array(numSamples);
    }
    
    for (let c = 0; c < numChannels; c++) {
      for (let i = 0; i < numSamples; i++) {
        const srcIdx = i / ratio;
        const idx0 = Math.floor(srcIdx);
        const idx1 = Math.min(idx0 + 1, signals[c].length - 1);
        const frac = srcIdx - idx0;
        
        resampled[c][i] = signals[c][idx0] * (1 - frac) + signals[c][idx1] * frac;
      }
    }
    
    return resampled;
  }
}

module.exports = {
  SourceSimulator,
  WAVReader
};
