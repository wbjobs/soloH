import { qdMaterials, electrodeMaterials, transportLayerMaterials } from '../data/materials';
import type { QDMaterial, TransportLayerMaterial, ElectrodeMaterial, AngularDistribution } from '../types';

const C = 2.99792458e8;
const EV_TO_J = 1.602176634e-19;
const HBAR = 1.0545718e-34;

function fresnelCoefficient(
  n1: number,
  n2: number,
  theta1: number,
  polarization: 's' | 'p'
): number {
  const sinTheta2 = (n1 / n2) * Math.sin(theta1);
  if (Math.abs(sinTheta2) > 1) return 0;
  
  const theta2 = Math.asin(sinTheta2);
  
  if (polarization === 's') {
    const numerator = n1 * Math.cos(theta1) - n2 * Math.cos(theta2);
    const denominator = n1 * Math.cos(theta1) + n2 * Math.cos(theta2);
    return Math.abs(numerator / denominator) ** 2;
  } else {
    const numerator = n2 * Math.cos(theta1) - n1 * Math.cos(theta2);
    const denominator = n2 * Math.cos(theta1) + n1 * Math.cos(theta2);
    return Math.abs(numerator / denominator) ** 2;
  }
}

function calculateTransmittance(
  n1: number,
  n2: number,
  theta: number,
  thickness: number,
  wavelength: number
): number {
  const k0 = 2 * Math.PI / (wavelength * 1e-9);
  const sinTheta2 = (n1 / n2) * Math.sin(theta);
  
  if (Math.abs(sinTheta2) > 1) {
    const alpha = k0 * Math.sqrt((n1 * Math.sin(theta)) ** 2 - n2 ** 2);
    return Math.exp(-2 * alpha * thickness * 1e-9);
  }
  
  const theta2 = Math.asin(sinTheta2);
  const phase = k0 * n2 * thickness * 1e-9 * Math.cos(theta2);
  
  const rs = fresnelCoefficient(n1, n2, theta, 's');
  const rp = fresnelCoefficient(n1, n2, theta, 'p');
  
  const ts = 4 * n1 * n2 * Math.cos(theta) * Math.cos(theta2) / 
             ((n1 * Math.cos(theta) + n2 * Math.cos(theta2)) ** 2);
  const tp = 4 * n1 * n2 * Math.cos(theta) * Math.cos(theta2) / 
             ((n2 * Math.cos(theta) + n1 * Math.cos(theta2)) ** 2);
  
  const interferences = Math.cos(2 * phase);
  const denom = 1 + rs ** 2 + rp ** 2 - 2 * (rs + rp) * interferences;
  
  return (ts + tp) / denom;
}

function calculateMicrocavityEffect(
  wavelength: number,
  angle: number,
  cavityLength: number,
  nCavity: number,
  reflectivity1: number,
  reflectivity2: number
): number {
  const k0 = 2 * Math.PI / (wavelength * 1e-9);
  const sinTheta = Math.sin(angle);
  const cosTheta = Math.cos(angle);
  
  const phase = 2 * k0 * nCavity * cavityLength * 1e-9 * cosTheta;
  const r1 = Math.sqrt(reflectivity1);
  const r2 = Math.sqrt(reflectivity2);
  
  const denominator = 1 + r1 * r1 * r2 * r2 - 2 * r1 * r2 * Math.cos(phase);
  
  if (denominator < 1e-10) return 1e10;
  
  return (1 - r1 * r1) * (1 - r2 * r2) / denominator;
}

function calculateDipoleOrientationFactor(
  angle: number,
  orientation: 'random' | 'horizontal' | 'vertical' = 'random'
): number {
  if (orientation === 'horizontal') {
    return 1.5 * Math.sin(angle) ** 2;
  } else if (orientation === 'vertical') {
    return 3 * Math.cos(angle) ** 2;
  } else {
    return (1 + Math.cos(angle) ** 2) / 2;
  }
}

function calculateOutcouplingEfficiency(
  nActive: number,
  nSubstrate: number,
  theta: number
): number {
  const sinThetaSubstrate = (nActive / nSubstrate) * Math.sin(theta);
  
  if (Math.abs(sinThetaSubstrate) > 1) {
    return 0;
  }
  
  const cosThetaSubstrate = Math.sqrt(1 - sinThetaSubstrate ** 2);
  const cosThetaActive = Math.cos(theta);
  
  const T = 4 * nActive * nSubstrate * cosThetaActive * cosThetaSubstrate / 
            ((nActive * cosThetaActive + nSubstrate * cosThetaSubstrate) ** 2);
  
  return T;
}

export function calculateAngularDistribution(
  peakWavelength: number,
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
  numAngles: number = 91
): AngularDistribution {
  const qdParams = qdMaterials[qdMaterial];
  const etlParams = transportLayerMaterials[deviceStructure.etl];
  const anodeParams = electrodeMaterials[deviceStructure.anode];
  
  const nActive = qdParams.refractiveIndex;
  const nETL = etlParams.refractiveIndex;
  const nGlass = 1.5;
  
  const cavityLength = deviceStructure.htlThickness + 
                       deviceStructure.qdLayerThickness + 
                       deviceStructure.etlThickness;
  const nCavity = (qdParams.refractiveIndex + etlParams.refractiveIndex) / 2;
  
  const reflectivityAnode = anodeParams.conductivity > 1e7 ? 0.8 : 0.2;
  const reflectivityCathode = electrodeMaterials[deviceStructure.cathode].conductivity > 1e7 ? 0.9 : 0.1;
  
  const angles = linspace(0, Math.PI / 2, numAngles);
  const intensities = new Float64Array(numAngles);
  
  let maxIntensity = 0;
  let peakAngle = 0;
  
  for (let i = 0; i < numAngles; i++) {
    const theta = angles[i];
    
    const orientationFactor = calculateDipoleOrientationFactor(theta, 'random');
    const microcavityFactor = calculateMicrocavityEffect(
      peakWavelength, theta, cavityLength, nCavity, 
      reflectivityAnode, reflectivityCathode
    );
    
    const tETL = calculateTransmittance(
      nActive, nETL, theta, deviceStructure.etlThickness, peakWavelength
    );
    
    const outcoupling = calculateOutcouplingEfficiency(nETL, nGlass, theta);
    
    const lambertian = Math.cos(theta);
    
    intensities[i] = orientationFactor * microcavityFactor * tETL * outcoupling * lambertian;
    
    if (intensities[i] > maxIntensity) {
      maxIntensity = intensities[i];
      peakAngle = theta;
    }
  }
  
  for (let i = 0; i < numAngles; i++) {
    intensities[i] /= maxIntensity;
  }
  
  const fwhmAngle = calculateFWHM(angles, intensities);
  
  const data = Array.from(angles).map((angle, i) => ({
    angle: angle * 180 / Math.PI,
    intensity: intensities[i],
    wavelength: peakWavelength,
  }));
  
  return {
    angles: Array.from(angles).map(a => a * 180 / Math.PI),
    intensities: Array.from(intensities),
    peakIntensityAngle: peakAngle * 180 / Math.PI,
    fwhmAngle,
    data,
  };
}

function linspace(start: number, end: number, num: number): number[] {
  const result: number[] = [];
  const step = (end - start) / (num - 1);
  for (let i = 0; i < num; i++) {
    result.push(start + i * step);
  }
  return result;
}

function calculateFWHM(angles: number[], intensities: Float64Array): number {
  const halfMax = 0.5;
  let leftIdx = 0;
  let rightIdx = angles.length - 1;
  
  for (let i = 0; i < angles.length; i++) {
    if (intensities[i] >= halfMax) {
      leftIdx = i;
      break;
    }
  }
  
  for (let i = angles.length - 1; i >= 0; i--) {
    if (intensities[i] >= halfMax) {
      rightIdx = i;
      break;
    }
  }
  
  if (leftIdx === 0 && rightIdx === angles.length - 1) {
    return angles[rightIdx] - angles[leftIdx];
  }
  
  const interpLeft = leftIdx > 0 ? 
    angles[leftIdx - 1] + (halfMax - intensities[leftIdx - 1]) * 
    (angles[leftIdx] - angles[leftIdx - 1]) / (intensities[leftIdx] - intensities[leftIdx - 1]) :
    angles[leftIdx];
  
  const interpRight = rightIdx < angles.length - 1 ?
    angles[rightIdx] + (halfMax - intensities[rightIdx]) *
    (angles[rightIdx + 1] - angles[rightIdx]) / (intensities[rightIdx + 1] - intensities[rightIdx]) :
    angles[rightIdx];
  
  return (interpRight - interpLeft) * 180 / Math.PI;
}

export function calculateExtractionEfficiency(
  angularDist: AngularDistribution,
  nActive: number
): number {
  let totalPower = 0;
  let extractedPower = 0;
  
  for (let i = 0; i < angularDist.angles.length; i++) {
    const theta = angularDist.angles[i] * Math.PI / 180;
    const dTheta = i > 0 ? 
      (angularDist.angles[i] - angularDist.angles[i - 1]) * Math.PI / 180 :
      (angularDist.angles[1] - angularDist.angles[0]) * Math.PI / 180;
    
    const sinTheta = Math.sin(theta);
    const element = 2 * Math.PI * sinTheta * dTheta;
    
    totalPower += angularDist.intensities[i] * element;
    
    const criticalAngle = Math.asin(1 / nActive);
    if (theta < criticalAngle) {
      extractedPower += angularDist.intensities[i] * element;
    }
  }
  
  return totalPower > 0 ? extractedPower / totalPower : 0;
}
