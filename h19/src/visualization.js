const THREE = require('three');
const { OrbitControls } = require('three/examples/jsm/controls/OrbitControls');

class HeatmapColor {
  static getColor(value, min = 0, max = 1) {
    const normalized = Math.max(0, Math.min(1, (value - min) / (max - min)));
    
    if (normalized < 0.25) {
      const t = normalized / 0.25;
      return {
        r: 0,
        g: 0,
        b: 0.5 + t * 0.5
      };
    } else if (normalized < 0.5) {
      const t = (normalized - 0.25) / 0.25;
      return {
        r: 0,
        g: t,
        b: 1
      };
    } else if (normalized < 0.75) {
      const t = (normalized - 0.5) / 0.25;
      return {
        r: t,
        g: 1,
        b: 1 - t
      };
    } else {
      const t = (normalized - 0.75) / 0.25;
      return {
        r: 1,
        g: 1 - t,
        b: 0
      };
    }
  }

  static getThreeColor(value, min = 0, max = 1) {
    const c = this.getColor(value, min, max);
    return new THREE.Color(c.r, c.g, c.b);
  }
}

class ArrayVisualizer3D {
  constructor(container, options = {}) {
    this.container = container;
    this.options = {
      backgroundColor: 0x0a0a0f,
      gridSize: 5,
      gridDivisions: 10,
      micRadius: 0.03,
      showGrid: true,
      showAxes: true,
      ...options
    };

    this.micMeshes = [];
    this.sourceMeshes = [];
    this.heatmapObjects = [];
    this.directionArrows = [];

    this._initScene();
    this._initLights();
    this._initGrid();
    this._animate();
  }

  _initScene() {
    const width = this.container.clientWidth;
    const height = this.container.clientHeight;

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(this.options.backgroundColor);
    this.scene.fog = new THREE.Fog(this.options.backgroundColor, 10, 30);

    this.camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 1000);
    this.camera.position.set(3, 3, 3);
    this.camera.lookAt(0, 0, 0);

    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setSize(width, height);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    this.container.appendChild(this.renderer.domElement);

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.05;
    this.controls.minDistance = 0.5;
    this.controls.maxDistance = 20;

    window.addEventListener('resize', () => this._onResize());
  }

  _initLights() {
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.4);
    this.scene.add(ambientLight);

    const mainLight = new THREE.DirectionalLight(0xffffff, 0.8);
    mainLight.position.set(5, 10, 5);
    mainLight.castShadow = true;
    mainLight.shadow.mapSize.width = 2048;
    mainLight.shadow.mapSize.height = 2048;
    mainLight.shadow.camera.near = 0.5;
    mainLight.shadow.camera.far = 50;
    mainLight.shadow.camera.left = -10;
    mainLight.shadow.camera.right = 10;
    mainLight.shadow.camera.top = 10;
    mainLight.shadow.camera.bottom = -10;
    this.scene.add(mainLight);

    const fillLight = new THREE.DirectionalLight(0x4488ff, 0.3);
    fillLight.position.set(-5, 3, -5);
    this.scene.add(fillLight);

    const rimLight = new THREE.PointLight(0x00ffff, 0.5, 20);
    rimLight.position.set(0, 2, -3);
    this.scene.add(rimLight);
  }

  _initGrid() {
    if (this.options.showGrid) {
      const gridHelper = new THREE.GridHelper(
        this.options.gridSize,
        this.options.gridDivisions,
        0x00ffff,
        0x1a1a2e
      );
      gridHelper.material.opacity = 0.5;
      gridHelper.material.transparent = true;
      this.scene.add(gridHelper);
      this.gridHelper = gridHelper;
    }

    if (this.options.showAxes) {
      const axesHelper = new THREE.AxesHelper(1);
      this.scene.add(axesHelper);
      this.axesHelper = axesHelper;
    }

    const groundGeometry = new THREE.CircleGeometry(this.options.gridSize / 2, 64);
    const groundMaterial = new THREE.MeshStandardMaterial({
      color: 0x0f0f1a,
      transparent: true,
      opacity: 0.5,
      side: THREE.DoubleSide
    });
    const ground = new THREE.Mesh(groundGeometry, groundMaterial);
    ground.rotation.x = -Math.PI / 2;
    ground.receiveShadow = true;
    this.scene.add(ground);
  }

  updateArray(positions) {
    this._clearMicMeshes();
    this._clearHeatmap();

    const group = new THREE.Group();

    positions.forEach((pos, index) => {
      const geometry = new THREE.SphereGeometry(this.options.micRadius, 16, 16);
      const material = new THREE.MeshStandardMaterial({
        color: 0x00ffff,
        emissive: 0x004444,
        emissiveIntensity: 0.3,
        metalness: 0.8,
        roughness: 0.2
      });
      const mesh = new THREE.Mesh(geometry, material);
      mesh.position.set(pos.x, pos.y, pos.z);
      mesh.castShadow = true;
      mesh.userData = { index, type: 'microphone' };

      const glowGeometry = new THREE.SphereGeometry(this.options.micRadius * 1.5, 16, 16);
      const glowMaterial = new THREE.MeshBasicMaterial({
        color: 0x00ffff,
        transparent: true,
        opacity: 0.2
      });
      const glow = new THREE.Mesh(glowGeometry, glowMaterial);
      mesh.add(glow);

      group.add(mesh);
      this.micMeshes.push(mesh);
    });

    if (positions.length > 1) {
      const lineGeometry = new THREE.BufferGeometry();
      const linePositions = new Float32Array(positions.length * 3);
      positions.forEach((pos, i) => {
        linePositions[i * 3] = pos.x;
        linePositions[i * 3 + 1] = pos.y;
        linePositions[i * 3 + 2] = pos.z;
      });
      lineGeometry.setAttribute('position', new THREE.BufferAttribute(linePositions, 3));
      const lineMaterial = new THREE.LineBasicMaterial({
        color: 0x0088aa,
        transparent: true,
        opacity: 0.4
      });
      const line = new THREE.LineLoop(lineGeometry, lineMaterial);
      group.add(line);
      this.arrayOutline = line;
    }

    this.scene.add(group);
    this.arrayGroup = group;
  }

  updateSources(sources) {
    this._clearSourceMeshes();

    sources.forEach((source, index) => {
      const group = new THREE.Group();
      
      const radius = 0.08 + source.normalizedPower * 0.08;
      const geometry = new THREE.SphereGeometry(radius, 32, 32);
      const color = HeatmapColor.getThreeColor(source.normalizedPower, 0, 1);
      
      const material = new THREE.MeshStandardMaterial({
        color: color,
        emissive: color,
        emissiveIntensity: 0.5,
        transparent: true,
        opacity: 0.9,
        metalness: 0.3,
        roughness: 0.4
      });
      const mesh = new THREE.Mesh(geometry, material);
      group.add(mesh);

      const ringGeometry = new THREE.RingGeometry(radius * 1.2, radius * 1.5, 32);
      const ringMaterial = new THREE.MeshBasicMaterial({
        color: color,
        transparent: true,
        opacity: 0.5,
        side: THREE.DoubleSide
      });
      const ring = new THREE.Mesh(ringGeometry, ringMaterial);
      ring.rotation.x = Math.PI / 2;
      group.add(ring);

      const distance = source.distance || 2;
      const x = distance * Math.cos(source.elevation) * Math.cos(source.azimuth);
      const y = distance * Math.cos(source.elevation) * Math.sin(source.azimuth);
      const z = distance * Math.sin(source.elevation);
      
      group.position.set(x, y, z);
      group.userData = { index, type: 'source', data: source };

      this.scene.add(group);
      this.sourceMeshes.push(group);

      const arrowHelper = new THREE.ArrowHelper(
        new THREE.Vector3(x, y, z).normalize(),
        new THREE.Vector3(0, 0, 0),
        distance * 0.95,
        color.getHex(),
        0.1,
        0.05
      );
      this.scene.add(arrowHelper);
      this.directionArrows.push(arrowHelper);
    });
  }

  updateHeatmap3D(powerMap, radius = 2) {
    this._clearHeatmap();

    let maxPower = 0;
    let minPower = Infinity;
    
    for (const [, power] of powerMap) {
      maxPower = Math.max(maxPower, power);
      minPower = Math.min(minPower, power);
    }

    const heatmapGroup = new THREE.Group();
    const entries = Array.from(powerMap.entries());

    entries.forEach(([key, power]) => {
      const [az, el] = key.split(',').map(Number);
      const normalized = (power - minPower) / (maxPower - minPower + 1e-10);
      
      if (normalized < 0.05) return;

      const scaledRadius = radius * (0.3 + normalized * 0.7);
      const x = scaledRadius * Math.cos(el) * Math.cos(az);
      const y = scaledRadius * Math.cos(el) * Math.sin(az);
      const z = scaledRadius * Math.sin(el);

      const size = 0.02 + normalized * 0.08;
      const geometry = new THREE.SphereGeometry(size, 8, 8);
      const material = new THREE.MeshBasicMaterial({
        color: HeatmapColor.getThreeColor(normalized, 0, 1),
        transparent: true,
        opacity: 0.2 + normalized * 0.6
      });
      const mesh = new THREE.Mesh(geometry, material);
      mesh.position.set(x, y, z);
      
      heatmapGroup.add(mesh);
      this.heatmapObjects.push(mesh);
    });

    this.scene.add(heatmapGroup);
    this.heatmapGroup = heatmapGroup;
  }

  updateHeatmapPolar(powerMap, container) {
    const canvas = container.querySelector('canvas') || document.createElement('canvas');
    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight;
    container.appendChild(canvas);

    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    const centerX = width / 2;
    const centerY = height / 2;
    const maxRadius = Math.min(width, height) / 2 - 20;

    ctx.fillStyle = '#0a0a0f';
    ctx.fillRect(0, 0, width, height);

    for (let r = maxRadius; r > 0; r -= maxRadius / 5) {
      ctx.beginPath();
      ctx.arc(centerX, centerY, r, 0, 2 * Math.PI);
      ctx.strokeStyle = 'rgba(0, 255, 255, 0.2)';
      ctx.lineWidth = 1;
      ctx.stroke();
    }

    for (let angle = 0; angle < 2 * Math.PI; angle += Math.PI / 6) {
      ctx.beginPath();
      ctx.moveTo(centerX, centerY);
      ctx.lineTo(
        centerX + maxRadius * Math.cos(angle),
        centerY + maxRadius * Math.sin(angle)
      );
      ctx.strokeStyle = 'rgba(0, 255, 255, 0.2)';
      ctx.lineWidth = 1;
      ctx.stroke();
    }

    let maxPower = 0;
    for (const [, power] of powerMap) {
      maxPower = Math.max(maxPower, power);
    }

    const resolution = 2;
    for (let r = 0; r < maxRadius; r += resolution) {
      for (let angle = 0; angle < 2 * Math.PI; angle += 0.05) {
        const key = `${angle.toFixed(4)},0.0000`;
        let power = powerMap.get(key) || 0;
        
        const normalized = power / (maxPower + 1e-10);
        
        if (normalized < 0.01) continue;

        const color = HeatmapColor.getColor(normalized, 0, 1);
        const alpha = 0.1 + normalized * 0.7;
        
        ctx.beginPath();
        ctx.arc(
          centerX + r * Math.cos(angle),
          centerY + r * Math.sin(angle),
          resolution * 1.2,
          0,
          2 * Math.PI
        );
        ctx.fillStyle = `rgba(${Math.floor(color.r * 255)}, ${Math.floor(color.g * 255)}, ${Math.floor(color.b * 255)}, ${alpha})`;
        ctx.fill();
      }
    }

    const angleLabels = ['0°', '30°', '60°', '90°', '120°', '150°', '180°', '210°', '240°', '270°', '300°', '330°'];
    for (let i = 0; i < 12; i++) {
      const angle = (i * 30) * Math.PI / 180;
      const labelRadius = maxRadius + 15;
      ctx.fillStyle = '#00ffff';
      ctx.font = '12px monospace';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(
        angleLabels[i],
        centerX + labelRadius * Math.cos(angle),
        centerY + labelRadius * Math.sin(angle)
      );
    }

    this.polarCanvas = canvas;
  }

  updateSpectrum(signals, container, sampleRate) {
    const canvas = container.querySelector('canvas') || document.createElement('canvas');
    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight;
    container.appendChild(canvas);

    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;

    ctx.fillStyle = '#0a0a0f';
    ctx.fillRect(0, 0, width, height);

    if (!signals || !signals[0]) return;

    const numChannels = signals.length;
    const numSamples = signals[0].length;
    const fftSize = Math.min(1024, numSamples);

    const barWidth = width / (fftSize / 2);
    const channelHeight = height / Math.min(numChannels, 8);

    const hanning = new Float64Array(fftSize);
    for (let i = 0; i < fftSize; i++) {
      hanning[i] = 0.5 * (1 - Math.cos(2 * Math.PI * i / (fftSize - 1)));
    }

    const channelsToShow = Math.min(numChannels, 8);
    
    for (let ch = 0; ch < channelsToShow; ch++) {
      const signal = signals[ch];
      const windowed = new Float64Array(fftSize);
      
      for (let i = 0; i < fftSize; i++) {
        windowed[i] = signal[i] * hanning[i];
      }

      const spectrum = this._computeFFTSpectrum(windowed);
      const maxMag = Math.max(...spectrum.map(s => Math.abs(s)));

      for (let i = 0; i < spectrum.length; i++) {
        const magnitude = Math.abs(spectrum[i]);
        const normalized = Math.log10(1 + magnitude) / Math.log10(1 + maxMag);
        const barHeight = normalized * channelHeight * 0.9;

        const x = i * barWidth;
        const y = height - ch * channelHeight - barHeight;

        const color = HeatmapColor.getColor(normalized, 0, 1);
        ctx.fillStyle = `rgb(${Math.floor(color.r * 255)}, ${Math.floor(color.g * 255)}, ${Math.floor(color.b * 255)})`;
        ctx.fillRect(x, y, barWidth - 1, barHeight);
      }

      ctx.fillStyle = '#00ffff';
      ctx.font = '10px monospace';
      ctx.textAlign = 'left';
      ctx.fillText(`CH${ch + 1}`, 5, height - ch * channelHeight - channelHeight + 15);
    }

    const freqLabels = [0, sampleRate / 8, sampleRate / 4, sampleRate * 3 / 8, sampleRate / 2];
    for (let i = 0; i < freqLabels.length; i++) {
      const x = (i / (freqLabels.length - 1)) * width;
      ctx.fillStyle = '#00aaaa';
      ctx.font = '9px monospace';
      ctx.textAlign = 'center';
      ctx.fillText(`${(freqLabels[i] / 1000).toFixed(0)}kHz`, x, height - 5);
    }

    this.spectrumCanvas = canvas;
  }

  _computeFFTSpectrum(signal) {
    const n = signal.length;
    const spectrum = new Float64Array(n / 2);
    
    const real = new Float64Array(n);
    const imag = new Float64Array(n);
    
    for (let i = 0; i < n; i++) {
      real[i] = signal[i];
      imag[i] = 0;
    }

    this._fft(real, imag);

    for (let i = 0; i < n / 2; i++) {
      spectrum[i] = Math.sqrt(real[i] * real[i] + imag[i] * imag[i]);
    }

    return spectrum;
  }

  _fft(real, imag) {
    const n = real.length;
    let bits = 0;
    for (let i = 1; i < n; i <<= 1) bits++;

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
      for (let i = 0; i < n; i += size) {
        for (let j = 0; j < half; j++) {
          const angle = -2 * Math.PI * j / size;
          const cos = Math.cos(angle);
          const sin = Math.sin(angle);
          
          const tr = real[i + j + half] * cos - imag[i + j + half] * sin;
          const ti = real[i + j + half] * sin + imag[i + j + half] * cos;
          
          real[i + j + half] = real[i + j] - tr;
          imag[i + j + half] = imag[i + j] - ti;
          real[i + j] += tr;
          imag[i + j] += ti;
        }
      }
    }
  }

  _clearMicMeshes() {
    if (this.arrayGroup) {
      this.scene.remove(this.arrayGroup);
      this.arrayGroup.traverse(child => {
        if (child.geometry) child.geometry.dispose();
        if (child.material) {
          if (Array.isArray(child.material)) {
            child.material.forEach(m => m.dispose());
          } else {
            child.material.dispose();
          }
        }
      });
    }
    this.micMeshes = [];
  }

  _clearSourceMeshes() {
    this.sourceMeshes.forEach(group => {
      this.scene.remove(group);
      group.traverse(child => {
        if (child.geometry) child.geometry.dispose();
        if (child.material) {
          if (Array.isArray(child.material)) {
            child.material.forEach(m => m.dispose());
          } else {
            child.material.dispose();
          }
        }
      });
    });
    this.sourceMeshes = [];

    this.directionArrows.forEach(arrow => {
      this.scene.remove(arrow);
    });
    this.directionArrows = [];
  }

  _clearHeatmap() {
    if (this.heatmapGroup) {
      this.scene.remove(this.heatmapGroup);
      this.heatmapGroup.traverse(child => {
        if (child.geometry) child.geometry.dispose();
        if (child.material) child.material.dispose();
      });
    }
    this.heatmapObjects = [];
  }

  _onResize() {
    const width = this.container.clientWidth;
    const height = this.container.clientHeight;

    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height);
  }

  _animate() {
    requestAnimationFrame(() => this._animate());
    
    this.controls.update();

    const time = Date.now() * 0.001;
    this.micMeshes.forEach((mesh, i) => {
      if (mesh.userData.signalAmplitude !== undefined) {
        const scale = 1 + mesh.userData.signalAmplitude * 0.3;
        mesh.scale.setScalar(scale);
      }
    });

    this.sourceMeshes.forEach((group, i) => {
      const pulse = 1 + Math.sin(time * 3 + i) * 0.1;
      group.scale.setScalar(pulse);
    });

    this.renderer.render(this.scene, this.camera);
  }

  updateMicActivity(amplitudes) {
    this.micMeshes.forEach((mesh, i) => {
      if (i < amplitudes.length) {
        mesh.userData.signalAmplitude = amplitudes[i];
        const material = mesh.material;
        if (material.emissive) {
          const intensity = 0.3 + amplitudes[i] * 0.7;
          material.emissiveIntensity = intensity;
        }
      }
    });
  }

  destroy() {
    this._clearMicMeshes();
    this._clearSourceMeshes();
    this._clearHeatmap();
    
    if (this.gridHelper) {
      this.scene.remove(this.gridHelper);
      this.gridHelper.geometry.dispose();
      this.gridHelper.material.dispose();
    }
    
    if (this.axesHelper) {
      this.scene.remove(this.axesHelper);
      this.axesHelper.geometry.dispose();
    }

    this.renderer.dispose();
    if (this.container && this.renderer.domElement) {
      this.container.removeChild(this.renderer.domElement);
    }
    
    window.removeEventListener('resize', () => this._onResize());
  }
}

module.exports = {
  ArrayVisualizer3D,
  HeatmapColor
};
