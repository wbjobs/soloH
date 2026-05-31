import type { SimulationParams, DomainStructurePoint } from '../types';
import { PHYSICAL_CONSTANTS } from './physics';

export function generatePolingStructure(
  params: SimulationParams,
  numPoints: number = 1000
): { z: number[]; polarity: number[]; period: number[] } {
  const z: number[] = [];
  const polarity: number[] = [];
  const period: number[] = [];

  const length = params.crystalLength * PHYSICAL_CONSTANTS.mm_to_m;
  const dz = length / numPoints;

  for (let i = 0; i < numPoints; i++) {
    const currentZ = i * dz;
    z.push(currentZ);

    const currentPeriod = calculatePeriodAtPosition(params, currentZ);
    period.push(currentPeriod);

    const cumulativePhase = calculateCumulativePhase(params, currentZ);
    const pol = Math.sign(Math.cos(cumulativePhase));
    polarity.push(pol === 0 ? 1 : pol);
  }

  return { z, polarity, period };
}

export function calculatePeriodAtPosition(
  params: SimulationParams,
  z: number
): number {
  const z_mm = z / PHYSICAL_CONSTANTS.mm_to_m;
  const basePeriod = params.polingPeriod * PHYSICAL_CONSTANTS.um_to_m;

  switch (params.polingType) {
    case 'uniform':
      return basePeriod;

    case 'linear_chirp':
      return basePeriod * (1 + params.chirpRate * z_mm / 100);

    case 'quadratic_chirp':
      return (
        basePeriod *
        (1 +
          params.chirpRate * z_mm / 100 +
          params.quadraticChirpRate * z_mm * z_mm / 10000)
      );

    case 'fan':
      return basePeriod;

    case '2d':
      return basePeriod;

    default:
      return basePeriod;
  }
}

function calculateCumulativePhase(
  params: SimulationParams,
  z: number
): number {
  const numSteps = 1000;
  const dz = z / numSteps;
  let cumulativePhase = 0;

  for (let i = 0; i < numSteps; i++) {
    const currentZ = (i + 0.5) * dz;
    const currentPeriod = calculatePeriodAtPosition(params, currentZ);
    cumulativePhase += (2 * Math.PI / currentPeriod) * dz;
  }

  return cumulativePhase;
}

export function generate2DPolingStructure(
  params: SimulationParams,
  nx: number = 50,
  nz: number = 200
): DomainStructurePoint[] {
  const result: DomainStructurePoint[] = [];
  const length = params.crystalLength * PHYSICAL_CONSTANTS.mm_to_m;
  const width = 0.5 * PHYSICAL_CONSTANTS.mm_to_m;

  for (let i = 0; i < nx; i++) {
    const x = (i - nx / 2) * width / nx;
    for (let j = 0; j < nz; j++) {
      const z = j * length / nz;
      let period: number;

      if (params.polingType === 'fan') {
        const basePeriod = params.polingPeriod * PHYSICAL_CONSTANTS.um_to_m;
        period = basePeriod * (1 + params.chirpRate * x / width);
      } else if (params.polingType === '2d') {
        const basePeriodZ = params.polingPeriod * PHYSICAL_CONSTANTS.um_to_m;
        const basePeriodX = basePeriodZ * 2;
        const phaseZ = (2 * Math.PI / basePeriodZ) * z;
        const phaseX = (2 * Math.PI / basePeriodX) * x;
        const polarity = Math.sign(Math.cos(phaseZ) * Math.cos(phaseX));
        result.push({
          x,
          y: 0,
          z,
          polarity,
          period: basePeriodZ,
        });
        continue;
      } else {
        period = calculatePeriodAtPosition(params, z);
      }

      const phase = (2 * Math.PI / period) * z;
      const dutyCyclePhase = 2 * Math.PI * params.dutyCycle;
      const normalizedPhase = phase % (2 * Math.PI);
      const polarity = normalizedPhase < dutyCyclePhase ? 1 : -1;

      result.push({
        x,
        y: 0,
        z,
        polarity,
        period,
      });
    }
  }

  return result;
}

export function calculateDomainCount(
  params: SimulationParams
): number {
  const length = params.crystalLength * PHYSICAL_CONSTANTS.mm_to_m;
  const avgPeriod = params.polingPeriod * PHYSICAL_CONSTANTS.um_to_m;
  return Math.floor(length / avgPeriod);
}

export function calculateFourierComponents(
  params: SimulationParams,
  numHarmonics: number = 10
): { harmonic: number; amplitude: number }[] {
  const result: { harmonic: number; amplitude: number }[] = [];
  const dutyCycle = params.dutyCycle;

  for (let m = 1; m <= numHarmonics; m++) {
    const amplitude = (2 / (m * Math.PI)) * Math.sin(m * Math.PI * dutyCycle);
    result.push({
      harmonic: m,
      amplitude: Math.abs(amplitude),
    });
  }

  return result;
}

export function generateDomainStructurePoints(
  params: SimulationParams
): DomainStructurePoint[] {
  if (params.polingType === 'fan' || params.polingType === '2d') {
    return generate2DPolingStructure(params, 30, 100);
  }

  const result: DomainStructurePoint[] = [];
  const structure = generatePolingStructure(params, 200);
  const width = 0.2 * PHYSICAL_CONSTANTS.mm_to_m;
  const nx = 10;

  for (let i = 0; i < nx; i++) {
    const x = (i - nx / 2) * width / nx;
    for (let j = 0; j < structure.z.length; j++) {
      result.push({
        x,
        y: 0,
        z: structure.z[j],
        polarity: structure.polarity[j],
        period: structure.period[j],
      });
    }
  }

  return result;
}

export function generateDomainStructureWithErrors(
  params: SimulationParams,
  seed: number = 0,
  periodStd: number = 0.05,
  dutyCycleStd: number = 0.02
): DomainStructurePoint[] {
  const rng = createRandomGenerator(seed);

  if (params.polingType === 'fan' || params.polingType === '2d') {
    const baseStructure = generate2DPolingStructure(params, 30, 100);
    return baseStructure.map(point => {
      const periodError = rng.gaussian() * periodStd;
      const newPeriod = Math.max(1, point.period * (1 + periodError));
      return {
        ...point,
        period: newPeriod,
      };
    });
  }

  const result: DomainStructurePoint[] = [];
  const length_si = params.crystalLength * PHYSICAL_CONSTANTS.mm_to_m;
  const numSteps = Math.max(500, Math.floor(params.crystalLength * 20));
  const dz = length_si / numSteps;
  const width = 0.2 * PHYSICAL_CONSTANTS.mm_to_m;
  const nx = 10;

  let currentZ = 0;
  const polaritySequence: number[] = [];
  const zSequence: number[] = [];
  const periodSequence: number[] = [];

  while (currentZ < length_si) {
    const periodError = rng.gaussian() * periodStd;
    const localPeriod = params.polingPeriod * (1 + periodError) * PHYSICAL_CONSTANTS.um_to_m;
    const dutyCycleError = rng.gaussian() * dutyCycleStd;
    const localDutyCycle = Math.max(0.1, Math.min(0.9, params.dutyCycle + dutyCycleError));

    const positiveLength = localPeriod * localDutyCycle;
    const negativeLength = localPeriod * (1 - localDutyCycle);

    if (currentZ + positiveLength <= length_si) {
      polaritySequence.push(1);
      zSequence.push(currentZ + positiveLength / 2);
      periodSequence.push(localPeriod / PHYSICAL_CONSTANTS.um_to_m);
    }
    currentZ += positiveLength;

    if (currentZ + negativeLength <= length_si) {
      polaritySequence.push(-1);
      zSequence.push(currentZ + negativeLength / 2);
      periodSequence.push(localPeriod / PHYSICAL_CONSTANTS.um_to_m);
    }
    currentZ += negativeLength;
  }

  for (let i = 0; i < nx; i++) {
    const x = (i - nx / 2) * width / nx;
    for (let j = 0; j < zSequence.length; j++) {
      result.push({
        x,
        y: 0,
        z: zSequence[j],
        polarity: polaritySequence[j],
        period: periodSequence[j],
      });
    }
  }

  return result;
}

function createRandomGenerator(seed: number = 0) {
  let s = seed;
  function next(): number {
    s = (s * 9301 + 49297) % 233280;
    return s / 233280;
  }

  function gaussian(): number {
    let u1 = 0, u2 = 0;
    while (u1 === 0) u1 = next();
    while (u2 === 0) u2 = next();
    return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
  }

  return { next, gaussian };
}
