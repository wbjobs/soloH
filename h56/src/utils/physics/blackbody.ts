import { PHYSICAL_CONSTANTS } from '../../data/materials';
import type { SpectrumPoint } from '../../types';

const { h, c, k, q } = PHYSICAL_CONSTANTS;

export function planckSpectralRadiance(
  wavelength: number,
  temperature: number
): number {
  const lambda = wavelength * 1e-9;
  const c1 = 2 * Math.PI * h * c * c;
  const c2 = h * c / (k * temperature);
  const expTerm = Math.exp(c2 / lambda);
  return c1 / (Math.pow(lambda, 5) * (expTerm - 1));
}

export function planckPhotonFlux(
  wavelength: number,
  temperature: number
): number {
  const lambda = wavelength * 1e-9;
  const c1 = 2 * Math.PI * c;
  const c2 = h * c / (k * temperature);
  const expTerm = Math.exp(c2 / lambda);
  return c1 / (Math.pow(lambda, 4) * (expTerm - 1)) / (h * c / lambda);
}

export function generateBlackbodySpectrum(
  temperature: number,
  minWavelength: number = 200,
  maxWavelength: number = 5000,
  numPoints: number = 1000
): SpectrumPoint[] {
  const spectrum: SpectrumPoint[] = [];
  const step = (maxWavelength - minWavelength) / (numPoints - 1);
  
  for (let i = 0; i < numPoints; i++) {
    const wavelength = minWavelength + i * step;
    const intensity = planckSpectralRadiance(wavelength, temperature);
    spectrum.push({ wavelength, intensity });
  }
  
  return spectrum;
}

export function WienDisplacementLaw(temperature: number): number {
  return 2.897771955e6 / temperature;
}

export function StefanBoltzmann(temperature: number): number {
  return PHYSICAL_CONSTANTS.sigma * Math.pow(temperature, 4);
}

export function photonEnergy(eV: number): number {
  return eV * q;
}

export function wavelengthToEnergy(wavelength: number): number {
  return PHYSICAL_CONSTANTS.hc / wavelength;
}

export function energyToWavelength(energy: number): number {
  return PHYSICAL_CONSTANTS.hc / energy;
}

export function bandgapToCutoffWavelength(bandgap: number): number {
  return PHYSICAL_CONSTANTS.hc / bandgap;
}

export function totalPhotonFlux(
  temperature: number,
  bandgap: number,
  maxWavelength: number = 10000
): number {
  const cutoffWavelength = bandgapToCutoffWavelength(bandgap);
  let flux = 0;
  const step = 1;
  
  for (let lambda = cutoffWavelength; lambda < maxWavelength; lambda += step) {
    flux += planckPhotonFlux(lambda, temperature) * step * 1e-9;
  }
  
  return flux;
}

export function totalPowerDensity(
  temperature: number,
  bandgap: number,
  reflectance: number[] = [],
  wavelengths: number[] = []
): number {
  const cutoffWavelength = bandgapToCutoffWavelength(bandgap);
  let power = 0;
  const step = 1;
  
  for (let lambda = cutoffWavelength; lambda < 10000; lambda += step) {
    let r = 0;
    if (wavelengths.length > 0 && reflectance.length > 0) {
      const idx = Math.floor((lambda - wavelengths[0]) / (wavelengths[1] - wavelengths[0]));
      if (idx >= 0 && idx < reflectance.length) {
        r = reflectance[idx];
      }
    }
    const energy = wavelengthToEnergy(lambda) * q;
    power += planckPhotonFlux(lambda, temperature) * energy * (1 - r) * step * 1e-9;
  }
  
  return power;
}
