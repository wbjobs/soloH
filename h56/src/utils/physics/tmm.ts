import type { EmitterLayer, ReflectancePoint } from '../../types';
import { planckPhotonFlux, bandgapToCutoffWavelength, wavelengthToEnergy } from './blackbody';
import { PHYSICAL_CONSTANTS } from '../../data/materials';
const { q } = PHYSICAL_CONSTANTS;

function degToRad(deg: number): number {
  return deg * Math.PI / 180;
}

function complexMultiply(a: { re: number; im: number }, b: { re: number; im: number }): { re: number; im: number } {
  return {
    re: a.re * b.re - a.im * b.im,
    im: a.re * b.im + a.im * b.re,
  };
}

function complexAdd(a: { re: number; im: number }, b: { re: number; im: number }): { re: number; im: number } {
  return {
    re: a.re + b.re,
    im: a.im + b.im,
  };
}

function complexSubtract(a: { re: number; im: number }, b: { re: number; im: number }): { re: number; im: number } {
  return {
    re: a.re - b.re,
    im: a.im - b.im,
  };
}

function complexDivide(a: { re: number; im: number }, b: { re: number; im: number }): { re: number; im: number } {
  const denom = b.re * b.re + b.im * b.im;
  return {
    re: (a.re * b.re + a.im * b.im) / denom,
    im: (a.im * b.re - a.re * b.im) / denom,
  };
}

function complexMagnitude(c: { re: number; im: number }): number {
  return Math.sqrt(c.re * c.re + c.im * c.im);
}

function complexExp(im: number): { re: number; im: number } {
  return {
    re: Math.cos(im),
    im: Math.sin(im),
  };
}

export function getTemperatureDependentNk(
  layer: EmitterLayer,
  temperature: number
): { n: number; k: number } {
  const T0 = layer.referenceTemperature || 300;
  const dT = temperature - T0;
  return {
    n: layer.n + (layer.dn_dT || 0) * dT,
    k: layer.k + (layer.dk_dT || 0) * dT,
  };
}

export function calculateReflectance(
  layers: EmitterLayer[],
  wavelength: number,
  angleOfIncidence: number = 0,
  nSubstrate: number = 3.5,
  nIncident: number = 1.0,
  temperature: number = 300
): number {
  const theta0 = degToRad(angleOfIncidence);
  const lambda = wavelength * 1e-9;
  
  const k0 = 2 * Math.PI / lambda;
  
  let totalMatrix = {
    m11: { re: 1, im: 0 },
    m12: { re: 0, im: 0 },
    m21: { re: 0, im: 0 },
    m22: { re: 1, im: 0 },
  };
  
  for (const layer of layers) {
    const { n, k } = getTemperatureDependentNk(layer, temperature);
    const d = layer.thickness * 1e-9;
    
    const nComplex = { re: n, im: -k };
    
    const cosTheta = Math.sqrt(1 - Math.pow(nIncident / n * Math.sin(theta0), 2));
    const phase = k0 * n * d * cosTheta;
    
    const eta = {
      re: n * cosTheta,
      im: -k * cosTheta,
    };
    
    const cosPhase = complexExp(phase);
    const sinPhase = { re: Math.sin(phase), im: 0 };
    
    const cosP = cosPhase;
    const cosM = { re: cosPhase.re, im: -cosPhase.im };
    const iSin = { re: -sinPhase.im, im: sinPhase.re };
    
    const iEta = { re: -eta.im, im: eta.re };
    const iOverEta = complexDivide({ re: 0, im: 1 }, eta);
    
    const m11 = cosP;
    const m12 = complexMultiply(iSin, iOverEta);
    const m21 = complexMultiply(iSin, iEta);
    const m22 = cosM;
    
    const newM11 = complexAdd(
      complexMultiply(totalMatrix.m11, m11),
      complexMultiply(totalMatrix.m12, m21)
    );
    const newM12 = complexAdd(
      complexMultiply(totalMatrix.m11, m12),
      complexMultiply(totalMatrix.m12, m22)
    );
    const newM21 = complexAdd(
      complexMultiply(totalMatrix.m21, m11),
      complexMultiply(totalMatrix.m22, m21)
    );
    const newM22 = complexAdd(
      complexMultiply(totalMatrix.m21, m12),
      complexMultiply(totalMatrix.m22, m22)
    );
    
    totalMatrix = {
      m11: newM11,
      m12: newM12,
      m21: newM21,
      m22: newM22,
    };
  }
  
  const eta0 = nIncident * Math.cos(theta0);
  const etaS = nSubstrate * Math.sqrt(1 - Math.pow(nIncident / nSubstrate * Math.sin(theta0), 2));
  
  const eta0C = { re: eta0, im: 0 };
  const etaSC = { re: etaS, im: 0 };
  
  const numerator = complexAdd(
    complexAdd(
      complexMultiply(totalMatrix.m11, eta0C),
      complexAdd(
        complexMultiply(complexMultiply(totalMatrix.m12, eta0C), etaSC),
        complexSubtract(totalMatrix.m21, complexMultiply(totalMatrix.m22, etaSC))
      )
    ),
    { re: 0, im: 0 }
  );
  
  const a = complexAdd(complexMultiply(totalMatrix.m11, eta0C), complexMultiply(complexMultiply(totalMatrix.m12, eta0C), etaSC));
  const b = complexSubtract(totalMatrix.m21, complexMultiply(totalMatrix.m22, etaSC));
  const num = complexAdd(a, b);
  
  const c = complexAdd(complexMultiply(totalMatrix.m11, eta0C), complexMultiply(complexMultiply(totalMatrix.m12, eta0C), etaSC));
  const d = complexAdd(totalMatrix.m21, complexMultiply(totalMatrix.m22, etaSC));
  const den = complexAdd(c, d);
  
  const r = complexDivide(num, den);
  const reflectance = Math.pow(complexMagnitude(r), 2);
  
  return Math.max(0, Math.min(1, reflectance));
}

export function calculateReflectanceSpectrum(
  layers: EmitterLayer[],
  minWavelength: number = 200,
  maxWavelength: number = 5000,
  numPoints: number = 200,
  angleOfIncidence: number = 0,
  nSubstrate: number = 3.5,
  temperature: number = 300
): ReflectancePoint[] {
  const spectrum: ReflectancePoint[] = [];
  const step = (maxWavelength - minWavelength) / (numPoints - 1);
  
  for (let i = 0; i < numPoints; i++) {
    const wavelength = minWavelength + i * step;
    const r = calculateReflectance(layers, wavelength, angleOfIncidence, nSubstrate, 1.0, temperature);
    spectrum.push({ wavelength, r });
  }
  
  return spectrum;
}

export function calculateTransmittance(
  layers: EmitterLayer[],
  wavelength: number,
  angleOfIncidence: number = 0,
  nSubstrate: number = 3.5,
  nIncident: number = 1.0,
  temperature: number = 300
): number {
  const r = calculateReflectance(layers, wavelength, angleOfIncidence, nSubstrate, nIncident, temperature);
  let absorption = 0;
  
  for (const layer of layers) {
    const { k } = getTemperatureDependentNk(layer, temperature);
    if (k > 0) {
      const alpha = 4 * Math.PI * k / (wavelength * 1e-9);
      absorption += (1 - Math.exp(-alpha * layer.thickness * 1e-9)) * 0.5;
    }
  }
  
  return Math.max(0, 1 - r - absorption);
}

export function calculateAbsorptance(
  layers: EmitterLayer[],
  wavelength: number,
  angleOfIncidence: number = 0,
  nSubstrate: number = 3.5,
  temperature: number = 300
): number {
  const r = calculateReflectance(layers, wavelength, angleOfIncidence, nSubstrate, 1.0, temperature);
  const t = calculateTransmittance(layers, wavelength, angleOfIncidence, nSubstrate, 1.0, temperature);
  return Math.max(0, 1 - r - t);
}

export function spectralMatchFactor(
  sourceTemp: number,
  bandgap: number,
  reflectanceSpectrum: ReflectancePoint[]
): number {
  const cutoffWavelength = bandgapToCutoffWavelength(bandgap);
  let usefulPower = 0;
  let totalPower = 0;
  
  const wavelengths = reflectanceSpectrum.map(p => p.wavelength);
  const reflectances = reflectanceSpectrum.map(p => p.r);
  
  for (let i = 0; i < wavelengths.length - 1; i++) {
    const lambda = wavelengths[i];
    const step = wavelengths[i + 1] - lambda;
    
    const flux = planckPhotonFlux(lambda, sourceTemp);
    const energy = wavelengthToEnergy(lambda) * q;
    const r = reflectances[i];
    
    totalPower += flux * energy * step * 1e-9;
    
    if (lambda < cutoffWavelength) {
      usefulPower += flux * energy * (1 - r) * step * 1e-9;
    }
  }
  
  return totalPower > 0 ? usefulPower / totalPower : 0;
}
