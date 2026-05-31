import { calculateEnergyLevels } from './schrodinger';
import { calculateRadiativeRate, calculateEmissionSpectrum } from './recombination';
import { 
  solveDriftDiffusion, 
  calculateIVLCharacteristics, 
  calculateBandDiagram,
  calculateAllVoltages
} from './driftDiffusion';
import { calculateAgingResults } from './aging';
import { analyzeMQWCoupling } from './mqwCoupling';
import type { InputParams, CalculationResults, CalculationProgress } from '../types';

export async function runFullSimulation(
  params: InputParams,
  onProgress?: (progress: CalculationProgress) => Promise<void>
): Promise<CalculationResults> {
  const startTime = Date.now();

  const updateProgress = async (progress: number, message: string) => {
    if (onProgress) {
      await onProgress({
        status: 'calculating',
        progress,
        message,
      });
      await new Promise(resolve => setTimeout(resolve, 50));
    }
  };

  try {
    await updateProgress(5, '正在构建核壳势能...');
    await updateProgress(10, '正在求解薛定谔方程（有效质量近似）...');

    const energyLevels = calculateEnergyLevels(
      params.qdMaterial,
      params.shellMaterial,
      params.coreSize,
      params.shellThickness,
      params.calculationParams.gridPoints,
      5
    );

    await updateProgress(30, '正在计算费米黄金定则 - 辐射复合速率...');

    const refCurrentDensity = 10;
    const recombination = calculateRadiativeRate(
      energyLevels,
      params.qdMaterial,
      params.calculationParams.temperature,
      refCurrentDensity
    );

    await updateProgress(40, '正在计算多量子阱耦合效应...');
    
    if (params.mqwParams && params.mqwParams.couplingEnabled) {
      const mqwCoupling = analyzeMQWCoupling(params.mqwParams);
      energyLevels.mqwCoupling = mqwCoupling;
    }

    await updateProgress(45, '正在生成发射光谱...');

    const emissionSpectrum = calculateEmissionSpectrum(
      energyLevels,
      recombination,
      params.qdMaterial,
      params.deviceStructure,
      params.calculationParams.temperature
    );

    await updateProgress(60, '正在运行漂移扩散模型...');

    const { voltageStart, voltageEnd, voltageStep } = params.calculationParams;
    const numVoltages = Math.ceil((voltageEnd - voltageStart) / voltageStep) + 1;

    let carrierDistribution = solveDriftDiffusion(params, voltageStart);
    let bandDiagram = calculateBandDiagram(params, voltageStart);

    for (let i = 1; i < numVoltages; i++) {
      const voltage = voltageStart + i * voltageStep;
      const progress = 60 + (i / numVoltages) * 25;
      await updateProgress(progress, `正在计算 ${voltage.toFixed(1)}V 偏压下的载流子输运...`);

      if (voltage > 2 && voltage < 4) {
        carrierDistribution = solveDriftDiffusion(params, voltage);
        bandDiagram = calculateBandDiagram(params, voltage);
      }
    }

    await updateProgress(88, '正在计算IVL特性曲线...');

    const ivlCharacteristics = calculateIVLCharacteristics(
      params,
      energyLevels,
      params.qdMaterial,
      params.calculationParams.temperature
    );

    await updateProgress(92, '正在计算老化特性和寿命预测...');

    const maxBrightnessPoint = ivlCharacteristics.lvData.reduce(
      (max, point) => point.brightness > max.brightness ? point : max,
      ivlCharacteristics.lvData[0]
    );
    const maxCurrentPoint = ivlCharacteristics.jvData.reduce(
      (max, point) => point.currentDensity > max.currentDensity ? point : max,
      ivlCharacteristics.jvData[0]
    );

    const agingParams = params.agingParams || {
      testCurrentDensity: 10,
      testTemperature: params.calculationParams.temperature,
      targetLifetime: 10000,
    };

    const aging = calculateAgingResults(
      params.qdMaterial,
      maxBrightnessPoint.brightness,
      maxCurrentPoint.currentDensity,
      ivlCharacteristics.turnOnVoltage,
      agingParams.testCurrentDensity,
      agingParams.testTemperature,
      agingParams.targetLifetime
    );
    
    ivlCharacteristics.aging = aging;

    await updateProgress(98, '正在整理计算结果...');

    const calculationTime = (Date.now() - startTime) / 1000;

    await updateProgress(100, '计算完成！');

    return {
      energyLevels,
      recombination,
      emissionSpectrum,
      ivlCharacteristics,
      carrierDistribution,
      bandDiagram,
      calculationTime,
    };
  } catch (error) {
    if (onProgress) {
      await onProgress({
        status: 'error',
        progress: 0,
        message: '计算出错',
        error: error instanceof Error ? error.message : String(error),
      });
    }
    throw error;
  }
}

export function validateParams(params: InputParams): string[] {
  const errors: string[] = [];

  if (params.coreSize < 1 || params.coreSize > 10) {
    errors.push('核尺寸应在1-10 nm范围内');
  }

  if (params.shellThickness < 0 || params.shellThickness > 5) {
    errors.push('壳层厚度应在0-5 nm范围内');
  }

  if (params.calculationParams.gridPoints < 50 || params.calculationParams.gridPoints > 500) {
    errors.push('网格点数应在50-500范围内');
  }

  if (params.calculationParams.temperature < 100 || params.calculationParams.temperature > 500) {
    errors.push('温度应在100-500 K范围内');
  }

  const totalDeviceThickness = 
    params.deviceStructure.anodeThickness +
    params.deviceStructure.htlThickness +
    params.deviceStructure.qdLayerThickness +
    params.deviceStructure.etlThickness +
    params.deviceStructure.cathodeThickness;

  if (totalDeviceThickness > 1000) {
    errors.push('器件总厚度不应超过1000 nm');
  }

  return errors;
}
