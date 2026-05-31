class Complex {
  constructor(real = 0, imag = 0) {
    this.real = real;
    this.imag = imag;
  }

  add(c) {
    return new Complex(this.real + c.real, this.imag + c.imag);
  }

  sub(c) {
    return new Complex(this.real - c.real, this.imag - c.imag);
  }

  mul(c) {
    return new Complex(
      this.real * c.real - this.imag * c.imag,
      this.real * c.imag + this.imag * c.real
    );
  }

  scale(s) {
    return new Complex(this.real * s, this.imag * s);
  }

  conj() {
    return new Complex(this.real, -this.imag);
  }

  magnitude() {
    return Math.sqrt(this.real * this.real + this.imag * this.imag);
  }

  magnitudeSq() {
    return this.real * this.real + this.imag * this.imag;
  }

  phase() {
    return Math.atan2(this.imag, this.real);
  }
}

class FFT {
  constructor(size) {
    this.size = size;
    this._table = this._precomputeTwiddle(size);
  }

  _precomputeTwiddle(size) {
    const table = [];
    for (let i = 0; i <= size; i++) {
      const angle = (-2 * Math.PI * i) / size;
      table.push(new Complex(Math.cos(angle), Math.sin(angle)));
    }
    return table;
  }

  transform(input, inPlace = false) {
    const n = this.size;
    const output = inPlace ? input : input.slice();
    
    let bits = 0;
    for (let i = 1; i < n; i <<= 1) bits++;
    
    for (let i = 0; i < n; i++) {
      let j = 0;
      for (let k = 0; k < bits; k++) {
        j = (j << 1) | ((i >> k) & 1);
      }
      if (j > i) {
        const temp = output[i];
        output[i] = output[j];
        output[j] = temp;
      }
    }

    for (let size = 2; size <= n; size <<= 1) {
      const half = size >> 1;
      const step = n / size;
      for (let i = 0; i < n; i += size) {
        let k = 0;
        for (let j = 0; j < half; j++) {
          const t = output[i + j + half].mul(this._table[k]);
          output[i + j + half] = output[i + j].sub(t);
          output[i + j] = output[i + j].add(t);
          k += step;
        }
      }
    }

    return output;
  }

  realTransform(input) {
    const n = this.size;
    const complexInput = new Array(n);
    for (let i = 0; i < n; i++) {
      complexInput[i] = new Complex(input[i], 0);
    }
    return this.transform(complexInput);
  }

  inverseTransform(input, inPlace = false) {
    const n = this.size;
    const conjInput = new Array(n);
    for (let i = 0; i < n; i++) {
      conjInput[i] = input[i].conj();
    }
    const output = this.transform(conjInput, inPlace);
    const invN = 1 / n;
    for (let i = 0; i < n; i++) {
      output[i] = output[i].conj().scale(invN);
    }
    return output;
  }
}

class ComplexMatrix {
  constructor(rows, cols) {
    this.rows = rows;
    this.cols = cols;
    this.data = new Array(rows);
    for (let i = 0; i < rows; i++) {
      this.data[i] = new Array(cols);
      for (let j = 0; j < cols; j++) {
        this.data[i][j] = new Complex(0, 0);
      }
    }
  }

  static fromArray(arr) {
    const rows = arr.length;
    const cols = arr[0].length;
    const mat = new ComplexMatrix(rows, cols);
    for (let i = 0; i < rows; i++) {
      for (let j = 0; j < cols; j++) {
        mat.data[i][j] = arr[i][j] instanceof Complex ? arr[i][j] : new Complex(arr[i][j], 0);
      }
    }
    return mat;
  }

  get(i, j) {
    return this.data[i][j];
  }

  set(i, j, val) {
    this.data[i][j] = val;
  }

  add(mat) {
    const result = new ComplexMatrix(this.rows, this.cols);
    for (let i = 0; i < this.rows; i++) {
      for (let j = 0; j < this.cols; j++) {
        result.data[i][j] = this.data[i][j].add(mat.data[i][j]);
      }
    }
    return result;
  }

  mul(mat) {
    const result = new ComplexMatrix(this.rows, mat.cols);
    for (let i = 0; i < this.rows; i++) {
      for (let j = 0; j < mat.cols; j++) {
        let sum = new Complex(0, 0);
        for (let k = 0; k < this.cols; k++) {
          sum = sum.add(this.data[i][k].mul(mat.data[k][j]));
        }
        result.data[i][j] = sum;
      }
    }
    return result;
  }

  scale(s) {
    const result = new ComplexMatrix(this.rows, this.cols);
    for (let i = 0; i < this.rows; i++) {
      for (let j = 0; j < this.cols; j++) {
        if (s instanceof Complex) {
          result.data[i][j] = this.data[i][j].mul(s);
        } else {
          result.data[i][j] = this.data[i][j].scale(s);
        }
      }
    }
    return result;
  }

  hermitian() {
    const result = new ComplexMatrix(this.cols, this.rows);
    for (let i = 0; i < this.rows; i++) {
      for (let j = 0; j < this.cols; j++) {
        result.data[j][i] = this.data[i][j].conj();
      }
    }
    return result;
  }

  clone() {
    const result = new ComplexMatrix(this.rows, this.cols);
    for (let i = 0; i < this.rows; i++) {
      for (let j = 0; j < this.cols; j++) {
        result.data[i][j] = new Complex(this.data[i][j].real, this.data[i][j].imag);
      }
    }
    return result;
  }
}

function solveComplexLinearSystem(A, b) {
  const n = A.rows;
  const mat = A.clone();
  const vec = new Array(n);
  for (let i = 0; i < n; i++) {
    vec[i] = new Complex(b[i].real, b[i].imag);
  }

  for (let col = 0; col < n; col++) {
    let maxRow = col;
    let maxMag = mat.data[col][col].magnitude();
    for (let row = col + 1; row < n; row++) {
      const mag = mat.data[row][col].magnitude();
      if (mag > maxMag) {
        maxMag = mag;
        maxRow = row;
      }
    }

    if (maxRow !== col) {
      [mat.data[col], mat.data[maxRow]] = [mat.data[maxRow], mat.data[col]];
      [vec[col], vec[maxRow]] = [vec[maxRow], vec[col]];
    }

    const pivot = mat.data[col][col];
    const pivotMagSq = pivot.magnitudeSq();
    if (pivotMagSq < 1e-10) {
      return null;
    }

    for (let row = col + 1; row < n; row++) {
      const factor = mat.data[row][col].mul(pivot.conj()).scale(1 / pivotMagSq);
      for (let k = col; k < n; k++) {
        mat.data[row][k] = mat.data[row][k].sub(factor.mul(mat.data[col][k]));
      }
      vec[row] = vec[row].sub(factor.mul(vec[col]));
    }
  }

  const x = new Array(n);
  for (let row = n - 1; row >= 0; row--) {
    let sum = new Complex(0, 0);
    for (let k = row + 1; k < n; k++) {
      sum = sum.add(mat.data[row][k].mul(x[k]));
    }
    const rhs = vec[row].sub(sum);
    const pivot = mat.data[row][row];
    x[row] = rhs.mul(pivot.conj()).scale(1 / pivot.magnitudeSq());
  }

  return x;
}

function invertComplexMatrix(A) {
  const n = A.rows;
  const mat = A.clone();
  const inv = new ComplexMatrix(n, n);
  
  for (let i = 0; i < n; i++) {
    inv.data[i][i] = new Complex(1, 0);
  }

  for (let col = 0; col < n; col++) {
    let maxRow = col;
    let maxMag = mat.data[col][col].magnitude();
    for (let row = col + 1; row < n; row++) {
      const mag = mat.data[row][col].magnitude();
      if (mag > maxMag) {
        maxMag = mag;
        maxRow = row;
      }
    }

    if (maxRow !== col) {
      [mat.data[col], mat.data[maxRow]] = [mat.data[maxRow], mat.data[col]];
      [inv.data[col], inv.data[maxRow]] = [inv.data[maxRow], inv.data[col]];
    }

    const pivot = mat.data[col][col];
    const pivotMagSq = pivot.magnitudeSq();
    if (pivotMagSq < 1e-10) {
      return null;
    }

    const invPivot = pivot.conj().scale(1 / pivotMagSq);
    
    for (let k = 0; k < n; k++) {
      mat.data[col][k] = mat.data[col][k].mul(invPivot);
      inv.data[col][k] = inv.data[col][k].mul(invPivot);
    }

    for (let row = 0; row < n; row++) {
      if (row !== col) {
        const factor = mat.data[row][col];
        for (let k = 0; k < n; k++) {
          mat.data[row][k] = mat.data[row][k].sub(factor.mul(mat.data[col][k]));
          inv.data[row][k] = inv.data[row][k].sub(factor.mul(inv.data[col][k]));
        }
      }
    }
  }

  return inv;
}

class Beamforming {
  constructor(arrayPositions, options = {}) {
    this.arrayPositions = arrayPositions;
    this.numElements = arrayPositions.length;
    this.soundSpeed = options.soundSpeed || 343;
    this.fftSize = options.fftSize || 1024;
    this.sampleRate = options.sampleRate || 48000;
    this.diagonalLoading = options.diagonalLoading || null;
    this.autoDiagonalLoadingFactor = options.autoDiagonalLoadingFactor || 1e-3;
    this.minFreq = options.minFreq || 2000;
    this.maxFreq = options.maxFreq || 5000;
    this.fft = new FFT(this.fftSize);
    this.halfSize = this.fftSize / 2;
    this.freqStep = this.sampleRate / this.fftSize;
    
    this._precomputeFFTInputs();
    this._precomputeSteeringCache();
    this._computeFreqRange();
    this._steeringCache = null;
    this._lastTrace = 0;
  }

  _computeFreqRange() {
    this._freqStart = Math.max(1, Math.floor(this.minFreq / this.freqStep));
    this._freqEnd = Math.min(this.halfSize, Math.ceil(this.maxFreq / this.freqStep));
    this._numFreqBins = this._freqEnd - this._freqStart + 1;
  }

  _precomputeFFTInputs() {
    this._fftInputReal = new Float64Array(this.fftSize);
    this._fftInputImag = new Float64Array(this.fftSize);
    this._spectraReal = new Array(this.numElements);
    this._spectraImag = new Array(this.numElements);
    for (let m = 0; m < this.numElements; m++) {
      this._spectraReal[m] = new Float64Array(this.halfSize + 1);
      this._spectraImag[m] = new Float64Array(this.halfSize + 1);
    }
  }

  _precomputeSteeringCache() {
    this._posX = new Float64Array(this.numElements);
    this._posY = new Float64Array(this.numElements);
    this._posZ = new Float64Array(this.numElements);
    for (let i = 0; i < this.numElements; i++) {
      this._posX[i] = this.arrayPositions[i].x;
      this._posY[i] = this.arrayPositions[i].y;
      this._posZ[i] = this.arrayPositions[i].z;
    }
  }

  _precomputeSteeringVectors(scanAngles) {
    const numAngles = scanAngles.length;
    const M = this.numElements;
    const invC = 2 * Math.PI / this.soundSpeed;
    const freqStart = this._freqStart;
    const freqEnd = this._freqEnd;
    const numFreqBins = this._numFreqBins;
    const freqStep = this.freqStep;

    const cacheKey = `${numAngles}_${freqStart}_${freqEnd}`;
    if (this._steeringCache && this._steeringCache.key === cacheKey) {
      return this._steeringCache;
    }

    const svCache = new Float64Array(numAngles * numFreqBins * M * 2);

    for (let a = 0; a < numAngles; a++) {
      const { azimuth, elevation } = scanAngles[a];
      const cosEl = Math.cos(elevation);
      const dirX = cosEl * Math.cos(azimuth);
      const dirY = cosEl * Math.sin(azimuth);
      const dirZ = Math.sin(elevation);

      for (let f = 0; f < numFreqBins; f++) {
        const freq = (freqStart + f) * freqStep;
        const k = freq * invC;
        const baseIdx = (a * numFreqBins + f) * M * 2;

        for (let m = 0; m < M; m++) {
          const phase = k * (this._posX[m] * dirX + this._posY[m] * dirY + this._posZ[m] * dirZ);
          svCache[baseIdx + m * 2] = Math.cos(phase);
          svCache[baseIdx + m * 2 + 1] = Math.sin(phase);
        }
      }
    }

    this._steeringCache = {
      key: cacheKey,
      data: svCache,
      numAngles,
      numFreqBins,
      M
    };

    return this._steeringCache;
  }

  computeSpectraFast(timeSignals) {
    const n = this.fftSize;
    const halfSize = this.halfSize;
    const bits = Math.log2(n);
    
    for (let m = 0; m < this.numElements; m++) {
      const signal = timeSignals[m];
      const real = this._fftInputReal;
      const imag = this._fftInputImag;
      
      for (let i = 0; i < n; i++) {
        real[i] = signal[i];
        imag[i] = 0;
      }
      
      for (let i = 0; i < n; i++) {
        let j = 0;
        for (let k = 0; k < bits; k++) {
          j = (j << 1) | ((i >> k) & 1);
        }
        if (j > i) {
          [real[i], real[j]] = [real[j], real[i]];
          [imag[i], imag[j]] = [imag[j], imag[i]];
        }
      }

      for (let size = 2; size <= n; size <<= 1) {
        const half = size >> 1;
        const step = n / size;
        for (let i = 0; i < n; i += size) {
          let k = 0;
          for (let j = 0; j < half; j++) {
            const angle = (-2 * Math.PI * k) / n;
            const cos = Math.cos(angle);
            const sin = Math.sin(angle);
            
            const tr = real[i + j + half] * cos - imag[i + j + half] * sin;
            const ti = real[i + j + half] * sin + imag[i + j + half] * cos;
            
            real[i + j + half] = real[i + j] - tr;
            imag[i + j + half] = imag[i + j] - ti;
            real[i + j] += tr;
            imag[i + j] += ti;
            k += step;
          }
        }
      }

      const specReal = this._spectraReal[m];
      const specImag = this._spectraImag[m];
      for (let f = 0; f <= halfSize; f++) {
        specReal[f] = real[f];
        specImag[f] = imag[f];
      }
    }
  }

  computeSteeringVectorFast(azimuth, elevation, k, svReal, svImag) {
    const cosEl = Math.cos(elevation);
    const dirX = cosEl * Math.cos(azimuth);
    const dirY = cosEl * Math.sin(azimuth);
    const dirZ = Math.sin(elevation);
    const posX = this._posX;
    const posY = this._posY;
    const posZ = this._posZ;
    
    for (let i = 0; i < this.numElements; i++) {
      const phase = k * (posX[i] * dirX + posY[i] * dirY + posZ[i] * dirZ);
      svReal[i] = Math.cos(phase);
      svImag[i] = Math.sin(phase);
    }
  }

  computeCovarianceMatrixFast() {
    const M = this.numElements;
    const freqStart = this._freqStart;
    const freqEnd = this._freqEnd;
    const numFreqBins = this._numFreqBins;
    const Rreal = new Float64Array(M * M);
    const Rimag = new Float64Array(M * M);
    const invN = 1 / numFreqBins;
    const specReal = this._spectraReal;
    const specImag = this._spectraImag;

    for (let f = freqStart; f <= freqEnd; f++) {
      for (let i = 0; i < M; i++) {
        const xi = specReal[i][f];
        const yi = specImag[i][f];
        const baseI = i * M;
        for (let j = 0; j < M; j++) {
          const xj = specReal[j][f];
          const yj = specImag[j][f];
          const idx = baseI + j;
          Rreal[idx] += (xi * xj + yi * yj) * invN;
          Rimag[idx] += (yi * xj - xi * yj) * invN;
        }
      }
    }

    let trace = 0;
    for (let i = 0; i < M; i++) {
      trace += Rreal[i * M + i];
    }
    const avgDiag = trace / M;
    this._lastTrace = trace;

    let loading;
    if (this.diagonalLoading !== null && this.diagonalLoading !== undefined) {
      loading = this.diagonalLoading;
    } else {
      loading = Math.max(this.autoDiagonalLoadingFactor * avgDiag, 1e-6);
    }

    for (let i = 0; i < M; i++) {
      Rreal[i * M + i] += loading;
    }

    return { Rreal, Rimag, M, loading, avgDiag };
  }

  invertComplexMatrixFast(Rreal, Rimag, M) {
    const Areal = new Float64Array(M * M);
    const Aimag = new Float64Array(M * M);
    const invReal = new Float64Array(M * M);
    const invImag = new Float64Array(M * M);
    
    for (let i = 0; i < M * M; i++) {
      Areal[i] = Rreal[i];
      Aimag[i] = Rimag[i];
    }
    
    for (let i = 0; i < M; i++) {
      invReal[i * M + i] = 1;
      invImag[i * M + i] = 0;
    }

    for (let col = 0; col < M; col++) {
      let maxRow = col;
      let maxMagSq = Areal[col * M + col] * Areal[col * M + col] + Aimag[col * M + col] * Aimag[col * M + col];
      
      for (let row = col + 1; row < M; row++) {
        const idx = row * M + col;
        const magSq = Areal[idx] * Areal[idx] + Aimag[idx] * Aimag[idx];
        if (magSq > maxMagSq) {
          maxMagSq = magSq;
          maxRow = row;
        }
      }

      if (maxRow !== col) {
        for (let k = 0; k < M; k++) {
          const idx1 = col * M + k;
          const idx2 = maxRow * M + k;
          [Areal[idx1], Areal[idx2]] = [Areal[idx2], Areal[idx1]];
          [Aimag[idx1], Aimag[idx2]] = [Aimag[idx2], Aimag[idx1]];
          [invReal[idx1], invReal[idx2]] = [invReal[idx2], invReal[idx1]];
          [invImag[idx1], invImag[idx2]] = [invImag[idx2], invImag[idx1]];
        }
      }

      const pivotReal = Areal[col * M + col];
      const pivotImag = Aimag[col * M + col];
      const pivotMagSq = pivotReal * pivotReal + pivotImag * pivotImag;
      
      if (pivotMagSq < 1e-12) return null;

      const invPivotReal = pivotReal / pivotMagSq;
      const invPivotImag = -pivotImag / pivotMagSq;

      for (let k = 0; k < M; k++) {
        const idx = col * M + k;
        const ar = Areal[idx];
        const ai = Aimag[idx];
        Areal[idx] = ar * invPivotReal - ai * invPivotImag;
        Aimag[idx] = ar * invPivotImag + ai * invPivotReal;
        
        const ir = invReal[idx];
        const ii = invImag[idx];
        invReal[idx] = ir * invPivotReal - ii * invPivotImag;
        invImag[idx] = ir * invPivotImag + ii * invPivotReal;
      }

      for (let row = 0; row < M; row++) {
        if (row !== col) {
          const factorReal = Areal[row * M + col];
          const factorImag = Aimag[row * M + col];
          
          for (let k = 0; k < M; k++) {
            const idxRow = row * M + k;
            const idxCol = col * M + k;
            
            const ar = Areal[idxRow];
            const ai = Aimag[idxRow];
            const br = Areal[idxCol];
            const bi = Aimag[idxCol];
            Areal[idxRow] = ar - (factorReal * br - factorImag * bi);
            Aimag[idxRow] = ai - (factorReal * bi + factorImag * br);
            
            const ir = invReal[idxRow];
            const ii = invImag[idxRow];
            const cr = invReal[idxCol];
            const ci = invImag[idxCol];
            invReal[idxRow] = ir - (factorReal * cr - factorImag * ci);
            invImag[idxRow] = ii - (factorReal * ci + factorImag * cr);
          }
        }
      }
    }

    return { invReal, invImag, M };
  }

  das(timeSignals, scanAngles) {
    this.computeSpectraFast(timeSignals);
    return this._dasInternal(scanAngles);
  }

  _dasInternal(scanAngles) {
    const cache = this._precomputeSteeringVectors(scanAngles);
    const { data: svCache, numAngles, numFreqBins, M } = cache;
    const freqStart = this._freqStart;
    const powerMap = new Map();

    const specReal = this._spectraReal;
    const specImag = this._spectraImag;
    const invNumFreq = 1 / numFreqBins;

    for (let a = 0; a < numAngles; a++) {
      const { azimuth, elevation } = scanAngles[a];
      let totalPower = 0;
      const angleBase = a * numFreqBins * M * 2;

      for (let f = 0; f < numFreqBins; f++) {
        const freqBin = freqStart + f;
        const freqBase = angleBase + f * M * 2;
        
        let sumReal = 0;
        let sumImag = 0;
        
        let m = 0;
        for (; m < M - 3; m += 4) {
          const sR0 = specReal[m][freqBin];
          const sI0 = specImag[m][freqBin];
          const vR0 = svCache[freqBase + m * 2];
          const vI0 = svCache[freqBase + m * 2 + 1];
          sumReal += sR0 * vR0 + sI0 * vI0;
          sumImag += sI0 * vR0 - sR0 * vI0;

          const sR1 = specReal[m + 1][freqBin];
          const sI1 = specImag[m + 1][freqBin];
          const vR1 = svCache[freqBase + (m + 1) * 2];
          const vI1 = svCache[freqBase + (m + 1) * 2 + 1];
          sumReal += sR1 * vR1 + sI1 * vI1;
          sumImag += sI1 * vR1 - sR1 * vI1;

          const sR2 = specReal[m + 2][freqBin];
          const sI2 = specImag[m + 2][freqBin];
          const vR2 = svCache[freqBase + (m + 2) * 2];
          const vI2 = svCache[freqBase + (m + 2) * 2 + 1];
          sumReal += sR2 * vR2 + sI2 * vI2;
          sumImag += sI2 * vR2 - sR2 * vI2;

          const sR3 = specReal[m + 3][freqBin];
          const sI3 = specImag[m + 3][freqBin];
          const vR3 = svCache[freqBase + (m + 3) * 2];
          const vI3 = svCache[freqBase + (m + 3) * 2 + 1];
          sumReal += sR3 * vR3 + sI3 * vI3;
          sumImag += sI3 * vR3 - sR3 * vI3;
        }
        for (; m < M; m++) {
          const sR = specReal[m][freqBin];
          const sI = specImag[m][freqBin];
          const vR = svCache[freqBase + m * 2];
          const vI = svCache[freqBase + m * 2 + 1];
          sumReal += sR * vR + sI * vI;
          sumImag += sI * vR - sR * vI;
        }
        
        totalPower += sumReal * sumReal + sumImag * sumImag;
      }
      
      const key = `${azimuth.toFixed(4)},${elevation.toFixed(4)}`;
      powerMap.set(key, totalPower * invNumFreq);
    }

    return powerMap;
  }

  computeSpectra(timeSignals) {
    this.computeSpectraFast(timeSignals);
    const spectra = new Array(this.numElements);
    for (let m = 0; m < this.numElements; m++) {
      spectra[m] = new Array(this.halfSize + 1);
      for (let f = 0; f <= this.halfSize; f++) {
        spectra[m][f] = new Complex(this._spectraReal[m][f], this._spectraImag[m][f]);
      }
    }
    return spectra;
  }

  computeSteeringVector(azimuth, elevation, frequency) {
    const k = 2 * Math.PI * frequency / this.soundSpeed;
    const svReal = new Float64Array(this.numElements);
    const svImag = new Float64Array(this.numElements);
    this.computeSteeringVectorFast(azimuth, elevation, k, svReal, svImag);
    const sv = new Array(this.numElements);
    for (let i = 0; i < this.numElements; i++) {
      sv[i] = new Complex(svReal[i], svImag[i]);
    }
    return sv;
  }

  mvdr(timeSignals, scanAngles) {
    this.computeSpectraFast(timeSignals);
    const { Rreal, Rimag, M } = this.computeCovarianceMatrixFast();
    const invResult = this.invertComplexMatrixFast(Rreal, Rimag, M);
    
    if (!invResult) {
      return this.das(timeSignals, scanAngles);
    }

    const { invReal, invImag } = invResult;
    const cache = this._precomputeSteeringVectors(scanAngles);
    const { data: svCache, numAngles, numFreqBins } = cache;
    const powerMap = new Map();
    const invNumFreq = 1 / numFreqBins;

    const wReal = new Float64Array(M);
    const wImag = new Float64Array(M);

    for (let a = 0; a < numAngles; a++) {
      const { azimuth, elevation } = scanAngles[a];
      let totalPower = 0;
      const angleBase = a * numFreqBins * M * 2;

      for (let f = 0; f < numFreqBins; f++) {
        const freqBase = angleBase + f * M * 2;
        
        let i = 0;
        for (; i < M - 3; i += 4) {
          const idxI0 = i * M;
          const idxI1 = (i + 1) * M;
          const idxI2 = (i + 2) * M;
          const idxI3 = (i + 3) * M;
          
          let wr0 = 0, wi0 = 0, wr1 = 0, wi1 = 0, wr2 = 0, wi2 = 0, wr3 = 0, wi3 = 0;
          
          let j = 0;
          for (; j < M - 3; j += 4) {
            const idx00 = idxI0 + j;
            const idx01 = idxI0 + j + 1;
            const idx02 = idxI0 + j + 2;
            const idx03 = idxI0 + j + 3;
            
            const vr0 = svCache[freqBase + j * 2];
            const vi0 = svCache[freqBase + j * 2 + 1];
            const vr1 = svCache[freqBase + (j + 1) * 2];
            const vi1 = svCache[freqBase + (j + 1) * 2 + 1];
            const vr2 = svCache[freqBase + (j + 2) * 2];
            const vi2 = svCache[freqBase + (j + 2) * 2 + 1];
            const vr3 = svCache[freqBase + (j + 3) * 2];
            const vi3 = svCache[freqBase + (j + 3) * 2 + 1];
            
            const ir00 = invReal[idx00], ii00 = invImag[idx00];
            const ir01 = invReal[idx01], ii01 = invImag[idx01];
            const ir02 = invReal[idx02], ii02 = invImag[idx02];
            const ir03 = invReal[idx03], ii03 = invImag[idx03];
            
            wr0 += ir00 * vr0 - ii00 * vi0 + ir01 * vr1 - ii01 * vi1 + ir02 * vr2 - ii02 * vi2 + ir03 * vr3 - ii03 * vi3;
            wi0 += ir00 * vi0 + ii00 * vr0 + ir01 * vi1 + ii01 * vr1 + ir02 * vi2 + ii02 * vr2 + ir03 * vi3 + ii03 * vr3;
            
            const idx10 = idxI1 + j;
            const idx11 = idxI1 + j + 1;
            const idx12 = idxI1 + j + 2;
            const idx13 = idxI1 + j + 3;
            
            const ir10 = invReal[idx10], ii10 = invImag[idx10];
            const ir11 = invReal[idx11], ii11 = invImag[idx11];
            const ir12 = invReal[idx12], ii12 = invImag[idx12];
            const ir13 = invReal[idx13], ii13 = invImag[idx13];
            
            wr1 += ir10 * vr0 - ii10 * vi0 + ir11 * vr1 - ii11 * vi1 + ir12 * vr2 - ii12 * vi2 + ir13 * vr3 - ii13 * vi3;
            wi1 += ir10 * vi0 + ii10 * vr0 + ir11 * vi1 + ii11 * vr1 + ir12 * vi2 + ii12 * vr2 + ir13 * vi3 + ii13 * vr3;
            
            const idx20 = idxI2 + j;
            const idx21 = idxI2 + j + 1;
            const idx22 = idxI2 + j + 2;
            const idx23 = idxI2 + j + 3;
            
            const ir20 = invReal[idx20], ii20 = invImag[idx20];
            const ir21 = invReal[idx21], ii21 = invImag[idx21];
            const ir22 = invReal[idx22], ii22 = invImag[idx22];
            const ir23 = invReal[idx23], ii23 = invImag[idx23];
            
            wr2 += ir20 * vr0 - ii20 * vi0 + ir21 * vr1 - ii21 * vi1 + ir22 * vr2 - ii22 * vi2 + ir23 * vr3 - ii23 * vi3;
            wi2 += ir20 * vi0 + ii20 * vr0 + ir21 * vi1 + ii21 * vr1 + ir22 * vi2 + ii22 * vr2 + ir23 * vi3 + ii23 * vr3;
            
            const idx30 = idxI3 + j;
            const idx31 = idxI3 + j + 1;
            const idx32 = idxI3 + j + 2;
            const idx33 = idxI3 + j + 3;
            
            const ir30 = invReal[idx30], ii30 = invImag[idx30];
            const ir31 = invReal[idx31], ii31 = invImag[idx31];
            const ir32 = invReal[idx32], ii32 = invImag[idx32];
            const ir33 = invReal[idx33], ii33 = invImag[idx33];
            
            wr3 += ir30 * vr0 - ii30 * vi0 + ir31 * vr1 - ii31 * vi1 + ir32 * vr2 - ii32 * vi2 + ir33 * vr3 - ii33 * vi3;
            wi3 += ir30 * vi0 + ii30 * vr0 + ir31 * vi1 + ii31 * vr1 + ir32 * vi2 + ii32 * vr2 + ir33 * vi3 + ii33 * vr3;
          }
          for (; j < M; j++) {
            const vr = svCache[freqBase + j * 2];
            const vi = svCache[freqBase + j * 2 + 1];
            
            wr0 += invReal[idxI0 + j] * vr - invImag[idxI0 + j] * vi;
            wi0 += invReal[idxI0 + j] * vi + invImag[idxI0 + j] * vr;
            wr1 += invReal[idxI1 + j] * vr - invImag[idxI1 + j] * vi;
            wi1 += invReal[idxI1 + j] * vi + invImag[idxI1 + j] * vr;
            wr2 += invReal[idxI2 + j] * vr - invImag[idxI2 + j] * vi;
            wi2 += invReal[idxI2 + j] * vi + invImag[idxI2 + j] * vr;
            wr3 += invReal[idxI3 + j] * vr - invImag[idxI3 + j] * vi;
            wi3 += invReal[idxI3 + j] * vi + invImag[idxI3 + j] * vr;
          }
          
          wReal[i] = wr0;
          wImag[i] = wi0;
          wReal[i + 1] = wr1;
          wImag[i + 1] = wi1;
          wReal[i + 2] = wr2;
          wImag[i + 2] = wi2;
          wReal[i + 3] = wr3;
          wImag[i + 3] = wi3;
        }
        for (; i < M; i++) {
          const idxI = i * M;
          let wr = 0, wi = 0;
          for (let j = 0; j < M; j++) {
            const idx = idxI + j;
            const vr = svCache[freqBase + j * 2];
            const vi = svCache[freqBase + j * 2 + 1];
            wr += invReal[idx] * vr - invImag[idx] * vi;
            wi += invReal[idx] * vi + invImag[idx] * vr;
          }
          wReal[i] = wr;
          wImag[i] = wi;
        }
        
        let denom = 0;
        i = 0;
        for (; i < M - 3; i += 4) {
          denom += svCache[freqBase + i * 2] * wReal[i] + svCache[freqBase + i * 2 + 1] * wImag[i];
          denom += svCache[freqBase + (i + 1) * 2] * wReal[i + 1] + svCache[freqBase + (i + 1) * 2 + 1] * wImag[i + 1];
          denom += svCache[freqBase + (i + 2) * 2] * wReal[i + 2] + svCache[freqBase + (i + 2) * 2 + 1] * wImag[i + 2];
          denom += svCache[freqBase + (i + 3) * 2] * wReal[i + 3] + svCache[freqBase + (i + 3) * 2 + 1] * wImag[i + 3];
        }
        for (; i < M; i++) {
          denom += svCache[freqBase + i * 2] * wReal[i] + svCache[freqBase + i * 2 + 1] * wImag[i];
        }
        
        if (denom > 1e-10) {
          totalPower += 1 / denom;
        }
      }
      
      const key = `${azimuth.toFixed(4)},${elevation.toFixed(4)}`;
      powerMap.set(key, totalPower * invNumFreq);
    }

    return powerMap;
  }

  computeEigenvaluesFast(Rreal, Rimag, M, numEigenvalues) {
    const Areal = new Float64Array(M * M);
    const Aimag = new Float64Array(M * M);
    const Qreal = new Float64Array(M * M);
    const Qimag = new Float64Array(M * M);
    
    for (let i = 0; i < M * M; i++) {
      Areal[i] = Rreal[i];
      Aimag[i] = Rimag[i];
    }
    
    for (let i = 0; i < M; i++) {
      Qreal[i * M + i] = 1;
      Qimag[i * M + i] = 0;
    }

    const maxIter = 60;
    const tolerance = 1e-10;

    for (let iter = 0; iter < maxIter; iter++) {
      let offDiagSum = 0;
      for (let i = 0; i < M; i++) {
        for (let j = 0; j < M; j++) {
          if (i !== j) {
            const idx = i * M + j;
            offDiagSum += Areal[idx] * Areal[idx] + Aimag[idx] * Aimag[idx];
          }
        }
      }
      
      if (offDiagSum < tolerance) break;

      let maxMagSq = 0;
      let p = 0, q = 1;
      for (let i = 0; i < M; i++) {
        for (let j = i + 1; j < M; j++) {
          const idx = i * M + j;
          const magSq = Areal[idx] * Areal[idx] + Aimag[idx] * Aimag[idx];
          if (magSq > maxMagSq) {
            maxMagSq = magSq;
            p = i;
            q = j;
          }
        }
      }

      const App = Areal[p * M + p];
      const Aqq = Areal[q * M + q];
      const ApqR = Areal[p * M + q];
      const ApqI = Aimag[p * M + q];

      let theta = 0;
      if (Math.abs(App - Aqq) > 1e-12) {
        theta = 0.5 * Math.atan2(2 * ApqR, App - Aqq);
      }
      
      const c = Math.cos(theta);
      const s = Math.sin(theta);

      for (let k = 0; k < M; k++) {
        if (k !== p && k !== q) {
          const pk = p * M + k;
          const qk = q * M + k;
          const kp = k * M + p;
          const kq = k * M + q;
          
          const AkpR = Areal[kp];
          const AkpI = Aimag[kp];
          const AkqR = Areal[kq];
          const AkqI = Aimag[kq];
          
          const newAkpR = c * AkpR + s * AkqR;
          const newAkpI = c * AkpI + s * AkqI;
          const newAkqR = -s * AkpR + c * AkqR;
          const newAkqI = -s * AkpI + c * AkqI;
          
          Areal[pk] = newAkpR; Aimag[pk] = newAkpI;
          Areal[kp] = newAkpR; Aimag[kp] = newAkpI;
          Areal[qk] = newAkqR; Aimag[qk] = newAkqI;
          Areal[kq] = newAkqR; Aimag[kq] = newAkqI;
        }

        const Qkp = k * M + p;
        const Qkq = k * M + q;
        const Qrp = Qreal[Qkp];
        const Qip = Qimag[Qkp];
        const Qrq = Qreal[Qkq];
        const Qiq = Qimag[Qkq];
        
        Qreal[Qkp] = c * Qrp + s * Qrq;
        Qimag[Qkp] = c * Qip + s * Qiq;
        Qreal[Qkq] = -s * Qrp + c * Qrq;
        Qimag[Qkq] = -s * Qip + c * Qiq;
      }

      const newApp = c * c * App + 2 * c * s * ApqR + s * s * Aqq;
      const newAqq = s * s * App - 2 * c * s * ApqR + c * c * Aqq;
      
      Areal[p * M + p] = newApp;
      Areal[q * M + q] = newAqq;
      Areal[p * M + q] = 0; Aimag[p * M + q] = 0;
      Areal[q * M + p] = 0; Aimag[q * M + p] = 0;
    }

    const eigenvalues = new Array(M);
    const eigenvectors = new Array(M);
    
    for (let i = 0; i < M; i++) {
      eigenvalues[i] = Areal[i * M + i];
      eigenvectors[i] = {
        real: new Float64Array(M),
        imag: new Float64Array(M)
      };
      for (let j = 0; j < M; j++) {
        eigenvectors[i].real[j] = Qreal[j * M + i];
        eigenvectors[i].imag[j] = Qimag[j * M + i];
      }
    }

    const sortedIndices = eigenvalues
      .map((val, idx) => ({ val, idx }))
      .sort((a, b) => b.val - a.val)
      .map(item => item.idx);

    return {
      eigenvalues: sortedIndices.map(idx => eigenvalues[idx]),
      eigenvectors: sortedIndices.map(idx => eigenvectors[idx])
    };
  }

  music(timeSignals, scanAngles, numSources = 1) {
    this.computeSpectraFast(timeSignals);
    const { Rreal, Rimag, M } = this.computeCovarianceMatrixFast();

    const eigResult = this.computeEigenvaluesFast(Rreal, Rimag, M, numSources);
    if (!eigResult) {
      return this.das(timeSignals, scanAngles);
    }

    const { eigenvalues, eigenvectors } = eigResult;
    const noiseStart = Math.min(numSources, M - 1);
    const numNoise = M - noiseStart;
    
    const noiseFlatReal = new Float64Array(numNoise * M);
    const noiseFlatImag = new Float64Array(numNoise * M);
    for (let i = 0; i < numNoise; i++) {
      const nr = eigenvectors[noiseStart + i].real;
      const ni = eigenvectors[noiseStart + i].imag;
      const baseI = i * M;
      for (let m = 0; m < M; m++) {
        noiseFlatReal[baseI + m] = nr[m];
        noiseFlatImag[baseI + m] = ni[m];
      }
    }

    const cache = this._precomputeSteeringVectors(scanAngles);
    const { data: svCache, numAngles, numFreqBins } = cache;
    const powerMap = new Map();
    const invNumFreq = 1 / numFreqBins;

    const dasPowerMap = this._dasInternal(scanAngles);

    for (let a = 0; a < numAngles; a++) {
      const { azimuth, elevation } = scanAngles[a];
      let totalPower = 0;
      const angleBase = a * numFreqBins * M * 2;

      for (let f = 0; f < numFreqBins; f++) {
        const freqBase = angleBase + f * M * 2;
        
        let projection = 0;
        for (let n = 0; n < numNoise; n++) {
          const noiseBase = n * M;
          let dotReal = 0;
          let dotImag = 0;
          
          let m = 0;
          for (; m < M - 3; m += 4) {
            const svR0 = svCache[freqBase + m * 2];
            const svI0 = svCache[freqBase + m * 2 + 1];
            const nr0 = noiseFlatReal[noiseBase + m];
            const ni0 = noiseFlatImag[noiseBase + m];
            dotReal += svR0 * nr0 + svI0 * ni0;
            dotImag += svI0 * nr0 - svR0 * ni0;
            
            const svR1 = svCache[freqBase + (m + 1) * 2];
            const svI1 = svCache[freqBase + (m + 1) * 2 + 1];
            const nr1 = noiseFlatReal[noiseBase + m + 1];
            const ni1 = noiseFlatImag[noiseBase + m + 1];
            dotReal += svR1 * nr1 + svI1 * ni1;
            dotImag += svI1 * nr1 - svR1 * ni1;
            
            const svR2 = svCache[freqBase + (m + 2) * 2];
            const svI2 = svCache[freqBase + (m + 2) * 2 + 1];
            const nr2 = noiseFlatReal[noiseBase + m + 2];
            const ni2 = noiseFlatImag[noiseBase + m + 2];
            dotReal += svR2 * nr2 + svI2 * ni2;
            dotImag += svI2 * nr2 - svR2 * ni2;
            
            const svR3 = svCache[freqBase + (m + 3) * 2];
            const svI3 = svCache[freqBase + (m + 3) * 2 + 1];
            const nr3 = noiseFlatReal[noiseBase + m + 3];
            const ni3 = noiseFlatImag[noiseBase + m + 3];
            dotReal += svR3 * nr3 + svI3 * ni3;
            dotImag += svI3 * nr3 - svR3 * ni3;
          }
          for (; m < M; m++) {
            const svR = svCache[freqBase + m * 2];
            const svI = svCache[freqBase + m * 2 + 1];
            const nr = noiseFlatReal[noiseBase + m];
            const ni = noiseFlatImag[noiseBase + m];
            dotReal += svR * nr + svI * ni;
            dotImag += svI * nr - svR * ni;
          }
          projection += dotReal * dotReal + dotImag * dotImag;
        }
        
        if (projection > 1e-10) {
          totalPower += 1 / projection;
        }
      }
      
      const key = `${azimuth.toFixed(4)},${elevation.toFixed(4)}`;
      powerMap.set(key, totalPower * invNumFreq);
    }

    const correctedPowerMap = new Map();
    const processed = new Set();
    
    const sortedEntries = Array.from(powerMap.entries())
      .sort((a, b) => b[1] - a[1]);
    
    for (const [key, musicPower] of sortedEntries) {
      if (processed.has(key)) continue;
      
      const [az, el] = key.split(',').map(Number);
      const dasPower = dasPowerMap.get(key) || 0;
      
      let oppositeAz = az + Math.PI;
      if (oppositeAz >= 2 * Math.PI) oppositeAz -= 2 * Math.PI;
      const oppositeKey = `${oppositeAz.toFixed(4)},${el.toFixed(4)}`;
      const oppositeDasPower = dasPowerMap.get(oppositeKey) || 0;
      const oppositeMusicPower = powerMap.get(oppositeKey) || 0;
      
      let correctedPower = musicPower;
      if (dasPower > 0 && oppositeDasPower > 0 && oppositeMusicPower > 0) {
        const ratio = dasPower / (dasPower + oppositeDasPower + 1e-10);
        correctedPower = musicPower * ratio;
        
        if (processed.has(oppositeKey)) continue;
        
        const oppositeCorrected = oppositeMusicPower * (1 - ratio);
        correctedPowerMap.set(oppositeKey, oppositeCorrected);
        processed.add(oppositeKey);
      }
      
      correctedPowerMap.set(key, correctedPower);
      processed.add(key);
    }

    for (const [key, power] of powerMap) {
      if (!correctedPowerMap.has(key)) {
        correctedPowerMap.set(key, power);
      }
    }

    return correctedPowerMap;
  }

  _evd(matrix) {
    const n = matrix.rows;
    const maxIter = 100;
    const tolerance = 1e-8;

    const A = matrix.clone();
    const Q = new ComplexMatrix(n, n);
    for (let i = 0; i < n; i++) {
      Q.data[i][i] = new Complex(1, 0);
    }

    for (let iter = 0; iter < maxIter; iter++) {
      let offDiagSum = 0;
      for (let i = 0; i < n; i++) {
        for (let j = 0; j < n; j++) {
          if (i !== j) {
            offDiagSum += A.data[i][j].magnitudeSq();
          }
        }
      }

      if (offDiagSum < tolerance) {
        break;
      }

      let maxMag = 0;
      let p = 0, q = 1;
      for (let i = 0; i < n; i++) {
        for (let j = i + 1; j < n; j++) {
          const mag = A.data[i][j].magnitudeSq();
          if (mag > maxMag) {
            maxMag = mag;
            p = i;
            q = j;
          }
        }
      }

      const App = A.data[p][p].real;
      const Aqq = A.data[q][q].real;
      const Apq = A.data[p][q];

      let theta = 0.5 * Math.atan2(2 * Apq.real, App - Aqq);
      if (App !== Aqq) {
        theta = 0.5 * Math.atan2(2 * Apq.real, Aqq - App);
      }

      const c = Math.cos(theta);
      const s = Math.sin(theta);

      for (let k = 0; k < n; k++) {
        if (k !== p && k !== q) {
          const Akp = A.data[k][p];
          const Akq = A.data[k][q];
          const newAkp = new Complex(c * Akp.real + s * Akq.real, c * Akp.imag + s * Akq.imag);
          const newAkq = new Complex(-s * Akp.real + c * Akq.real, -s * Akp.imag + c * Akq.imag);
          A.data[k][p] = newAkp;
          A.data[p][k] = newAkp.conj();
          A.data[k][q] = newAkq;
          A.data[q][k] = newAkq.conj();
        }
      }

      const newApp = c * c * App + 2 * c * s * Apq.real + s * s * Aqq;
      const newAqq = s * s * App - 2 * c * s * Apq.real + c * c * Aqq;
      A.data[p][p] = new Complex(newApp, 0);
      A.data[q][q] = new Complex(newAqq, 0);
      A.data[p][q] = new Complex(0, 0);
      A.data[q][p] = new Complex(0, 0);

      for (let k = 0; k < n; k++) {
        const Qkp = Q.data[k][p];
        const Qkq = Q.data[k][q];
        Q.data[k][p] = new Complex(c * Qkp.real + s * Qkq.real, c * Qkp.imag + s * Qkq.imag);
        Q.data[k][q] = new Complex(-s * Qkp.real + c * Qkq.real, -s * Qkp.imag + c * Qkq.imag);
      }
    }

    const eigenvalues = new Array(n);
    const eigenvectors = new Array(n);
    
    for (let i = 0; i < n; i++) {
      eigenvalues[i] = A.data[i][i];
      eigenvectors[i] = new Array(n);
      for (let j = 0; j < n; j++) {
        eigenvectors[i][j] = Q.data[j][i];
      }
    }

    return { eigenvalues, eigenvectors };
  }

  estimateDistance(timeSignals, azimuth, elevation, frequency) {
    const c = this.soundSpeed;
    const spectra = this.computeSpectra(timeSignals);
    const numFreqBins = spectra[0].length;
    const freqStep = this.sampleRate / this.fftSize;

    let targetBin = Math.round(frequency / freqStep);
    targetBin = Math.max(1, Math.min(numFreqBins - 1, targetBin));

    const sv = this.computeSteeringVector(azimuth, elevation, frequency);
    
    let maxCorr = 0;
    let estimatedDelay = 0;
    
    const refSpectrum = spectra[0];
    
    for (let delayBin = 0; delayBin < this.fftSize / 4; delayBin++) {
      let corr = 0;
      
      for (let m = 0; m < this.numElements; m++) {
        const expectedPhase = (2 * Math.PI * frequency * delayBin) / this.sampleRate;
        const expected = new Complex(Math.cos(expectedPhase), Math.sin(expectedPhase));
        const weighted = spectra[m][targetBin].mul(sv[m].conj());
        const diff = weighted.sub(expected.mul(refSpectrum[targetBin]));
        corr += 1 / (diff.magnitudeSq() + 1e-10);
      }
      
      if (corr > maxCorr) {
        maxCorr = corr;
        estimatedDelay = delayBin / this.sampleRate;
      }
    }

    const distance = estimatedDelay * c;
    
    const r0 = 1;
    const powerRatio = this._measurePowerRatio(spectra, targetBin);
    const distanceFromPower = r0 * Math.sqrt(1 / Math.max(powerRatio, 1e-6));
    
    return {
      delayBased: Math.min(Math.max(distance, 0.1), 100),
      powerBased: Math.min(Math.max(distanceFromPower, 0.1), 100),
      combined: Math.min(Math.max((distance + distanceFromPower) / 2, 0.1), 100)
    };
  }

  _measurePowerRatio(spectra, targetBin) {
    let totalPower = 0;
    for (let m = 0; m < this.numElements; m++) {
      totalPower += spectra[m][targetBin].magnitudeSq();
    }
    const avgPower = totalPower / this.numElements;
    return avgPower / 1e-2;
  }
}

function generateScanAngles(resolution = 5, includeElevation = false) {
  const angles = [];
  const azimuthStep = resolution * Math.PI / 180;
  
  if (includeElevation) {
    const elevationStep = resolution * Math.PI / 180;
    for (let el = -Math.PI / 2; el <= Math.PI / 2; el += elevationStep) {
      for (let az = 0; az < 2 * Math.PI; az += azimuthStep) {
        angles.push({ azimuth: az, elevation: el });
      }
    }
  } else {
    for (let az = 0; az < 2 * Math.PI; az += azimuthStep) {
      angles.push({ azimuth: az, elevation: 0 });
    }
  }
  
  return angles;
}

function angularDistance(az1, el1, az2, el2) {
  let deltaAz = Math.abs(az1 - az2);
  if (deltaAz > Math.PI) {
    deltaAz = 2 * Math.PI - deltaAz;
  }
  const deltaEl = Math.abs(el1 - el2);
  return Math.sqrt(deltaAz * deltaAz + deltaEl * deltaEl);
}

function findPeaks(powerMap, numPeaks = 3, minThreshold = 0.1, scanResolution = 5) {
  const entries = Array.from(powerMap.entries());
  
  let maxPower = 0;
  for (const [, power] of entries) {
    maxPower = Math.max(maxPower, power);
  }
  
  const threshold = maxPower * minThreshold;
  
  const validEntries = entries
    .filter(([, power]) => power >= threshold)
    .sort((a, b) => b[1] - a[1]);
  
  const peaks = [];
  const usedKeys = new Set();
  
  const minAngleSeparation = Math.max(
    scanResolution * Math.PI / 180 * 1.5,
    0.15
  );
  
  const angleBuckets = new Map();
  
  for (const [key, power] of validEntries) {
    if (peaks.length >= numPeaks) break;
    
    const [az, el] = key.split(',').map(Number);
    
    let isFarEnough = true;
    for (const peak of peaks) {
      const dist = angularDistance(az, el, peak.azimuth, peak.elevation);
      if (dist < minAngleSeparation) {
        isFarEnough = false;
        break;
      }
    }
    
    if (isFarEnough) {
      const bucketKey = `${Math.round(az * 10) / 10},${Math.round(el * 10) / 10}`;
      
      if (!angleBuckets.has(bucketKey) || power > angleBuckets.get(bucketKey).power) {
        const nearbyPeaks = [];
        for (const [otherKey, otherPower] of validEntries) {
          if (otherKey === key) continue;
          const [otherAz, otherEl] = otherKey.split(',').map(Number);
          const dist = angularDistance(az, el, otherAz, otherEl);
          if (dist < minAngleSeparation) {
            nearbyPeaks.push({ azimuth: otherAz, elevation: otherEl, power: otherPower });
          }
        }
        
        let weightedAz = az * power;
        let weightedEl = el * power;
        let totalWeight = power;
        
        for (const np of nearbyPeaks) {
          const w = np.power;
          let deltaAz = np.azimuth - az;
          if (deltaAz > Math.PI) deltaAz -= 2 * Math.PI;
          if (deltaAz < -Math.PI) deltaAz += 2 * Math.PI;
          weightedAz += (az + deltaAz) * w;
          weightedEl += np.elevation * w;
          totalWeight += w;
        }
        
        let finalAz = weightedAz / totalWeight;
        const finalEl = weightedEl / totalWeight;
        
        if (finalAz < 0) finalAz += 2 * Math.PI;
        if (finalAz >= 2 * Math.PI) finalAz -= 2 * Math.PI;
        
        peaks.push({
          azimuth: finalAz,
          elevation: finalEl,
          power: power,
          normalizedPower: power / maxPower,
          nearbyCount: nearbyPeaks.length + 1
        });
        angleBuckets.set(bucketKey, peaks[peaks.length - 1]);
        usedKeys.add(key);
      }
    }
  }
  
  return peaks.sort((a, b) => b.power - a.power);
}

module.exports = {
  Complex,
  FFT,
  ComplexMatrix,
  Beamforming,
  generateScanAngles,
  findPeaks,
  angularDistance,
  solveComplexLinearSystem,
  invertComplexMatrix
};
