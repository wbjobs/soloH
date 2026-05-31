const { Complex, FFT, Beamforming } = require('./signal-processing');

class NearfieldAcousticHolography {
  constructor(arrayPositions, options = {}) {
    this.arrayPositions = arrayPositions;
    this.numElements = arrayPositions.length;
    this.soundSpeed = options.soundSpeed || 343;
    this.sampleRate = options.sampleRate || 48000;
    this.fftSize = options.fftSize || 1024;
    this.fft = new FFT(this.fftSize);
    this.halfSize = this.fftSize / 2;
    this.freqStep = this.sampleRate / this.fftSize;
    
    this.reconstructionGrid = options.reconstructionGrid || {
      xMin: -2, xMax: 2, xStep: 0.1,
      yMin: -2, yMax: 2, yStep: 0.1,
      z: 0.5
    };
    
    this.regularizationFactor = options.regularizationFactor || 1e-3;
    
    this._precomputeGridPoints();
    this._precomputeFFTBuffers();
  }

  _precomputeGridPoints() {
    const { xMin, xMax, xStep, yMin, yMax, yStep, z } = this.reconstructionGrid;
    this.gridPoints = [];
    this.gridDimensions = {
      xSize: Math.ceil((xMax - xMin) / xStep) + 1,
      ySize: Math.ceil((yMax - yMin) / yStep) + 1,
      z
    };
    
    let idx = 0;
    for (let y = yMin; y <= yMax + 1e-10; y += yStep) {
      for (let x = xMin; x <= xMax + 1e-10; x += xStep) {
        this.gridPoints.push({ x, y, z, index: idx++ });
      }
    }
  }

  _precomputeFFTBuffers() {
    this._fftInputReal = new Float64Array(this.fftSize);
    this._fftInputImag = new Float64Array(this.fftSize);
    this._spectraReal = new Array(this.numElements);
    this._spectraImag = new Array(this.numElements);
    for (let m = 0; m < this.numElements; m++) {
      this._spectraReal[m] = new Float64Array(this.halfSize + 1);
      this._spectraImag[m] = new Float64Array(this.halfSize + 1);
    }
  }

  _computeSpectra(timeSignals) {
    for (let m = 0; m < this.numElements; m++) {
      const signal = timeSignals[m];
      const spectrum = this.fft.realTransform(signal);
      
      this._spectraReal[m][0] = spectrum[0].real;
      this._spectraImag[m][0] = 0;
      for (let i = 1; i <= this.halfSize; i++) {
        this._spectraReal[m][i] = spectrum[i].real;
        this._spectraImag[m][i] = spectrum[i].imag;
      }
    }
  }

  _greenFunction(x1, y1, z1, x2, y2, z2, frequency) {
    const dx = x2 - x1;
    const dy = y2 - y1;
    const dz = z2 - z1;
    const r = Math.sqrt(dx * dx + dy * dy + dz * dz);
    
    if (r < 1e-6) return { real: 0, imag: 0 };
    
    const k = 2 * Math.PI * frequency / this.soundSpeed;
    const phase = k * r;
    const amplitude = 1 / (4 * Math.PI * r);
    
    return {
      real: amplitude * Math.cos(phase),
      imag: amplitude * Math.sin(phase)
    };
  }

  _computeTransferMatrix(frequency) {
    const M = this.numElements;
    const N = this.gridPoints.length;
    
    const Greal = new Float64Array(M * N);
    const Gimag = new Float64Array(M * N);
    
    for (let n = 0; n < N; n++) {
      const gp = this.gridPoints[n];
      for (let m = 0; m < M; m++) {
        const mp = this.arrayPositions[m];
        const g = this._greenFunction(gp.x, gp.y, gp.z, mp.x, mp.y, mp.z, frequency);
        const idx = m * N + n;
        Greal[idx] = g.real;
        Gimag[idx] = g.imag;
      }
    }
    
    return { Greal, Gimag, M, N };
  }

  _invertRegularized(Greal, Gimag, M, N, lambda) {
    const GHGreal = new Float64Array(N * N);
    const GHGimag = new Float64Array(N * N);
    
    for (let i = 0; i < N; i++) {
      for (let j = 0; j < N; j++) {
        let sumReal = 0;
        let sumImag = 0;
        for (let m = 0; m < M; m++) {
          const idxMi = m * N + i;
          const idxMj = m * N + j;
          const gr1 = Greal[idxMi];
          const gi1 = Gimag[idxMi];
          const gr2 = Greal[idxMj];
          const gi2 = Gimag[idxMj];
          sumReal += gr1 * gr2 + gi1 * gi2;
          sumImag += gr1 * gi2 - gi1 * gr2;
        }
        const idx = i * N + j;
        GHGreal[idx] = sumReal;
        GHGimag[idx] = sumImag;
      }
    }
    
    for (let i = 0; i < N; i++) {
      const idx = i * N + i;
      GHGreal[idx] += lambda * lambda;
    }
    
    const invGHG = this._invertComplexMatrix(GHGreal, GHGimag, N);
    return invGHG;
  }

  _invertComplexMatrix(real, imag, n) {
    const Areal = new Float64Array(n * n);
    const Aimag = new Float64Array(n * n);
    for (let i = 0; i < n * n; i++) {
      Areal[i] = real[i];
      Aimag[i] = imag[i];
    }
    
    const invReal = new Float64Array(n * n);
    const invImag = new Float64Array(n * n);
    const augReal = new Float64Array(n * n * 2);
    const augImag = new Float64Array(n * n * 2);
    
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        augReal[i * n * 2 + j] = Areal[i * n + j];
        augImag[i * n * 2 + j] = Aimag[i * n + j];
      }
      for (let j = n; j < n * 2; j++) {
        augReal[i * n * 2 + j] = (j - n === i) ? 1 : 0;
        augImag[i * n * 2 + j] = 0;
      }
    }
    
    for (let col = 0; col < n; col++) {
      let pivotIdx = col;
      let maxMagSq = 0;
      for (let row = col; row < n; row++) {
        const idx = row * n * 2 + col;
        const magSq = augReal[idx] * augReal[idx] + augImag[idx] * augImag[idx];
        if (magSq > maxMagSq) {
          maxMagSq = magSq;
          pivotIdx = row;
        }
      }
      
      if (maxMagSq < 1e-20) {
        for (let i = 0; i < n * n; i++) {
          invReal[i] = 0;
          invImag[i] = 0;
        }
        return { invReal, invImag, n };
      }
      
      if (pivotIdx !== col) {
        for (let j = 0; j < n * 2; j++) {
          const idxCol = col * n * 2 + j;
          const idxPivot = pivotIdx * n * 2 + j;
          const tempR = augReal[idxCol];
          const tempI = augImag[idxCol];
          augReal[idxCol] = augReal[idxPivot];
          augImag[idxCol] = augImag[idxPivot];
          augReal[idxPivot] = tempR;
          augImag[idxPivot] = tempI;
        }
      }
      
      const pivotCol = col * n * 2 + col;
      const pivotReal = augReal[pivotCol];
      const pivotImag = augImag[pivotCol];
      const magSq = pivotReal * pivotReal + pivotImag * pivotImag;
      const invMagSq = 1 / magSq;
      
      for (let j = col; j < n * 2; j++) {
        const idx = col * n * 2 + j;
        const real = augReal[idx];
        const imag = augImag[idx];
        augReal[idx] = (real * pivotReal + imag * pivotImag) * invMagSq;
        augImag[idx] = (imag * pivotReal - real * pivotImag) * invMagSq;
      }
      
      for (let row = 0; row < n; row++) {
        if (row === col) continue;
        
        const factorIdx = row * n * 2 + col;
        const factorReal = augReal[factorIdx];
        const factorImag = augImag[factorIdx];
        
        for (let j = col; j < n * 2; j++) {
          const idxRow = row * n * 2 + j;
          const idxCol = col * n * 2 + j;
          const cr = augReal[idxRow];
          const ci = augImag[idxRow];
          const pr = augReal[idxCol];
          const pi = augImag[idxCol];
          augReal[idxRow] = cr - (factorReal * pr - factorImag * pi);
          augImag[idxRow] = ci - (factorReal * pi + factorImag * pr);
        }
      }
    }
    
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        invReal[i * n + j] = augReal[i * n * 2 + n + j];
        invImag[i * n + j] = augImag[i * n * 2 + n + j];
      }
    }
    
    return { invReal, invImag, n };
  }

  reconstruct(timeSignals, frequencyRange = null) {
    this._computeSpectra(timeSignals);
    
    const minFreq = frequencyRange ? frequencyRange.min : 1000;
    const maxFreq = frequencyRange ? frequencyRange.max : 4000;
    const freqStart = Math.max(1, Math.floor(minFreq / this.freqStep));
    const freqEnd = Math.min(this.halfSize, Math.ceil(maxFreq / this.freqStep));
    
    const N = this.gridPoints.length;
    const pressureAmplitude = new Float64Array(N);
    const pressurePhase = new Float64Array(N);
    
    let numFreqBins = 0;
    
    for (let f = freqStart; f <= freqEnd; f++) {
      const frequency = f * this.freqStep;
      
      const { Greal, Gimag, M } = this._computeTransferMatrix(frequency);
      const { invReal, invImag, n } = this._invertRegularized(Greal, Gimag, M, N, this.regularizationFactor);
      
      const pReal = new Float64Array(N);
      const pImag = new Float64Array(N);
      
      for (let i = 0; i < N; i++) {
        let sumReal = 0;
        let sumImag = 0;
        for (let m = 0; m < M; m++) {
          const idxGM = m * N + i;
          const gr = Greal[idxGM];
          const gi = Gimag[idxGM];
          const pr = this._spectraReal[m][f];
          const pi = this._spectraImag[m][f];
          sumReal += gr * pr + gi * pi;
          sumImag += gr * pi - gi * pr;
        }
        
        let invSumReal = 0;
        let invSumImag = 0;
        for (let j = 0; j < N; j++) {
          const idx = i * N + j;
          const ir = invReal[idx];
          const ii = invImag[idx];
          const sr = (j === i) ? sumReal : 0;
          const si = (j === i) ? sumImag : 0;
          invSumReal += ir * sr - ii * si;
          invSumImag += ir * si + ii * sr;
        }
        
        pReal[i] = invSumReal;
        pImag[i] = invSumImag;
      }
      
      for (let i = 0; i < N; i++) {
        const amp = Math.sqrt(pReal[i] * pReal[i] + pImag[i] * pImag[i]);
        pressureAmplitude[i] += amp;
      }
      
      numFreqBins++;
    }
    
    if (numFreqBins > 0) {
      for (let i = 0; i < N; i++) {
        pressureAmplitude[i] /= numFreqBins;
      }
    }
    
    let maxAmp = 0;
    for (let i = 0; i < N; i++) {
      maxAmp = Math.max(maxAmp, pressureAmplitude[i]);
    }
    
    if (maxAmp > 0) {
      for (let i = 0; i < N; i++) {
        pressureAmplitude[i] /= maxAmp;
      }
    }
    
    return {
      gridPoints: this.gridPoints,
      gridDimensions: this.gridDimensions,
      pressureAmplitude,
      pressurePhase,
      frequencyRange: { min: minFreq, max: maxFreq }
    };
  }

  _precomputeDistances() {
    const N = this.gridPoints.length;
    const M = this.numElements;
    this._distances = new Float64Array(N * M);
    this._dx = new Float64Array(N * M);
    this._dy = new Float64Array(N * M);
    this._dz = new Float64Array(N * M);
    
    for (let i = 0; i < N; i++) {
      const gp = this.gridPoints[i];
      for (let m = 0; m < M; m++) {
        const mp = this.arrayPositions[m];
        const dx = gp.x - mp.x;
        const dy = gp.y - mp.y;
        const dz = gp.z - mp.z;
        const r = Math.sqrt(dx * dx + dy * dy + dz * dz);
        const idx = i * M + m;
        this._distances[idx] = r < 1e-6 ? 1e6 : r;
        this._dx[idx] = dx;
        this._dy[idx] = dy;
        this._dz[idx] = dz;
      }
    }
  }

  reconstructFast(timeSignals, frequencyRange = null) {
    this._computeSpectra(timeSignals);
    
    if (!this._distances) {
      this._precomputeDistances();
    }
    
    const minFreq = frequencyRange ? frequencyRange.min : 2000;
    const maxFreq = frequencyRange ? frequencyRange.max : 4000;
    const freqStart = Math.max(1, Math.floor(minFreq / this.freqStep));
    const freqEnd = Math.min(this.halfSize, Math.ceil(maxFreq / this.freqStep));
    
    const freqStep = Math.max(1, Math.floor((freqEnd - freqStart) / 10));
    
    const N = this.gridPoints.length;
    const M = this.numElements;
    const pressureAmplitude = new Float64Array(N);
    
    let numFreqBins = 0;
    const distances = this._distances;
    
    for (let f = freqStart; f <= freqEnd; f += freqStep) {
      const frequency = f * this.freqStep;
      const k = 2 * Math.PI * frequency / this.soundSpeed;
      
      const spectraR = new Float64Array(M);
      const spectraI = new Float64Array(M);
      for (let m = 0; m < M; m++) {
        spectraR[m] = this._spectraReal[m][f];
        spectraI[m] = this._spectraImag[m][f];
      }
      
      for (let i = 0; i < N; i++) {
        let sumReal = 0;
        let sumImag = 0;
        const baseIdx = i * M;
        
        let m = 0;
        for (; m + 3 < M; m += 4) {
          const r0 = distances[baseIdx + m];
          const r1 = distances[baseIdx + m + 1];
          const r2 = distances[baseIdx + m + 2];
          const r3 = distances[baseIdx + m + 3];
          
          const phase0 = -k * r0;
          const phase1 = -k * r1;
          const phase2 = -k * r2;
          const phase3 = -k * r3;
          
          const cR0 = Math.cos(phase0);
          const cI0 = Math.sin(phase0);
          const cR1 = Math.cos(phase1);
          const cI1 = Math.sin(phase1);
          const cR2 = Math.cos(phase2);
          const cI2 = Math.sin(phase2);
          const cR3 = Math.cos(phase3);
          const cI3 = Math.sin(phase3);
          
          const pR0 = spectraR[m], pI0 = spectraI[m];
          const pR1 = spectraR[m + 1], pI1 = spectraI[m + 1];
          const pR2 = spectraR[m + 2], pI2 = spectraI[m + 2];
          const pR3 = spectraR[m + 3], pI3 = spectraI[m + 3];
          
          sumReal += (pR0 * cR0 + pI0 * cI0) / r0;
          sumImag += (pI0 * cR0 - pR0 * cI0) / r0;
          sumReal += (pR1 * cR1 + pI1 * cI1) / r1;
          sumImag += (pI1 * cR1 - pR1 * cI1) / r1;
          sumReal += (pR2 * cR2 + pI2 * cI2) / r2;
          sumImag += (pI2 * cR2 - pR2 * cI2) / r2;
          sumReal += (pR3 * cR3 + pI3 * cI3) / r3;
          sumImag += (pI3 * cR3 - pR3 * cI3) / r3;
        }
        
        for (; m < M; m++) {
          const r = distances[baseIdx + m];
          const phase = -k * r;
          const cR = Math.cos(phase);
          const cI = Math.sin(phase);
          const pR = spectraR[m], pI = spectraI[m];
          
          sumReal += (pR * cR + pI * cI) / r;
          sumImag += (pI * cR - pR * cI) / r;
        }
        
        pressureAmplitude[i] += Math.sqrt(sumReal * sumReal + sumImag * sumImag);
      }
      
      numFreqBins++;
    }
    
    if (numFreqBins > 0) {
      for (let i = 0; i < N; i++) {
        pressureAmplitude[i] /= numFreqBins;
      }
    }
    
    let maxAmp = 0;
    for (let i = 0; i < N; i++) {
      maxAmp = Math.max(maxAmp, pressureAmplitude[i]);
    }
    
    if (maxAmp > 0) {
      for (let i = 0; i < N; i++) {
        pressureAmplitude[i] /= maxAmp;
      }
    }
    
    return {
      gridPoints: this.gridPoints,
      gridDimensions: this.gridDimensions,
      pressureAmplitude,
      frequencyRange: { min: minFreq, max: maxFreq }
    };
  }

  setReconstructionGrid(grid) {
    this.reconstructionGrid = { ...this.reconstructionGrid, ...grid };
    this._precomputeGridPoints();
  }
}

module.exports = { NearfieldAcousticHolography };
