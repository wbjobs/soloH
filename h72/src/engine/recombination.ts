import { linspace } from './math/matrix';
import { qdMaterials } from '../data/materials';
import { calculateOverlapIntegral } from './schrodinger';
import { calculateAngularDistribution } from './angularDistribution';
import type { QDMaterial, EnergyLevels, RecombinationResults, EmissionSpectrum, TransportLayerMaterial, ElectrodeMaterial } from '../types';

const HBAR = 1.0545718e-34;
const C = 2.99792458e8;
const E = 1.602176634e-19;
const EPSILON_0 = 8.854187817e-12;
const NM_TO_M = 1e-9;
const EV_TO_J = 1.602176634e-19;
const KB = 1.380649e-23;
const M0 = 9.10938356e-31;

export function calculateThermalVelocity(effectiveMass: number, temperature: number): number {
  return Math.sqrt(3 * KB * temperature / (effectiveMass * M0));
}

export function calculateSRHRate(
  n: number,
  p: number,
  ni: number,
  Nt: number,
  sigmaN: number,
  sigmaP: number,
  Et: number,
  Ei: number,
  vThN: number,
  vThP: number,
  temperature: number
): number {
  const kT = KB * temperature / EV_TO_J;
  
  const tauN = 1 / (sigmaN * vThN * Nt);
  const tauP = 1 / (sigmaP * vThP * Nt);
  
  const exp1 = Math.exp((Et - Ei) / kT);
  const exp2 = Math.exp((Ei - Et) / kT);
  
  const numerator = n * p - ni * ni;
  const denominator = tauP * (n + ni * exp1) + tauN * (p + ni * exp2);
  
  if (Math.abs(denominator) < 1e-30) return 0;
  
  return numerator / denominator;
}

export function calculateAugerRate(
  n: number,
  p: number,
  Cn: number,
  Cp: number
): number {
  return Cn * n * n * p + Cp * n * p * p;
}

export function calculateIntrinsicCarrierConcentration(
  bandGap: number,
  electronMass: number,
  holeMass: number,
  temperature: number
): number {
  const kT = KB * temperature;
  const h = 2 * Math.PI * HBAR;
  
  const Nc = 2 * Math.pow(2 * Math.PI * electronMass * M0 * kT / (h * h), 1.5);
  const Nv = 2 * Math.pow(2 * Math.PI * holeMass * M0 * kT / (h * h), 1.5);
  
  return Math.sqrt(Nc * Nv) * Math.exp(-bandGap * EV_TO_J / (2 * kT));
}

export function calculateRadiativeRate(
  energyLevels: EnergyLevels,
  qdMaterial: QDMaterial,
  temperature: number = 300,
  currentDensity: number = 1,
  numPoints: number = 200
): RecombinationResults {
  const material = qdMaterials[qdMaterial];

  const electronGroundState = energyLevels.electronLevels[0];
  const holeGroundState = energyLevels.holeLevels[0];
  const transitionEnergy = Math.abs(electronGroundState - holeGroundState);

  let overlapIntegral = 0.8;
  if (energyLevels.wavefunctions) {
    const dx = (10 * NM_TO_M) / numPoints;
    overlapIntegral = calculateOverlapIntegral(
      energyLevels.wavefunctions.electron[0],
      energyLevels.wavefunctions.hole[0],
      dx
    );
  }

  const omega = transitionEnergy * EV_TO_J / HBAR;
  const n = material.refractiveIndex;
  const dipoleMoment = 1e-29;

  const prefactor = (4 * E * E * omega * omega * omega * n) / 
                    (3 * EPSILON_0 * HBAR * C * C * C);
  const radiativeRate = prefactor * dipoleMoment * dipoleMoment * overlapIntegral;

  const J = currentDensity;
  const qdArea = 1e-10;
  const carrierDensity = J * 1e-3 / (E * 1e-4 * 1e-9) * 1e-6;
  const nCarrier = Math.max(1e15, Math.sqrt(carrierDensity));
  const pCarrier = nCarrier;

  const ni = calculateIntrinsicCarrierConcentration(
    material.bandGap,
    material.electronMass,
    material.holeMass,
    temperature
  );

  const Nt = material.interfaceStateDensity || 1e12;
  const sigmaN = material.electronCaptureCrossSection || 1e-15;
  const sigmaP = material.holeCaptureCrossSection || 1e-15;
  const Et = material.defectEnergyLevel || 0.5;
  const Ei = material.bandGap / 2;
  const vThN = calculateThermalVelocity(material.electronMass, temperature);
  const vThP = calculateThermalVelocity(material.holeMass, temperature);

  const srhRate = calculateSRHRate(
    nCarrier, pCarrier, ni, Nt, sigmaN, sigmaP, Et, Ei, vThN, vThP, temperature
  );

  const Cn = material.augerCoefficientN || 1e-28;
  const Cp = material.augerCoefficientP || 5e-29;
  const augerRate = calculateAugerRate(nCarrier, pCarrier, Cn, Cp);

  const jFactor = 1 + 0.3 * Math.log10(Math.max(1, J));
  const srhRateScaled = srhRate * Math.sqrt(jFactor);
  const augerRateScaled = augerRate * Math.pow(J / 10, 0.7);

  const nonRadiativeRate = srhRateScaled + augerRateScaled;
  const totalRate = radiativeRate + nonRadiativeRate;
  const iqe = radiativeRate / totalRate;

  const lightExtractionEfficiency = 0.25;
  const eqe = iqe * lightExtractionEfficiency;

  return {
    radiativeRate,
    nonRadiativeRate,
    srhRate: srhRateScaled,
    augerRate: augerRateScaled,
    iqe,
    eqe,
    overlapIntegral,
    currentDensity,
  };
}

export function calculateEmissionSpectrum(
  energyLevels: EnergyLevels,
  recombination: RecombinationResults,
  qdMaterial: QDMaterial,
  deviceStructure: {
    anode: ElectrodeMaterial;
    anodeThickness: number;
    htl: TransportLayerMaterial;
    htlThickness: number;
    qdLayerThickness: number;
    etl: TransportLayerMaterial;
    etlThickness: number;
    cathode: ElectrodeMaterial;
  },
  temperature: number = 300,
  wavelengthRange: [number, number] = [400, 800],
  numPoints: number = 200,
  calculateAngular: boolean = true
): EmissionSpectrum {
  const electronGroundState = energyLevels.electronLevels[0];
  const holeGroundState = energyLevels.holeLevels[0];
  const transitionEnergy = Math.abs(electronGroundState - holeGroundState);

  const peakWavelength = 1240 / transitionEnergy;
  const fwhm = 30 + 5 * (temperature / 300);

  const wavelengths = linspace(wavelengthRange[0], wavelengthRange[1], numPoints);
  const spectrumData: { wavelength: number; intensity: number }[] = [];

  const sigma = fwhm / (2 * Math.sqrt(2 * Math.log(2)));

  for (let i = 0; i < numPoints; i++) {
    const lambda = wavelengths[i];
    const gaussian = Math.exp(-Math.pow(lambda - peakWavelength, 2) / (2 * sigma * sigma));

    const photonEnergy = 1240 / lambda;
    const boltzmannFactor = Math.exp(-Math.abs(photonEnergy - transitionEnergy) * EV_TO_J / (1.38e-23 * temperature));

    const intensity = gaussian * boltzmannFactor * recombination.iqe;

    spectrumData.push({
      wavelength: lambda,
      intensity,
    });
  }

  const maxIntensity = Math.max(...spectrumData.map(d => d.intensity));
  for (const point of spectrumData) {
    point.intensity /= maxIntensity;
  }

  const result: EmissionSpectrum = {
    peakWavelength,
    fwhm,
    spectrumData,
  };

  if (calculateAngular) {
    result.angularDistribution = calculateAngularDistribution(
      peakWavelength,
      qdMaterial,
      deviceStructure,
      91
    );
  }

  return result;
}

export function calculateJointDensityOfStates(
  energy: number,
  dimensionality: '0D' | '2D' | '3D' = '0D',
  electronMass: number,
  holeMass: number,
  bandGap: number
): number {
  const reducedMass = (electronMass * holeMass) / (electronMass + holeMass);
  const m0 = 9.10938356e-31;
  const hbar = 1.0545718e-34;

  if (energy < bandGap) return 0;

  const kineticEnergy = (energy - bandGap) * 1.602176634e-19;

  switch (dimensionality) {
    case '0D': {
      const energyLevels = [0.1, 0.3, 0.5];
      const linewidth = 0.02 * 1.602176634e-19;
      let dos = 0;
      for (const level of energyLevels) {
        const levelEnergy = level * 1.602176634e-19;
        dos += Math.exp(-Math.pow(kineticEnergy - levelEnergy, 2) / (2 * linewidth * linewidth));
      }
      return dos / (Math.sqrt(2 * Math.PI) * linewidth);
    }
    case '2D': {
      return (reducedMass * m0) / (Math.PI * hbar * hbar);
    }
    case '3D': {
      return (Math.sqrt(2) * Math.pow(reducedMass * m0, 1.5) * Math.sqrt(kineticEnergy)) /
             (Math.PI * Math.PI * Math.pow(hbar, 3));
    }
  }
}

export function einsteinACoefficient(
  transitionEnergy: number,
  dipoleMoment: number,
  refractiveIndex: number,
  overlapIntegral: number
): number {
  const omega = transitionEnergy * EV_TO_J / HBAR;
  const n = refractiveIndex;

  return (4 * E * E * omega * omega * omega * n * dipoleMoment * dipoleMoment * overlapIntegral) /
         (3 * EPSILON_0 * HBAR * C * C * C);
}

export function spontaneousEmissionRate(
  transitionEnergy: number,
  jointDOS: number,
  dipoleMoment: number,
  refractiveIndex: number,
  overlapIntegral: number
): number {
  const A = einsteinACoefficient(transitionEnergy, dipoleMoment, refractiveIndex, overlapIntegral);
  return A * jointDOS;
}
