import { solveTridiagonalEigen, type EigenResult } from './math/eigenvalue';
import { linspace, normalize, trapz } from './math/matrix';
import { qdMaterials } from '../data/materials';
import type { QDMaterial, EnergyLevels } from '../types';

const HBAR = 1.0545718e-34;
const M0 = 9.10938356e-31;
const EV_TO_J = 1.602176634e-19;
const NM_TO_M = 1e-9;

export interface PotentialProfile {
  x: Float64Array;
  V: Float64Array;
  effectiveMass: Float64Array;
  dx: number;
}

export function buildCoreShellPotential(
  coreMaterial: QDMaterial,
  shellMaterial: QDMaterial,
  coreRadius: number,
  shellThickness: number,
  numPoints: number = 200,
  carrierType: 'electron' | 'hole' = 'electron'
): PotentialProfile {
  const coreParams = qdMaterials[coreMaterial];
  const shellParams = qdMaterials[shellMaterial];

  const totalRadius = coreRadius + shellThickness;
  const boundary = totalRadius * 2;
  const x = linspace(-boundary, boundary, numPoints);
  const dx = x[1] - x[0];
  const V = new Float64Array(numPoints);
  const effectiveMass = new Float64Array(numPoints);

  const coreBandGap = coreParams.bandGap;
  const shellBandGap = shellParams.bandGap;
  const conductionBandOffset = (shellBandGap - coreBandGap) * 0.6;
  const valenceBandOffset = (shellBandGap - coreBandGap) * 0.4;

  const coreMass = carrierType === 'electron' ? coreParams.electronMass : coreParams.holeMass;
  const shellMass = carrierType === 'electron' ? shellParams.electronMass : shellParams.holeMass;
  const barrierMass = shellMass * 1.5;

  for (let i = 0; i < numPoints; i++) {
    const r = Math.abs(x[i]);
    if (r <= coreRadius) {
      V[i] = 0;
      effectiveMass[i] = coreMass;
    } else if (r <= totalRadius) {
      const smoothFactor = Math.exp(-Math.pow((r - coreRadius) / Math.max(shellThickness * 0.1, 0.1), 2));
      V[i] = carrierType === 'electron' ? conductionBandOffset : valenceBandOffset;
      effectiveMass[i] = coreMass * smoothFactor + shellMass * (1 - smoothFactor);
    } else {
      V[i] = (carrierType === 'electron' ? conductionBandOffset : valenceBandOffset) + 10;
      effectiveMass[i] = barrierMass;
    }
  }

  return { x, V, effectiveMass, dx };
}

export function solve1DSchrodinger(
  potential: PotentialProfile,
  numEigenstates: number = 5
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

export function calculateEnergyLevels(
  qdMaterial: QDMaterial,
  shellMaterial: QDMaterial,
  coreSize: number,
  shellThickness: number,
  numPoints: number = 200,
  numEigenstates: number = 5
): EnergyLevels {
  const coreParams = qdMaterials[qdMaterial];
  const coreRadius = coreSize / 2;

  const electronPotential = buildCoreShellPotential(
    qdMaterial,
    shellMaterial,
    coreRadius,
    shellThickness,
    numPoints,
    'electron'
  );

  const holePotential = buildCoreShellPotential(
    qdMaterial,
    shellMaterial,
    coreRadius,
    shellThickness,
    numPoints,
    'hole'
  );

  for (let i = 0; i < holePotential.V.length; i++) {
    holePotential.V[i] = -holePotential.V[i];
  }

  const electronResult = solve1DSchrodinger(
    electronPotential,
    numEigenstates
  );

  const holeResult = solve1DSchrodinger(
    holePotential,
    numEigenstates
  );

  const electronLevels = electronResult.eigenvalues.map(e => coreParams.electronAffinity - e);
  const holeLevels = holeResult.eigenvalues.map(e => coreParams.electronAffinity - coreParams.bandGap - e);

  const electronWavefunctions = electronResult.eigenvectors;
  const holeWavefunctions = holeResult.eigenvectors;

  const conductionBand = coreParams.electronAffinity;
  const valenceBand = coreParams.electronAffinity - coreParams.bandGap;
  const fermiLevel = (conductionBand + valenceBand) / 2;

  return {
    conductionBand,
    valenceBand,
    electronLevels,
    holeLevels,
    fermiLevel,
    bandGap: coreParams.bandGap,
    wavefunctions: {
      electron: electronWavefunctions,
      hole: holeWavefunctions,
    },
  };
}

export function calculateOverlapIntegral(
  electronWavefunction: number[],
  holeWavefunction: number[],
  dx: number
): number {
  const n = electronWavefunction.length;
  const product = new Float64Array(n);
  const xAxis = linspace(0, dx * (n - 1), n);

  for (let i = 0; i < n; i++) {
    product[i] = electronWavefunction[i] * holeWavefunction[i];
  }

  const integral = trapz(product, xAxis);
  return integral * integral;
}

export function getPotentialProfile(
  qdMaterial: QDMaterial,
  shellMaterial: QDMaterial,
  coreSize: number,
  shellThickness: number,
  numPoints: number = 200,
  carrierType: 'electron' | 'hole' = 'electron'
): { x: number[]; V: number[]; effectiveMass: number[]; dx: number } {
  const potential = buildCoreShellPotential(
    qdMaterial,
    shellMaterial,
    coreSize / 2,
    shellThickness,
    numPoints,
    carrierType
  );

  return {
    x: Array.from(potential.x),
    V: Array.from(potential.V),
    effectiveMass: Array.from(potential.effectiveMass),
    dx: potential.dx,
  };
}
