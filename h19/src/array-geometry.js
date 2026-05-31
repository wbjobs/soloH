class ArrayGeometry {
  constructor(options = {}) {
    this.numElements = options.numElements || 16;
    this.topology = options.topology || 'circular';
    this.spacing = options.spacing || 0.08;
    this.centerFrequency = options.centerFrequency || 1000;
    this.soundSpeed = options.soundSpeed || 343;
  }

  generate() {
    switch (this.topology) {
      case 'linear':
        return this.generateLinear();
      case 'circular':
        return this.generateCircular();
      case 'spiral':
        return this.generateSpiral();
      case 'planar':
        return this.generatePlanar();
      default:
        return this.generateCircular();
    }
  }

  generateLinear() {
    const positions = [];
    const half = (this.numElements - 1) / 2;
    
    for (let i = 0; i < this.numElements; i++) {
      positions.push({
        x: (i - half) * this.spacing,
        y: 0,
        z: 0,
        index: i
      });
    }
    return positions;
  }

  generateCircular() {
    const positions = [];
    const radius = this.spacing * this.numElements / (2 * Math.PI);
    
    for (let i = 0; i < this.numElements; i++) {
      const angle = (2 * Math.PI * i) / this.numElements;
      const perturbation = (i % 2 === 0 ? 1 : -1) * 0.02 * this.spacing;
      positions.push({
        x: radius * Math.cos(angle) + perturbation * Math.cos(angle + Math.PI / 4),
        y: radius * Math.sin(angle) + perturbation * Math.sin(angle + Math.PI / 4),
        z: (i % 3) * 0.01 * this.spacing,
        index: i
      });
    }
    return positions;
  }

  generateSpiral() {
    const positions = [];
    const numArms = 3;
    const pointsPerArm = Math.ceil(this.numElements / numArms);
    const maxRadius = this.spacing * this.numElements / 4;
    
    let idx = 0;
    for (let arm = 0; arm < numArms && idx < this.numElements; arm++) {
      const armOffset = (2 * Math.PI * arm) / numArms;
      for (let n = 0; n < pointsPerArm && idx < this.numElements; n++) {
        const t = n / pointsPerArm;
        const angle = armOffset + t * 2 * Math.PI * 1.5;
        const radius = t * maxRadius;
        positions.push({
          x: radius * Math.cos(angle),
          y: radius * Math.sin(angle),
          z: (t - 0.5) * this.spacing * 2,
          index: idx
        });
        idx++;
      }
    }
    return positions;
  }

  generatePlanar() {
    const positions = [];
    const cols = Math.ceil(Math.sqrt(this.numElements));
    const rows = Math.ceil(this.numElements / cols);
    const halfCols = (cols - 1) / 2;
    const halfRows = (rows - 1) / 2;
    
    let idx = 0;
    for (let i = 0; i < rows; i++) {
      for (let j = 0; j < cols && idx < this.numElements; j++) {
        positions.push({
          x: (j - halfCols) * this.spacing,
          y: (i - halfRows) * this.spacing,
          z: 0,
          index: idx
        });
        idx++;
      }
    }
    return positions;
  }

  getWavelength(frequency) {
    return this.soundSpeed / frequency;
  }

  getBaseline() {
    const positions = this.generate();
    let maxDist = 0;
    for (let i = 0; i < positions.length; i++) {
      for (let j = i + 1; j < positions.length; j++) {
        const dx = positions[i].x - positions[j].x;
        const dy = positions[i].y - positions[j].y;
        const dz = positions[i].z - positions[j].z;
        const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
        maxDist = Math.max(maxDist, dist);
      }
    }
    return maxDist;
  }

  getDOAResolution(frequency) {
    const baseline = this.getBaseline();
    const wavelength = this.getWavelength(frequency);
    return Math.asin(wavelength / (2 * baseline)) * (180 / Math.PI);
  }

  getMaxFrequency() {
    return this.soundSpeed / (2 * this.spacing);
  }
}

module.exports = ArrayGeometry;
