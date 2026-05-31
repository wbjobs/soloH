import { 
  Particle, 
  SPHParameters, 
  ImpactForceData, 
  Vector3, 
  CollisionResult,
  ParticleGrainType,
  createVector3, 
  vecSub, 
  vecAdd, 
  vecScale, 
  vecDot, 
  vecLength, 
  vecNormalize 
} from '../types/physics';
import { BinghamModel } from './BinghamModel';
import { SpatialHash } from './SpatialHash';
import { CollisionDetector } from './Collision';
import { ForceCalculator } from './ForceCalculator';

export class SPHEngine {
  private params: SPHParameters;
  private particles: Particle[] = [];
  private binghamModel: BinghamModel;
  private spatialHash: SpatialHash;
  private collisionDetector: CollisionDetector;
  private forceCalculator: ForceCalculator;
  private simulationTime: number = 0;
  private lastImpactData: ImpactForceData | null = null;
  private particlePool: Particle[] = [];

  constructor(params: SPHParameters) {
    this.params = { ...params };
    
    this.binghamModel = new BinghamModel({
      yieldStress: params.yieldStress,
      viscosity: params.viscosity,
      smoothingLength: params.smoothingLength,
      regularizationFactor: 100
    });

    this.spatialHash = new SpatialHash(params.smoothingLength * 2);
    
    this.collisionDetector = new CollisionDetector({
      min: createVector3(-50, -10, -50),
      max: createVector3(50, 50, 50)
    });

    this.forceCalculator = new ForceCalculator(params.particleRadius);
  }

  initParticles(count: number, positions?: Vector3[]): void {
    this.particles = [];
    this.particlePool = [];
    this.simulationTime = 0;
    this.forceCalculator.clearHistory();

    const { grainSize } = this.params;

    for (let i = 0; i < Math.min(count, this.params.maxParticles); i++) {
      let position: Vector3;
      
      if (positions && positions[i]) {
        position = { ...positions[i] };
      } else {
        const nx = 10;
        const ny = 5;
        const nz = 10;
        const spacing = this.params.particleRadius * 2.5;
        
        const xi = i % nx;
        const yi = Math.floor((i / nx) % ny);
        const zi = Math.floor(i / (nx * ny));
        
        position = createVector3(
          -30 + xi * spacing + (Math.random() - 0.5) * spacing * 0.1,
          15 + yi * spacing + (Math.random() - 0.5) * spacing * 0.1,
          -20 + zi * spacing + (Math.random() - 0.5) * spacing * 0.1
        );
      }

      const grainType: ParticleGrainType = Math.random() < grainSize.fineFraction ? 'fine' : 'coarse';
      const grainRadius = grainType === 'fine' ? grainSize.fineRadius : grainSize.coarseRadius;
      const grainDensity = grainType === 'fine' ? grainSize.fineDensity : grainSize.coarseDensity;
      const particleMass = (4 / 3) * Math.PI * Math.pow(grainRadius, 3) * grainDensity;

      const particle: Particle = {
        id: i,
        position,
        velocity: createVector3(),
        acceleration: createVector3(),
        density: this.params.density0,
        densityPrev: this.params.density0,
        pressure: 0,
        mass: particleMass,
        viscosity: this.params.viscosity,
        impactForce: createVector3(),
        isActive: true,
        isFreeSurface: false,
        neighborCount: 0,
        colorField: 0,
        grainType,
        grainRadius,
        grainDensity,
        collisionCount: 0,
        collidedWithBridge: false,
        velocityBeforeCollision: null,
        collisionNormal: null,
        bridgePenetration: 0,
        smoothedImpactForce: createVector3()
      };

      this.particles.push(particle);
      this.particlePool.push(particle);
    }

    this.spatialHash.build(this.particles);
  }

  step(dt: number): void {
    const actualDt = Math.min(dt, this.params.timeStep);
    
    this.spatialHash.build(this.particles);
    this.savePreviousDensity();
    this.computeDensity();
    this.identifyFreeSurface();
    this.applyDensityConstraint();
    this.computePressure();
    this.computeForces();
    this.applyVegetationDrag();
    this.applyGrainSegregation(actualDt);
    this.integrate(actualDt);
    this.handleCollisions(actualDt);
    this.computeImpactData(actualDt);
    
    this.simulationTime += actualDt;
  }

  private savePreviousDensity(): void {
    for (const particle of this.particles) {
      if (!particle.isActive) continue;
      particle.densityPrev = particle.density;
    }
  }

  private computeDensity(): void {
    const h = this.params.smoothingLength;
    const h2 = h * h;
    const sigma = 1 / (Math.PI * h * h * h);

    for (let i = 0; i < this.particles.length; i++) {
      const pi = this.particles[i];
      if (!pi.isActive) continue;

      pi.density = pi.mass * this.binghamModel.computeKernel(0, h);
      pi.neighborCount = 0;
      pi.colorField = sigma;

      const neighbors = this.spatialHash.getNeighbors(pi.position, h * 2);

      for (const j of neighbors) {
        if (j === i) continue;
        const pj = this.particles[j];
        if (!pj.isActive) continue;

        const rij = vecSub(pi.position, pj.position);
        const r2 = vecDot(rij, rij);

        if (r2 < 4 * h2 && r2 > 1e-10) {
          const r = Math.sqrt(r2);
          const kernel = this.binghamModel.computeKernel(r, h);
          pi.density += pj.mass * kernel;
          pi.colorField += kernel;
          pi.neighborCount++;
        }
      }
    }
  }

  private identifyFreeSurface(): void {
    const h = this.params.smoothingLength;
    const expectedNeighbors = 20;
    const colorFieldThreshold = 0.6;
    const sigma = 1 / (Math.PI * h * h * h);

    for (const particle of this.particles) {
      if (!particle.isActive) continue;

      const normalizedColor = particle.colorField / sigma;
      const neighborRatio = particle.neighborCount / expectedNeighbors;

      particle.isFreeSurface = 
        neighborRatio < 0.4 || 
        normalizedColor < colorFieldThreshold;
    }
  }

  private applyDensityConstraint(): void {
    const { density0 } = this.params;
    const minDensityRatio = 0.85;
    const maxDensityRatio = 1.3;
    const constraintStrength = 0.3;

    for (const particle of this.particles) {
      if (!particle.isActive) continue;

      if (particle.isFreeSurface) {
        const targetDensity = density0 * 0.95;
        const densityError = targetDensity - particle.density;
        particle.density += densityError * constraintStrength;
      } else {
        const minDensity = density0 * minDensityRatio;
        const maxDensity = density0 * maxDensityRatio;

        if (particle.density < minDensity) {
          const densityError = minDensity - particle.density;
          particle.density += densityError * constraintStrength;
        } else if (particle.density > maxDensity) {
          const densityError = maxDensity - particle.density;
          particle.density += densityError * constraintStrength;
        }
      }

      particle.density = Math.max(particle.density, density0 * 0.7);
    }
  }

  private computePressure(): void {
    const { stiffness, density0 } = this.params;

    for (const particle of this.particles) {
      if (!particle.isActive) continue;
      
      const densityRatio = particle.density / density0;
      particle.pressure = stiffness * (Math.pow(densityRatio, 7) - 1);
      
      if (particle.isFreeSurface) {
        particle.pressure *= 0.5;
      }
      
      particle.pressure = Math.max(particle.pressure, -100);
    }
  }

  private computeForces(): void {
    const h = this.params.smoothingLength;
    const h2 = h * h;

    for (let i = 0; i < this.particles.length; i++) {
      const pi = this.particles[i];
      if (!pi.isActive) continue;

      const pressureForce = createVector3();
      const viscousForce = createVector3();

      const neighbors = this.spatialHash.getNeighbors(pi.position, h * 2);

      for (const j of neighbors) {
        if (j === i) continue;
        const pj = this.particles[j];
        if (!pj.isActive) continue;

        const rij = vecSub(pi.position, pj.position);
        const r2 = vecDot(rij, rij);

        if (r2 < 4 * h2 && r2 > 1e-10) {
          const r = Math.sqrt(r2);
          const q = r / h;

          let gradFactor: number;
          const sigma = 1 / (Math.PI * h * h * h);

          if (q <= 1.0) {
            gradFactor = sigma * (-3 * q + 2.25 * q * q) / (h * r);
          } else {
            const twoMinusQ = 2 - q;
            gradFactor = sigma * (-0.75 * twoMinusQ * twoMinusQ) / (h * r);
          }

          const gradW = vecScale(rij, gradFactor);

          const pressureTerm = (pi.pressure / (pi.density * pi.density)) + 
                               (pj.pressure / (pj.density * pj.density));
          pressureForce.x -= pj.mass * pressureTerm * gradW.x;
          pressureForce.y -= pj.mass * pressureTerm * gradW.y;
          pressureForce.z -= pj.mass * pressureTerm * gradW.z;

          const viscForce = this.binghamModel.computeViscousForce(
            pi.velocity, pj.velocity, pi.position, pj.position,
            pi.density, pj.density, pj.mass, h
          );
          viscousForce.x += viscForce.x;
          viscousForce.y += viscForce.y;
          viscousForce.z += viscForce.z;
        }
      }

      pi.acceleration.x = pressureForce.x + viscousForce.x + this.params.gravity.x;
      pi.acceleration.y = pressureForce.y + viscousForce.y + this.params.gravity.y;
      pi.acceleration.z = pressureForce.z + viscousForce.z + this.params.gravity.z;
    }
  }

  private integrate(dt: number): void {
    for (const particle of this.particles) {
      if (!particle.isActive) continue;

      particle.velocity.x += particle.acceleration.x * dt;
      particle.velocity.y += particle.acceleration.y * dt;
      particle.velocity.z += particle.acceleration.z * dt;

      const speed = vecLength(particle.velocity);
      const maxSpeed = 50;
      if (speed > maxSpeed) {
        particle.velocity = vecScale(particle.velocity, maxSpeed / speed);
      }

      particle.position.x += particle.velocity.x * dt;
      particle.position.y += particle.velocity.y * dt;
      particle.position.z += particle.velocity.z * dt;
    }
  }

  private handleCollisions(dt: number): void {
    const restitution = 0.1;
    const friction = 0.5;
    const penaltyStiffness = 5000;
    const dampingCoefficient = 2.0;
    const smoothingFactor = 0.2;

    for (const particle of this.particles) {
      if (!particle.isActive) continue;

      particle.velocityBeforeCollision = { ...particle.velocity };
      particle.collidedWithBridge = false;
      particle.collisionNormal = null;
      particle.bridgePenetration = 0;

      const terrainCollision = this.collisionDetector.checkTerrainCollision(
        particle, this.params.particleRadius
      );

      if (terrainCollision.collided) {
        const { velocityDelta, positionDelta } = this.collisionDetector.resolveCollision(
          particle, terrainCollision, restitution, friction
        );
        particle.position = vecAdd(particle.position, positionDelta);
        particle.velocity = vecAdd(particle.velocity, velocityDelta);
      }

      const boundaryCollision = this.collisionDetector.checkBoundaryCollision(
        particle, this.params.particleRadius
      );

      if (boundaryCollision.collided) {
        const { velocityDelta, positionDelta } = this.collisionDetector.resolveCollision(
          particle, boundaryCollision, restitution * 0.5, friction
        );
        particle.position = vecAdd(particle.position, positionDelta);
        particle.velocity = vecAdd(particle.velocity, velocityDelta);
      }

      const bridgeCollision = this.collisionDetector.checkBridgeCollision(
        particle, this.params.particleRadius
      );

      if (bridgeCollision.collided) {
        particle.collidedWithBridge = true;
        particle.collisionNormal = { ...bridgeCollision.normal };
        particle.bridgePenetration = bridgeCollision.penetration;

        const penaltyForce = this.computePenaltyForce(
          particle, 
          bridgeCollision, 
          penaltyStiffness, 
          dampingCoefficient
        );

        particle.acceleration = vecAdd(particle.acceleration, vecScale(penaltyForce, 1 / particle.mass));

        const positionCorrection = vecScale(
          bridgeCollision.normal, 
          bridgeCollision.penetration * 0.5
        );
        particle.position = vecAdd(particle.position, positionCorrection);

        const vn = vecDot(particle.velocity, bridgeCollision.normal);
        if (vn < 0) {
          const normalComponent = vecScale(bridgeCollision.normal, -0.95 * vn);
          particle.velocity = vecAdd(particle.velocity, normalComponent);
        }

        const rawImpactForce = this.forceCalculator.computeParticleImpactForce(particle, dt);
        particle.impactForce = rawImpactForce;
        
        particle.smoothedImpactForce = vecAdd(
          vecScale(particle.smoothedImpactForce, 1 - smoothingFactor),
          vecScale(rawImpactForce, smoothingFactor)
        );
      } else {
        particle.impactForce = createVector3();
        particle.smoothedImpactForce = vecScale(particle.smoothedImpactForce, 0.9);
      }
    }
  }

  private computePenaltyForce(
    particle: Particle,
    collision: CollisionResult,
    stiffness: number,
    damping: number
  ): Vector3 {
    const penetration = collision.penetration;
    const normal = collision.normal;
    
    const springForce = vecScale(normal, stiffness * penetration);
    
    const relativeVelocity = particle.velocity;
    const normalVelocity = vecDot(relativeVelocity, normal);
    const dampingForce = vecScale(normal, -damping * normalVelocity);
    
    return vecAdd(springForce, dampingForce);
  }

  private applyVegetationDrag(): void {
    const { vegetation } = this.params;
    if (!vegetation.enabled) return;

    const { density, stemDiameter, stemHeight, dragCoefficient, vegetationZone } = vegetation;
    const stemsPerUnitArea = density;
    const frontalAreaPerStem = stemDiameter * stemHeight;

    for (const particle of this.particles) {
      if (!particle.isActive) continue;

      const inZone = 
        particle.position.x >= vegetationZone.startX &&
        particle.position.x <= vegetationZone.endX &&
        particle.position.z >= vegetationZone.startZ &&
        particle.position.z <= vegetationZone.endZ &&
        particle.position.y <= stemHeight;

      if (!inZone) continue;

      const speed = vecLength(particle.velocity);
      if (speed < 1e-6) continue;

      const velocityNorm = vecNormalize(particle.velocity);
      
      const reynoldsNumber = (particle.density * speed * particle.grainRadius * 2) / this.params.viscosity;
      const dragFactor = reynoldsNumber > 1000 ? dragCoefficient : dragCoefficient * (1 + 10 / Math.sqrt(reynoldsNumber));

      const dragForceMagnitude = 0.5 * dragFactor * particle.density * speed * speed * 
                                frontalAreaPerStem * stemsPerUnitArea * (4 * Math.PI * Math.pow(particle.grainRadius, 2) / 3);

      const dragForce = vecScale(velocityNorm, -dragForceMagnitude / particle.mass);
      
      particle.acceleration = vecAdd(particle.acceleration, dragForce);
    }
  }

  private applyGrainSegregation(dt: number): void {
    const { grainSize } = this.params;
    
    for (let i = 0; i < this.particles.length; i++) {
      const pi = this.particles[i];
      if (!pi.isActive) continue;

      const neighbors = this.spatialHash.getNeighbors(pi.position, this.params.smoothingLength * 2);

      for (const j of neighbors) {
        if (j === i) continue;
        const pj = this.particles[j];
        if (!pj.isActive) continue;

        if (pi.grainType === pj.grainType) continue;

        const rij = vecSub(pi.position, pj.position);
        const r2 = vecDot(rij, rij);
        const h = this.params.smoothingLength;

        if (r2 > 4 * h * h || r2 < 1e-10) continue;

        const r = Math.sqrt(r2);
        const q = r / h;

        let gradFactor: number;
        const sigma = 1 / (Math.PI * h * h * h);
        if (q <= 1.0) {
          gradFactor = sigma * (-3 * q + 2.25 * q * q) / (h * r);
        } else {
          const twoMinusQ = 2 - q;
          gradFactor = sigma * (-0.75 * twoMinusQ * twoMinusQ) / (h * r);
        }

        const gradW = vecScale(rij, gradFactor);

        const densityDiff = pi.grainDensity - pj.grainDensity;
        const gravity = this.params.gravity;

        const buoyancyForce = vecScale(gravity, -densityDiff / ((pi.density + pj.density) / 2));

        const segregationVel = vecScale(buoyancyForce, grainSize.segregationVelocity);

        const randomWalk = createVector3(
          (Math.random() - 0.5) * grainSize.turbulentDiffusion,
          (Math.random() - 0.5) * grainSize.turbulentDiffusion,
          (Math.random() - 0.5) * grainSize.turbulentDiffusion
        );

        const interactionStrength = pj.mass * gradFactor * dt;
        pi.velocity = vecAdd(pi.velocity, vecScale(segregationVel, interactionStrength));
        pi.velocity = vecAdd(pi.velocity, vecScale(randomWalk, Math.sqrt(dt)));
      }
    }
  }

  private computeImpactData(dt: number): void {
    this.lastImpactData = this.forceCalculator.computeTotalImpactForces(
      this.particles, dt, this.simulationTime
    );
  }

  getParticles(): Particle[] {
    return this.particles.filter(p => p.isActive);
  }

  getImpactForceData(): ImpactForceData {
    return this.lastImpactData || {
      timestamp: this.simulationTime,
      totalForce: createVector3(),
      maxPressure: 0,
      impactArea: 0,
      particleCount: 0,
      averageVelocity: 0,
      fineParticleForce: createVector3(),
      coarseParticleForce: createVector3(),
      fineParticleCount: 0,
      coarseParticleCount: 0
    };
  }

  getImpactHistory(): ImpactForceData[] {
    return this.forceCalculator.getImpactHistory();
  }

  getSimulationTime(): number {
    return this.simulationTime;
  }

  getParticleCount(): number {
    return this.particles.filter(p => p.isActive).length;
  }

  reset(): void {
    this.simulationTime = 0;
    this.forceCalculator.clearHistory();
    this.lastImpactData = null;

    for (const particle of this.particles) {
      particle.isActive = false;
    }
  }

  updateParameters(params: Partial<SPHParameters>): void {
    this.params = { 
      ...this.params, 
      ...params,
      vegetation: params.vegetation ? { ...this.params.vegetation, ...params.vegetation } : this.params.vegetation,
      grainSize: params.grainSize ? { ...this.params.grainSize, ...params.grainSize } : this.params.grainSize
    };

    if (params.yieldStress !== undefined || params.viscosity !== undefined) {
      this.binghamModel.updateConfig({
        yieldStress: params.yieldStress ?? this.params.yieldStress,
        viscosity: params.viscosity ?? this.params.viscosity
      });
    }

    if (params.smoothingLength !== undefined) {
      this.spatialHash.setCellSize(params.smoothingLength * 2);
      this.binghamModel.updateConfig({ smoothingLength: params.smoothingLength });
    }

    if (params.particleRadius !== undefined) {
      this.forceCalculator.setParticleRadius(params.particleRadius);
    }

    if (params.vegetation?.vegetationZone) {
      this.params.vegetation.vegetationZone = {
        ...this.params.vegetation.vegetationZone,
        ...params.vegetation.vegetationZone
      };
    }
  }

  getParameters(): SPHParameters {
    return { ...this.params };
  }

  setTerrain(heights: number[][], params: { width: number; depth: number; resolution: number }): void {
    this.collisionDetector.setTerrain(heights, params);
  }

  setBridgeMesh(mesh: THREE.Mesh): void {
    this.collisionDetector.setBridgeMesh(mesh);
  }

  setBoundary(min: Vector3, max: Vector3): void {
    this.collisionDetector.setBoundary({ min, max });
  }

  getPeakImpactForce(): { magnitude: number; timestamp: number } {
    const peak = this.forceCalculator.getPeakImpactForce();
    return { magnitude: peak.magnitude, timestamp: peak.timestamp };
  }

  getPeakPressure(): { pressure: number; timestamp: number } {
    return this.forceCalculator.getPeakPressure();
  }

  getStats() {
    return {
      ...this.forceCalculator.getStats(),
      activeParticles: this.getParticleCount(),
      simulationTime: this.simulationTime,
      spatialHashStats: this.spatialHash.getStats()
    };
  }

  computeAdaptiveTimeStep(): number {
    let maxSpeed = 0;
    for (const p of this.particles) {
      if (!p.isActive) continue;
      const speed = vecLength(p.velocity);
      if (speed > maxSpeed) maxSpeed = speed;
    }

    if (maxSpeed < 1e-6) return this.params.timeStep;

    const cflDt = this.params.cflCoefficient * this.params.smoothingLength / maxSpeed;
    return Math.min(cflDt, this.params.timeStep);
  }
}
