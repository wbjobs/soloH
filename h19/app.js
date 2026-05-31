const { ipcRenderer } = require('electron');
const ProcessingPipeline = require('./src/processing-pipeline');
const { ArrayVisualizer3D, HeatmapColor } = require('./src/visualization');

class AcousticLocalizerApp {
  constructor() {
    this.pipeline = null;
    this.visualizer = null;
    this.isProcessing = false;
    this.frameOffset = 0;
    this.currentSourceConfig = null;

    this._initElements();
    this._initEventListeners();
    this._initPipeline();
    this._initVisualizer();
    this._generateInitialSignal();
  }

  _initElements() {
    this.elements = {
      topology: document.getElementById('topology'),
      numChannels: document.getElementById('num-channels'),
      channelsValue: document.getElementById('channels-value'),
      spacing: document.getElementById('spacing'),
      spacingValue: document.getElementById('spacing-value'),
      fftSize: document.getElementById('fft-size'),
      sampleRate: document.getElementById('sample-rate'),
      applyArrayConfig: document.getElementById('apply-array-config'),
      
      algorithm: document.getElementById('algorithm'),
      scanResolution: document.getElementById('scan-resolution'),
      resolutionValue: document.getElementById('resolution-value'),
      numSources: document.getElementById('num-sources'),
      sourcesValue: document.getElementById('sources-value'),
      includeElevation: document.getElementById('include-elevation'),
      
      sourceType: document.getElementById('source-type'),
      sourceFrequency: document.getElementById('source-frequency'),
      freqValue: document.getElementById('freq-value'),
      sourceAzimuth: document.getElementById('source-azimuth'),
      azimuthValue: document.getElementById('azimuth-value'),
      sourceElevation: document.getElementById('source-elevation'),
      elevationValue: document.getElementById('elevation-value'),
      sourceDistance: document.getElementById('source-distance'),
      distanceValue: document.getElementById('distance-value'),
      noiseLevel: document.getElementById('noise-level'),
      noiseValue: document.getElementById('noise-value'),
      enableReflections: document.getElementById('enable-reflections'),
      enableReverb: document.getElementById('enable-reverb'),
      generateSignal: document.getElementById('generate-signal'),
      loadWav: document.getElementById('load-wav'),
      
      viewMode: document.getElementById('view-mode'),
      showSources: document.getElementById('show-sources'),
      showHeatmap: document.getElementById('show-heatmap'),
      showSpectrum: document.getElementById('show-spectrum'),
      startProcessing: document.getElementById('start-processing'),
      stopProcessing: document.getElementById('stop-processing'),
      saveResults: document.getElementById('save-results'),
      
      currentAlgorithm: document.getElementById('current-algorithm'),
      currentChannels: document.getElementById('current-channels'),
      currentFps: document.getElementById('current-fps'),
      currentLatency: document.getElementById('current-latency'),
      
      arrayInfoBadge: document.getElementById('array-info-badge'),
      sampleRateBadge: document.getElementById('sample-rate-badge'),
      
      canvas3dContainer: document.getElementById('canvas-3d-container'),
      canvasPolarContainer: document.getElementById('canvas-polar-container'),
      canvasSpectrumContainer: document.getElementById('canvas-spectrum-container'),
      resultsGrid: document.getElementById('results-grid'),
      
      fftBar: document.getElementById('fft-bar'),
      fftTime: document.getElementById('fft-time'),
      beamformingBar: document.getElementById('beamforming-bar'),
      beamformingTime: document.getElementById('beamforming-time'),
      postBar: document.getElementById('post-bar'),
      postTime: document.getElementById('post-time'),
      totalBar: document.getElementById('total-bar'),
      totalTime: document.getElementById('total-time'),
      
      view3d: document.getElementById('view-3d'),
      viewPolar: document.getElementById('view-polar')
    };
  }

  _initEventListeners() {
    this.elements.numChannels.addEventListener('input', (e) => {
      this.elements.channelsValue.textContent = e.target.value;
    });

    this.elements.spacing.addEventListener('input', (e) => {
      this.elements.spacingValue.textContent = parseFloat(e.target.value).toFixed(2);
    });

    this.elements.scanResolution.addEventListener('input', (e) => {
      this.elements.resolutionValue.textContent = e.target.value;
    });

    this.elements.numSources.addEventListener('input', (e) => {
      this.elements.sourcesValue.textContent = e.target.value;
    });

    this.elements.sourceFrequency.addEventListener('input', (e) => {
      this.elements.freqValue.textContent = e.target.value;
    });

    this.elements.sourceAzimuth.addEventListener('input', (e) => {
      this.elements.azimuthValue.textContent = e.target.value;
    });

    this.elements.sourceElevation.addEventListener('input', (e) => {
      this.elements.elevationValue.textContent = e.target.value;
    });

    this.elements.sourceDistance.addEventListener('input', (e) => {
      this.elements.distanceValue.textContent = parseFloat(e.target.value).toFixed(1);
    });

    this.elements.noiseLevel.addEventListener('input', (e) => {
      this.elements.noiseValue.textContent = parseFloat(e.target.value).toFixed(3);
    });

    this.elements.applyArrayConfig.addEventListener('click', () => {
      this._applyArrayConfig();
    });

    this.elements.algorithm.addEventListener('change', () => {
      this._updateAlgorithm();
    });

    this.elements.scanResolution.addEventListener('change', () => {
      this._updateScanConfig();
    });

    this.elements.includeElevation.addEventListener('change', () => {
      this._updateScanConfig();
    });

    this.elements.numSources.addEventListener('change', () => {
      this._updateScanConfig();
    });

    this.elements.generateSignal.addEventListener('click', () => {
      this._generateSignal();
    });

    this.elements.loadWav.addEventListener('click', () => {
      this._loadWAVFile();
    });

    this.elements.viewMode.addEventListener('change', () => {
      this._updateViewMode();
    });

    this.elements.startProcessing.addEventListener('click', () => {
      this._startProcessing();
    });

    this.elements.stopProcessing.addEventListener('click', () => {
      this._stopProcessing();
    });

    this.elements.saveResults.addEventListener('click', () => {
      this._saveResults();
    });

    window.addEventListener('resize', () => {
      if (this.visualizer) {
        this.visualizer._onResize();
      }
    });
  }

  _initPipeline() {
    this.pipeline = new ProcessingPipeline({
      numChannels: parseInt(this.elements.numChannels.value),
      fftSize: parseInt(this.elements.fftSize.value),
      sampleRate: parseInt(this.elements.sampleRate.value),
      topology: this.elements.topology.value,
      spacing: parseFloat(this.elements.spacing.value),
      algorithm: this.elements.algorithm.value,
      scanResolution: parseInt(this.elements.scanResolution.value),
      includeElevation: this.elements.includeElevation.checked,
      numSources: parseInt(this.elements.numSources.value),
      centerFrequency: parseInt(this.elements.sourceFrequency.value),
      enableReflections: this.elements.enableReflections.checked,
      enableReverb: this.elements.enableReverb.checked,
      reverbTime: 0.3
    });

    this._updateHeaderStats();
  }

  _initVisualizer() {
    this.visualizer = new ArrayVisualizer3D(this.elements.canvas3dContainer, {
      backgroundColor: 0x0a0a0f,
      gridSize: 5,
      gridDivisions: 10,
      micRadius: 0.03
    });

    const arrayInfo = this.pipeline.getArrayInfo();
    this.visualizer.updateArray(arrayInfo.positions);
    this._updateArrayBadge();
  }

  _generateInitialSignal() {
    const azimuth = parseInt(this.elements.sourceAzimuth.value) * Math.PI / 180;
    const elevation = parseInt(this.elements.sourceElevation.value) * Math.PI / 180;
    const distance = parseFloat(this.elements.sourceDistance.value);

    const sourcePos = {
      x: distance * Math.cos(elevation) * Math.cos(azimuth),
      y: distance * Math.cos(elevation) * Math.sin(azimuth),
      z: distance * Math.sin(elevation)
    };

    this.currentSourceConfig = [{
      type: this.elements.sourceType.value,
      position: sourcePos,
      options: {
        amplitude: 1,
        frequency: parseInt(this.elements.sourceFrequency.value),
        startFreq: 200,
        endFreq: 5000,
        baseFreq: 150,
        pulseFreq: 10,
        dutyCycle: 0.1
      }
    }];

    this.pipeline.sourceSimulator.noiseLevel = parseFloat(this.elements.noiseLevel.value);
    this.pipeline.options.enableReflections = this.elements.enableReflections.checked;
    this.pipeline.options.enableReverb = this.elements.enableReverb.checked;
    
    this.pipeline.generateSimulatedSignals(this.currentSourceConfig, this.pipeline.options.fftSize * 8);
    
    const result = this.pipeline.processFrame(0);
    if (result) {
      this._updateVisualization(result);
    }
  }

  _applyArrayConfig() {
    this.pipeline.updateConfig({
      numChannels: parseInt(this.elements.numChannels.value),
      fftSize: parseInt(this.elements.fftSize.value),
      sampleRate: parseInt(this.elements.sampleRate.value),
      topology: this.elements.topology.value,
      spacing: parseFloat(this.elements.spacing.value)
    });

    const arrayInfo = this.pipeline.getArrayInfo();
    this.visualizer.updateArray(arrayInfo.positions);
    
    this._updateHeaderStats();
    this._updateArrayBadge();
    this._updateSampleRateBadge();
    
    if (this.currentSourceConfig) {
      this.pipeline.generateSimulatedSignals(this.currentSourceConfig, this.pipeline.options.fftSize * 8);
      const result = this.pipeline.processFrame(0);
      if (result) {
        this._updateVisualization(result);
      }
    }
  }

  _updateAlgorithm() {
    this.pipeline.updateConfig({
      algorithm: this.elements.algorithm.value
    });
    this._updateHeaderStats();
  }

  _updateScanConfig() {
    this.pipeline.updateConfig({
      scanResolution: parseInt(this.elements.scanResolution.value),
      includeElevation: this.elements.includeElevation.checked,
      numSources: parseInt(this.elements.numSources.value)
    });
  }

  _generateSignal() {
    const azimuth = parseInt(this.elements.sourceAzimuth.value) * Math.PI / 180;
    const elevation = parseInt(this.elements.sourceElevation.value) * Math.PI / 180;
    const distance = parseFloat(this.elements.sourceDistance.value);

    const sourcePos = {
      x: distance * Math.cos(elevation) * Math.cos(azimuth),
      y: distance * Math.cos(elevation) * Math.sin(azimuth),
      z: distance * Math.sin(elevation)
    };

    this.currentSourceConfig = [{
      type: this.elements.sourceType.value,
      position: sourcePos,
      options: {
        amplitude: 1,
        frequency: parseInt(this.elements.sourceFrequency.value),
        startFreq: 200,
        endFreq: 5000,
        baseFreq: 150,
        pulseFreq: 10,
        dutyCycle: 0.1
      }
    }];

    this.pipeline.sourceSimulator.noiseLevel = parseFloat(this.elements.noiseLevel.value);
    this.pipeline.options.enableReflections = this.elements.enableReflections.checked;
    this.pipeline.options.enableReverb = this.elements.enableReverb.checked;
    this.pipeline.options.centerFrequency = parseInt(this.elements.sourceFrequency.value);
    
    this.pipeline.generateSimulatedSignals(this.currentSourceConfig, this.pipeline.options.fftSize * 8);
    
    this.frameOffset = 0;
    const result = this.pipeline.processFrame(0);
    if (result) {
      this._updateVisualization(result);
    }
  }

  async _loadWAVFile() {
    try {
      const result = await ipcRenderer.invoke('open-wav-file');
      if (result) {
        const buffer = Uint8Array.from(result.buffer).buffer;
        const azimuth = parseInt(this.elements.sourceAzimuth.value) * Math.PI / 180;
        const elevation = parseInt(this.elements.sourceElevation.value) * Math.PI / 180;
        const distance = parseFloat(this.elements.sourceDistance.value);

        const loadResult = this.pipeline.loadWAVFile(buffer, azimuth, elevation, distance);
        
        if (loadResult.success) {
          this.frameOffset = 0;
          const processResult = this.pipeline.processFrame(0);
          if (processResult) {
            this._updateVisualization(processResult);
          }
        } else {
          alert('加载WAV文件失败: ' + loadResult.error);
        }
      }
    } catch (error) {
      console.error('Error loading WAV:', error);
      alert('加载WAV文件时发生错误');
    }
  }

  _updateViewMode() {
    const mode = this.elements.viewMode.value;
    
    if (mode === '3d') {
      this.elements.view3d.style.display = 'flex';
      this.elements.viewPolar.style.display = 'none';
      this.elements.view3d.style.flex = '1';
    } else if (mode === 'polar') {
      this.elements.view3d.style.display = 'none';
      this.elements.viewPolar.style.display = 'flex';
      this.elements.viewPolar.style.flex = '1';
    } else {
      this.elements.view3d.style.display = 'flex';
      this.elements.viewPolar.style.display = 'flex';
      this.elements.view3d.style.flex = '1';
      this.elements.viewPolar.style.flex = '1';
    }

    setTimeout(() => {
      this.visualizer._onResize();
    }, 100);
  }

  _startProcessing() {
    if (this.isProcessing) return;
    
    this.isProcessing = true;
    this.elements.startProcessing.disabled = true;
    this.elements.stopProcessing.disabled = false;
    
    this._processLoop();
  }

  _stopProcessing() {
    this.isProcessing = false;
    this.elements.startProcessing.disabled = false;
    this.elements.stopProcessing.disabled = true;
  }

  _processLoop() {
    if (!this.isProcessing) return;

    const t0 = performance.now();
    const result = this.pipeline.processFrame(this.frameOffset);
    
    if (result) {
      this._updateVisualization(result);
    }

    this.frameOffset = (this.frameOffset + Math.floor(this.pipeline.options.fftSize / 2)) % 
      Math.max(1, this.pipeline.currentSignals[0].length - this.pipeline.options.fftSize);

    const elapsed = performance.now() - t0;
    const targetInterval = Math.max(16, 50 - elapsed);
    
    setTimeout(() => this._processLoop(), targetInterval);
  }

  _updateVisualization(result) {
    const { powerMap, peaks, frame, performance } = result;

    if (this.elements.showHeatmap.checked) {
      if (this.elements.viewMode.value !== 'polar') {
        this.visualizer.updateHeatmap3D(powerMap, 2);
      }
      if (this.elements.viewMode.value !== '3d') {
        this.visualizer.updateHeatmapPolar(powerMap, this.elements.canvasPolarContainer);
      }
    }

    if (this.elements.showSources.checked && peaks.length > 0) {
      this.visualizer.updateSources(peaks);
    }

    if (this.elements.showSpectrum.checked) {
      this.visualizer.updateSpectrum(frame, this.elements.canvasSpectrumContainer, this.pipeline.options.sampleRate);
    }

    const amplitudes = this.pipeline.getSignalAmplitudes();
    this.visualizer.updateMicActivity(amplitudes);

    this._updateResults(peaks);
    this._updatePerformance(performance);
    this._updateHeaderStats();
  }

  _updateResults(peaks) {
    if (!peaks || peaks.length === 0) {
      this.elements.resultsGrid.innerHTML = `
        <div class="result-placeholder">
          <p>未检测到声源</p>
        </div>
      `;
      return;
    }

    let html = '';
    peaks.forEach((peak, index) => {
      const azimuthDeg = (peak.azimuth * 180 / Math.PI).toFixed(1);
      const elevationDeg = (peak.elevation * 180 / Math.PI).toFixed(1);
      const powerDb = (10 * Math.log10(peak.normalizedPower + 1e-10)).toFixed(1);
      
      const color = HeatmapColor.getColor(peak.normalizedPower, 0, 1);
      const bgColor = `rgba(${Math.floor(color.r * 255)}, ${Math.floor(color.g * 255)}, ${Math.floor(color.b * 255)}, 0.8)`;

      html += `
        <div class="result-card">
          <div class="result-header">
            <div class="result-index" style="background: ${bgColor}">${index + 1}</div>
            <div class="result-power">${powerDb} dB</div>
          </div>
          <div class="result-params">
            <div class="param-item">
              <span class="param-label">方位角</span>
              <span class="param-value">${azimuthDeg}°</span>
            </div>
            <div class="param-item">
              <span class="param-label">仰角</span>
              <span class="param-value">${elevationDeg}°</span>
            </div>
            <div class="param-item">
              <span class="param-label">距离</span>
              <span class="param-value">${peak.distance.toFixed(2)} m</span>
            </div>
            <div class="param-item">
              <span class="param-label">功率</span>
              <span class="param-value">${(peak.normalizedPower * 100).toFixed(1)}%</span>
            </div>
          </div>
        </div>
      `;
    });

    this.elements.resultsGrid.innerHTML = html;
  }

  _updatePerformance(perf) {
    const maxTime = 50;
    
    const fftPct = Math.min(100, (perf.preprocessing / maxTime) * 100);
    const beamPct = Math.min(100, (perf.beamforming / maxTime) * 100);
    const postPct = Math.min(100, (perf.postprocessing / maxTime) * 100);
    const totalPct = Math.min(100, (perf.total / maxTime) * 100);

    this.elements.fftBar.style.width = fftPct + '%';
    this.elements.beamformingBar.style.width = beamPct + '%';
    this.elements.postBar.style.width = postPct + '%';
    this.elements.totalBar.style.width = totalPct + '%';

    this.elements.fftTime.textContent = perf.preprocessing.toFixed(1) + ' ms';
    this.elements.beamformingTime.textContent = perf.beamforming.toFixed(1) + ' ms';
    this.elements.postTime.textContent = perf.postprocessing.toFixed(1) + ' ms';
    this.elements.totalTime.textContent = perf.total.toFixed(1) + ' ms';
  }

  _updateHeaderStats() {
    const algoMap = {
      'das': 'DAS',
      'mvdr': 'MVDR',
      'music': 'MUSIC'
    };
    
    this.elements.currentAlgorithm.textContent = algoMap[this.pipeline.options.algorithm] || 'DAS';
    this.elements.currentChannels.textContent = this.pipeline.options.numChannels;
    
    const stats = this.pipeline.getPerformanceStats();
    this.elements.currentFps.textContent = stats.fps ? stats.fps.toFixed(1) : '0';
    this.elements.currentLatency.textContent = stats.avgTotalTime ? stats.avgTotalTime.toFixed(1) + 'ms' : '0ms';
  }

  _updateArrayBadge() {
    const info = this.pipeline.getArrayInfo();
    const topologyMap = {
      'linear': '线性',
      'circular': '圆形',
      'spiral': '螺旋',
      'planar': '平面'
    };
    this.elements.arrayInfoBadge.textContent = `${info.numElements}通道 ${topologyMap[info.topology] || info.topology}阵列`;
  }

  _updateSampleRateBadge() {
    this.elements.sampleRateBadge.textContent = this.pipeline.options.sampleRate + ' Hz';
  }

  async _saveResults() {
    const results = this.pipeline.exportResults();
    try {
      const success = await ipcRenderer.invoke('save-results', results);
      if (success) {
        alert('结果已成功保存！');
      }
    } catch (error) {
      console.error('Error saving results:', error);
    }
  }

  destroy() {
    this._stopProcessing();
    if (this.visualizer) {
      this.visualizer.destroy();
    }
  }
}

window.addEventListener('DOMContentLoaded', () => {
  window.app = new AcousticLocalizerApp();
});

window.addEventListener('beforeunload', () => {
  if (window.app) {
    window.app.destroy();
  }
});
