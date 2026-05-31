import type {
  CalculationParams,
  CalculationResult,
  Material,
  WorkerMessage,
  WorkerMessageType,
} from '../types';
import { getMaterialById, getBandgapAtTemperature } from '../data/materials';
import { generateBlackbodySpectrum } from '../utils/physics/blackbody';
import {
  calculateQuantumEfficiency,
  calculateJscWithQE,
  calculateIVCurve,
  calculateIVCurveDistributed,
  calculateFillFactor,
  calculateEfficiency,
  findMaxPowerPoint,
  performBandgapScan,
  calculateConcentrationPerformance,
  performConcentrationScan,
  calculateWasteHeatRecovery,
  calculateLifetimePrediction,
} from '../utils/physics/detailedBalance';
import { calculateReflectanceSpectrum } from '../utils/physics/tmm';
import { optimizeEmitter } from '../utils/physics/optimizer';

let isCancelled = false;

function sendMessage(type: WorkerMessageType, payload?: any): void {
  self.postMessage({ type, payload });
}

function sendProgress(progress: number, currentStep: string): void {
  sendMessage('progress', { progress, currentStep });
}

async function performCalculation(
  params: CalculationParams,
  customMaterials: Material[] = []
): Promise<CalculationResult> {
  const startTime = performance.now();
  isCancelled = false;

  const allMaterials = [...customMaterials];
  let material = allMaterials.find(m => m.id === params.materialId);
  if (!material) {
    material = getMaterialById(params.materialId);
  }
  if (!material) {
    throw new Error(`Material with id ${params.materialId} not found`);
  }

  const bandgap = getBandgapAtTemperature(material, params.temperature);

  sendProgress(0.05, '计算黑体辐射谱...');
  const blackbodySpectrum = generateBlackbodySpectrum(
    params.sourceTemperature,
    200,
    5000,
    500
  );

  if (isCancelled) throw new Error('Calculation cancelled');

  let emitterStructure = params.emitterStructure;
  
  if (params.optimizeEmitter) {
    sendProgress(0.15, '优化选择性发射极结构...');
    emitterStructure = await optimizeEmitter(
      params.sourceTemperature,
      bandgap,
      params.emitterStructure,
      true,
      (progress, fitness) => {
        sendProgress(0.15 + progress * 0.25, `优化发射极中... (匹配度: ${(fitness * 100).toFixed(1)}%)`);
      }
    );
  }

  if (isCancelled) throw new Error('Calculation cancelled');

  sendProgress(0.45, '计算发射极反射谱...');
  const emitterReflectance = calculateReflectanceSpectrum(
    emitterStructure,
    200,
    5000,
    200,
    0,
    material.refractiveIndex,
    params.sourceTemperature
  );

  if (isCancelled) throw new Error('Calculation cancelled');

  sendProgress(0.55, '计算量子效率...');
  const quantumEfficiency = calculateQuantumEfficiency(
    bandgap,
    material,
    200,
    5000,
    200
  );

  if (isCancelled) throw new Error('Calculation cancelled');

  sendProgress(0.65, '计算短路电流...');
  const refWavelengths = emitterReflectance.map(p => p.wavelength);
  const reflectances = emitterReflectance.map(p => p.r);
  
  const shortCircuitCurrent = calculateJscWithQE(
    params.sourceTemperature,
    quantumEfficiency,
    reflectances,
    refWavelengths
  );

  if (isCancelled) throw new Error('Calculation cancelled');

  sendProgress(0.75, '计算I-V曲线...');
  let ivCurve;
  if (params.useDistributedResistance && params.includeSeriesResistance) {
    ivCurve = calculateIVCurveDistributed(
      shortCircuitCurrent,
      bandgap,
      params.temperature,
      params.seriesResistance,
      params.shuntResistance,
      params.includeRadiative,
      params.includeAuger,
      params.includeSeriesResistance,
      material,
      params.emitterSheetResistance,
      params.fingerSpacing,
      params.fingerWidth,
      150
    );
  } else {
    ivCurve = calculateIVCurve(
      shortCircuitCurrent,
      bandgap,
      params.temperature,
      params.includeSeriesResistance ? params.seriesResistance : 0,
      params.shuntResistance,
      params.includeRadiative,
      params.includeAuger,
      params.includeSeriesResistance,
      material,
      150
    );
  }

  if (isCancelled) throw new Error('Calculation cancelled');

  sendProgress(0.85, '计算性能指标...');
  const fillFactor = calculateFillFactor(ivCurve);
  const efficiency = calculateEfficiency(ivCurve, params.sourceTemperature);
  const { maxPowerDensity, voltageAtMaxPower, currentAtMaxPower } = findMaxPowerPoint(ivCurve);
  
  const openCircuitVoltage = ivCurve.find(p => p.j <= 0.001)?.v || 0;

  if (isCancelled) throw new Error('Calculation cancelled');

  sendProgress(0.9, '进行带隙-效率二维扫描...');
  const bandgapScan = performBandgapScan(
    params.sourceTemperature,
    0.3,
    2.0,
    25,
    600,
    2000,
    15,
    material,
    params.temperature
  );

  if (isCancelled) throw new Error('Calculation cancelled');

  let concentrationResult;
  if (params.includeConcentration) {
    sendProgress(0.94, '计算聚光条件下的性能...');
    const concPerformance = calculateConcentrationPerformance(
      shortCircuitCurrent,
      openCircuitVoltage,
      fillFactor,
      efficiency,
      params.sourceTemperature,
      params.temperature,
      params.concentrationRatio,
      params.includeSeriesResistance ? params.seriesResistance : 0
    );
    
    const concScan = performConcentrationScan(
      shortCircuitCurrent,
      openCircuitVoltage,
      fillFactor,
      efficiency,
      params.sourceTemperature,
      params.temperature,
      params.includeSeriesResistance ? params.seriesResistance : 0
    );
    
    concentrationResult = {
      concentrationRatio: params.concentrationRatio,
      concentratedJsc: concPerformance.jsc,
      concentratedVoc: concPerformance.voc,
      concentratedEfficiency: concPerformance.efficiency,
      concentratedFillFactor: concPerformance.ff,
      cellTemperatureRise: concPerformance.tempRise,
      actualCellTemperature: concPerformance.actualTemp,
      concentrationEfficiencyCurve: concScan.curve,
      optimumConcentration: concScan.optimumCR,
      maximumEfficiency: concScan.maxEff,
    };
  }

  if (isCancelled) throw new Error('Calculation cancelled');

  let wasteHeatResult;
  if (params.includeWasteHeatRecovery) {
    sendProgress(0.96, '计算热电耦合废热回收...');
    const baseEfficiency = concentrationResult?.concentratedEfficiency ?? efficiency;
    const cellTemp = concentrationResult?.actualCellTemperature ?? params.temperature;
    
    const whResult = calculateWasteHeatRecovery(
      baseEfficiency,
      params.sourceTemperature,
      cellTemp,
      params.tegColdSideTemperature,
      params.tegFigureOfMerit,
      params.tegEfficiency
    );
    
    wasteHeatResult = {
      wasteHeatDensity: whResult.wasteHeatDensity,
      totalWasteHeat: whResult.totalWasteHeat,
      tegOutputPower: whResult.tegOutputPower,
      tegEfficiency: whResult.tegEfficiencyActual,
      systemTotalEfficiency: whResult.systemTotalEfficiency,
      heatRejectionTemperature: whResult.heatRejectionTemperature,
      carnotEfficiency: whResult.carnotEff,
    };
  }

  if (isCancelled) throw new Error('Calculation cancelled');

  let lifetimeResult;
  if (params.includeLifetimePrediction) {
    sendProgress(0.98, '预测电池寿命...');
    const operatingTemp = wasteHeatResult?.heatRejectionTemperature 
      ?? concentrationResult?.actualCellTemperature 
      ?? params.temperature;
    
    const lifeResult = calculateLifetimePrediction(
      params.referenceLifetime,
      params.activationEnergy,
      operatingTemp,
      params.temperature
    );
    
    lifetimeResult = {
      estimatedLifetime: lifeResult.estimatedLifetime,
      accelerationFactor: lifeResult.accelerationFactor,
      remainingLifetime: lifeResult.remainingLifetime,
      degradationRate: lifeResult.degradationRate,
      lifetimeCurve: lifeResult.lifetimeCurve,
      mtbf: lifeResult.mtbf,
      failureRate: lifeResult.failureRate,
    };
  }

  const calculationTime = (performance.now() - startTime) / 1000;

  sendProgress(1.0, '计算完成!');

  return {
    efficiency,
    shortCircuitCurrent,
    openCircuitVoltage,
    fillFactor,
    ivCurve,
    quantumEfficiency,
    blackbodySpectrum,
    emitterReflectance,
    bandgapScan,
    optimizedEmitter: emitterStructure,
    calculationTime,
    maxPowerDensity,
    voltageAtMaxPower,
    currentAtMaxPower,
    concentrationResult,
    wasteHeatResult,
    lifetimeResult,
  };
}

self.onmessage = async (e: MessageEvent<WorkerMessage>) => {
  const { type, payload } = e.data;

  switch (type) {
    case 'startCalculation':
      try {
        const result = await performCalculation(
          payload.params,
          payload.customMaterials || []
        );
        sendMessage('result', result);
      } catch (error) {
        if (error instanceof Error && error.message === 'Calculation cancelled') {
          sendMessage('error', { message: '计算已取消' });
        } else {
          sendMessage('error', { 
            message: error instanceof Error ? error.message : '未知错误' 
          });
        }
      }
      break;

    case 'cancelCalculation':
      isCancelled = true;
      break;
  }
};

export {};
