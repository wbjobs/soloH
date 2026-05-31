import { PHYSICAL_CONSTANTS, getBandgapAtTemperature } from '../../data/materials';
import type { Material, CalculationParams, IVPoint, QEPoint } from '../../types';
import {
  planckPhotonFlux,
  wavelengthToEnergy,
  bandgapToCutoffWavelength,
} from './blackbody';

const { q, k, m0 } = PHYSICAL_CONSTANTS;

export function intrinsicCarrierConcentration(
  bandgap: number,
  effectiveMassElectron: number,
  effectiveMassHole: number,
  temperature: number
): number {
  const Nc = 2 * Math.pow((2 * Math.PI * effectiveMassElectron * m0 * k * temperature) / (h * h), 1.5);
  const Nv = 2 * Math.pow((2 * Math.PI * effectiveMassHole * m0 * k * temperature) / (h * h), 1.5);
  return Math.sqrt(Nc * Nv) * Math.exp(-bandgap * q / (2 * k * temperature));
}

const h = PHYSICAL_CONSTANTS.h;

export function radiativeRecombination(
  n: number,
  p: number,
  radiativeCoeff: number,
  ni: number
): number {
  return radiativeCoeff * (n * p - ni * ni);
}

export function augerRecombination(
  n: number,
  p: number,
  augerCoeff: number
): number {
  return augerCoeff * (n * n * p + n * p * p);
}

export function shortCircuitCurrent(
  sourceTemperature: number,
  bandgap: number,
  reflectance: number[] = [],
  wavelengths: number[] = [],
  eqe: number = 1.0
): number {
  const cutoffWavelength = bandgapToCutoffWavelength(bandgap);
  let jsc = 0;
  const step = 2;
  
  for (let lambda = 200; lambda < cutoffWavelength; lambda += step) {
    let r = 0;
    if (wavelengths.length > 1) {
      const idx = Math.round((lambda - wavelengths[0]) / (wavelengths[1] - wavelengths[0]));
      if (idx >= 0 && idx < reflectance.length) {
        r = reflectance[idx];
      }
    }
    const flux = planckPhotonFlux(lambda, sourceTemperature);
    jsc += q * eqe * flux * (1 - r) * step * 1e-9;
  }
  
  return jsc;
}

export function openCircuitVoltage(
  jsc: number,
  bandgap: number,
  temperature: number,
  seriesResistance: number = 0,
  includeRs: boolean = true
): number {
  const Vt = k * temperature / q;
  let voc = Vt * Math.log(jsc / 1e-10 + 1);
  
  voc = Math.min(voc, bandgap / q * 0.9);
  
  if (includeRs && seriesResistance > 0) {
    voc -= jsc * seriesResistance * 0.1;
  }
  
  return Math.max(0, voc);
}

export function calculateIVCurve(
  jsc: number,
  bandgap: number,
  temperature: number,
  seriesResistance: number,
  shuntResistance: number,
  includeRadiative: boolean,
  includeAuger: boolean,
  includeRs: boolean,
  material: Material,
  numPoints: number = 100
): IVPoint[] {
  const Vt = k * temperature / q;
  
  const voc = openCircuitVoltage(jsc, bandgap, temperature, seriesResistance, includeRs);
  const ivCurve: IVPoint[] = [];
  
  const j0Rad = includeRadiative 
    ? darkCurrentRad(bandgap, temperature, material.radiativeCoeff, material.effectiveMassElectron, material.effectiveMassHole)
    : 1e-12;
  const j0Auger = includeAuger 
    ? darkCurrentAuger(bandgap, temperature, material.augerCoefficient, material.effectiveMassElectron, material.effectiveMassHole)
    : 0;
  const j0 = j0Rad + j0Auger;
  
  for (let i = 0; i < numPoints; i++) {
    const v = (i / (numPoints - 1)) * voc * 1.1;
    
    let j = jsc;
    
    const jDiode = j0 * (Math.exp(v / Vt) - 1);
    j -= jDiode;
    
    if (includeRs && seriesResistance > 0) {
      const jRs = v / (seriesResistance * 10);
      j -= jRs;
    }
    
    if (shuntResistance > 0) {
      const jShunt = v / shuntResistance;
      j -= jShunt;
    }
    
    ivCurve.push({ v, j: Math.max(0, j) });
  }
  
  return ivCurve;
}

export function calculateQuantumEfficiency(
  bandgap: number,
  material: Material,
  minWavelength: number = 200,
  maxWavelength: number = 5000,
  numPoints: number = 200
): QEPoint[] {
  const cutoffWavelength = bandgapToCutoffWavelength(bandgap);
  const qe: QEPoint[] = [];
  const step = (maxWavelength - minWavelength) / (numPoints - 1);
  
  for (let i = 0; i < numPoints; i++) {
    const wavelength = minWavelength + i * step;
    
    let eqe = 0;
    if (wavelength < cutoffWavelength) {
      const energy = wavelengthToEnergy(wavelength);
      const excessEnergy = energy - bandgap;
      
      eqe = 0.85 * Math.exp(-excessEnergy * 0.5);
      
      if (wavelength > cutoffWavelength * 0.9) {
        const tailFactor = 1 - Math.pow((wavelength / cutoffWavelength - 0.9) / 0.1, 2);
        eqe *= Math.max(0, tailFactor);
      }
    }
    
    qe.push({ wavelength, eqe: Math.max(0, Math.min(1, eqe)) });
  }
  
  return qe;
}

export function calculateFillFactor(
  ivCurve: IVPoint[]
): number {
  let maxPower = 0;
  let jsc = 0;
  let voc = 0;
  
  for (const point of ivCurve) {
    if (point.v <= 0.01) {
      jsc = Math.max(jsc, point.j);
    }
    if (point.j <= 0.001) {
      voc = Math.max(voc, point.v);
    }
    const power = point.v * point.j;
    if (power > maxPower) {
      maxPower = power;
    }
  }
  
  if (jsc * voc <= 0) return 0;
  return (maxPower / (jsc * voc)) * 100;
}

export function calculateEfficiency(
  ivCurve: IVPoint[],
  sourceTemperature: number
): number {
  const inputPower = PHYSICAL_CONSTANTS.sigma * Math.pow(sourceTemperature, 4);
  
  let maxPower = 0;
  for (const point of ivCurve) {
    const power = point.v * point.j;
    if (power > maxPower) {
      maxPower = power;
    }
  }
  
  return (maxPower / inputPower) * 100;
}

export function findMaxPowerPoint(
  ivCurve: IVPoint[]
): { maxPowerDensity: number; voltageAtMaxPower: number; currentAtMaxPower: number } {
  let maxPower = 0;
  let vmp = 0;
  let jmp = 0;
  
  for (const point of ivCurve) {
    const power = point.v * point.j;
    if (power > maxPower) {
      maxPower = power;
      vmp = point.v;
      jmp = point.j;
    }
  }
  
  return {
    maxPowerDensity: maxPower,
    voltageAtMaxPower: vmp,
    currentAtMaxPower: jmp,
  };
}

export function localCurrentDensity(
  V: number,
  jsc: number,
  j0: number,
  Vt: number,
  Rshunt: number
): number {
  const jDiode = j0 * (Math.exp(V / Vt) - 1);
  const jShunt = Rshunt > 0 ? V / Rshunt : 0;
  return Math.max(0, jsc - jDiode - jShunt);
}

export function solveTLM(
  terminalVoltage: number,
  jsc: number,
  j0: number,
  Vt: number,
  Rsheet: number,
  fingerSpacing: number,
  fingerWidth: number,
  Rshunt: number
): number {
  const s = fingerSpacing / 2;
  const dx = s / 50;
  const numPoints = Math.ceil(s / dx) + 1;
  
  let V: number[] = new Array(numPoints).fill(terminalVoltage);
  let dVdx: number[] = new Array(numPoints).fill(0);
  
  const maxIter = 50;
  const tolerance = 1e-6;
  
  for (let iter = 0; iter < maxIter; iter++) {
    let maxChange = 0;
    
    for (let i = 1; i < numPoints - 1; i++) {
      const x = i * dx;
      const localV = V[i];
      const j = localCurrentDensity(localV, jsc, j0, Vt, Rshunt);
      
      const d2Vdx2 = Rsheet * j;
      
      const V_new = (V[i-1] + V[i+1] - d2Vdx2 * dx * dx) / 2;
      const change = Math.abs(V_new - V[i]);
      maxChange = Math.max(maxChange, change);
      V[i] = V_new;
    }
    
    V[0] = terminalVoltage;
    dVdx[0] = 0;
    
    V[numPoints - 1] = V[numPoints - 2];
    
    if (maxChange < tolerance) break;
  }
  
  let totalCurrent = 0;
  for (let i = 0; i < numPoints - 1; i++) {
    const x = i * dx;
    const j = localCurrentDensity(V[i], jsc, j0, Vt, Rshunt);
    totalCurrent += j * dx;
  }
  
  totalCurrent *= 2;
  
  const totalWidth = fingerSpacing;
  const activeWidth = fingerSpacing - fingerWidth;
  
  return (totalCurrent / totalWidth) * (activeWidth / fingerSpacing);
}

export function calculateIVCurveDistributed(
  jsc: number,
  bandgap: number,
  temperature: number,
  seriesResistance: number,
  shuntResistance: number,
  includeRadiative: boolean,
  includeAuger: boolean,
  includeRs: boolean,
  material: Material,
  Rsheet: number,
  fingerSpacing: number,
  fingerWidth: number,
  numPoints: number = 100
): IVPoint[] {
  const Vt = k * temperature / q;
  
  const j0Rad = includeRadiative 
    ? darkCurrentRad(bandgap, temperature, material.radiativeCoeff, material.effectiveMassElectron, material.effectiveMassHole)
    : 1e-12;
  const j0Auger = includeAuger 
    ? darkCurrentAuger(bandgap, temperature, material.augerCoefficient, material.effectiveMassElectron, material.effectiveMassHole)
    : 0;
  const j0 = j0Rad + j0Auger;
  
  const voc = openCircuitVoltage(jsc, bandgap, temperature, seriesResistance, includeRs);
  const ivCurve: IVPoint[] = [];
  
  for (let i = 0; i < numPoints; i++) {
    const vTerm = (i / (numPoints - 1)) * voc * 1.1;
    
    let j = 0;
    if (includeRs && Rsheet > 0 && fingerSpacing > 0) {
      j = solveTLM(vTerm, jsc, j0, Vt, Rsheet, fingerSpacing, fingerWidth, shuntResistance);
      
      if (seriesResistance > 0) {
        const vDrop = j * seriesResistance;
        j = solveTLM(vTerm - vDrop, jsc, j0, Vt, Rsheet, fingerSpacing, fingerWidth, shuntResistance);
      }
    } else {
      j = localCurrentDensity(vTerm, jsc, j0, Vt, shuntResistance);
      
      if (includeRs && seriesResistance > 0) {
        const vDrop = j * seriesResistance;
        j = localCurrentDensity(vTerm - vDrop, jsc, j0, Vt, shuntResistance);
      }
    }
    
    ivCurve.push({ v: vTerm, j: Math.max(0, j) });
  }
  
  return ivCurve;
}

export function seriesResistanceCorrectionFactor(
  jsc: number,
  Rsheet: number,
  fingerSpacing: number
): number {
  const s = fingerSpacing / 2;
  const j0 = 1e-12;
  const Vt = 0.026;
  
  const V = jsc * Rsheet * s * s / 2;
  const correction = 1 - V / (Vt * Math.log(jsc / j0 + 1));
  
  return Math.max(0.5, Math.min(1.0, correction));
}

export function calculateJscWithQE(
  sourceTemperature: number,
  qeCurve: QEPoint[],
  reflectance: number[] = [],
  refWavelengths: number[] = []
): number {
  let jsc = 0;
  
  for (let i = 0; i < qeCurve.length - 1; i++) {
    const { wavelength, eqe } = qeCurve[i];
    const nextWavelength = qeCurve[i + 1].wavelength;
    const step = nextWavelength - wavelength;
    
    let r = 0;
    if (refWavelengths.length > 1) {
      const idx = Math.round((wavelength - refWavelengths[0]) / (refWavelengths[1] - refWavelengths[0]));
      if (idx >= 0 && idx < reflectance.length) {
        r = reflectance[idx];
      }
    }
    
    const flux = planckPhotonFlux(wavelength, sourceTemperature);
    jsc += q * eqe * flux * (1 - r) * step * 1e-9;
  }
  
  return jsc;
}

export function temperatureDependentBandgap(
  Eg0: number,
  alpha: number,
  beta: number,
  T: number
): number {
  return Eg0 - (alpha * T * T) / (T + beta);
}

export function darkCurrentRad(
  bandgap: number,
  temperature: number,
  radiativeCoeff: number,
  effectiveMassElectron: number,
  effectiveMassHole: number
): number {
  const { k, q, m0, h } = PHYSICAL_CONSTANTS;
  
  const Nc = 2 * Math.pow((2 * Math.PI * effectiveMassElectron * m0 * k * temperature) / (h * h), 1.5);
  const Nv = 2 * Math.pow((2 * Math.PI * effectiveMassHole * m0 * k * temperature) / (h * h), 1.5);
  const ni = Math.sqrt(Nc * Nv) * Math.exp(-bandgap * q / (2 * k * temperature));
  
  return q * radiativeCoeff * ni * ni;
}

export function darkCurrentAuger(
  bandgap: number,
  temperature: number,
  augerCoeff: number,
  effectiveMassElectron: number,
  effectiveMassHole: number
): number {
  const { k, q, m0, h } = PHYSICAL_CONSTANTS;
  
  const Nc = 2 * Math.pow((2 * Math.PI * effectiveMassElectron * m0 * k * temperature) / (h * h), 1.5);
  const Nv = 2 * Math.pow((2 * Math.PI * effectiveMassHole * m0 * k * temperature) / (h * h), 1.5);
  const ni = Math.sqrt(Nc * Nv) * Math.exp(-bandgap * q / (2 * k * temperature));
  
  return q * augerCoeff * Math.pow(ni, 3);
}

export function performBandgapScan(
  sourceTemperature: number,
  minBandgap: number = 0.3,
  maxBandgap: number = 2.0,
  numBandgaps: number = 30,
  minTemp: number = 600,
  maxTemp: number = 2000,
  numTemps: number = 20,
  materialTemplate: Material,
  cellTemperature: number = 300
): { bandgaps: number[]; temperatures: number[]; efficiencies: number[][] } {
  const bandgaps: number[] = [];
  const temperatures: number[] = [];
  const efficiencies: number[][] = [];
  
  for (let i = 0; i < numBandgaps; i++) {
    bandgaps.push(minBandgap + (i / (numBandgaps - 1)) * (maxBandgap - minBandgap));
  }
  
  for (let j = 0; j < numTemps; j++) {
    temperatures.push(minTemp + (j / (numTemps - 1)) * (maxTemp - minTemp));
  }
  
  for (let i = 0; i < numBandgaps; i++) {
    efficiencies[i] = [];
    for (let j = 0; j < numTemps; j++) {
      const bg300 = bandgaps[i];
      const sourceTemp = temperatures[j];
      
      const bgAtCellTemp = temperatureDependentBandgap(
        bg300 + 0.1,
        Math.abs(materialTemplate.bandgapTempCoeff) * 1000,
        300,
        cellTemperature
      );
      
      const mat = { ...materialTemplate, bandgap: bgAtCellTemp };
      
      const jsc = shortCircuitCurrent(sourceTemp, bgAtCellTemp);
      const ivCurve = calculateIVCurve(
        jsc, bgAtCellTemp, cellTemperature, 0.1, 1000, true, true, true, mat
      );
      const eff = calculateEfficiency(ivCurve, sourceTemp);
      
      efficiencies[i][j] = eff;
    }
  }
  
  return { bandgaps, temperatures, efficiencies };
}

export function concentratedJsc(
  jscOneSun: number,
  concentrationRatio: number
): number {
  return jscOneSun * concentrationRatio;
}

export function concentratedVoc(
  vocOneSun: number,
  jscOneSun: number,
  concentrationRatio: number,
  temperature: number,
  idealityFactor: number = 1.0
): number {
  const { k, q } = PHYSICAL_CONSTANTS;
  const Vt = k * temperature / q;
  return vocOneSun + idealityFactor * Vt * Math.log(concentrationRatio);
}

export function concentrationFillFactor(
  ffOneSun: number,
  vocOneSun: number,
  concentrationRatio: number,
  temperature: number,
  seriesResistance: number,
  jscOneSun: number,
  idealityFactor: number = 1.0
): number {
  const { k, q } = PHYSICAL_CONSTANTS;
  const Vt = k * temperature / q;
  const vocConc = concentratedVoc(vocOneSun, jscOneSun, concentrationRatio, temperature, idealityFactor);
  const jscConc = concentratedJsc(jscOneSun, concentrationRatio);
  
  const vocNorm = vocConc / Vt;
  const rsNorm = seriesResistance * jscConc / vocConc;
  
  const ff = ffOneSun * (1 - (vocNorm * rsNorm) / (vocNorm + 1) * Math.log(vocNorm + 1) / vocNorm);
  
  return Math.max(0.5, Math.min(ffOneSun, ff));
}

export function cellTemperatureRise(
  concentrationRatio: number,
  inputPower: number,
  efficiency: number,
  thermalResistance: number = 0.5
): number {
  const dissipatedPower = inputPower * concentrationRatio * (1 - efficiency / 100);
  return dissipatedPower * thermalResistance;
}

export function calculateConcentrationPerformance(
  jscOneSun: number,
  vocOneSun: number,
  ffOneSun: number,
  efficiencyOneSun: number,
  sourceTemperature: number,
  cellTemperature: number,
  concentrationRatio: number,
  seriesResistance: number,
  idealityFactor: number = 1.0
): { cr: number; jsc: number; voc: number; ff: number; efficiency: number; tempRise: number; actualTemp: number } {
  const { sigma } = PHYSICAL_CONSTANTS;
  const inputPower = sigma * Math.pow(sourceTemperature, 4);
  
  let actualTemp = cellTemperature;
  let efficiency = efficiencyOneSun;
  
  for (let iter = 0; iter < 5; iter++) {
    const jscConc = concentratedJsc(jscOneSun, concentrationRatio);
    const vocConc = concentratedVoc(vocOneSun, jscOneSun, concentrationRatio, actualTemp, idealityFactor);
    const ffConc = concentrationFillFactor(ffOneSun, vocOneSun, concentrationRatio, actualTemp, seriesResistance, jscOneSun, idealityFactor);
    
    efficiency = (jscConc * vocConc * ffConc) / inputPower * 100;
    const tempRise = cellTemperatureRise(concentrationRatio, inputPower, efficiency);
    actualTemp = cellTemperature + tempRise;
  }
  
  const tempRise = actualTemp - cellTemperature;
  const jscConc = concentratedJsc(jscOneSun, concentrationRatio);
  const vocConc = concentratedVoc(vocOneSun, jscOneSun, concentrationRatio, actualTemp, idealityFactor);
  const ffConc = concentrationFillFactor(ffOneSun, vocOneSun, concentrationRatio, actualTemp, seriesResistance, jscOneSun, idealityFactor);
  
  return {
    cr: concentrationRatio,
    jsc: jscConc,
    voc: vocConc,
    ff: ffConc,
    efficiency,
    tempRise,
    actualTemp,
  };
}

export function performConcentrationScan(
  jscOneSun: number,
  vocOneSun: number,
  ffOneSun: number,
  efficiencyOneSun: number,
  sourceTemperature: number,
  cellTemperature: number,
  seriesResistance: number,
  minCR: number = 1,
  maxCR: number = 1000,
  numPoints: number = 30
): { curve: { cr: number; efficiency: number; jsc: number }[]; optimumCR: number; maxEff: number } {
  const curve: { cr: number; efficiency: number; jsc: number }[] = [];
  let maxEff = 0;
  let optimumCR = 1;
  
  for (let i = 0; i < numPoints; i++) {
    const cr = minCR * Math.pow(maxCR / minCR, i / (numPoints - 1));
    const result = calculateConcentrationPerformance(
      jscOneSun, vocOneSun, ffOneSun, efficiencyOneSun,
      sourceTemperature, cellTemperature, cr, seriesResistance
    );
    
    curve.push({ cr, efficiency: result.efficiency, jsc: result.jsc });
    
    if (result.efficiency > maxEff) {
      maxEff = result.efficiency;
      optimumCR = cr;
    }
  }
  
  return { curve, optimumCR, maxEff };
}

export function carnotEfficiency(
  hotTemperature: number,
  coldTemperature: number
): number {
  return (1 - coldTemperature / hotTemperature) * 100;
}

export function tegEfficiency(
  ZT: number,
  hotTemperature: number,
  coldTemperature: number
): number {
  const Th = hotTemperature;
  const Tc = coldTemperature;
  const Tavg = (Th + Tc) / 2;
  
  const carnot = (Th - Tc) / Th;
  const sqrtTerm = Math.sqrt(1 + ZT * Tavg);
  const numerator = (sqrtTerm - 1) * (Th - Tc);
  const denominator = (sqrtTerm + Tc / Th) * Th;
  
  return (numerator / denominator) * 100;
}

export function calculateWasteHeatRecovery(
  tpvEfficiency: number,
  sourceTemperature: number,
  cellTemperature: number,
  coldSideTemperature: number,
  ZT: number = 1.0,
  customTEGEfficiency?: number
): {
  wasteHeatDensity: number;
  totalWasteHeat: number;
  tegOutputPower: number;
  tegEfficiencyActual: number;
  systemTotalEfficiency: number;
  heatRejectionTemperature: number;
  carnotEff: number;
} {
  const { sigma } = PHYSICAL_CONSTANTS;
  
  const inputPower = sigma * Math.pow(sourceTemperature, 4);
  const tpvOutput = inputPower * tpvEfficiency / 100;
  const wasteHeatDensity = inputPower - tpvOutput;
  
  const heatRejectionTemp = Math.max(cellTemperature, coldSideTemperature + 20);
  
  const carnotEff = carnotEfficiency(heatRejectionTemp, coldSideTemperature);
  const tegEff = customTEGEfficiency ?? tegEfficiency(ZT, heatRejectionTemp, coldSideTemperature);
  
  const tegOutputPower = wasteHeatDensity * tegEff / 100;
  const totalOutput = tpvOutput + tegOutputPower;
  const systemTotalEfficiency = (totalOutput / inputPower) * 100;
  
  return {
    wasteHeatDensity,
    totalWasteHeat: wasteHeatDensity,
    tegOutputPower,
    tegEfficiencyActual: tegEff,
    systemTotalEfficiency,
    heatRejectionTemperature: heatRejectionTemp,
    carnotEff,
  };
}

export function arrheniusAccelerationFactor(
  activationEnergy: number,
  operatingTemperature: number,
  referenceTemperature: number = 300
): number {
  const { k } = PHYSICAL_CONSTANTS;
  const Ea = activationEnergy * 1.602e-19;
  
  return Math.exp(
    (Ea / k) * (1 / referenceTemperature - 1 / operatingTemperature)
  );
}

export function calculateLifetime(
  referenceLifetime: number,
  activationEnergy: number,
  operatingTemperature: number,
  referenceTemperature: number = 300
): {
  estimatedLifetime: number;
  accelerationFactor: number;
  degradationRate: number;
} {
  const AF = arrheniusAccelerationFactor(activationEnergy, operatingTemperature, referenceTemperature);
  const estimatedLifetime = referenceLifetime / AF;
  const degradationRate = 1 / estimatedLifetime;
  
  return {
    estimatedLifetime,
    accelerationFactor: AF,
    degradationRate,
  };
}

export function performLifetimeScan(
  referenceLifetime: number,
  activationEnergy: number,
  minTemp: number = 300,
  maxTemp: number = 500,
  numPoints: number = 30,
  referenceTemperature: number = 300
): { temperature: number; lifetime: number }[] {
  const curve: { temperature: number; lifetime: number }[] = [];
  
  for (let i = 0; i < numPoints; i++) {
    const temp = minTemp + (i / (numPoints - 1)) * (maxTemp - minTemp);
    const result = calculateLifetime(referenceLifetime, activationEnergy, temp, referenceTemperature);
    curve.push({ temperature: temp, lifetime: result.estimatedLifetime });
  }
  
  return curve;
}

export function calculateLifetimePrediction(
  referenceLifetime: number,
  activationEnergy: number,
  operatingTemperature: number,
  referenceTemperature: number = 300,
  operatingHours: number = 0
): {
  estimatedLifetime: number;
  accelerationFactor: number;
  remainingLifetime: number;
  degradationRate: number;
  lifetimeCurve: { temperature: number; lifetime: number }[];
  mtbf: number;
  failureRate: number;
} {
  const lifetimeResult = calculateLifetime(
    referenceLifetime, activationEnergy, operatingTemperature, referenceTemperature
  );
  
  const remainingLifetime = Math.max(0, lifetimeResult.estimatedLifetime - operatingHours);
  const mtbf = lifetimeResult.estimatedLifetime / 0.693;
  const failureRate = 1 / mtbf;
  
  const lifetimeCurve = performLifetimeScan(
    referenceLifetime, activationEnergy, 300, 500, 30, referenceTemperature
  );
  
  return {
    estimatedLifetime: lifetimeResult.estimatedLifetime,
    accelerationFactor: lifetimeResult.accelerationFactor,
    remainingLifetime,
    degradationRate: lifetimeResult.degradationRate,
    lifetimeCurve,
    mtbf,
    failureRate,
  };
}
