import { Vector3, Particle, createVector3 } from '../types/physics';

export class SpatialHash {
  private cellSize: number;
  private grid: Map<number, number[]>;
  private particleIndices: Map<number, number>;
  private readonly P1 = 73856093;
  private readonly P2 = 19349663;
  private readonly P3 = 83492791;

  constructor(cellSize: number) {
    this.cellSize = cellSize;
    this.grid = new Map();
    this.particleIndices = new Map();
  }

  setCellSize(cellSize: number): void {
    this.cellSize = cellSize;
  }

  getCellSize(): number {
    return this.cellSize;
  }

  clear(): void {
    this.grid.clear();
    this.particleIndices.clear();
  }

  private hashCell(ix: number, iy: number, iz: number): number {
    return ((ix * this.P1) ^ (iy * this.P2) ^ (iz * this.P3)) >>> 0;
  }

  private getCellIndices(position: Vector3): [number, number, number] {
    return [
      Math.floor(position.x / this.cellSize),
      Math.floor(position.y / this.cellSize),
      Math.floor(position.z / this.cellSize)
    ];
  }

  insert(particle: Particle, index: number): void {
    const [ix, iy, iz] = this.getCellIndices(particle.position);
    const hash = this.hashCell(ix, iy, iz);

    if (!this.grid.has(hash)) {
      this.grid.set(hash, []);
    }
    this.grid.get(hash)!.push(index);
    this.particleIndices.set(particle.id, hash);
  }

  build(particles: Particle[]): void {
    this.clear();
    for (let i = 0; i < particles.length; i++) {
      if (particles[i].isActive) {
        this.insert(particles[i], i);
      }
    }
  }

  getNeighbors(position: Vector3, radius: number): number[] {
    const neighbors: number[] = [];
    const searchRadius = Math.ceil(radius / this.cellSize);
    const [ix, iy, iz] = this.getCellIndices(position);

    for (let dz = -searchRadius; dz <= searchRadius; dz++) {
      for (let dy = -searchRadius; dy <= searchRadius; dy++) {
        for (let dx = -searchRadius; dx <= searchRadius; dx++) {
          const hash = this.hashCell(ix + dx, iy + dy, iz + dz);
          const cell = this.grid.get(hash);
          if (cell) {
            neighbors.push(...cell);
          }
        }
      }
    }

    return neighbors;
  }

  getNearbyParticles(position: Vector3, particles: Particle[], maxDist: number): Particle[] {
    const neighborIndices = this.getNeighbors(position, maxDist);
    const result: Particle[] = [];
    const maxDistSq = maxDist * maxDist;

    for (const idx of neighborIndices) {
      const p = particles[idx];
      if (!p.isActive) continue;
      
      const dx = p.position.x - position.x;
      const dy = p.position.y - position.y;
      const dz = p.position.z - position.z;
      const distSq = dx * dx + dy * dy + dz * dz;
      
      if (distSq <= maxDistSq) {
        result.push(p);
      }
    }

    return result;
  }

  getCellBounds(position: Vector3): { min: Vector3; max: Vector3 } {
    const [ix, iy, iz] = this.getCellIndices(position);
    return {
      min: createVector3(
        ix * this.cellSize,
        iy * this.cellSize,
        iz * this.cellSize
      ),
      max: createVector3(
        (ix + 1) * this.cellSize,
        (iy + 1) * this.cellSize,
        (iz + 1) * this.cellSize
      )
    };
  }

  getStats(): { cellCount: number; totalParticles: number; avgParticlesPerCell: number } {
    let totalParticles = 0;
    for (const cell of this.grid.values()) {
      totalParticles += cell.length;
    }
    return {
      cellCount: this.grid.size,
      totalParticles,
      avgParticlesPerCell: this.grid.size > 0 ? totalParticles / this.grid.size : 0
    };
  }
}
