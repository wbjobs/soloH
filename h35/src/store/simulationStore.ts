import { create } from 'zustand';
import type {
  SimulationParams,
  CalculationResult,
  PhaseMatchingResult,
  CoupledWaveResult,
  EfficiencyCurvePoint,
  ToleranceData,
  FieldDataPoint,
  DomainStructurePoint,
  SpectrumPoint,
  CascadeResult,
  NoncollinearResult,
  MonteCarloResult,
} from '../types';
import { DEFAULT_PARAMS } from '../types';
import { calculatePhaseMatching, calculateNoncollinearPhaseMatching } from '../utils/phaseMatching';
import {
  solveCoupledWaveEquations,
  calculateEfficiencyCurve,
  calculateToleranceData,
  generateFieldDistribution,
  scanEfficiencyVsTemperature,
  scanEfficiencyVsAngle,
  scanEfficiencyVsLength,
  solveCascadeProcesses,
} from '../utils/coupledWave';
import { generateDomainStructurePoints, generateDomainStructureWithErrors } from '../utils/poling';
import { analyzeSignalSpectrum } from '../utils/fft';
import { runMonteCarloAnalysis } from '../utils/monteCarlo';

interface SimulationState {
  params: SimulationParams;
  result: CalculationResult;
  isCalculating: boolean;
  calculationProgress: number;
  error: string | null;
  activeTab: 'phase' | 'poling' | 'coupled' | 'efficiency' | 'field' | 'spectrum' | 'cascade' | 'noncollinear' | 'montecarlo';
  scanType: 'wavelength' | 'temperature' | 'angle' | 'length';

  setParams: (params: Partial<SimulationParams>) => void;
  resetParams: () => void;
  calculateAll: () => Promise<void>;
  calculatePhaseMatching: () => void;
  calculateCoupledWave: () => void;
  calculateEfficiencyCurve: () => Promise<void>;
  calculateTolerance: () => void;
  generateDomainStructure: () => void;
  generateFieldDistribution: () => void;
  calculateSpectrum: () => void;
  calculateCascade: () => void;
  calculateNoncollinear: () => void;
  calculateMonteCarlo: () => Promise<void>;
  setActiveTab: (tab: SimulationState['activeTab']) => void;
  setScanType: (type: SimulationState['scanType']) => void;
  clearError: () => void;
}

export const useSimulationStore = create<SimulationState>((set, get) => ({
  params: { ...DEFAULT_PARAMS },
  result: {
    phaseMatching: null,
    coupledWave: null,
    efficiencyCurve: [],
    toleranceData: null,
    fieldDistribution: [],
    domainStructure: [],
    spectrumData: [],
    cascadeResult: null,
    noncollinearResult: null,
    monteCarloResult: null,
  },
  isCalculating: false,
  calculationProgress: 0,
  error: null,
  activeTab: 'phase',
  scanType: 'wavelength',

  setParams: (newParams) => {
    set((state) => ({
      params: { ...state.params, ...newParams },
    }));
  },

  resetParams: () => {
    set({
      params: { ...DEFAULT_PARAMS },
      result: {
        phaseMatching: null,
        coupledWave: null,
        efficiencyCurve: [],
        toleranceData: null,
        fieldDistribution: [],
        domainStructure: [],
        spectrumData: [],
        cascadeResult: null,
        noncollinearResult: null,
        monteCarloResult: null,
      },
    });
  },

  calculateAll: async () => {
    set({ isCalculating: true, calculationProgress: 0, error: null });

    try {
      const { params } = get();

      let pmResult = calculatePhaseMatching(params);
      set({
        result: { ...get().result, phaseMatching: pmResult },
        calculationProgress: 0.15,
      });

      let noncollinearResult: NoncollinearResult | null = null;
      if (params.noncollinearConfig !== 'collinear') {
        noncollinearResult = calculateNoncollinearPhaseMatching(params);
        set({
          result: { ...get().result, noncollinearResult },
          calculationProgress: 0.25,
        });
      }

      const cwResult = solveCoupledWaveEquations(params);
      set({
        result: { ...get().result, coupledWave: cwResult },
        calculationProgress: 0.4,
      });

      let cascadeResult: CascadeResult | null = null;
      if (params.enableCascade) {
        cascadeResult = solveCascadeProcesses(params, cwResult);
        set({
          result: { ...get().result, cascadeResult },
          calculationProgress: 0.55,
        });
      }

      const efficiencyCurve = await calculateEfficiencyCurve(params, (progress) => {
        set({ calculationProgress: 0.55 + progress * 0.2 });
      });
      set({
        result: { ...get().result, efficiencyCurve },
        calculationProgress: 0.75,
      });

      const toleranceData = calculateToleranceData(params);
      set({
        result: { ...get().result, toleranceData },
        calculationProgress: 0.82,
      });

      let domainStructure = generateDomainStructurePoints(params);
      if (params.enableMonteCarlo) {
        domainStructure = generateDomainStructureWithErrors(params, 0, params.periodFluctuationStd);
      }
      set({
        result: { ...get().result, domainStructure },
        calculationProgress: 0.88,
      });

      const fieldDistribution = generateFieldDistribution(params, cwResult);
      const spectrumData = analyzeSignalSpectrum(
        cwResult,
        (params.signalWavelengthMin + params.signalWavelengthMax) / 2
      );
      set({
        result: {
          ...get().result,
          fieldDistribution,
          spectrumData,
        },
        calculationProgress: 0.94,
      });

      let monteCarloResult: MonteCarloResult | null = null;
      if (params.enableMonteCarlo) {
        monteCarloResult = await runMonteCarloAnalysis(params, (progress) => {
          set({ calculationProgress: 0.94 + progress * 0.06 });
        });
        set({
          result: { ...get().result, monteCarloResult },
          calculationProgress: 1.0,
        });
      } else {
        set({ calculationProgress: 1.0 });
      }
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : '计算过程中发生未知错误',
      });
    } finally {
      set({ isCalculating: false });
    }
  },

  calculatePhaseMatching: () => {
    set({ isCalculating: true, error: null });
    try {
      const { params } = get();
      const result = calculatePhaseMatching(params);
      set({
        result: { ...get().result, phaseMatching: result },
        isCalculating: false,
      });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : '相位匹配计算失败',
        isCalculating: false,
      });
    }
  },

  calculateCoupledWave: () => {
    set({ isCalculating: true, error: null });
    try {
      const { params } = get();
      const result = solveCoupledWaveEquations(params);
      set({
        result: { ...get().result, coupledWave: result },
        isCalculating: false,
      });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : '耦合波方程求解失败',
        isCalculating: false,
      });
    }
  },

  calculateEfficiencyCurve: async () => {
    set({ isCalculating: true, calculationProgress: 0, error: null });
    try {
      const { params, scanType } = get();
      let efficiencyCurve: EfficiencyCurvePoint[] = [];

      if (scanType === 'wavelength') {
        efficiencyCurve = await calculateEfficiencyCurve(params, (progress) => {
          set({ calculationProgress: progress });
        });
      } else if (scanType === 'temperature') {
        const data = scanEfficiencyVsTemperature(params);
        efficiencyCurve = data.map((d) => ({
          wavelength: d.temperature,
          efficiency: d.efficiency,
        }));
      } else if (scanType === 'angle') {
        const data = scanEfficiencyVsAngle(params);
        efficiencyCurve = data.map((d) => ({
          wavelength: d.angle,
          efficiency: d.efficiency,
        }));
      } else if (scanType === 'length') {
        const data = scanEfficiencyVsLength(params);
        efficiencyCurve = data.map((d) => ({
          wavelength: d.length,
          efficiency: d.efficiency,
        }));
      }

      set({
        result: { ...get().result, efficiencyCurve },
        calculationProgress: 1.0,
        isCalculating: false,
      });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : '效率曲线计算失败',
        isCalculating: false,
      });
    }
  },

  calculateTolerance: () => {
    set({ isCalculating: true, error: null });
    try {
      const { params } = get();
      const result = calculateToleranceData(params);
      set({
        result: { ...get().result, toleranceData: result },
        isCalculating: false,
      });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : '容许公差计算失败',
        isCalculating: false,
      });
    }
  },

  generateDomainStructure: () => {
    set({ isCalculating: true, error: null });
    try {
      const { params } = get();
      const result = generateDomainStructurePoints(params);
      set({
        result: { ...get().result, domainStructure: result },
        isCalculating: false,
      });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : '畴结构生成失败',
        isCalculating: false,
      });
    }
  },

  generateFieldDistribution: () => {
    set({ isCalculating: true, error: null });
    try {
      const { params, result } = get();
      if (!result.coupledWave) {
        throw new Error('请先计算耦合波方程');
      }
      const fieldData = generateFieldDistribution(params, result.coupledWave);
      set({
        result: { ...get().result, fieldDistribution: fieldData },
        isCalculating: false,
      });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : '场分布生成失败',
        isCalculating: false,
      });
    }
  },

  calculateSpectrum: () => {
    set({ isCalculating: true, error: null });
    try {
      const { params, result } = get();
      if (!result.coupledWave) {
        throw new Error('请先计算耦合波方程');
      }
      const spectrumData = analyzeSignalSpectrum(
        result.coupledWave,
        (params.signalWavelengthMin + params.signalWavelengthMax) / 2
      );
      set({
        result: { ...get().result, spectrumData },
        isCalculating: false,
      });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : '频谱分析失败',
        isCalculating: false,
      });
    }
  },

  calculateCascade: () => {
    set({ isCalculating: true, error: null });
    try {
      const { params, result } = get();
      if (!result.coupledWave) {
        throw new Error('请先计算耦合波方程');
      }
      const cascadeResult = solveCascadeProcesses(params, result.coupledWave);
      set({
        result: { ...get().result, cascadeResult },
        isCalculating: false,
      });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : '级联过程计算失败',
        isCalculating: false,
      });
    }
  },

  calculateNoncollinear: () => {
    set({ isCalculating: true, error: null });
    try {
      const { params } = get();
      const noncollinearResult = calculateNoncollinearPhaseMatching(params);
      set({
        result: { ...get().result, noncollinearResult },
        isCalculating: false,
      });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : '非共线相位匹配计算失败',
        isCalculating: false,
      });
    }
  },

  calculateMonteCarlo: async () => {
    set({ isCalculating: true, calculationProgress: 0, error: null });
    try {
      const { params } = get();
      const monteCarloResult = await runMonteCarloAnalysis(params, (progress) => {
        set({ calculationProgress: progress });
      });
      set({
        result: { ...get().result, monteCarloResult },
        isCalculating: false,
        calculationProgress: 1.0,
      });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : '蒙特卡洛分析失败',
        isCalculating: false,
      });
    }
  },

  setActiveTab: (tab) => {
    set({ activeTab: tab });
  },

  setScanType: (type) => {
    set({ scanType: type });
  },

  clearError: () => {
    set({ error: null });
  },
}));
