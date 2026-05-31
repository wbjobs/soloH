import { solveTridiagonalEigen, type EigenResult } from './math/eigenvalue';
import { linspace, normalize } from './math/matrix';
import { qdMaterials } from '../data/materials';
import type { QDMaterial, CoupledEnergyLevels, MQWParams } from '../types';

const HBAR = 1.0545718e-34;
const M0 = 9.10938356e-31;
const EV_TO_J = 1.602176634e-19;
const NM_TO_M = 1e-9;

export function buildMQWPotential(
  mqwParams: MQWParams,
  numPoints: number = 500,
  carrierType: 'electron' | 'hole' = 'electron'
): { x: Float64Array; V: Float64Array; effectiveMass: Float64Array; dx: number } {
  const { numWells, wellWidth, barrierWidth, wellMaterial, barrierMaterial } = mqwParams;
  
  const wellParams = qdMaterials[wellMaterial];
  const barrierParams = qdMaterials[barrierMaterial];
  
  const wellBandGap = wellParams.bandGap;
  const barrierBandGap = barrierParams.bandGap;
  const bandOffset = carrierType === 'electron' 
    ? (barrierBandGap - wellBandGap) * 0.6 
    : (barrierBandGap - wellBandGap) * 0.4;
  
  const totalLength = numWells * wellWidth + (numWells + 1) * barrierWidth;
  const boundary = totalLength * 1.2;
  
  const x = linspace(-boundary, boundary, numPoints);
  const dx = x[1] - x[0];
  const V = new Float64Array(numPoints);
  const effectiveMass = new Float64Array(numPoints);
  
  const wellMass = carrierType === 'electron' ? wellParams.electronMass : wellParams.holeMass;
  const barrierMass = carrierType === 'electron' ? barrierParams.electronMass : barrierParams.holeMass;
  
  const startX = -totalLength / 2;
  
  for (let i = 0; i < numPoints; i++) {
    const pos = x[i] - startX;
    const period = wellWidth + barrierWidth;
    const periodPos = pos % period;
    
    const isBarrierRegion = pos < 0 || pos > totalLength || periodPos < barrierWidth / 2 || periodPos > barrierWidth / 2 + wellWidth;
    
    if (isBarrierRegion) {
      V[i] = bandOffset;
      effectiveMass[i] = barrierMass;
    } else {
      V[i] = 0;
      effectiveMass[i] = wellMass;
    }
  }
  
  for (let i = 0; i < numPoints; i++) {
    const pos = x[i] - startX;
    if (Math.abs(pos) > totalLength / 2) {
      V[i] = bandOffset + 5;
    }
  }
  
  return { x, V, effectiveMass, dx };
}

export function solve1DSchrodingerMQW(
  potential: { x: Float64Array; V: Float64Array; effectiveMass: Float64Array; dx: number },
  numEigenstates: number = 10
): EigenResult {
  const { x, V, effectiveMass, dx } = potential;
  const n = x.length;
  const dxM = dx * NM_TO_M;
  const hbarSqOver2 = (HBAR * HBAR) / (2 * M0) / EV_TO_J;
  
  const diag = new Float64Array(n);
  const offDiag = new Float64Array(n - 1);
  
  for (let i = 0; i < n; i++) {
    const m = effectiveMass[i];
    const mPrev = i > 0 ? effectiveMass[i - 1] : m;
    const mNext = i < n - 1 ? effectiveMass[i + 1] : m;
    
    const mAvg = (mPrev + 2 * m + mNext) / 4;
    const hbarSqOver2m = hbarSqOver2 / mAvg;
    
    diag[i] = 2 * hbarSqOver2m / (dxM * dxM) + V[i];
  }
  
  for (let i = 0; i < n - 1; i++) {
    const m1 = effectiveMass[i];
    const m2 = effectiveMass[i + 1];
    const mAvg = 2 * m1 * m2 / (m1 + m2);
    const hbarSqOver2m = hbarSqOver2 / mAvg;
    offDiag[i] = -hbarSqOver2m / (dxM * dxM);
  }
  
  const result = solveTridiagonalEigen(diag, offDiag, numEigenstates);
  
  const normalizedEigenvectors: number[][] = [];
  for (let i = 0; i < Math.min(numEigenstates, result.eigenvectors.length); i++) {
    const vec = new Float64Array(result.eigenvectors[i]);
    const normalized = normalize(vec, dxM);
    normalizedEigenvectors.push(Array.from(normalized));
  }
  
  return {
    eigenvalues: result.eigenvalues.slice(0, numEigenstates),
    eigenvectors: normalizedEigenvectors,
  };
}

export function calculateCouplingStrength(
  wavefunction1: number[],
  wavefunction2: number[],
  potential: number[],
  dx: number
): number {
  let coupling = 0;
  const dxM = dx * NM_TO_M;
  
  for (let i = 0; i < wavefunction1.length; i++) {
    coupling += wavefunction1[i] * potential[i] * wavefunction2[i] * dxM;
  }
  
  return Math.abs(coupling);
}

export function calculateWavefunctionOverlap(
  wavefunction1: number[],
  wavefunction2: number[],
  dx: number
): number {
  let overlap = 0;
  const dxM = dx * NM_TO_M;
  
  for (let i = 0; i < wavefunction1.length; i++) {
    overlap += Math.abs(wavefunction1[i] * wavefunction2[i]) * dxM;
  }
  
  return overlap;
}

export function calculateMinibandWidth(
  eigenvalues: number[],
  numWells: number
): number {
  if (eigenvalues.length < numWells) {
    return 0;
  }
  
  const bandLevels = eigenvalues.slice(0, numWells);
  return Math.max(...bandLevels) - Math.min(...bandLevels);
}

export function analyzeMQWCoupling(
  mqwParams: MQWParams,
  numPoints: number = 500
): CoupledEnergyLevels {
  const electronPotential = buildMQWPotential(mqwParams, numPoints, 'electron');
  const holePotential = buildMQWPotential(mqwParams, numPoints, 'hole');
  
  const numStates = Math.max(10, mqwParams.numWells * 3);
  const electronResult = solve1DSchrodingerMQW(electronPotential, numStates);
  
  for (let i = 0; i < holePotential.V.length; i++) {
    holePotential.V[i] = -holePotential.V[i];
  }
  
  const holeResult = solve1DSchrodingerMQW(holePotential, numStates);
  
  const electronLevels = electronResult.eigenvalues;
  const holeLevels = holeResult.eigenvalues;
  
  const electronMiniband = calculateMinibandWidth(electronLevels, mqwParams.numWells);
  const holeMiniband = calculateMinibandWidth(holeLevels, mqwParams.numWells);
  
  const totalMinibandWidth = electronMiniband + holeMiniband;
  
  const potentialBarrier: number[] = [];
  for (let i = 0; i < electronPotential.V.length; i++) {
    potentialBarrier.push(electronPotential.V[i] > 0 ? 1 : 0);
  }
  
  let totalCoupling = 0;
  const overlaps: number[] = [];
  
  for (let i = 0; i < mqwParams.numWells - 1; i++) {
    if (i + 1 < electronResult.eigenvectors.length) {
      const coupling = calculateCouplingStrength(
        electronResult.eigenvectors[i],
        electronResult.eigenvectors[i + 1],
        potentialBarrier,
        electronPotential.dx
      );
      totalCoupling += coupling;
      
      const overlap = calculateWavefunctionOverlap(
        electronResult.eigenvectors[i],
        electronResult.eigenvectors[i + 1],
        electronPotential.dx
      );
      overlaps.push(overlap);
    }
  }
  
  const avgCoupling = mqwParams.numWells > 1 ? totalCoupling / (mqwParams.numWells - 1) : 0;
  const barrierThickness = mqwParams.barrierWidth;
  const couplingStrength = avgCoupling * Math.exp(barrierThickness / 2);
  
  const splitLevels = electronLevels.slice(0, mqwParams.numWells);
  
  return {
    minibandWidth: totalMinibandWidth,
    couplingStrength,
    splitLevels,
    wavefunctionOverlaps: overlaps,
  };
}

export function calculateDensityOfStatesMQW(
  energy: number,
  mqwParams: MQWParams,
  coupledEnergyLevels: CoupledEnergyLevels
): number {
  const { numWells, wellWidth, barrierWidth } = mqwParams;
  const { minibandWidth, splitLevels } = coupledEnergyLevels;
  
  const linewidth = Math.max(0.01, minibandWidth / numWells);
  
  let dos = 0;
  
  for (const level of splitLevels) {
    const gaussian = Math.exp(-Math.pow(energy - level, 2) / (2 * linewidth * linewidth));
    dos += numWells * gaussian;
  }
  
  return dos / (Math.sqrt(2 * Math.PI) * linewidth);
}

export function calculateGainMQW(
  energy: number,
  carrierDensity: number,
  mqwParams: MQWParams,
  coupledEnergyLevels: CoupledEnergyLevels,
  temperature: number = 300
): number {
  const kT = 8.617e-5 * temperature;
  const { numWells } = mqwParams;
  const { splitLevels } = coupledEnergyLevels;
  
  let gain = 0;
  const linewidth = 0.02;
  
  for (const level of splitLevels) {
    const transitionEnergy = level;
    const occupation = 1 / (1 + Math.exp((transitionEnergy - 0.1) / kT));
    const invertedPopulation = 2 * occupation - 1;
    
    const gaussian = Math.exp(-Math.pow(energy - transitionEnergy, 2) / (2 * linewidth * linewidth));
    const peakGain = 1e-16 * carrierDensity / (1e17);
    
    gain += numWells * peakGain * invertedPopulation * gaussian;
  }
  
  return gain;
}
