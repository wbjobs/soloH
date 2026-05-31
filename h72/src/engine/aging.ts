import { qdMaterials } from '../data/materials';
import type { QDMaterial, AgingResults, AgingPoint } from '../types';

const KB = 1.380649e-23;
const EV_TO_J = 1.602176634e-19;

interface DegradationMode {
  name: string;
  activationEnergy: number;
  currentExponent: number;
  preFactor: number;
}

const DEGRADATION_MODES: DegradationMode[] = [
  { name: '界面缺陷产生', activationEnergy: 0.4, currentExponent: 1.2, preFactor: 1e-6 },
  { name: '有机传输层降解', activationEnergy: 0.6, currentExponent: 0.8, preFactor: 5e-7 },
  { name: '量子点光漂白', activationEnergy: 0.3, currentExponent: 1.5, preFactor: 2e-7 },
  { name: '电极扩散', activationEnergy: 0.8, currentExponent: 0.3, preFactor: 1e-8 },
];

export function calculateDegradationRate(
  currentDensity: number,
  temperature: number,
  activationEnergy: number,
  currentExponent: number,
  preFactor: number
): number {
  const kT = KB * temperature;
  const jNorm = Math.max(1e-3, currentDensity / 10);
  
  return preFactor * Math.pow(jNorm, currentExponent) * Math.exp(-activationEnergy * EV_TO_J / kT);
}

export function calculateBrightnessDecay(
  initialBrightness: number,
  time: number,
  degradationRate: number,
  decayExponent: number = 0.5
): number {
  const normalizedTime = time * degradationRate;
  return initialBrightness * Math.exp(-Math.pow(normalizedTime, decayExponent));
}

export function findLifetime(
  initialBrightness: number,
  targetRatio: number,
  degradationRate: number,
  decayExponent: number = 0.5
): number {
  const targetBrightness = initialBrightness * targetRatio;
  const ratio = targetBrightness / initialBrightness;
  
  if (ratio <= 0) return Infinity;
  
  const normalizedTime = Math.pow(-Math.log(ratio), 1 / decayExponent);
  return normalizedTime / degradationRate;
}

export function calculateAgingResults(
  qdMaterial: QDMaterial,
  initialBrightness: number,
  initialCurrentDensity: number,
  initialVoltage: number,
  testCurrentDensity: number = 10,
  testTemperature: number = 300,
  targetLifetime: number = 10000,
  numPoints: number = 50
): AgingResults {
  const material = qdMaterials[qdMaterial];
  
  const dominantMode = DEGRADATION_MODES.reduce((prev, curr) => {
    const prevRate = calculateDegradationRate(
      testCurrentDensity, testTemperature, 
      prev.activationEnergy, prev.currentExponent, prev.preFactor
    );
    const currRate = calculateDegradationRate(
      testCurrentDensity, testTemperature, 
      curr.activationEnergy, curr.currentExponent, curr.preFactor
    );
    return currRate > prevRate ? curr : prev;
  });
  
  const totalDegradationRate = DEGRADATION_MODES.reduce((sum, mode) => {
    return sum + calculateDegradationRate(
      testCurrentDensity, testTemperature,
      mode.activationEnergy, mode.currentExponent, mode.preFactor
    );
  }, 0);
  
  const decayExponent = 0.4 + 0.1 * (material.interfaceStateDensity || 1e12) / 1e13;
  
  const maxTime = targetLifetime * 3;
  const agingData: AgingPoint[] = [];
  
  for (let i = 0; i < numPoints; i++) {
    const time = Math.pow(10, (i / (numPoints - 1)) * Math.log10(maxTime + 1)) - 1;
    
    const brightness = calculateBrightnessDecay(
      initialBrightness, time, totalDegradationRate, decayExponent
    );
    
    const efficiencyFactor = Math.exp(-0.1 * Math.pow(time * totalDegradationRate, 0.3));
    const currentDensity = initialCurrentDensity / efficiencyFactor;
    const voltage = initialVoltage * (1 + 0.05 * Math.log(1 + time * 1e-4));
    
    agingData.push({
      time,
      brightness,
      currentDensity,
      voltage,
    });
  }
  
  const lt50 = findLifetime(initialBrightness, 0.5, totalDegradationRate, decayExponent);
  const lt70 = findLifetime(initialBrightness, 0.7, totalDegradationRate, decayExponent);
  const lt95 = findLifetime(initialBrightness, 0.95, totalDegradationRate, decayExponent);
  
  const refCurrent = 10;
  const refTemp = 300;
  const referenceRate = DEGRADATION_MODES.reduce((sum, mode) => {
    return sum + calculateDegradationRate(
      refCurrent, refTemp,
      mode.activationEnergy, mode.currentExponent, mode.preFactor
    );
  }, 0);
  
  const accelerationFactor = referenceRate / totalDegradationRate;
  
  return {
    lt50,
    lt70,
    lt95,
    agingData,
    accelerationFactor,
    degradationMode: dominantMode.name,
  };
}

export function calculateVoltageShift(
  agingData: AgingPoint[],
  initialVoltage: number
): { time: number; voltageShift: number }[] {
  return agingData.map(point => ({
    time: point.time,
    voltageShift: point.voltage - initialVoltage,
  }));
}

export function calculateEfficiencyRollOff(
  agingData: AgingPoint[]
): { time: number; efficiencyRatio: number }[] {
  const initialEfficiency = agingData[0].brightness / agingData[0].currentDensity;
  
  return agingData.map(point => ({
    time: point.time,
    efficiencyRatio: (point.brightness / point.currentDensity) / initialEfficiency,
  }));
}

export function predictLifetimeAtConditions(
  baseResults: AgingResults,
  targetCurrentDensity: number,
  targetTemperature: number
): { lt50: number; lt70: number; lt95: number } {
  const totalDegradationRate = DEGRADATION_MODES.reduce((sum, mode) => {
    return sum + calculateDegradationRate(
      targetCurrentDensity, targetTemperature,
      mode.activationEnergy, mode.currentExponent, mode.preFactor
    );
  }, 0);
  
  const baseRate = DEGRADATION_MODES.reduce((sum, mode) => {
    return sum + calculateDegradationRate(
      10, 300,
      mode.activationEnergy, mode.currentExponent, mode.preFactor
    );
  }, 0);
  
  const scalingFactor = baseRate / totalDegradationRate;
  
  return {
    lt50: baseResults.lt50 * scalingFactor,
    lt70: baseResults.lt70 * scalingFactor,
    lt95: baseResults.lt95 * scalingFactor,
  };
}
