import type { SimulationParams, MonteCarloResult } from '../types';
import { solveCoupledWaveEquations } from './coupledWave';
import { generateDomainStructureWithErrors } from './poling';
import { PHYSICAL_CONSTANTS } from './physics';

interface TrialResult {
  trial: number;
  efficiency: number;
  periodError: number;
  dutyCycleError: number;
  temperatureError: number;
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

function calculateMean(values: number[]): number {
  return values.reduce((sum, v) => sum + v, 0) / values.length;
}

function calculateStd(values: number[], mean: number): number {
  const variance = values.reduce((sum, v) => sum + (v - mean) ** 2, 0) / values.length;
  return Math.sqrt(variance);
}

function calculateMedian(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0
    ? (sorted[mid - 1] + sorted[mid]) / 2
    : sorted[mid];
}

function calculateYield(values: number[], threshold: number): number {
  const aboveThreshold = values.filter(v => v >= threshold).length;
  return (aboveThreshold / values.length) * 100;
}

function createHistogram(values: number[], numBins: number = 20): { bin: number; count: number }[] {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const binWidth = (max - min) / numBins || 1;

  const histogram: { bin: number; count: number }[] = [];
  for (let i = 0; i < numBins; i++) {
    histogram.push({ bin: min + (i + 0.5) * binWidth, count: 0 });
  }

  values.forEach(v => {
    const binIndex = Math.min(Math.floor((v - min) / binWidth), numBins - 1);
    if (binIndex >= 0 && binIndex < numBins) {
      histogram[binIndex].count++;
    }
  });

  return histogram;
}

export function runMonteCarloAnalysis(
  params: SimulationParams,
  onProgress?: (progress: number) => void
): Promise<MonteCarloResult> {
  return new Promise((resolve) => {
    const trials = params.monteCarloTrials;
    const results: TrialResult[] = [];
    const rng = createRandomGenerator(Date.now() % 100000);

    const batchSize = Math.max(1, Math.floor(trials / 50));

    function processBatch(startIdx: number) {
      const endIdx = Math.min(startIdx + batchSize, trials);

      for (let i = startIdx; i < endIdx; i++) {
        const periodError = rng.gaussian() * params.periodFluctuationStd;
        const dutyCycleError = rng.gaussian() * params.dutyCycleFluctuationStd;
        const temperatureError = rng.gaussian() * params.temperatureFluctuationStd;

        const modifiedParams: SimulationParams = {
          ...params,
          polingPeriod: Math.max(1, params.polingPeriod * (1 + periodError)),
          dutyCycle: Math.max(0.1, Math.min(0.9, params.dutyCycle + dutyCycleError)),
          temperature: params.temperature + temperatureError,
        };

        try {
          const cwResult = solveCoupledWaveEquations(modifiedParams);
          results.push({
            trial: i,
            efficiency: cwResult.conversionEfficiency,
            periodError,
            dutyCycleError,
            temperatureError,
          });
        } catch (e) {
          results.push({
            trial: i,
            efficiency: 0,
            periodError,
            dutyCycleError,
            temperatureError,
          });
        }
      }

      if (onProgress) {
        onProgress(endIdx / trials);
      }

      if (endIdx < trials) {
        setTimeout(() => processBatch(endIdx), 0);
      } else {
        const efficiencies = results.map(r => r.efficiency);
        const meanEff = calculateMean(efficiencies);
        const stdEff = calculateStd(efficiencies, meanEff);
        const medianEff = calculateMedian(efficiencies);
        const minEff = Math.min(...efficiencies);
        const maxEff = Math.max(...efficiencies);

        const nominalEfficiency = getNominalEfficiency(params);
        const yield95 = calculateYield(efficiencies, nominalEfficiency * 0.95);
        const yield50 = calculateYield(efficiencies, nominalEfficiency * 0.5);

        const histogram = createHistogram(efficiencies);

        const correlationData = results.map(r => ({
          periodError: r.periodError * 100,
          efficiency: r.efficiency,
        }));

        resolve({
          trials,
          meanEfficiency: meanEff,
          stdEfficiency: stdEff,
          minEfficiency: minEff,
          maxEfficiency: maxEff,
          medianEfficiency: medianEff,
          efficiencyDistribution: histogram,
          periodFluctuationStd: params.periodFluctuationStd,
          dutyCycleFluctuationStd: params.dutyCycleFluctuationStd,
          temperatureFluctuationStd: params.temperatureFluctuationStd,
          yield95,
          yield50,
          correlationData,
        });
      }
    }

    setTimeout(() => processBatch(0), 0);
  });
}

function getNominalEfficiency(params: SimulationParams): number {
  try {
    const cwResult = solveCoupledWaveEquations(params);
    return cwResult.conversionEfficiency;
  } catch (e) {
    return 1;
  }
}

export function analyzeErrorSensitivity(
  params: SimulationParams,
  paramName: 'period' | 'dutyCycle' | 'temperature',
  errorRange: number = 0.2,
  numPoints: number = 21
): { error: number; efficiency: number }[] {
  const results: { error: number; efficiency: number }[] = [];

  for (let i = 0; i < numPoints; i++) {
    const error = -errorRange + (2 * errorRange * i) / (numPoints - 1);
    let modifiedParams: SimulationParams = { ...params };

    switch (paramName) {
      case 'period':
        modifiedParams.polingPeriod = Math.max(1, params.polingPeriod * (1 + error));
        break;
      case 'dutyCycle':
        modifiedParams.dutyCycle = Math.max(0.1, Math.min(0.9, params.dutyCycle + error));
        break;
      case 'temperature':
        modifiedParams.temperature = params.temperature + error * 50;
        break;
    }

    try {
      const cwResult = solveCoupledWaveEquations(modifiedParams);
      results.push({ error: error * 100, efficiency: cwResult.conversionEfficiency });
    } catch (e) {
      results.push({ error: error * 100, efficiency: 0 });
    }
  }

  return results;
}

export function calculateProcessMargin(
  params: SimulationParams,
  efficiencyThreshold: number = 0.5
): {
  periodMargin: [number, number];
  dutyCycleMargin: [number, number];
  temperatureMargin: [number, number];
} {
  const nominalEff = getNominalEfficiency(params);
  const threshold = nominalEff * efficiencyThreshold;

  function findMargin(
    paramSetter: (error: number) => SimulationParams,
    searchRange: number = 0.3
  ): [number, number] {
    let lowError = -searchRange;
    let highError = searchRange;

    for (let iter = 0; iter < 50; iter++) {
      const midLow = (lowError + (-searchRange)) / 2;
      const paramsLow = paramSetter(midLow);
      const effLow = safeGetEfficiency(paramsLow);

      if (effLow >= threshold) {
        lowError = midLow;
      } else {
        lowError = (lowError + midLow) / 2;
      }

      const midHigh = (highError + searchRange) / 2;
      const paramsHigh = paramSetter(midHigh);
      const effHigh = safeGetEfficiency(paramsHigh);

      if (effHigh >= threshold) {
        highError = midHigh;
      } else {
        highError = (highError + midHigh) / 2;
      }
    }

    return [lowError * 100, highError * 100];
  }

  const periodMargin = findMargin((e) => ({
    ...params,
    polingPeriod: Math.max(1, params.polingPeriod * (1 + e)),
  }));

  const dutyCycleMargin = findMargin((e) => ({
    ...params,
    dutyCycle: Math.max(0.1, Math.min(0.9, params.dutyCycle + e)),
  }));

  const temperatureMargin = findMargin((e) => ({
    ...params,
    temperature: params.temperature + e * 50,
  }));

  return {
    periodMargin,
    dutyCycleMargin,
    temperatureMargin,
  };
}

function safeGetEfficiency(params: SimulationParams): number {
  try {
    return solveCoupledWaveEquations(params).conversionEfficiency;
  } catch (e) {
    return 0;
  }
}
