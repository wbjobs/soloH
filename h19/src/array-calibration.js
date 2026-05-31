const { Complex, FFT } = require('./signal-processing');

class ArrayCalibration {
  constructor(arrayPositions, options = {}) {
    this.arrayPositions = arrayPositions;
    this.numElements = arrayPositions.length;
    this.soundSpeed = options.soundSpeed || 343;
    this.sampleRate = options.sampleRate || 48000;
    this.fftSize = options.fftSize || 1024;
    this.fft = new FFT(this.fftSize);
    this.halfSize = this.fftSize / 2;
    this.freqStep = this.sampleRate / this.fftSize;
    
    this.amplitudeGains = new Float64Array(this.numElements);
    this.phaseOffsets = new Float64Array(this.numElements);
    
    for (let i = 0; i < this.numElements; i++) {
      this.amplitudeGains[i] = 1.0;
      this.phaseOffsets[i] = 0.0;
    }
    
    this.calibrationData = [];
    this.isCalibrated = false;
    this._precomputeFFTBuffers();
  }

  _precomputeFFTBuffers() {
    this._fftInputReal = new Float64Array(this.fftSize);
    this._fftInputImag = new Float64Array(this.fftSize);
  }

  _computeSpectrum(signal) {
    const complexSpectrum = this.fft.realTransform(signal);
    
    const spectrum = {
      real: new Float64Array(this.halfSize + 1),
      imag: new Float64Array(this.halfSize + 1)
    };
    
    spectrum.real[0] = complexSpectrum[0].real;
    spectrum.imag[0] = 0;
    for (let i = 1; i <= this.halfSize; i++) {
      spectrum.real[i] = complexSpectrum[i].real;
      spectrum.imag[i] = complexSpectrum[i].imag;
    }
    
    return spectrum;
  }

  _computeSteeringVector(azimuth, elevation, frequency) {
    const k = 2 * Math.PI * frequency / this.soundSpeed;
    const svReal = new Float64Array(this.numElements);
    const svImag = new Float64Array(this.numElements);
    
    for (let i = 0; i < this.numElements; i++) {
      const pos = this.arrayPositions[i];
      const tau = (pos.x * Math.sin(elevation) * Math.cos(azimuth) +
                   pos.y * Math.sin(elevation) * Math.sin(azimuth) +
                   pos.z * Math.cos(elevation)) / this.soundSpeed;
      const phase = 2 * Math.PI * frequency * tau;
      svReal[i] = Math.cos(phase);
      svImag[i] = Math.sin(phase);
    }
    
    return { svReal, svImag };
  }

  addCalibrationData(timeSignals, knownSource) {
    const { azimuth, elevation, distance, frequency } = knownSource;
    
    const spectra = new Array(this.numElements);
    for (let i = 0; i < this.numElements; i++) {
      spectra[i] = this._computeSpectrum(timeSignals[i]);
    }
    
    const freqBin = Math.max(1, Math.min(this.halfSize, Math.round(frequency / this.freqStep)));
    
    const observedPhases = new Float64Array(this.numElements);
    const observedAmplitudes = new Float64Array(this.numElements);
    
    for (let i = 0; i < this.numElements; i++) {
      const real = spectra[i].real[freqBin];
      const imag = spectra[i].imag[freqBin];
      observedAmplitudes[i] = Math.sqrt(real * real + imag * imag);
      observedPhases[i] = Math.atan2(imag, real);
    }
    
    const { svReal, svImag } = this._computeSteeringVector(azimuth, elevation, frequency);
    const expectedPhases = new Float64Array(this.numElements);
    for (let i = 0; i < this.numElements; i++) {
      expectedPhases[i] = Math.atan2(svImag[i], svReal[i]);
    }
    
    this.calibrationData.push({
      timeSignals,
      knownSource,
      observedAmplitudes,
      observedPhases,
      expectedPhases,
      frequency
    });
    
    return this.calibrationData.length;
  }

  calibrate() {
    if (this.calibrationData.length === 0) {
      return { success: false, message: 'No calibration data available' };
    }
    
    const refChannel = 0;
    const N = this.calibrationData.length;
    
    const amplitudeErrors = new Float64Array(this.numElements);
    const phaseErrors = new Float64Array(this.numElements);
    
    for (let calIdx = 0; calIdx < N; calIdx++) {
      const data = this.calibrationData[calIdx];
      const { observedAmplitudes, observedPhases, expectedPhases } = data;
      
      for (let i = 0; i < this.numElements; i++) {
        let phaseDiff = observedPhases[i] - expectedPhases[i];
        while (phaseDiff > Math.PI) phaseDiff -= 2 * Math.PI;
        while (phaseDiff < -Math.PI) phaseDiff += 2 * Math.PI;
        
        const refPhaseDiff = observedPhases[refChannel] - expectedPhases[refChannel];
        while (refPhaseDiff > Math.PI) refPhaseDiff -= 2 * Math.PI;
        while (refPhaseDiff < -Math.PI) refPhaseDiff += 2 * Math.PI;
        
        amplitudeErrors[i] += observedAmplitudes[i] / observedAmplitudes[refChannel];
        phaseErrors[i] += phaseDiff - refPhaseDiff;
      }
    }
    
    for (let i = 0; i < this.numElements; i++) {
      this.amplitudeGains[i] = 1.0 / (amplitudeErrors[i] / N);
      this.phaseOffsets[i] = -(phaseErrors[i] / N);
    }
    
    this.isCalibrated = true;
    
    let maxAmplitudeError = 0;
    let maxPhaseError = 0;
    for (let i = 0; i < this.numElements; i++) {
      maxAmplitudeError = Math.max(maxAmplitudeError, Math.abs(1 - this.amplitudeGains[i]));
      maxPhaseError = Math.max(maxPhaseError, Math.abs(this.phaseOffsets[i]) * 180 / Math.PI);
    }
    
    return {
      success: true,
      amplitudeGains: Array.from(this.amplitudeGains),
      phaseOffsets: Array.from(this.phaseOffsets),
      maxAmplitudeError,
      maxPhaseError,
      numCalibrationPoints: N
    };
  }

  applyCalibration(timeSignals) {
    if (!this.isCalibrated) {
      return timeSignals;
    }
    
    const correctedSignals = new Array(this.numElements);
    const freqRange = {
      start: Math.max(1, Math.floor(500 / this.freqStep)),
      end: Math.min(this.halfSize, Math.ceil(8000 / this.freqStep))
    };
    
    for (let i = 0; i < this.numElements; i++) {
      const spectrum = this._computeSpectrum(timeSignals[i]);
      
      for (let f = freqRange.start; f <= freqRange.end; f++) {
        const gain = this.amplitudeGains[i];
        const phase = this.phaseOffsets[i];
        
        const cosP = Math.cos(phase);
        const sinP = Math.sin(phase);
        
        const r = spectrum.real[f];
        const im = spectrum.imag[f];
        
        spectrum.real[f] = (r * cosP - im * sinP) * gain;
        spectrum.imag[f] = (r * sinP + im * cosP) * gain;
      }
      
      for (let f = 0; f <= this.halfSize; f++) {
        this._fftInputReal[f] = spectrum.real[f];
        this._fftInputImag[f] = spectrum.imag[f];
      }
      for (let f = this.halfSize + 1; f < this.fftSize; f++) {
        const idx = this.fftSize - f;
        this._fftInputReal[f] = spectrum.real[idx];
        this._fftInputImag[f] = -spectrum.imag[idx];
      }
      
      this.fft.inverse(this._fftInputReal, this._fftInputImag);
      
      correctedSignals[i] = new Float64Array(this.fftSize);
      for (let n = 0; n < this.fftSize; n++) {
        correctedSignals[i][n] = this._fftInputReal[n] / this.fftSize;
      }
    }
    
    return correctedSignals;
  }

  applyCalibrationFast(timeSignals) {
    if (!this.isCalibrated) {
      return timeSignals;
    }
    
    const correctedSignals = new Array(this.numElements);
    
    for (let i = 0; i < this.numElements; i++) {
      correctedSignals[i] = new Float64Array(timeSignals[i].length);
      
      const gain = this.amplitudeGains[i];
      const phase = this.phaseOffsets[i];
      
      if (Math.abs(phase) < 1e-6 && Math.abs(gain - 1) < 1e-6) {
        for (let n = 0; n < timeSignals[i].length; n++) {
          correctedSignals[i][n] = timeSignals[i][n];
        }
        continue;
      }
      
      const spectrum = this._computeSpectrum(timeSignals[i]);
      
      for (let f = 1; f <= this.halfSize; f++) {
        const cosP = Math.cos(phase);
        const sinP = Math.sin(phase);
        
        const r = spectrum.real[f];
        const im = spectrum.imag[f];
        
        spectrum.real[f] = (r * cosP - im * sinP) * gain;
        spectrum.imag[f] = (r * sinP + im * cosP) * gain;
      }
      
      const complexSpectrum = new Array(this.fftSize);
      for (let f = 0; f <= this.halfSize; f++) {
        complexSpectrum[f] = new Complex(spectrum.real[f], spectrum.imag[f]);
      }
      for (let f = this.halfSize + 1; f < this.fftSize; f++) {
        const idx = this.fftSize - f;
        complexSpectrum[f] = new Complex(spectrum.real[idx], -spectrum.imag[idx]);
      }
      
      const timeDomain = this.fft.inverseTransform(complexSpectrum);
      
      for (let n = 0; n < Math.min(timeSignals[i].length, this.fftSize); n++) {
        correctedSignals[i][n] = timeDomain[n].real;
      }
    }
    
    return correctedSignals;
  }

  simulateChannelErrors(options = {}) {
    const maxAmplitudeError = options.maxAmplitudeError || 0.2;
    const maxPhaseError = options.maxPhaseError || 30;
    
    const trueAmplitudeGains = new Float64Array(this.numElements);
    const truePhaseOffsets = new Float64Array(this.numElements);
    
    for (let i = 0; i < this.numElements; i++) {
      trueAmplitudeGains[i] = 1 + (Math.random() * 2 - 1) * maxAmplitudeError;
      truePhaseOffsets[i] = (Math.random() * 2 - 1) * maxPhaseError * Math.PI / 180;
    }
    
    return {
      amplitudeGains: trueAmplitudeGains,
      phaseOffsets: truePhaseOffsets,
      apply: (timeSignals) => {
        const distortedSignals = new Array(this.numElements);
        for (let i = 0; i < this.numElements; i++) {
          distortedSignals[i] = new Float64Array(timeSignals[i].length);
          const gain = trueAmplitudeGains[i];
          const phase = truePhaseOffsets[i];
          
          const spectrum = this._computeSpectrum(timeSignals[i]);
          
          for (let f = 1; f <= this.halfSize; f++) {
            const cosP = Math.cos(phase);
            const sinP = Math.sin(phase);
            const r = spectrum.real[f];
            const im = spectrum.imag[f];
            spectrum.real[f] = (r * cosP - im * sinP) * gain;
            spectrum.imag[f] = (r * sinP + im * cosP) * gain;
          }
          
          const complexSpectrum = new Array(this.fftSize);
          for (let f = 0; f <= this.halfSize; f++) {
            complexSpectrum[f] = new Complex(spectrum.real[f], spectrum.imag[f]);
          }
          for (let f = this.halfSize + 1; f < this.fftSize; f++) {
            const idx = this.fftSize - f;
            complexSpectrum[f] = new Complex(spectrum.real[idx], -spectrum.imag[idx]);
          }
          
          const timeDomain = this.fft.inverseTransform(complexSpectrum);
          
          for (let n = 0; n < Math.min(timeSignals[i].length, this.fftSize); n++) {
            distortedSignals[i][n] = timeDomain[n].real;
          }
        }
        return distortedSignals;
      }
    };
  }

  selfCalibrate(timeSignals, numSources, options = {}) {
    const maxIterations = options.maxIterations || 50;
    const convergenceThreshold = options.convergenceThreshold || 1e-6;
    
    let currentGains = new Float64Array(this.numElements);
    let currentPhases = new Float64Array(this.numElements);
    for (let i = 0; i < this.numElements; i++) {
      currentGains[i] = 1.0;
      currentPhases[i] = 0.0;
    }
    
    let prevCost = Infinity;
    
    for (let iter = 0; iter < maxIterations; iter++) {
      const correctedSignals = new Array(this.numElements);
      for (let i = 0; i < this.numElements; i++) {
        correctedSignals[i] = new Float64Array(timeSignals[i].length);
        const gain = currentGains[i];
        const phase = currentPhases[i];
        
        const spectrum = this._computeSpectrum(timeSignals[i]);
        
        for (let f = 1; f <= this.halfSize; f++) {
          const cosP = Math.cos(phase);
          const sinP = Math.sin(phase);
          const r = spectrum.real[f];
          const im = spectrum.imag[f];
          spectrum.real[f] = (r * cosP - im * sinP) * gain;
          spectrum.imag[f] = (r * sinP + im * cosP) * gain;
        }
        
        for (let f = 0; f <= this.halfSize; f++) {
          this._fftInputReal[f] = spectrum.real[f];
          this._fftInputImag[f] = spectrum.imag[f];
        }
        for (let f = this.halfSize + 1; f < this.fftSize; f++) {
          const idx = this.fftSize - f;
          this._fftInputReal[f] = spectrum.real[idx];
          this._fftInputImag[f] = -spectrum.imag[idx];
        }
        
        this.fft.inverse(this._fftInputReal, this._fftInputImag);
        
        for (let n = 0; n < Math.min(timeSignals[i].length, this.fftSize); n++) {
          correctedSignals[i][n] = this._fftInputReal[n] / this.fftSize;
        }
      }
      
      let cost = 0;
      const freqStart = Math.max(1, Math.floor(1000 / this.freqStep));
      const freqEnd = Math.min(this.halfSize, Math.ceil(4000 / this.freqStep));
      
      for (let f = freqStart; f <= freqEnd; f++) {
        const spectra = new Array(this.numElements);
        for (let i = 0; i < this.numElements; i++) {
          const spec = this._computeSpectrum(correctedSignals[i]);
          spectra[i] = { real: spec.real[f], imag: spec.imag[f] };
        }
        
        let maxVariance = 0;
        for (let i = 0; i < this.numElements; i++) {
          for (let j = i + 1; j < this.numElements; j++) {
            const dr = spectra[i].real - spectra[j].real;
            const di = spectra[i].imag - spectra[j].imag;
            maxVariance = Math.max(maxVariance, dr * dr + di * di);
          }
        }
        cost += maxVariance;
      }
      
      cost /= (freqEnd - freqStart + 1);
      
      if (Math.abs(prevCost - cost) < convergenceThreshold * cost) {
        break;
      }
      prevCost = cost;
      
      for (let i = 0; i < this.numElements; i++) {
        currentGains[i] += (Math.random() - 0.5) * 0.01;
        currentPhases[i] += (Math.random() - 0.5) * 0.01;
        currentGains[i] = Math.max(0.5, Math.min(2.0, currentGains[i]));
      }
    }
    
    for (let i = 0; i < this.numElements; i++) {
      this.amplitudeGains[i] = currentGains[i];
      this.phaseOffsets[i] = currentPhases[i];
    }
    
    this.isCalibrated = true;
    
    return {
      success: true,
      amplitudeGains: Array.from(currentGains),
      phaseOffsets: Array.from(currentPhases),
      finalCost: prevCost
    };
  }

  reset() {
    for (let i = 0; i < this.numElements; i++) {
      this.amplitudeGains[i] = 1.0;
      this.phaseOffsets[i] = 0.0;
    }
    this.calibrationData = [];
    this.isCalibrated = false;
  }

  getCalibrationStatus() {
    return {
      isCalibrated: this.isCalibrated,
      amplitudeGains: Array.from(this.amplitudeGains),
      phaseOffsets: Array.from(this.phaseOffsets),
      numCalibrationPoints: this.calibrationData.length
    };
  }
}

class AutoGainControl {
  constructor(numChannels, options = {}) {
    this.numChannels = numChannels;
    this.targetLevel = options.targetLevel || 0.5;
    this.attackTime = options.attackTime || 0.01;
    this.releaseTime = options.releaseTime || 0.1;
    this.sampleRate = options.sampleRate || 48000;
    
    this.gains = new Float64Array(numChannels);
    for (let i = 0; i < numChannels; i++) {
      this.gains[i] = 1.0;
    }
    
    this.attackCoef = Math.exp(-1 / (this.sampleRate * this.attackTime));
    this.releaseCoef = Math.exp(-1 / (this.sampleRate * this.releaseTime));
    
    this.rms = new Float64Array(numChannels);
  }

  process(signals) {
    const output = new Array(this.numChannels);
    
    for (let i = 0; i < this.numChannels; i++) {
      output[i] = new Float64Array(signals[i].length);
      
      for (let n = 0; n < signals[i].length; n++) {
        const input = signals[i][n];
        this.rms[i] = this.attackCoef * this.rms[i] + (1 - this.attackCoef) * input * input;
        
        const currentLevel = Math.sqrt(this.rms[i]);
        const targetGain = currentLevel > 1e-6 ? this.targetLevel / currentLevel : 1;
        
        if (targetGain < this.gains[i]) {
          this.gains[i] = this.attackCoef * this.gains[i] + (1 - this.attackCoef) * targetGain;
        } else {
          this.gains[i] = this.releaseCoef * this.gains[i] + (1 - this.releaseCoef) * targetGain;
        }
        
        output[i][n] = input * this.gains[i];
      }
    }
    
    return output;
  }

  reset() {
    for (let i = 0; i < this.numChannels; i++) {
      this.gains[i] = 1.0;
      this.rms[i] = 0;
    }
  }
}

module.exports = {
  ArrayCalibration,
  AutoGainControl
};
