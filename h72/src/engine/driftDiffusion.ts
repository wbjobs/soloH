import { linspace, solveTridiagonal } from './math/matrix';
import { qdMaterials, transportLayerMaterials, electrodeMaterials } from '../data/materials';
import { 
  calculateSRHRate, 
  calculateAugerRate, 
  calculateThermalVelocity, 
  calculateIntrinsicCarrierConcentration,
  calculateRadiativeRate as calcRadiativeRate
} from './recombination';
import type { 
  InputParams, 
  CarrierDistribution, 
  IVLCharacteristics,
  BandDiagram,
  QDMaterial,
  EnergyLevels
} from '../types';

const Q = 1.602176634e-19;
const KB = 1.380649e-23;
const EPSILON_0 = 8.854187817e-12;
const NM_TO_M = 1e-9;
const CM_TO_M = 0.01;
const EV_TO_J = 1.602176634e-19;

interface Layer {
  name: string;
  thickness: number;
  material: string;
  type: 'anode' | 'htl' | 'qdl' | 'etl' | 'cathode';
}

function buildLayerStructure(params: InputParams): Layer[] {
  const ds = params.deviceStructure;
  return [
    { name: ds.anode, thickness: ds.anodeThickness, material: ds.anode, type: 'anode' },
    { name: ds.htl, thickness: ds.htlThickness, material: ds.htl, type: 'htl' },
    { name: 'QD Layer', thickness: ds.qdLayerThickness, material: params.qdMaterial, type: 'qdl' },
    { name: ds.etl, thickness: ds.etlThickness, material: ds.etl, type: 'etl' },
    { name: ds.cathode, thickness: ds.cathodeThickness, material: ds.cathode, type: 'cathode' },
  ];
}

function getMaterialProperties(layer: Layer, qdMaterial: string) {
  if (layer.type === 'qdl') {
    return qdMaterials[qdMaterial as keyof typeof qdMaterials];
  } else if (layer.type === 'anode' || layer.type === 'cathode') {
    return {
      bandGap: 0,
      electronAffinity: electrodeMaterials[layer.material as keyof typeof electrodeMaterials].workFunction,
      electronMass: 1,
      holeMass: 1,
      permittivity: 10,
      refractiveIndex: 1.5,
      electronMobility: 1e6,
      holeMobility: 1e6,
      augerCoefficientN: 0,
      augerCoefficientP: 0,
      interfaceStateDensity: 0,
      defectEnergyLevel: 0,
      electronCaptureCrossSection: 0,
      holeCaptureCrossSection: 0,
    };
  } else {
    const baseProps = transportLayerMaterials[layer.material as keyof typeof transportLayerMaterials];
    return {
      ...baseProps,
      augerCoefficientN: baseProps.augerCoefficientN || 1e-30,
      augerCoefficientP: baseProps.augerCoefficientP || 1e-31,
      interfaceStateDensity: baseProps.interfaceStateDensity || 1e11,
      defectEnergyLevel: baseProps.defectEnergyLevel || 0.5,
      electronCaptureCrossSection: baseProps.electronCaptureCrossSection || 1e-16,
      holeCaptureCrossSection: baseProps.holeCaptureCrossSection || 1e-16,
    };
  }
}

function generateGrid(layers: Layer[], totalPoints: number): {
  x: Float64Array;
  layerIndices: number[];
  layerBoundaries: { name: string; position: number }[];
} {
  const totalThickness = layers.reduce((sum, l) => sum + l.thickness, 0);
  const x = linspace(0, totalThickness, totalPoints);
  const layerIndices = new Array(totalPoints).fill(0);
  const layerBoundaries: { name: string; position: number }[] = [];

  let currentPosition = 0;
  for (let li = 0; li < layers.length; li++) {
    const layer = layers[li];
    layerBoundaries.push({ name: layer.name, position: currentPosition });
    const nextPosition = currentPosition + layer.thickness;
    for (let i = 0; i < totalPoints; i++) {
      if (x[i] >= currentPosition && x[i] < nextPosition) {
        layerIndices[i] = li;
      }
    }
    currentPosition = nextPosition;
  }
  layerBoundaries.push({ name: 'End', position: totalThickness });

  return { x, layerIndices, layerBoundaries };
}

function calculateBandEdges(
  x: Float64Array,
  layers: Layer[],
  layerIndices: number[],
  qdMaterial: string,
  voltage: number
): { Ec: Float64Array; Ev: Float64Array } {
  const Ec = new Float64Array(x.length);
  const Ev = new Float64Array(x.length);

  for (let i = 0; i < x.length; i++) {
    const layer = layers[layerIndices[i]];
    const props = getMaterialProperties(layer, qdMaterial);

    const anodeWF = electrodeMaterials[layers[0].material as keyof typeof electrodeMaterials].workFunction;
    const cathodeWF = electrodeMaterials[layers[layers.length - 1].material as keyof typeof electrodeMaterials].workFunction;
    const builtInVoltage = Math.abs(anodeWF - cathodeWF);

    const potentialDrop = (voltage + builtInVoltage) * (x[i] / x[x.length - 1]);

    if (layer.type === 'anode') {
      Ec[i] = anodeWF - potentialDrop;
      Ev[i] = Ec[i];
    } else if (layer.type === 'cathode') {
      Ec[i] = cathodeWF - voltage;
      Ev[i] = Ec[i];
    } else {
      Ec[i] = props.electronAffinity - potentialDrop;
      Ev[i] = Ec[i] - props.bandGap;
    }
  }

  return { Ec, Ev };
}

function calculateMobility(
  electricField: number,
  baseMobility: number,
  temperature: number
): number {
  const fieldFactor = Math.exp(0.01 * Math.sqrt(Math.abs(electricField)));
  return baseMobility * fieldFactor;
}

function calculateTotalRecombination(
  n: number,
  p: number,
  layer: Layer,
  qdMaterial: string,
  temperature: number,
  currentDensity: number = 1
): { radiative: number; srh: number; auger: number; total: number } {
  const props = getMaterialProperties(layer, qdMaterial);
  const isQDLayer = layer.type === 'qdl';
  
  const B = isQDLayer ? 1e-10 : 1e-12;
  const radiative = B * n * p;
  
  if (!isQDLayer) {
    const ni = 1e10;
    return {
      radiative,
      srh: Math.max(0, (n * p - ni * ni) / 1e-6),
      auger: 0,
      total: radiative + Math.max(0, (n * p - ni * ni) / 1e-6),
    };
  }
  
  const ni = calculateIntrinsicCarrierConcentration(
    props.bandGap,
    props.electronMass,
    props.holeMass,
    temperature
  );
  
  const Nt = props.interfaceStateDensity || 1e12;
  const sigmaN = props.electronCaptureCrossSection || 1e-15;
  const sigmaP = props.holeCaptureCrossSection || 1e-15;
  const Et = props.defectEnergyLevel || 0.5;
  const Ei = props.bandGap / 2;
  const vThN = calculateThermalVelocity(props.electronMass, temperature);
  const vThP = calculateThermalVelocity(props.holeMass, temperature);
  
  let srh = calculateSRHRate(n, p, ni, Nt, sigmaN, sigmaP, Et, Ei, vThN, vThP, temperature);
  srh = Math.max(0, srh);
  
  const J = currentDensity;
  const jFactor = 1 + 0.3 * Math.log10(Math.max(1, J));
  srh *= Math.sqrt(jFactor);
  
  const Cn = props.augerCoefficientN || 1e-28;
  const Cp = props.augerCoefficientP || 5e-29;
  let auger = calculateAugerRate(n, p, Cn, Cp);
  auger *= Math.pow(Math.max(1, J / 10), 0.7);
  
  const total = radiative + srh + auger;
  
  return { radiative, srh, auger, total };
}

export function solveDriftDiffusion(
  params: InputParams,
  biasVoltage: number
): CarrierDistribution {
  const layers = buildLayerStructure(params);
  const grid = generateGrid(layers, params.calculationParams.gridPoints);
  const { x, layerIndices, layerBoundaries } = grid;
  const T = params.calculationParams.temperature;
  const dx = x[1] - x[0];
  const dxM = dx * NM_TO_M;

  const { Ec, Ev } = calculateBandEdges(x, layers, layerIndices, params.qdMaterial, biasVoltage);

  let n = new Float64Array(x.length).fill(1e14);
  let p = new Float64Array(x.length).fill(1e14);
  let phi = new Float64Array(x.length);

  for (let iter = 0; iter < 50; iter++) {
    const E = new Float64Array(x.length);
    for (let i = 1; i < x.length - 1; i++) {
      E[i] = -(phi[i + 1] - phi[i - 1]) / (2 * dxM);
    }
    E[0] = E[1];
    E[x.length - 1] = E[x.length - 2];

    const a = new Float64Array(x.length);
    const b = new Float64Array(x.length);
    const c = new Float64Array(x.length);
    const d = new Float64Array(x.length);

    for (let i = 1; i < x.length - 1; i++) {
      const layer = layers[layerIndices[i]];
      const props = getMaterialProperties(layer, params.qdMaterial);
      const permittivity = props.permittivity * EPSILON_0;

      const muN = calculateMobility(E[i], props.electronMobility * CM_TO_M * CM_TO_M, T);
      const muP = calculateMobility(E[i], props.holeMobility * CM_TO_M * CM_TO_M, T);

      b[i] = 2 / (dxM * dxM);
      a[i] = -1 / (dxM * dxM);
      c[i] = -1 / (dxM * dxM);
      d[i] = -Q * (p[i] - n[i]) / permittivity;
    }

    b[0] = 1;
    a[0] = 0;
    c[0] = 0;
    d[0] = -phi[0] + biasVoltage;

    b[x.length - 1] = 1;
    a[x.length - 1] = 0;
    c[x.length - 1] = 0;
    d[x.length - 1] = -phi[x.length - 1];

    phi = solveTridiagonal(a, b, c, d);

    for (let i = 1; i < x.length - 1; i++) {
      E[i] = -(phi[i + 1] - phi[i - 1]) / (2 * dxM);
    }

    for (let i = 1; i < x.length - 1; i++) {
      const layer = layers[layerIndices[i]];
      const props = getMaterialProperties(layer, params.qdMaterial);
      const muN = calculateMobility(E[i], props.electronMobility * CM_TO_M * CM_TO_M, T);
      const muP = calculateMobility(E[i], props.holeMobility * CM_TO_M * CM_TO_M, T);
      const Dn = muN * KB * T / Q;
      const Dp = muP * KB * T / Q;

      const nFlux = muN * (n[i + 1] * E[i + 1] - n[i - 1] * E[i - 1]) / (2 * dxM) +
                   Dn * (n[i + 1] - 2 * n[i] + n[i - 1]) / (dxM * dxM);
      const pFlux = -muP * (p[i + 1] * E[i + 1] - p[i - 1] * E[i - 1]) / (2 * dxM) +
                   Dp * (p[i + 1] - 2 * p[i] + p[i - 1]) / (dxM * dxM);

      const estimatedJ = Math.max(1, biasVoltage * 10);
      const recombination = calculateTotalRecombination(
        n[i], p[i], layers[layerIndices[i]], params.qdMaterial, T, estimatedJ
      );

      n[i] += 1e-9 * (nFlux - recombination.total);
      p[i] += 1e-9 * (pFlux - recombination.total);

      n[i] = Math.max(1e10, n[i]);
      p[i] = Math.max(1e10, p[i]);
    }

    n[0] = 1e18;
    p[0] = 1e14;
    n[x.length - 1] = 1e14;
    p[x.length - 1] = 1e18;
  }

  const electricField = new Float64Array(x.length);
  const recombinationRate = new Float64Array(x.length);

  for (let i = 0; i < x.length; i++) {
    if (i === 0) {
      electricField[i] = -(phi[1] - phi[0]) / dxM;
    } else if (i === x.length - 1) {
      electricField[i] = -(phi[i] - phi[i - 1]) / dxM;
    } else {
      electricField[i] = -(phi[i + 1] - phi[i - 1]) / (2 * dxM);
    }

    const estimatedJ = Math.max(1, biasVoltage * 10);
    const recombination = calculateTotalRecombination(
      n[i], p[i], layers[layerIndices[i]], params.qdMaterial, T, estimatedJ
    );
    recombinationRate[i] = recombination.total;
  }

  return {
    depth: Array.from(x),
    electronDensity: Array.from(n),
    holeDensity: Array.from(p),
    recombinationRate: Array.from(recombinationRate),
    electricField: Array.from(electricField),
  };
}

export function calculateIVLCharacteristics(
  params: InputParams,
  energyLevels: EnergyLevels,
  qdMaterial: string,
  temperature: number
): IVLCharacteristics {
  const { voltageStart, voltageEnd, voltageStep } = params.calculationParams;
  const numPoints = Math.ceil((voltageEnd - voltageStart) / voltageStep) + 1;

  const jvData: { voltage: number; currentDensity: number }[] = [];
  const lvData: { voltage: number; brightness: number }[] = [];
  let turnOnVoltage = voltageEnd;
  let maxEQE = 0;

  for (let i = 0; i < numPoints; i++) {
    const voltage = voltageStart + i * voltageStep;
    const carrierDist = solveDriftDiffusion(params, voltage);

    let totalRecombination = 0;
    let totalCurrent = 0;
    let radiativeRecombination = 0;
    const dx = carrierDist.depth[1] - carrierDist.depth[0];
    const dxM = dx * NM_TO_M;

    for (let j = 1; j < carrierDist.depth.length - 1; j++) {
      totalRecombination += carrierDist.recombinationRate[j] * dxM;
      const dndx = (carrierDist.electronDensity[j + 1] - carrierDist.electronDensity[j - 1]) / (2 * dxM);
      totalCurrent += Q * carrierDist.electronDensity[j] * 1e-4 * Math.abs(carrierDist.electricField[j]) + Q * 1e-4 * 0.01 * dndx;
    }

    const currentDensity = totalCurrent / carrierDist.depth.length * 1e3;
    
    const J = Math.max(0.1, Math.abs(currentDensity));
    const recombination = calcRadiativeRate(
      energyLevels,
      qdMaterial as QDMaterial,
      temperature,
      J
    );

    const iqe = recombination.iqe;
    const photonFlux = totalRecombination * iqe;
    const brightness = photonFlux * 1240 / 683 * 1e-7;

    if (brightness > 1 && voltage < turnOnVoltage) {
      turnOnVoltage = voltage;
    }

    const eqe = voltage > 0 ? (brightness * Q * 1240 / (voltage * currentDensity * 1e-3)) * 100 : 0;
    maxEQE = Math.max(maxEQE, eqe);

    jvData.push({ voltage, currentDensity });
    lvData.push({ voltage, brightness });
  }

  return {
    jvData,
    lvData,
    turnOnVoltage,
    maxEQE,
  };
}

export function calculateBandDiagram(
  params: InputParams,
  biasVoltage: number = 0
): BandDiagram {
  const layers = buildLayerStructure(params);
  const grid = generateGrid(layers, params.calculationParams.gridPoints);
  const { x, layerIndices, layerBoundaries } = grid;

  const { Ec, Ev } = calculateBandEdges(x, layers, layerIndices, params.qdMaterial, biasVoltage);

  const anodeWF = electrodeMaterials[layers[0].material as keyof typeof electrodeMaterials].workFunction;
  const cathodeWF = electrodeMaterials[layers[layers.length - 1].material as keyof typeof electrodeMaterials].workFunction;
  const builtInVoltage = Math.abs(anodeWF - cathodeWF);

  const fermiLevel = new Float64Array(x.length);
  for (let i = 0; i < x.length; i++) {
    fermiLevel[i] = anodeWF - (biasVoltage + builtInVoltage) * (x[i] / x[x.length - 1]);
  }

  return {
    depth: Array.from(x),
    conductionBand: Array.from(Ec),
    valenceBand: Array.from(Ev),
    fermiLevel: Array.from(fermiLevel),
    layerBoundaries,
  };
}

export function calculateAllVoltages(
  params: InputParams,
  energyLevels: EnergyLevels,
  onProgress?: (progress: number, message: string) => void
): {
  ivl: IVLCharacteristics;
  carrierDistributions: Map<number, CarrierDistribution>;
  bandDiagrams: Map<number, BandDiagram>;
} {
  const { voltageStart, voltageEnd, voltageStep } = params.calculationParams;
  const numPoints = Math.ceil((voltageEnd - voltageStart) / voltageStep) + 1;

  const carrierDistributions = new Map<number, CarrierDistribution>();
  const bandDiagrams = new Map<number, BandDiagram>();

  for (let i = 0; i < numPoints; i++) {
    const voltage = voltageStart + i * voltageStep;
    const progress = ((i + 1) / numPoints) * 100;

    if (onProgress) {
      onProgress(progress / 2, `正在计算 ${voltage.toFixed(1)}V 下的载流子分布...`);
    }

    const carrierDist = solveDriftDiffusion(params, voltage);
    carrierDistributions.set(voltage, carrierDist);

    if (onProgress) {
      onProgress(50 + progress / 2, `正在计算 ${voltage.toFixed(1)}V 下的能带图...`);
    }

    const bandDiagram = calculateBandDiagram(params, voltage);
    bandDiagrams.set(voltage, bandDiagram);
  }

  if (onProgress) {
    onProgress(95, '正在计算IVL特性...');
  }

  const ivl = calculateIVLCharacteristics(
    params,
    energyLevels,
    params.qdMaterial,
    params.calculationParams.temperature
  );

  if (onProgress) {
    onProgress(100, '计算完成！');
  }

  return { ivl, carrierDistributions, bandDiagrams };
}
