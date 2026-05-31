import type { SpectrumPoint, CoupledWaveResult } from '../types';
import { PHYSICAL_CONSTANTS } from './physics';

interface Complex {
  re: number;
  im: number;
}

function complexAdd(a: Complex, b: Complex): Complex {
  return { re: a.re + b.re, im: a.im + b.im };
}

function complexSub(a: Complex, b: Complex): Complex {
  return { re: a.re - b.re, im: a.im - b.im };
}

function complexMul(a: Complex, b: Complex): Complex {
  return {
    re: a.re * b.re - a.im * b.im,
    im: a.re * b.im + a.im * b.re,
  };
}

function complexExp(phi: number): Complex {
  return { re: Math.cos(phi), im: Math.sin(phi) };
}

function nextPowerOf2(n: number): number {
  let p = 1;
  while (p < n) p <<= 1;
  return p;
}

export function fft(data: Complex[], inverse: boolean = false): Complex[] {
  const n = data.length;
  if (n <= 1) return [...data];

  const N = nextPowerOf2(n);
  const padded: Complex[] = [...data];
  while (padded.length < N) {
    padded.push({ re: 0, im: 0 });
  }

  const result = fftRadix2(padded, inverse);

  if (inverse) {
    return result.map(c => ({ re: c.re / N, im: c.im / N }));
  }

  return result.slice(0, n);
}

function fftRadix2(data: Complex[], inverse: boolean): Complex[] {
  const n = data.length;
  if (n <= 1) return [...data];

  const even: Complex[] = [];
  const odd: Complex[] = [];
  for (let i = 0; i < n; i += 2) {
    even.push(data[i]);
    odd.push(data[i + 1]);
  }

  const fftEven = fftRadix2(even, inverse);
  const fftOdd = fftRadix2(odd, inverse);

  const result: Complex[] = new Array(n);
  const sign = inverse ? 1 : -1;

  for (let k = 0; k < n / 2; k++) {
    const t = complexMul(fftOdd[k], complexExp((sign * 2 * Math.PI * k) / n));
    result[k] = complexAdd(fftEven[k], t);
    result[k + n / 2] = complexSub(fftEven[k], t);
  }

  return result;
}

export function fftReal(data: number[], inverse: boolean = false): Complex[] {
  const complexData: Complex[] = data.map(re => ({ re, im: 0 }));
  return fft(complexData, inverse);
}

export function calculateMagnitudeSpectrum(data: Complex[]): number[] {
  return data.map(c => Math.sqrt(c.re * c.re + c.im * c.im));
}

export function calculatePowerSpectrum(data: Complex[]): number[] {
  return data.map(c => c.re * c.re + c.im * c.im);
}

export function calculatePhaseSpectrum(data: Complex[]): number[] {
  return data.map(c => Math.atan2(c.im, c.re));
}

export function analyzeSignalSpectrum(
  cwResult: CoupledWaveResult,
  centerWavelength: number
): SpectrumPoint[] {
  const signalIntensity = cwResult.signalIntensity;
  const n = signalIntensity.length;

  const fftResult = fftReal(signalIntensity);
  const magnitude = calculateMagnitudeSpectrum(fftResult);

  const dz = cwResult.z[1] - cwResult.z[0];
  const fs = 1 / dz;
  const freqStep = fs / n;

  const result: SpectrumPoint[] = [];
  const centerOmega = (2 * Math.PI * PHYSICAL_CONSTANTS.c) / (centerWavelength * PHYSICAL_CONSTANTS.nm_to_m);

  for (let i = 0; i < Math.floor(n / 2); i++) {
    const frequency = i * freqStep;
    const omegaOffset = frequency * 2 * Math.PI;
    const omega = centerOmega + omegaOffset;
    const wavelength = (2 * Math.PI * PHYSICAL_CONSTANTS.c) / omega / PHYSICAL_CONSTANTS.nm_to_m;

    if (wavelength > 0 && wavelength < 10000) {
      result.push({
        frequency,
        amplitude: magnitude[i],
        wavelength,
      });
    }
  }

  return result.sort((a, b) => a.wavelength - b.wavelength);
}

export function analyzeSpatialSpectrum(
  data: number[],
  spatialStep: number
): { frequency: number; amplitude: number; period: number }[] {
  const n = data.length;
  const fftResult = fftReal(data);
  const magnitude = calculateMagnitudeSpectrum(fftResult);

  const fs = 1 / spatialStep;
  const freqStep = fs / n;

  const result: { frequency: number; amplitude: number; period: number }[] = [];

  for (let i = 0; i < Math.floor(n / 2); i++) {
    const frequency = i * freqStep;
    const period = frequency > 0 ? 1 / frequency : Infinity;

    result.push({
      frequency,
      amplitude: magnitude[i],
      period,
    });
  }

  return result;
}

export function calculateDiffractionPattern(
  wavelength: number,
  waist: number,
  propagationDistance: number,
  nx: number = 256,
  nz: number = 100
): { x: number[]; z: number[]; intensity: number[][] } {
  const wavelength_si = wavelength * PHYSICAL_CONSTANTS.nm_to_m;
  const waist_si = waist * PHYSICAL_CONSTANTS.um_to_m;
  const distance_si = propagationDistance * PHYSICAL_CONSTANTS.mm_to_m;

  const x: number[] = [];
  const z: number[] = [];
  const intensity: number[][] = [];

  const width = waist_si * 8;
  const dx = width / nx;
  const dz = distance_si / nz;

  for (let i = 0; i < nx; i++) {
    x.push((i - nx / 2) * dx);
  }
  for (let k = 0; k < nz; k++) {
    z.push(k * dz);
  }

  let field: Complex[] = [];
  for (let i = 0; i < nx; i++) {
    const r2 = x[i] * x[i];
    const amplitude = Math.exp(-r2 / (waist_si * waist_si));
    field.push({ re: amplitude, im: 0 });
  }

  for (let k = 0; k < nz; k++) {
    intensity.push(field.map(c => c.re * c.re + c.im * c.im));

    const fftField = fft(field);

    for (let i = 0; i < nx; i++) {
      const fx = (i < nx / 2 ? i : i - nx) * (1 / (nx * dx));
      const kx = 2 * Math.PI * fx;
      const k = 2 * Math.PI / wavelength_si;
      const kz = Math.sqrt(Math.max(0, k * k - kx * kx));
      const phase = kz * dz;
      fftField[i] = complexMul(fftField[i], complexExp(phase));
    }

    field = fft(fftField, true);
  }

  return { x, z, intensity };
}

export function findPeaks(
  spectrum: { wavelength: number; amplitude: number }[],
  threshold: number = 0.1,
  minDistance: number = 10
): { wavelength: number; amplitude: number }[] {
  const peaks: { wavelength: number; amplitude: number }[] = [];
  const maxAmplitude = Math.max(...spectrum.map(s => s.amplitude));

  for (let i = 1; i < spectrum.length - 1; i++) {
    if (
      spectrum[i].amplitude > spectrum[i - 1].amplitude &&
      spectrum[i].amplitude > spectrum[i + 1].amplitude &&
      spectrum[i].amplitude > threshold * maxAmplitude
    ) {
      const tooClose = peaks.some(
        p => Math.abs(p.wavelength - spectrum[i].wavelength) < minDistance
      );
      if (!tooClose) {
        peaks.push({ ...spectrum[i] });
      }
    }
  }

  return peaks.sort((a, b) => b.amplitude - a.amplitude);
}

export function calculateSpectralWidth(
  spectrum: SpectrumPoint[],
  centerWavelength: number
): { fwhm: number; leftWavelength: number; rightWavelength: number; peakWavelength: number; peakAmplitude: number } {
  if (spectrum.length < 3) {
    return { fwhm: 0, leftWavelength: centerWavelength, rightWavelength: centerWavelength, peakWavelength: centerWavelength, peakAmplitude: 0 };
  }

  let peakIdx = spectrum.reduce(
    (best, s, i) => s.amplitude > spectrum[best].amplitude ? i : best,
    0
  );

  if (peakIdx > 0 && peakIdx < spectrum.length - 1) {
    const a = spectrum[peakIdx - 1].amplitude;
    const b = spectrum[peakIdx].amplitude;
    const c = spectrum[peakIdx + 1].amplitude;
    const denom = 2 * (a - 2 * b + c);
    if (Math.abs(denom) > 1e-12) {
      const offset = (a - c) / denom;
      if (Math.abs(offset) <= 1) {
        peakIdx = peakIdx + offset;
      }
    }
  }

  const floorPeakIdx = Math.min(Math.max(Math.floor(peakIdx), 0), spectrum.length - 1);
  const ceilPeakIdx = Math.min(Math.max(Math.ceil(peakIdx), 0), spectrum.length - 1);
  const peakFrac = peakIdx - floorPeakIdx;
  const peakAmplitude = spectrum[floorPeakIdx].amplitude * (1 - peakFrac) + spectrum[ceilPeakIdx].amplitude * peakFrac;
  const peakWavelength = spectrum[floorPeakIdx].wavelength * (1 - peakFrac) + spectrum[ceilPeakIdx].wavelength * peakFrac;

  const halfMax = peakAmplitude / 2;

  let leftWavelength: number;
  const leftStartIdx = Math.floor(peakIdx);

  if (leftStartIdx <= 0) {
    leftWavelength = spectrum[0].wavelength;
  } else {
    let leftCrossIdx = leftStartIdx;
    while (leftCrossIdx > 0 && spectrum[leftCrossIdx].amplitude > halfMax) {
      leftCrossIdx--;
    }

    if (spectrum[leftCrossIdx].amplitude <= halfMax && leftCrossIdx < spectrum.length - 1) {
      const x1 = spectrum[leftCrossIdx].wavelength;
      const y1 = spectrum[leftCrossIdx].amplitude;
      const x2 = spectrum[leftCrossIdx + 1].wavelength;
      const y2 = spectrum[leftCrossIdx + 1].amplitude;

      if (Math.abs(y2 - y1) > 1e-12) {
        const t = (halfMax - y1) / (y2 - y1);
        leftWavelength = x1 + t * (x2 - x1);
      } else {
        leftWavelength = x1;
      }
    } else {
      leftWavelength = spectrum[leftCrossIdx].wavelength;
    }
  }

  let rightWavelength: number;
  const rightStartIdx = Math.ceil(peakIdx);

  if (rightStartIdx >= spectrum.length - 1) {
    rightWavelength = spectrum[spectrum.length - 1].wavelength;
  } else {
    let rightCrossIdx = rightStartIdx;
    while (rightCrossIdx < spectrum.length - 1 && spectrum[rightCrossIdx].amplitude > halfMax) {
      rightCrossIdx++;
    }

    if (spectrum[rightCrossIdx].amplitude <= halfMax && rightCrossIdx > 0) {
      const x1 = spectrum[rightCrossIdx - 1].wavelength;
      const y1 = spectrum[rightCrossIdx - 1].amplitude;
      const x2 = spectrum[rightCrossIdx].wavelength;
      const y2 = spectrum[rightCrossIdx].amplitude;

      if (Math.abs(y2 - y1) > 1e-12) {
        const t = (halfMax - y1) / (y2 - y1);
        rightWavelength = x1 + t * (x2 - x1);
      } else {
        rightWavelength = x2;
      }
    } else {
      rightWavelength = spectrum[rightCrossIdx].wavelength;
    }
  }

  const fwhm = Math.max(0, rightWavelength - leftWavelength);

  return { fwhm, leftWavelength, rightWavelength, peakWavelength, peakAmplitude };
}
