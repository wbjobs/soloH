import type { SellmeierCoefficients, Polarization } from '../types';
import { getCrystalById } from '../data/crystals';

export const PHYSICAL_CONSTANTS = {
  c: 299792458,
  h: 6.62607015e-34,
  epsilon0: 8.8541878128e-12,
  pi: Math.PI,
  nm_to_m: 1e-9,
  um_to_m: 1e-6,
  mm_to_m: 1e-3,
  cm_to_m: 1e-2,
  pm_to_V: 1e-12,
};

export function degToRad(deg: number): number {
  return (deg * Math.PI) / 180;
}

export function radToDeg(rad: number): number {
  return (rad * 180) / Math.PI;
}

export function calculateRefractiveIndex(
  sellmeier: SellmeierCoefficients,
  wavelength: number,
  temperature: number = 25,
  dn_dT: number = 0,
  transparencyRange?: [number, number]
): number {
  let lambda_um = wavelength / 1000;

  if (transparencyRange) {
    const [minNm, maxNm] = transparencyRange;
    if (wavelength < minNm || wavelength > maxNm) {
      lambda_um = Math.max(minNm / 1000, Math.min(maxNm / 1000, lambda_um));
    }
  }

  const lambda2 = lambda_um * lambda_um;
  const eps = 1e-12;

  const denom1 = lambda2 - sellmeier.A2 * sellmeier.A2;
  const denom2 = lambda2 - sellmeier.B2 * sellmeier.B2;

  const safeDenom1 = Math.abs(denom1) < eps ? Math.sign(denom1) * eps : denom1;
  const safeDenom2 = Math.abs(denom2) < eps ? Math.sign(denom2) * eps : denom2;

  const term1 = (sellmeier.B1 * lambda2) / safeDenom1;
  const term2 = (sellmeier.B3 * lambda2) / safeDenom2;

  let n2 = sellmeier.A1 + term1 + term2;

  if (n2 < 0.1) {
    n2 = sellmeier.A1;
  }

  let n = Math.sqrt(Math.abs(n2));

  if (n < 1.0) {
    n = 1.5;
  }

  const deltaT = temperature - 25;
  n += dn_dT * deltaT;

  return Math.max(1.0, n);
}

export function calculateRefractiveIndexByCrystal(
  crystalId: string,
  wavelength: number,
  polarization: Polarization,
  temperature: number = 25
): number {
  const crystal = getCrystalById(crystalId);
  if (!crystal) {
    throw new Error(`Crystal not found: ${crystalId}`);
  }

  const sellmeier =
    polarization === 'ordinary'
      ? crystal.sellmeier.ordinary
      : crystal.sellmeier.extraordinary || crystal.sellmeier.ordinary;

  const dn_dT =
    polarization === 'ordinary'
      ? crystal.thermoOpticCoefficients.dn_o_dT
      : crystal.thermoOpticCoefficients.dn_e_dT;

  return calculateRefractiveIndex(sellmeier, wavelength, temperature, dn_dT, crystal.transparencyRange);
}

export function calculateExtraordinaryIndex(
  nO: number,
  nE: number,
  theta: number
): number {
  const thetaRad = degToRad(theta);
  const cos2 = Math.cos(thetaRad) ** 2;
  const sin2 = Math.sin(thetaRad) ** 2;
  return 1 / Math.sqrt(cos2 / (nO * nO) + sin2 / (nE * nE));
}

export function calculateIdlerWavelength(
  pumpWavelength: number,
  signalWavelength: number
): number {
  return 1 / (1 / pumpWavelength - 1 / signalWavelength);
}

export function calculateWavevector(
  wavelength: number,
  refractiveIndex: number
): number {
  return (2 * Math.PI * refractiveIndex) / (wavelength * PHYSICAL_CONSTANTS.nm_to_m);
}

export function calculatePhaseMismatch(
  kPump: number,
  kSignal: number,
  kIdler: number,
  polingPeriod: number
): number {
  const kGrating = (2 * Math.PI) / (polingPeriod * PHYSICAL_CONSTANTS.um_to_m);
  return kPump - kSignal - kIdler - kGrating;
}

export function calculateCoherenceLength(
  deltaK: number
): number {
  if (Math.abs(deltaK) < 1e-12) return Infinity;
  return Math.PI / Math.abs(deltaK);
}

export function calculateWalkoffAngle(
  nO: number,
  nE: number,
  theta: number
): number {
  const thetaRad = degToRad(theta);
  const tanRho =
    (nO * nO - nE * nE) *
    Math.sin(2 * thetaRad) /
    (2 * (nO * nO * Math.cos(thetaRad) ** 2 + nE * nE * Math.sin(thetaRad) ** 2));
  return radToDeg(Math.atan(tanRho));
}

export function calculateGroupVelocity(
  wavelength: number,
  refractiveIndex: number,
  dn_dLambda: number
): number {
  const nGroup = refractiveIndex - wavelength * dn_dLambda;
  return PHYSICAL_CONSTANTS.c / nGroup;
}

export function calculateGroupVelocityMismatch(
  vgPump: number,
  vgSignal: number,
  vgIdler: number
): number {
  return Math.abs(1 / vgPump - 1 / vgSignal - 1 / vgIdler);
}

export function calculateEffectiveNonlinearity(
  crystalId: string,
  phaseMatchType: string,
  theta: number,
  phi: number
): number {
  const crystal = getCrystalById(crystalId);
  if (!crystal) return 0;

  const { d33, d31, d22 } = crystal.nonlinearCoefficients;
  const thetaRad = degToRad(theta);
  const phiRad = degToRad(phi);

  let deff = 0;

  if (phaseMatchType === 'type1') {
    deff =
      d31 * Math.sin(thetaRad) -
      d22 * Math.cos(thetaRad) * Math.sin(3 * phiRad) +
      d33 * Math.sin(thetaRad) * Math.cos(2 * phiRad);
  } else {
    deff =
      d22 * Math.cos(thetaRad) * Math.cos(3 * phiRad) +
      d31 * Math.sin(thetaRad) * Math.sin(2 * phiRad) -
      d33 * Math.sin(thetaRad) * Math.cos(2 * phiRad);
  }

  return Math.abs(deff);
}

export function calculateTheoreticalEfficiency(
  deff: number,
  pumpIntensity: number,
  crystalLength: number,
  deltaK: number,
  nPump: number,
  nSignal: number,
  nIdler: number,
  pumpWavelength: number
): number {
  const omegaP = (2 * Math.PI * PHYSICAL_CONSTANTS.c) / (pumpWavelength * PHYSICAL_CONSTANTS.nm_to_m);
  const deff_si = deff * PHYSICAL_CONSTANTS.pm_to_V;
  const length_si = crystalLength * PHYSICAL_CONSTANTS.mm_to_m;

  const numerator =
    8 * Math.pow(omegaP, 2) * deff_si * deff_si * pumpIntensity * length_si * length_si;
  const denominator =
    PHYSICAL_CONSTANTS.c *
    PHYSICAL_CONSTANTS.c *
    PHYSICAL_CONSTANTS.epsilon0 *
    nPump *
    nSignal *
    nIdler *
    pumpWavelength *
    PHYSICAL_CONSTANTS.nm_to_m;

  const syncFactor = deltaK * length_si / 2;
  const sinc2 = Math.sin(syncFactor) ** 2 / (syncFactor * syncFactor || 1);

  return (numerator / denominator) * sinc2 * 100;
}

export function calculateBandwidth(
  centerWavelength: number,
  crystalLength: number,
  groupVelocityMismatch: number
): number {
  const length_si = crystalLength * PHYSICAL_CONSTANTS.mm_to_m;
  const lambda2 = centerWavelength * centerWavelength * PHYSICAL_CONSTANTS.nm_to_m * PHYSICAL_CONSTANTS.nm_to_m;
  return (0.886 * lambda2) / (2 * Math.PI * PHYSICAL_CONSTANTS.c * groupVelocityMismatch * length_si) * 1e9;
}

export function calculateTemperatureTolerance(
  crystalLength: number,
  dnPump_dT: number,
  dnSignal_dT: number,
  dnIdler_dT: number,
  pumpWavelength: number,
  signalWavelength: number,
  idlerWavelength: number
): number {
  const length_si = crystalLength * PHYSICAL_CONSTANTS.mm_to_m;
  const kPump = 2 * Math.PI / (pumpWavelength * PHYSICAL_CONSTANTS.nm_to_m);
  const kSignal = 2 * Math.PI / (signalWavelength * PHYSICAL_CONSTANTS.nm_to_m);
  const kIdler = 2 * Math.PI / (idlerWavelength * PHYSICAL_CONSTANTS.nm_to_m);

  const dDeltaK_dT = kPump * dnPump_dT - kSignal * dnSignal_dT - kIdler * dnIdler_dT;
  const tolerance = 0.886 * Math.PI / (Math.abs(dDeltaK_dT) * length_si);

  return tolerance;
}

export function calculateAngleTolerance(
  crystalLength: number,
  deltaN: number,
  wavelength: number
): number {
  const length_si = crystalLength * PHYSICAL_CONSTANTS.mm_to_m;
  const wavelength_si = wavelength * PHYSICAL_CONSTANTS.nm_to_m;
  return (0.886 * wavelength_si) / (Math.PI * deltaN * length_si) * 1000;
}

export function calculateWavelengthTolerance(
  crystalLength: number,
  groupVelocityMismatch: number
): number {
  const length_si = crystalLength * PHYSICAL_CONSTANTS.mm_to_m;
  return (0.886) / (groupVelocityMismatch * length_si) * 1e-9;
}
