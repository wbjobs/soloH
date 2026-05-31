import { Vector3, vecSub, vecDot, vecScale, createVector3 } from '../types/physics';

export interface BinghamConfig {
  yieldStress: number;
  viscosity: number;
  smoothingLength: number;
  regularizationFactor: number;
}

export class BinghamModel {
  private config: BinghamConfig;
  private readonly P1 = 73856093;
  private readonly P2 = 19349663;
  private readonly P3 = 83492791;

  constructor(config: BinghamConfig) {
    this.config = { ...config };
  }

  updateConfig(config: Partial<BinghamConfig>): void {
    this.config = { ...this.config, ...config };
  }

  getConfig(): BinghamConfig {
    return { ...this.config };
  }

  computeShearRate(
    vi: Vector3,
    vj: Vector3,
    ri: Vector3,
    rj: Vector3,
    h: number
  ): number {
    const rij = vecSub(ri, rj);
    const vij = vecSub(vi, vj);
    const rMag = Math.sqrt(vecDot(rij, rij));
    
    if (rMag < 1e-10 || rMag > 2 * h) {
      return 0;
    }

    const rijNorm = vecScale(rij, 1 / rMag);
    const vDotR = vecDot(vij, rijNorm);
    
    const shearRate = Math.abs(vDotR) / rMag;
    
    return shearRate;
  }

  computeApparentViscosity(shearRate: number): number {
    const { yieldStress, viscosity, regularizationFactor } = this.config;
    
    if (shearRate < 1e-10) {
      return viscosity + yieldStress / regularizationFactor;
    }

    const tau_y_over_gamma = yieldStress / shearRate;
    const regularization = 1.0 - Math.exp(-shearRate * regularizationFactor);
    
    const apparentViscosity = viscosity + tau_y_over_gamma * regularization;
    
    return Math.max(apparentViscosity, viscosity);
  }

  computeViscousForce(
    vi: Vector3,
    vj: Vector3,
    ri: Vector3,
    rj: Vector3,
    rhoi: number,
    rhoj: number,
    mj: number,
    h: number
  ): Vector3 {
    const rij = vecSub(ri, rj);
    const vij = vecSub(vi, vj);
    const rMag = Math.sqrt(vecDot(rij, rij));
    
    if (rMag < 1e-10 || rMag > 2 * h) {
      return createVector3();
    }

    const shearRate = this.computeShearRate(vi, vj, ri, rj, h);
    const muApp = this.computeApparentViscosity(shearRate);

    const gradW = this.computeKernelGradient(rij, rMag, h);
    const mu_ij = 2 * muApp / (rhoi + rhoj + 1e-10);
    
    const force = vecScale(gradW, mu_ij * mj * vecDot(vij, rij) / (rMag * rMag + 0.01 * h * h));
    
    return force;
  }

  computeYieldStressEffect(
    shearRate: number,
    viscosity: number
  ): number {
    const { yieldStress, regularizationFactor } = this.config;
    
    if (shearRate < 1e-10) {
      return yieldStress;
    }

    const tau = yieldStress + viscosity * shearRate;
    const regularization = 1.0 - Math.exp(-shearRate * regularizationFactor);
    
    return tau * regularization;
  }

  isFlowing(shearStress: number, shearRate: number): boolean {
    const { yieldStress } = this.config;
    
    if (shearRate < 1e-10) {
      return false;
    }
    
    return shearStress > yieldStress;
  }

  private computeKernelGradient(rij: Vector3, rMag: number, h: number): Vector3 {
    const q = rMag / h;
    const sigma = 1 / (Math.PI * h * h * h);
    
    let gradFactor: number;
    
    if (q <= 1.0) {
      gradFactor = sigma * (-3 * q + 2.25 * q * q) / (h * rMag);
    } else if (q <= 2.0) {
      gradFactor = sigma * (-0.75 * (2 - q) * (2 - q)) / (h * rMag);
    } else {
      return createVector3();
    }
    
    return vecScale(rij, gradFactor);
  }

  computeKernel(rMag: number, h: number): number {
    const q = rMag / h;
    const sigma = 1 / (Math.PI * h * h * h);
    
    if (q <= 1.0) {
      return sigma * (1 - 1.5 * q * q + 0.75 * q * q * q);
    } else if (q <= 2.0) {
      const twoMinusQ = 2 - q;
      return sigma * 0.25 * twoMinusQ * twoMinusQ * twoMinusQ;
    } else {
      return 0;
    }
  }

  hashPosition(position: Vector3, cellSize: number): number {
    const i = Math.floor(position.x / cellSize) * this.P1;
    const j = Math.floor(position.y / cellSize) * this.P2;
    const k = Math.floor(position.z / cellSize) * this.P3;
    return (i ^ j ^ k) >>> 0;
  }
}
