const ArrayGeometry = require('./array-geometry');
const { Beamforming, generateScanAngles, findPeaks } = require('./signal-processing');
const { SourceSimulator, WAVReader } = require('./source-simulation');
const { NearfieldAcousticHolography } = require('./acoustic-holography');
const { SourceTracker, MovingSourceSimulator } = require('./source-tracking');
const { ArrayCalibration, AutoGainControl } = require('./array-calibration');

class ProcessingPipeline {
  constructor(options = {}) {
    this.options = {
      numChannels: 16,
      fftSize: 1024,
      sampleRate: 48000,
      soundSpeed: 343,
      topology: 'circular',
      spacing: 0.08,
      algorithm: 'das',
      scanResolution: 3,
      includeElevation: false,
      numSources: 1,
      enableHolography: false,
      enableTracking: false,
      enableCalibration: false,
      ...options
    };

    this.arrayGeometry = null;
    this.arrayPositions = null;
    this.beamforming = null;
    this.sourceSimulator = null;
    this.wavReader = null;
    this.scanAngles = null;
    this.currentSignals = null;
    this.currentPowerMap = null;
    this.currentPeaks = null;
    this.currentDistances = null;

    this.holography = null;
    this.currentHologram = null;
    this.sourceTracker = null;
    this.currentTracks = null;
    this.movingSourceSimulator = null;
    this.arrayCalibration = null;
    this.autoGainControl = null;
    this.calibrationStatus = { isCalibrated: false };

    this.performanceStats = {
      fftTime: 0,
      beamformingTime: 0,
      holographyTime: 0,
      trackingTime: 0,
      calibrationTime: 0,
      totalTime: 0,
      frameCount: 0,
      fps: 0
    };

    this._init();
  }

  _init() {
    this.arrayGeometry = new ArrayGeometry({
      numElements: this.options.numChannels,
      topology: this.options.topology,
      spacing: this.options.spacing,
      soundSpeed: this.options.soundSpeed
    });

    this.arrayPositions = this.arrayGeometry.generate();

    this.beamforming = new Beamforming(this.arrayPositions, {
      fftSize: this.options.fftSize,
      sampleRate: this.options.sampleRate,
      soundSpeed: this.options.soundSpeed
    });

    this.sourceSimulator = new SourceSimulator({
      sampleRate: this.options.sampleRate,
      soundSpeed: this.options.soundSpeed,
      noiseLevel: 0.02
    });

    this.wavReader = new WAVReader();

    this.scanAngles = generateScanAngles(
      this.options.scanResolution,
      this.options.includeElevation
    );

    if (this.options.enableHolography) {
      this.holography = new NearfieldAcousticHolography(this.arrayPositions, {
        fftSize: this.options.fftSize,
        sampleRate: this.options.sampleRate,
        soundSpeed: this.options.soundSpeed
      });
    } else {
      this.holography = null;
      this.currentHologram = null;
    }

    if (this.options.enableTracking) {
      this.sourceTracker = new SourceTracker({
        maxSources: this.options.numSources,
        dt: this.options.fftSize / this.options.sampleRate
      });
    } else {
      this.sourceTracker = null;
      this.currentTracks = null;
    }

    if (this.options.enableCalibration) {
      this.arrayCalibration = new ArrayCalibration(this.arrayPositions, {
        fftSize: this.options.fftSize,
        sampleRate: this.options.sampleRate,
        soundSpeed: this.options.soundSpeed
      });
      this.autoGainControl = new AutoGainControl(this.options.numChannels, {
        sampleRate: this.options.sampleRate
      });
    } else {
      this.arrayCalibration = null;
      this.autoGainControl = null;
    }

    this.movingSourceSimulator = new MovingSourceSimulator({
      sampleRate: this.options.sampleRate,
      soundSpeed: this.options.soundSpeed
    });

    this._timeBuffer = [];
  }

  updateConfig(newOptions) {
    const needsReinit = 
      newOptions.numChannels !== this.options.numChannels ||
      newOptions.fftSize !== this.options.fftSize ||
      newOptions.topology !== this.options.topology ||
      newOptions.spacing !== this.options.spacing ||
      newOptions.scanResolution !== this.options.scanResolution ||
      newOptions.includeElevation !== this.options.includeElevation;

    Object.assign(this.options, newOptions);

    if (needsReinit) {
      this._init();
    }
  }

  generateSimulatedSignals(sourcesConfig, numSamples = null) {
    const samples = numSamples || this.options.fftSize * 4;
    
    const sources = sourcesConfig.map(s => ({
      type: s.type || 'white_noise',
      position: s.position || { x: 2, y: 0, z: 0 },
      options: s.options || { amplitude: 1 }
    }));

    const reflectors = this.options.enableReflections ? [
      { position: { x: 0, y: 5, z: 0 }, normal: { x: 0, y: -1, z: 0 }, reflection: 0.3 },
      { position: { x: 0, y: -5, z: 0 }, normal: { x: 0, y: 1, z: 0 }, reflection: 0.3 },
      { position: { x: 5, y: 0, z: 0 }, normal: { x: -1, y: 0, z: 0 }, reflection: 0.2 },
      { position: { x: -5, y: 0, z: 0 }, normal: { x: 1, y: 0, z: 0 }, reflection: 0.2 }
    ] : [];

    this.currentSignals = this.sourceSimulator.generateMultiSourceSignals(
      sources,
      this.arrayPositions,
      samples,
      reflectors
    );

    if (this.options.enableReverb && this.options.reverbTime > 0) {
      this.currentSignals = this.sourceSimulator.addReverberation(
        this.currentSignals,
        this.options.reverbTime
      );
    }

    return this.currentSignals;
  }

  loadWAVFile(buffer, sourceAzimuth = 0, sourceElevation = 0, sourceDistance = 2) {
    try {
      const audioData = this.wavReader.extractChannels(buffer, this.options.numChannels);
      
      let signals = audioData.channels;
      
      if (audioData.sampleRate !== this.options.sampleRate) {
        signals = this.wavReader.resample(
          signals,
          audioData.sampleRate,
          this.options.sampleRate
        );
      }

      const sourcePos = {
        x: sourceDistance * Math.cos(sourceElevation) * Math.cos(sourceAzimuth),
        y: sourceDistance * Math.cos(sourceElevation) * Math.sin(sourceAzimuth),
        z: sourceDistance * Math.sin(sourceElevation)
      };

      const numSamples = signals[0].length;
      const propagated = new Array(this.options.numChannels);
      
      for (let m = 0; m < this.options.numChannels; m++) {
        const micPos = this.arrayPositions[m];
        const dx = micPos.x - sourcePos.x;
        const dy = micPos.y - sourcePos.y;
        const dz = micPos.z - sourcePos.z;
        const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
        const delay = dist / this.options.soundSpeed;
        const delaySamples = Math.round(delay * this.options.sampleRate);
        const attenuation = Math.min(1, 1 / (1 + dist * 0.5));

        propagated[m] = new Float64Array(numSamples);
        for (let i = 0; i < numSamples; i++) {
          const idx = i - delaySamples;
          if (idx >= 0 && idx < numSamples) {
            propagated[m][i] = attenuation * signals[m][idx];
          } else {
            propagated[m][i] = 0;
          }
        }

        const noise = this.sourceSimulator.generateWhiteNoise(numSamples, 0.01);
        for (let i = 0; i < numSamples; i++) {
          propagated[m][i] += noise[i];
        }
      }

      this.currentSignals = propagated;
      return {
        success: true,
        numSamples,
        sampleRate: this.options.sampleRate,
        duration: numSamples / this.options.sampleRate
      };
    } catch (error) {
      return {
        success: false,
        error: error.message
      };
    }
  }

  processFrame(frameOffset = 0) {
    if (!this.currentSignals) {
      return null;
    }

    const t0 = performance.now();

    const frameSize = this.options.fftSize;
    const numChannels = this.options.numChannels;
    
    let frame = new Array(numChannels);
    for (let m = 0; m < numChannels; m++) {
      const signal = this.currentSignals[m];
      frame[m] = new Float64Array(frameSize);
      const start = frameOffset % Math.max(1, signal.length - frameSize);
      for (let i = 0; i < frameSize; i++) {
        frame[m][i] = signal[start + i] || 0;
      }
    }

    const t1 = performance.now();

    if (this.autoGainControl) {
      frame = this.autoGainControl.process(frame);
    }

    if (this.arrayCalibration && this.arrayCalibration.isCalibrated) {
      frame = this.arrayCalibration.applyCalibrationFast(frame);
    }

    const tCalib = performance.now();

    let powerMap;
    
    switch (this.options.algorithm) {
      case 'mvdr':
        powerMap = this.beamforming.mvdr(frame, this.scanAngles);
        break;
      case 'music':
        powerMap = this.beamforming.music(frame, this.scanAngles, this.options.numSources);
        break;
      case 'das':
      default:
        powerMap = this.beamforming.das(frame, this.scanAngles);
    }

    const t2 = performance.now();

    const peaks = findPeaks(powerMap, this.options.numSources, 0.1, this.options.scanResolution);

    const distances = [];
    const centerFreq = this.options.centerFrequency || 2000;
    for (const peak of peaks) {
      const dist = this.beamforming.estimateDistance(
        frame,
        peak.azimuth,
        peak.elevation,
        centerFreq
      );
      distances.push(dist);
      peak.distance = dist.combined;
    }

    const t3 = performance.now();

    let tracks = null;
    if (this.sourceTracker) {
      tracks = this.sourceTracker.update(peaks);
      this.currentTracks = tracks;
    }
    const tTrack = performance.now();

    let hologram = null;
    if (this.holography) {
      hologram = this.holography.reconstructFast(frame);
      this.currentHologram = hologram;
    }
    const tHol = performance.now();

    this.currentPowerMap = powerMap;
    this.currentPeaks = peaks;
    this.currentDistances = distances;

    this._updateStats(t0, t1, tCalib, t2, t3, tTrack, tHol);

    return {
      powerMap,
      peaks,
      distances,
      tracks,
      hologram,
      frame,
      performance: {
        preprocessing: t1 - t0,
        calibration: tCalib - t1,
        beamforming: t2 - tCalib,
        postprocessing: t3 - t2,
        tracking: tTrack - t3,
        holography: tHol - tTrack,
        total: tHol - t0
      }
    };
  }

  _updateStats(t0, t1, tCalib, t2, t3, tTrack, tHol) {
    this._timeBuffer.push(tHol - t0);
    if (this._timeBuffer.length > 30) {
      this._timeBuffer.shift();
    }

    const avgTime = this._timeBuffer.reduce((a, b) => a + b, 0) / this._timeBuffer.length;
    
    this.performanceStats = {
      fftTime: t1 - t0,
      calibrationTime: tCalib - t1,
      beamformingTime: t2 - tCalib,
      postprocessingTime: t3 - t2,
      trackingTime: tTrack - t3,
      holographyTime: tHol - tTrack,
      totalTime: tHol - t0,
      avgTotalTime: avgTime,
      frameCount: this.performanceStats.frameCount + 1,
      fps: 1000 / avgTime
    };
  }

  getSignalAmplitudes() {
    if (!this.currentSignals) return [];
    
    const amplitudes = [];
    const frameSize = this.options.fftSize;
    
    for (let m = 0; m < this.currentSignals.length; m++) {
      let sumSq = 0;
      const signal = this.currentSignals[m];
      const samples = Math.min(frameSize, signal.length);
      for (let i = 0; i < samples; i++) {
        sumSq += signal[i] * signal[i];
      }
      const rms = Math.sqrt(sumSq / samples);
      amplitudes.push(Math.min(1, rms * 3));
    }
    
    return amplitudes;
  }

  getArrayInfo() {
    return {
      numElements: this.arrayGeometry.numElements,
      topology: this.arrayGeometry.topology,
      spacing: this.arrayGeometry.spacing,
      maxFrequency: this.arrayGeometry.getMaxFrequency(),
      baseline: this.arrayGeometry.getBaseline(),
      resolution: this.arrayGeometry.getDOAResolution(2000),
      positions: this.arrayPositions
    };
  }

  getSpectrumForChannel(channelIndex, fftSize = 512) {
    if (!this.currentSignals || channelIndex >= this.currentSignals.length) {
      return null;
    }

    const signal = this.currentSignals[channelIndex];
    const n = Math.min(fftSize, signal.length);
    
    const windowed = new Float64Array(n);
    for (let i = 0; i < n; i++) {
      const w = 0.5 * (1 - Math.cos(2 * Math.PI * i / (n - 1)));
      windowed[i] = signal[i] * w;
    }

    const { FFT, Complex } = require('./signal-processing');
    const fft = new FFT(n);
    const spectrum = fft.realTransform(windowed);
    
    const magnitude = spectrum.slice(0, n / 2).map(c => c.magnitude());
    return magnitude;
  }

  processContinuous(onResult, frameStep = null) {
    if (this.isRunning) return;
    
    this.isRunning = true;
    const step = frameStep || Math.floor(this.options.fftSize / 2);
    let offset = 0;

    const processNext = () => {
      if (!this.isRunning) return;

      const result = this.processFrame(offset);
      if (result) {
        onResult(result);
      }

      offset = (offset + step) % (this.currentSignals[0].length - this.options.fftSize);
      
      setTimeout(processNext, Math.max(0, 50 - (result?.performance?.total || 0)));
    };

    processNext();
  }

  stopProcessing() {
    this.isRunning = false;
  }

  getPerformanceStats() {
    return { ...this.performanceStats };
  }

  exportResults() {
    return {
      timestamp: Date.now(),
      config: { ...this.options },
      arrayInfo: this.getArrayInfo(),
      peaks: this.currentPeaks ? this.currentPeaks.map(p => ({
        azimuth: p.azimuth,
        elevation: p.elevation,
        azimuthDeg: p.azimuth * 180 / Math.PI,
        elevationDeg: p.elevation * 180 / Math.PI,
        power: p.power,
        normalizedPower: p.normalizedPower,
        distance: p.distance
      })) : [],
      tracks: this.currentTracks ? this.currentTracks.map(t => ({
        id: t.id,
        azimuth: t.azimuth,
        elevation: t.elevation,
        distance: t.distance,
        velocityAzimuth: t.velocityAzimuth,
        velocityElevation: t.velocityElevation,
        velocityDistance: t.velocityDistance,
        confidence: t.confidence
      })) : [],
      performance: this.getPerformanceStats()
    };
  }

  addCalibrationData(knownSource) {
    if (!this.arrayCalibration || !this.currentSignals) {
      return { success: false, message: 'Calibration not enabled or no signal available' };
    }

    const frameSize = this.options.fftSize;
    const frame = new Array(this.options.numChannels);
    for (let m = 0; m < this.options.numChannels; m++) {
      frame[m] = this.currentSignals[m].slice(0, frameSize);
    }

    const count = this.arrayCalibration.addCalibrationData(frame, knownSource);
    return { success: true, calibrationPoints: count };
  }

  calibrateArray() {
    if (!this.arrayCalibration) {
      return { success: false, message: 'Calibration not enabled' };
    }

    const result = this.arrayCalibration.calibrate();
    this.calibrationStatus = this.arrayCalibration.getCalibrationStatus();
    return result;
  }

  selfCalibrateArray(numSources = 1) {
    if (!this.arrayCalibration || !this.currentSignals) {
      return { success: false, message: 'Calibration not enabled or no signal available' };
    }

    const frameSize = this.options.fftSize;
    const frame = new Array(this.options.numChannels);
    for (let m = 0; m < this.options.numChannels; m++) {
      frame[m] = this.currentSignals[m].slice(0, frameSize);
    }

    const result = this.arrayCalibration.selfCalibrate(frame, numSources);
    this.calibrationStatus = this.arrayCalibration.getCalibrationStatus();
    return result;
  }

  resetCalibration() {
    if (this.arrayCalibration) {
      this.arrayCalibration.reset();
      this.calibrationStatus = { isCalibrated: false };
    }
    if (this.autoGainControl) {
      this.autoGainControl.reset();
    }
    return { success: true };
  }

  getCalibrationStatus() {
    return this.arrayCalibration ? this.arrayCalibration.getCalibrationStatus() : { isCalibrated: false };
  }

  simulateChannelErrors(options = {}) {
    if (!this.arrayCalibration || !this.currentSignals) {
      return null;
    }

    const errorSim = this.arrayCalibration.simulateChannelErrors(options);
    
    const distorted = errorSim.apply(this.currentSignals);
    this.currentSignals = distorted;
    
    return {
      success: true,
      amplitudeGains: Array.from(errorSim.amplitudeGains),
      phaseOffsets: Array.from(errorSim.phaseOffsets)
    };
  }

  generateMovingSourceSignals(trajectory, duration, options = {}) {
    if (!this.movingSourceSimulator) {
      return { success: false, message: 'Moving source simulator not initialized' };
    }

    this.movingSourceSimulator.setTrajectory(trajectory);
    this.movingSourceSimulator.reset();
    
    const signals = this.movingSourceSimulator.generateSignals(this.arrayPositions, duration, options);
    this.currentSignals = signals;
    
    return {
      success: true,
      numSamples: signals[0].length,
      sampleRate: this.options.sampleRate,
      duration
    };
  }

  getMovingSourcePosition(time) {
    if (!this.movingSourceSimulator) return null;
    return this.movingSourceSimulator.getPositionAtTime(time);
  }

  getTrackPredictions(trackId, steps = 10) {
    if (!this.sourceTracker) return null;
    return this.sourceTracker.predictFuture(trackId, steps);
  }

  resetTracking() {
    if (this.sourceTracker) {
      this.sourceTracker.reset();
      this.currentTracks = null;
    }
    return { success: true };
  }

  setHolographyGrid(grid) {
    if (this.holography) {
      this.holography.setReconstructionGrid(grid);
    }
    return { success: true };
  }

  getCurrentHologram() {
    return this.currentHologram;
  }

  getCurrentTracks() {
    return this.currentTracks;
  }

  simulateAndCalibrate(calibrationSource, numPoints = 5) {
    const results = [];
    for (let i = 0; i < numPoints; i++) {
      const azimuth = (i / numPoints) * Math.PI * 2;
      const source = { ...calibrationSource, azimuth };
      
      this.generateSimulatedSignals([{
        type: 'sine',
        position: {
          x: 3 * Math.cos(azimuth),
          y: 3 * Math.sin(azimuth),
          z: 0
        },
        options: { frequency: 2000 }
      }]);
      
      const result = this.addCalibrationData(source);
      results.push(result);
    }
    
    const calResult = this.calibrateArray();
    return { points: results, calibration: calResult };
  }
}

module.exports = ProcessingPipeline;
