class KalmanFilter {
  constructor(dimState, dimObs, options = {}) {
    this.dimState = dimState;
    this.dimObs = dimObs;
    
    this.F = options.F || this._createIdentity(dimState);
    this.H = options.H || this._createIdentity(dimObs, dimState);
    this.Q = options.Q || this._createIdentity(dimState, dimState, 0.01);
    this.R = options.R || this._createIdentity(dimObs, dimObs, 0.1);
    
    this.x = options.x || new Float64Array(dimState);
    this.P = options.P || this._createIdentity(dimState, dimState, 1);
    
    this.I = this._createIdentity(dimState);
  }

  _createIdentity(rows, cols = null, value = 1) {
    const c = cols || rows;
    const mat = new Float64Array(rows * c);
    for (let i = 0; i < Math.min(rows, c); i++) {
      mat[i * c + i] = value;
    }
    return mat;
  }

  _matMul(A, B, n, m, p) {
    const C = new Float64Array(n * p);
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < p; j++) {
        let sum = 0;
        for (let k = 0; k < m; k++) {
          sum += A[i * m + k] * B[k * p + j];
        }
        C[i * p + j] = sum;
      }
    }
    return C;
  }

  _matTranspose(A, n, m) {
    const At = new Float64Array(m * n);
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < m; j++) {
        At[j * n + i] = A[i * m + j];
      }
    }
    return At;
  }

  _matAdd(A, B, n, m) {
    const C = new Float64Array(n * m);
    for (let i = 0; i < n * m; i++) {
      C[i] = A[i] + B[i];
    }
    return C;
  }

  _matSub(A, B, n, m) {
    const C = new Float64Array(n * m);
    for (let i = 0; i < n * m; i++) {
      C[i] = A[i] - B[i];
    }
    return C;
  }

  _matVecMul(A, v, n, m) {
    const result = new Float64Array(n);
    for (let i = 0; i < n; i++) {
      let sum = 0;
      for (let j = 0; j < m; j++) {
        sum += A[i * m + j] * v[j];
      }
      result[i] = sum;
    }
    return result;
  }

  _invertSymmetric(A, n) {
    const L = new Float64Array(n * n);
    const D = new Float64Array(n);
    
    for (let i = 0; i < n; i++) {
      for (let j = 0; j <= i; j++) {
        let sum = A[i * n + j];
        for (let k = 0; k < j; k++) {
          sum -= L[i * n + k] * D[k] * L[j * n + k];
        }
        if (i === j) {
          if (sum < 1e-10) sum = 1e-10;
          D[i] = sum;
          L[i * n + i] = 1;
        } else {
          L[i * n + j] = sum / D[j];
        }
      }
    }
    
    const inv = new Float64Array(n * n);
    const y = new Float64Array(n);
    
    for (let b = 0; b < n; b++) {
      for (let i = 0; i < n; i++) {
        let sum = (i === b) ? 1 : 0;
        for (let k = 0; k < i; k++) {
          sum -= L[i * n + k] * y[k];
        }
        y[i] = sum;
      }
      
      for (let i = n - 1; i >= 0; i--) {
        let sum = y[i] / D[i];
        for (let k = i + 1; k < n; k++) {
          sum -= L[k * n + i] * inv[k * n + b];
        }
        inv[i * n + b] = sum;
      }
    }
    
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        inv[i * n + j] = inv[j * n + i];
      }
    }
    
    return inv;
  }

  predict(u = null) {
    this.x = this._matVecMul(this.F, this.x, this.dimState, this.dimState);
    if (u) {
      this.x = this._matAdd(this.x, u, this.dimState, 1);
    }
    
    const Ft = this._matTranspose(this.F, this.dimState, this.dimState);
    this.P = this._matMul(this.F, this.P, this.dimState, this.dimState, this.dimState);
    this.P = this._matMul(this.P, Ft, this.dimState, this.dimState, this.dimState);
    this.P = this._matAdd(this.P, this.Q, this.dimState, this.dimState);
    
    return this.x.slice();
  }

  update(z) {
    const Ht = this._matTranspose(this.H, this.dimObs, this.dimState);
    const PHt = this._matMul(this.P, Ht, this.dimState, this.dimState, this.dimObs);
    const HP = this._matMul(this.H, this.P, this.dimObs, this.dimState, this.dimState);
    const S = this._matMul(HP, Ht, this.dimObs, this.dimState, this.dimObs);
    for (let i = 0; i < this.dimObs; i++) {
      S[i * this.dimObs + i] += this.R[i * this.dimObs + i];
    }
    
    const S_inv = this._invertSymmetric(S, this.dimObs);
    const K = this._matMul(PHt, S_inv, this.dimState, this.dimObs, this.dimObs);
    
    const Hx = this._matVecMul(this.H, this.x, this.dimObs, this.dimState);
    const y = new Float64Array(this.dimObs);
    for (let i = 0; i < this.dimObs; i++) {
      y[i] = z[i] - Hx[i];
      
      if (i < 2) {
        while (y[i] > Math.PI) y[i] -= 2 * Math.PI;
        while (y[i] < -Math.PI) y[i] += 2 * Math.PI;
      }
    }
    
    const Ky = this._matVecMul(K, y, this.dimState, this.dimObs);
    this.x = this._matAdd(this.x, Ky, this.dimState, 1);
    
    const KH = this._matMul(K, this.H, this.dimState, this.dimObs, this.dimState);
    const IKH = new Float64Array(this.dimState * this.dimState);
    for (let i = 0; i < this.dimState; i++) {
      for (let j = 0; j < this.dimState; j++) {
        IKH[i * this.dimState + j] = (i === j ? 1 : 0) - KH[i * this.dimState + j];
      }
    }
    
    const KHt = this._matTranspose(KH, this.dimState, this.dimState);
    this.P = this._matMul(KH, this.P, this.dimState, this.dimState, this.dimState);
    this.P = this._matMul(this.P, KHt, this.dimState, this.dimState, this.dimState);
    
    let KRKt = this._matMul(K, this.R, this.dimState, this.dimObs, this.dimObs);
    const Kt = this._matTranspose(K, this.dimState, this.dimObs);
    KRKt = this._matMul(KRKt, Kt, this.dimState, this.dimObs, this.dimState);
    this.P = this._matAdd(this.P, KRKt, this.dimState, this.dimState);
    
    return {
      x: this.x.slice(),
      P: this.P.slice(),
      innovation: y,
      gain: K
    };
  }

  getState() {
    return this.x.slice();
  }

  getCovariance() {
    return this.P.slice();
  }

  setState(x) {
    this.x = new Float64Array(x);
  }

  setCovariance(P) {
    this.P = new Float64Array(P);
  }
}

class SourceTracker {
  constructor(options = {}) {
    this.maxSources = options.maxSources || 5;
    this.dt = options.dt || 0.05;
    this.processNoise = options.processNoise || 0.1;
    this.measurementNoise = options.measurementNoise || 0.05;
    
    this.trackers = new Map();
    this.trackIdCounter = 0;
    this.maxCoastFrames = options.maxCoastFrames || 10;
    this.associationGate = options.associationGate || 0.5;
    
    this._initializeTransitionMatrix();
  }

  _initializeTransitionMatrix() {
    const dt = this.dt;
    const dimState = 6;
    const F = new Float64Array(dimState * dimState);
    
    F[0] = 1; F[1] = dt;
    F[6] = 0; F[7] = 1;
    F[14] = 1; F[15] = dt;
    F[20] = 0; F[21] = 1;
    F[28] = 1; F[29] = dt;
    F[34] = 0; F[35] = 1;
    
    this.transitionMatrix = F;
  }

  _createMeasurementMatrix() {
    const dimState = 6;
    const dimObs = 3;
    const H = new Float64Array(dimObs * dimState);
    H[0] = 1;
    H[8] = 1;
    H[16] = 1;
    return H;
  }

  _createProcessNoise() {
    const dimState = 6;
    const q = this.processNoise * this.processNoise;
    const Q = new Float64Array(dimState * dimState);
    
    Q[0] = q * 0.1;
    Q[7] = q;
    Q[14] = q * 0.1;
    Q[21] = q;
    Q[28] = q * 0.1;
    Q[35] = q;
    
    return Q;
  }

  _createMeasurementNoise() {
    const dimObs = 3;
    const r = this.measurementNoise * this.measurementNoise;
    const R = new Float64Array(dimObs * dimObs);
    R[0] = r * 2;
    R[4] = r * 2;
    R[8] = r * 5;
    return R;
  }

  _createInitialCovariance() {
    const dimState = 6;
    const P = new Float64Array(dimState * dimState);
    P[0] = 0.5;
    P[7] = 2;
    P[14] = 0.5;
    P[21] = 2;
    P[28] = 1;
    P[35] = 2;
    return P;
  }

  _computeDistance(measurement, tracker) {
    const predicted = tracker.kf.getState();
    let dAz = measurement[0] - predicted[0];
    let dEl = measurement[1] - predicted[2];
    
    while (dAz > Math.PI) dAz -= 2 * Math.PI;
    while (dAz < -Math.PI) dAz += 2 * Math.PI;
    while (dEl > Math.PI) dEl -= 2 * Math.PI;
    while (dEl < -Math.PI) dEl += 2 * Math.PI;
    
    const dR = measurement[2] - predicted[4];
    
    return Math.sqrt(dAz * dAz + dEl * dEl + dR * dR / 25);
  }

  _associateMeasurements(measurements) {
    const assignments = new Map();
    const usedTrackers = new Set();
    const usedMeasurements = new Set();
    
    const distances = [];
    for (const [id, tracker] of this.trackers) {
      for (let i = 0; i < measurements.length; i++) {
        if (usedMeasurements.has(i)) continue;
        const dist = this._computeDistance(measurements[i], tracker);
        if (dist < this.associationGate) {
          distances.push({ dist, id, measurementIdx: i });
        }
      }
    }
    
    distances.sort((a, b) => a.dist - b.dist);
    
    for (const { dist, id, measurementIdx } of distances) {
      if (usedTrackers.has(id) || usedMeasurements.has(measurementIdx)) continue;
      assignments.set(id, measurementIdx);
      usedTrackers.add(id);
      usedMeasurements.add(measurementIdx);
    }
    
    return { assignments, unassignedMeasurements: usedMeasurements };
  }

  update(measurements) {
    const obs = measurements.map(m => {
      const r = m.distance || 3;
      return [m.azimuth, m.elevation, r];
    });
    
    for (const [id, tracker] of this.trackers) {
      tracker.kf.predict();
      tracker.coastFrames++;
    }
    
    const { assignments, unassignedMeasurements } = this._associateMeasurements(obs);
    
    for (const [id, measurementIdx] of assignments) {
      const tracker = this.trackers.get(id);
      tracker.kf.update(obs[measurementIdx]);
      tracker.coastFrames = 0;
      tracker.lastSeen = Date.now();
    }
    
    for (let i = 0; i < obs.length; i++) {
      if (!unassignedMeasurements.has(i) && this.trackers.size < this.maxSources) {
        this._createNewTracker(obs[i]);
      }
    }
    
    const toRemove = [];
    for (const [id, tracker] of this.trackers) {
      if (tracker.coastFrames > this.maxCoastFrames) {
        toRemove.push(id);
      }
    }
    for (const id of toRemove) {
      this.trackers.delete(id);
    }
    
    return this.getTracks();
  }

  _createNewTracker(measurement) {
    const id = this.trackIdCounter++;
    
    const initialState = new Float64Array([
      measurement[0], 0,
      measurement[1], 0,
      measurement[2] || 3, 0
    ]);
    
    const kf = new KalmanFilter(6, 3, {
      F: this.transitionMatrix,
      H: this._createMeasurementMatrix(),
      Q: this._createProcessNoise(),
      R: this._createMeasurementNoise(),
      x: initialState,
      P: this._createInitialCovariance()
    });
    
    this.trackers.set(id, {
      id,
      kf,
      coastFrames: 0,
      lastSeen: Date.now(),
      history: [measurement]
    });
  }

  getTracks() {
    const tracks = [];
    for (const [id, tracker] of this.trackers) {
      const state = tracker.kf.getState();
      const cov = tracker.kf.getCovariance();
      
      let azimuth = state[0];
      while (azimuth < 0) azimuth += 2 * Math.PI;
      while (azimuth >= 2 * Math.PI) azimuth -= 2 * Math.PI;
      
      let elevation = state[2];
      elevation = Math.max(-Math.PI / 2, Math.min(Math.PI / 2, elevation));
      
      tracks.push({
        id,
        azimuth,
        elevation,
        distance: Math.max(0.5, Math.min(100, state[4])),
        velocityAzimuth: state[1],
        velocityElevation: state[3],
        velocityDistance: state[5],
        confidence: Math.max(0, 1 - tracker.coastFrames / this.maxCoastFrames),
        coastFrames: tracker.coastFrames,
        covariance: {
          azimuth: cov[0],
          elevation: cov[14],
          distance: cov[28]
        }
      });
    }
    return tracks.sort((a, b) => b.confidence - a.confidence);
  }

  reset() {
    this.trackers.clear();
    this.trackIdCounter = 0;
  }

  predictFuture(trackId, steps = 10) {
    const tracker = this.trackers.get(trackId);
    if (!tracker) return null;
    
    const predictions = [];
    const kfCopy = new KalmanFilter(6, 3, {
      F: this.transitionMatrix,
      H: this._createMeasurementMatrix(),
      Q: this._createProcessNoise(),
      R: this._createMeasurementNoise(),
      x: tracker.kf.getState(),
      P: tracker.kf.getCovariance()
    });
    
    for (let i = 0; i < steps; i++) {
      const state = kfCopy.predict();
      let azimuth = state[0];
      while (azimuth < 0) azimuth += 2 * Math.PI;
      while (azimuth >= 2 * Math.PI) azimuth -= 2 * Math.PI;
      
      predictions.push({
        time: (i + 1) * this.dt,
        azimuth,
        elevation: Math.max(-Math.PI / 2, Math.min(Math.PI / 2, state[2])),
        distance: Math.max(0.5, Math.min(100, state[4]))
      });
    }
    
    return predictions;
  }
}

class MovingSourceSimulator {
  constructor(options = {}) {
    this.sampleRate = options.sampleRate || 48000;
    this.soundSpeed = options.soundSpeed || 343;
    this.trajectory = options.trajectory || this._defaultTrajectory();
    this.currentTime = 0;
  }

  _defaultTrajectory() {
    return {
      type: 'circular',
      center: { x: 0, y: 0, z: 0 },
      radius: 3,
      angularVelocity: 1,
      startAngle: 0
    };
  }

  getPositionAtTime(time) {
    switch (this.trajectory.type) {
      case 'circular':
        const angle = this.trajectory.startAngle + this.trajectory.angularVelocity * time;
        return {
          x: this.trajectory.center.x + this.trajectory.radius * Math.cos(angle),
          y: this.trajectory.center.y + this.trajectory.radius * Math.sin(angle),
          z: this.trajectory.center.z
        };
      case 'linear':
        return {
          x: this.trajectory.start.x + this.trajectory.velocity.x * time,
          y: this.trajectory.start.y + this.trajectory.velocity.y * time,
          z: this.trajectory.start.z + this.trajectory.velocity.z * time
        };
      case 'custom':
        if (this.trajectory.getPosition) {
          return this.trajectory.getPosition(time);
        }
        return { x: 0, y: 0, z: 0 };
      default:
        return { x: 3, y: 0, z: 0 };
    }
  }

  generateSignals(arrayPositions, duration, options = {}) {
    const numSamples = Math.ceil(duration * this.sampleRate);
    const numChannels = arrayPositions.length;
    const signals = new Array(numChannels);
    
    for (let i = 0; i < numChannels; i++) {
      signals[i] = new Float64Array(numSamples);
    }
    
    const sourceType = options.type || 'sine';
    const frequency = options.frequency || 2000;
    const amplitude = options.amplitude || 1;
    const noiseLevel = options.noiseLevel || 0.02;
    
    for (let n = 0; n < numSamples; n++) {
      const time = n / this.sampleRate;
      const pos = this.getPositionAtTime(time);
      const t = this.currentTime + time;
      
      let sourceSignal = 0;
      switch (sourceType) {
        case 'sine':
          sourceSignal = amplitude * Math.sin(2 * Math.PI * frequency * t);
          break;
        case 'white_noise':
          sourceSignal = amplitude * (Math.random() * 2 - 1);
          break;
        case 'sweep':
          const sweepFreq = 500 + (frequency - 500) * (t / duration);
          sourceSignal = amplitude * Math.sin(2 * Math.PI * sweepFreq * t);
          break;
        default:
          sourceSignal = amplitude * Math.sin(2 * Math.PI * frequency * t);
      }
      
      for (let m = 0; m < numChannels; m++) {
        const mic = arrayPositions[m];
        const dx = pos.x - mic.x;
        const dy = pos.y - mic.y;
        const dz = pos.z - mic.z;
        const distance = Math.sqrt(dx * dx + dy * dy + dz * dz);
        
        const delay = distance / this.soundSpeed;
        const sampleDelay = delay * this.sampleRate;
        const n1 = Math.floor(n - sampleDelay);
        const n2 = n1 + 1;
        const frac = n - sampleDelay - n1;
        
        let delayedSignal = 0;
        if (n1 >= 0 && n2 < numSamples) {
          let s1 = 0, s2 = 0;
          if (sourceType === 'sine') {
            const t1 = this.currentTime + n1 / this.sampleRate;
            const t2 = this.currentTime + n2 / this.sampleRate;
            s1 = amplitude * Math.sin(2 * Math.PI * frequency * t1);
            s2 = amplitude * Math.sin(2 * Math.PI * frequency * t2);
          }
          delayedSignal = s1 * (1 - frac) + s2 * frac;
        }
        
        const attenuation = 1 / (1 + distance * 0.1);
        signals[m][n] = delayedSignal * attenuation + (Math.random() * 2 - 1) * noiseLevel;
      }
    }
    
    this.currentTime += duration;
    
    return signals;
  }

  setTrajectory(trajectory) {
    this.trajectory = { ...trajectory };
    this.currentTime = 0;
  }

  reset() {
    this.currentTime = 0;
  }
}

module.exports = {
  KalmanFilter,
  SourceTracker,
  MovingSourceSimulator
};
