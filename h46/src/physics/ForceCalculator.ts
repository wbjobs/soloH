import { Vector3, Particle, ImpactForceData, ProbabilityDistribution, ProbabilityBin, createVector3, vecSub, vecDot, vecScale, vecLength, vecAdd } from '../types/physics';

export class ForceCalculator {
  private particleRadius: number;
  private impactHistory: ImpactForceData[] = [];
  private maxHistoryLength: number = 10000;
  private allImpactForces: number[] = [];
  private allImpactPressures: number[] = [];
  private maxSampleSize: number = 5000;
  private distributionUpdateInterval: number = 5;
  private lastDistributionUpdate: number = 0;

  constructor(particleRadius: number) {
    this.particleRadius = particleRadius;
  }

  setParticleRadius(radius: number): void {
    this.particleRadius = radius;
  }

  computeParticleImpactForce(
    particle: Particle,
    dt: number
  ): Vector3 {
    if (!particle.collidedWithBridge || !particle.velocityBeforeCollision) {
      return createVector3();
    }

    const velocityChange = vecSub(particle.velocity, particle.velocityBeforeCollision);
    const force = vecScale(velocityChange, particle.mass / dt);

    return force;
  }

  computeImpactPressure(
    impactForce: Vector3,
    collisionNormal: Vector3,
    particleRadius: number
  ): number {
    const normalForce = Math.abs(vecDot(impactForce, collisionNormal));
    const area = Math.PI * particleRadius * particleRadius;
    return area > 0 ? normalForce / area : 0;
  }

  computeTotalImpactForces(
    particles: Particle[],
    dt: number,
    timestamp: number
  ): ImpactForceData {
    let totalForce = createVector3();
    let totalSmoothedForce = createVector3();
    let maxPressure = 0;
    let maxSmoothedPressure = 0;
    let impactArea = 0;
    let impactParticleCount = 0;
    let totalVelocity = 0;

    let fineParticleForce = createVector3();
    let coarseParticleForce = createVector3();
    let fineParticleCount = 0;
    let coarseParticleCount = 0;

    const particleArea = Math.PI * this.particleRadius * this.particleRadius;

    for (const particle of particles) {
      if (!particle.isActive || !particle.collidedWithBridge) continue;

      const impactForce = particle.smoothedImpactForce || this.computeParticleImpactForce(particle, dt);
      totalForce = vecAdd(totalForce, impactForce);
      totalSmoothedForce = vecAdd(totalSmoothedForce, impactForce);

      const pressure = vecLength(impactForce) / particleArea;
      if (pressure > maxPressure) {
        maxPressure = pressure;
      }

      if (particle.collisionNormal) {
        const normalPressure = this.computeImpactPressure(
          impactForce,
          particle.collisionNormal,
          this.particleRadius
        );
        if (normalPressure > maxSmoothedPressure) {
          maxSmoothedPressure = normalPressure;
        }
      }

      if (particle.grainType === 'fine') {
        fineParticleForce = vecAdd(fineParticleForce, impactForce);
        fineParticleCount++;
      } else {
        coarseParticleForce = vecAdd(coarseParticleForce, impactForce);
        coarseParticleCount++;
      }

      if (timestamp - this.lastDistributionUpdate >= this.distributionUpdateInterval) {
        const forceMag = vecLength(impactForce);
        if (forceMag > 0.01) {
          this.allImpactForces.push(forceMag);
          this.allImpactPressures.push(pressure);
          
          if (this.allImpactForces.length > this.maxSampleSize) {
            this.allImpactForces.shift();
            this.allImpactPressures.shift();
          }
        }
      }

      impactArea += particleArea;
      impactParticleCount++;
      totalVelocity += vecLength(particle.velocity);
    }

    const windowSize = 5;
    const smoothedForce = this.applyTimeWindowSmoothing(
      totalSmoothedForce,
      windowSize
    );

    const finalMaxPressure = maxSmoothedPressure > 0 ? maxSmoothedPressure : maxPressure;

    let probabilityDistribution: ProbabilityDistribution | undefined;
    if (timestamp - this.lastDistributionUpdate >= this.distributionUpdateInterval && 
        this.allImpactForces.length >= 50) {
      probabilityDistribution = this.computeProbabilityDistribution();
      this.lastDistributionUpdate = timestamp;
    } else if (this.impactHistory.length > 0) {
      probabilityDistribution = this.impactHistory[this.impactHistory.length - 1].probabilityDistribution;
    }

    const data: ImpactForceData = {
      timestamp,
      totalForce: smoothedForce,
      maxPressure: finalMaxPressure,
      impactArea,
      particleCount: impactParticleCount,
      averageVelocity: impactParticleCount > 0 ? totalVelocity / impactParticleCount : 0,
      fineParticleForce,
      coarseParticleForce,
      fineParticleCount,
      coarseParticleCount,
      probabilityDistribution
    };

    this.impactHistory.push(data);
    if (this.impactHistory.length > this.maxHistoryLength) {
      this.impactHistory.shift();
    }

    return data;
  }

  private computeProbabilityDistribution(): ProbabilityDistribution {
    const forces = this.allImpactForces;
    const pressures = this.allImpactPressures;

    const forceStats = this.computeStatistics(forces);
    const pressureStats = this.computeStatistics(pressures);

    const forceHistogram = this.buildHistogram(forces, 20);
    const pressureHistogram = this.buildHistogram(pressures, 20);

    const forceCDF = this.buildCDF(forces);
    const pressureCDF = this.buildCDF(pressures);

    const returnPeriods = this.computeReturnPeriods(forceCDF, pressureCDF);

    return {
      forceHistogram,
      pressureHistogram,
      forceCDF,
      pressureCDF,
      forceMean: forceStats.mean,
      forceStd: forceStats.std,
      forceSkewness: forceStats.skewness,
      pressureMean: pressureStats.mean,
      pressureStd: pressureStats.std,
      pressureSkewness: pressureStats.skewness,
      returnPeriods
    };
  }

  private computeStatistics(data: number[]): { mean: number; std: number; skewness: number } {
    if (data.length === 0) return { mean: 0, std: 0, skewness: 0 };

    const mean = data.reduce((a, b) => a + b, 0) / data.length;
    const variance = data.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / data.length;
    const std = Math.sqrt(variance);
    
    let skewness = 0;
    if (std > 1e-10) {
      skewness = data.reduce((a, b) => a + Math.pow((b - mean) / std, 3), 0) / data.length;
    }

    return { mean, std, skewness };
  }

  private buildHistogram(data: number[], binCount: number): ProbabilityBin[] {
    if (data.length === 0) return [];

    const min = Math.min(...data);
    const max = Math.max(...data);
    const binWidth = (max - min) / binCount;

    const bins: ProbabilityBin[] = [];
    for (let i = 0; i < binCount; i++) {
      bins.push({
        minValue: min + i * binWidth,
        maxValue: min + (i + 1) * binWidth,
        count: 0,
        probability: 0,
        exceedanceProbability: 0
      });
    }

    for (const value of data) {
      const binIndex = Math.min(Math.floor((value - min) / binWidth), binCount - 1);
      if (binIndex >= 0 && binIndex < binCount) {
        bins[binIndex].count++;
      }
    }

    for (let i = 0; i < binCount; i++) {
      bins[i].probability = bins[i].count / data.length;
      
      let exceedanceCount = 0;
      for (let j = i; j < binCount; j++) {
        exceedanceCount += bins[j].count;
      }
      bins[i].exceedanceProbability = exceedanceCount / data.length;
    }

    return bins;
  }

  private buildCDF(data: number[]): { value: number; probability: number }[] {
    if (data.length === 0) return [];

    const sorted = [...data].sort((a, b) => a - b);
    const cdf: { value: number; probability: number }[] = [];

    const samplePoints = 100;
    const step = Math.floor(sorted.length / samplePoints) || 1;

    for (let i = 0; i < sorted.length; i += step) {
      cdf.push({
        value: sorted[i],
        probability: (i + 1) / sorted.length
      });
    }

    if (cdf[cdf.length - 1].value !== sorted[sorted.length - 1]) {
      cdf.push({
        value: sorted[sorted.length - 1],
        probability: 1.0
      });
    }

    return cdf;
  }

  private computeReturnPeriods(
    forceCDF: { value: number; probability: number }[],
    pressureCDF: { value: number; probability: number }[]
  ): { period: number; force: number; pressure: number }[] {
    const periods = [1, 5, 10, 25, 50, 100, 200, 500, 1000];
    
    return periods.map(period => {
      const exceedanceProb = 1 / period;
      const cdfProb = 1 - exceedanceProb;

      const force = this.interpolateCDF(forceCDF, cdfProb);
      const pressure = this.interpolateCDF(pressureCDF, cdfProb);

      return { period, force, pressure };
    });
  }

  private interpolateCDF(cdf: { value: number; probability: number }[], targetProb: number): number {
    if (cdf.length === 0) return 0;
    if (targetProb <= 0) return cdf[0].value;
    if (targetProb >= 1) return cdf[cdf.length - 1].value;

    for (let i = 1; i < cdf.length; i++) {
      if (cdf[i].probability >= targetProb) {
        const prev = cdf[i - 1];
        const curr = cdf[i];
        const t = (targetProb - prev.probability) / (curr.probability - prev.probability);
        return prev.value + t * (curr.value - prev.value);
      }
    }

    return cdf[cdf.length - 1].value;
  }

  private applyTimeWindowSmoothing(
    currentForce: Vector3,
    windowSize: number
  ): Vector3 {
    if (this.impactHistory.length === 0) {
      return currentForce;
    }

    const recentData = this.impactHistory.slice(-windowSize);
    const weights: number[] = [];
    let totalWeight = 0;

    for (let i = 0; i < recentData.length; i++) {
      const weight = (i + 1) / (recentData.length + 1);
      weights.push(weight);
      totalWeight += weight;
    }

    let smoothedForce = createVector3();
    
    for (let i = 0; i < recentData.length; i++) {
      const w = weights[i] / totalWeight;
      smoothedForce = vecAdd(smoothedForce, vecScale(recentData[i].totalForce, w));
    }

    const currentWeight = 1.0 / (recentData.length + 1);
    smoothedForce = vecAdd(
      vecScale(smoothedForce, 1 - currentWeight),
      vecScale(currentForce, currentWeight)
    );

    return smoothedForce;
  }

  getImpactHistory(): ImpactForceData[] {
    return [...this.impactHistory];
  }

  getPeakImpactForce(): { force: Vector3; magnitude: number; timestamp: number } {
    let peakMagnitude = 0;
    let peakForce = createVector3();
    let peakTime = 0;

    for (const data of this.impactHistory) {
      const mag = vecLength(data.totalForce);
      if (mag > peakMagnitude) {
        peakMagnitude = mag;
        peakForce = data.totalForce;
        peakTime = data.timestamp;
      }
    }

    return { force: peakForce, magnitude: peakMagnitude, timestamp: peakTime };
  }

  getPeakPressure(): { pressure: number; timestamp: number } {
    let peakPressure = 0;
    let peakTime = 0;

    for (const data of this.impactHistory) {
      if (data.maxPressure > peakPressure) {
        peakPressure = data.maxPressure;
        peakTime = data.timestamp;
      }
    }

    return { pressure: peakPressure, timestamp: peakTime };
  }

  getAverageImpactForce(startTime: number = 0, endTime: number = Infinity): Vector3 {
    let sum = createVector3();
    let count = 0;

    for (const data of this.impactHistory) {
      if (data.timestamp >= startTime && data.timestamp <= endTime) {
        sum = vecAdd(sum, data.totalForce);
        count++;
      }
    }

    return count > 0 ? vecScale(sum, 1 / count) : createVector3();
  }

  getTotalImpulse(startTime: number = 0, endTime: number = Infinity): Vector3 {
    let impulse = createVector3();
    let lastTime = startTime;

    for (let i = 1; i < this.impactHistory.length; i++) {
      const data = this.impactHistory[i];
      const prevData = this.impactHistory[i - 1];

      if (data.timestamp >= startTime && prevData.timestamp <= endTime) {
        const dt = data.timestamp - prevData.timestamp;
        const avgForce = vecScale(vecAdd(data.totalForce, prevData.totalForce), 0.5);
        impulse = vecAdd(impulse, vecScale(avgForce, dt));
      }

      lastTime = data.timestamp;
      if (lastTime > endTime) break;
    }

    return impulse;
  }

  clearHistory(): void {
    this.impactHistory = [];
    this.allImpactForces = [];
    this.allImpactPressures = [];
    this.lastDistributionUpdate = 0;
  }

  getStats() {
    const peak = this.getPeakImpactForce();
    const peakPressure = this.getPeakPressure();
    
    return {
      totalDataPoints: this.impactHistory.length,
      peakForceMagnitude: peak.magnitude,
      peakForceTime: peak.timestamp,
      peakPressure: peakPressure.pressure,
      peakPressureTime: peakPressure.timestamp
    };
  }
}
