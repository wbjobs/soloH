import type {
  SimulationParams,
  CoupledWaveResult,
  EfficiencyCurvePoint,
  ToleranceData,
  FieldDataPoint,
  CascadeResult,
  CascadeStageResult,
} from '../types';
import {
  calculatePhaseMatching,
} from './phaseMatching';
import {
  generatePolingStructure,
} from './poling';
import {
  calculateRefractiveIndexByCrystal,
  calculateExtraordinaryIndex,
  calculateIdlerWavelength,
  calculateWavevector,
  calculatePhaseMismatch,
  calculateBandwidth,
  calculateTemperatureTolerance,
  calculateAngleTolerance,
  calculateWavelengthTolerance,
  calculateEffectiveNonlinearity,
  PHYSICAL_CONSTANTS,
} from './physics';
import { getCrystalById } from '../data/crystals';

interface Complex {
  re: number;
  im: number;
}

function complexAdd(a: Complex, b: Complex): Complex {
  return { re: a.re + b.re, im: a.im + b.im };
}

function complexMul(a: Complex, b: Complex): Complex {
  return {
    re: a.re * b.re - a.im * b.im,
    im: a.re * b.im + a.im * b.re,
  };
}

function complexMulScalar(a: Complex, s: number): Complex {
  return { re: a.re * s, im: a.im * s };
}

function complexExp(phi: number): Complex {
  return { re: Math.cos(phi), im: Math.sin(phi) };
}

function complexConj(a: Complex): Complex {
  return { re: a.re, im: -a.im };
}

function complexAbs(a: Complex): number {
  return Math.sqrt(a.re * a.re + a.im * a.im);
}

export function solveCoupledWaveEquations(
  params: SimulationParams,
  signalWavelength?: number
): CoupledWaveResult {
  const signalLambda = signalWavelength ?? (params.signalWavelengthMin + params.signalWavelengthMax) / 2;
  const idlerLambda = calculateIdlerWavelength(params.pumpWavelength, signalLambda);
  const crystal = getCrystalById(params.crystalId);

  if (!crystal) {
    throw new Error(`Crystal not found: ${params.crystalId}`);
  }

  const pmResult = calculatePhaseMatching(params, signalLambda);

  const length_si = params.crystalLength * PHYSICAL_CONSTANTS.mm_to_m;
  const numSteps = Math.max(1000, Math.floor(params.crystalLength * 100));
  const dz = length_si / numSteps;

  const omegaP = (2 * Math.PI * PHYSICAL_CONSTANTS.c) / (params.pumpWavelength * PHYSICAL_CONSTANTS.nm_to_m);
  const omegaS = (2 * Math.PI * PHYSICAL_CONSTANTS.c) / (signalLambda * PHYSICAL_CONSTANTS.nm_to_m);
  const omegaI = (2 * Math.PI * PHYSICAL_CONSTANTS.c) / (idlerLambda * PHYSICAL_CONSTANTS.nm_to_m);

  const deff_si = pmResult.effectiveNonlinearity * PHYSICAL_CONSTANTS.pm_to_V;

  const pumpArea = Math.PI * (params.pumpWaist * PHYSICAL_CONSTANTS.um_to_m) ** 2;
  const signalArea = Math.PI * (params.signalWaist * PHYSICAL_CONSTANTS.um_to_m) ** 2;
  const pumpIntensity = params.pumpPower / pumpArea;
  const signalIntensity = params.signalPower / signalArea;

  const nPump = pmResult.nPump;
  const nSignal = pmResult.nSignal;
  const nIdler = pmResult.nIdler;

  let A_pump: Complex = {
    re: Math.sqrt(2 * pumpIntensity * nPump * PHYSICAL_CONSTANTS.epsilon0 * PHYSICAL_CONSTANTS.c),
    im: 0,
  };
  let A_signal: Complex = {
    re: Math.sqrt(2 * signalIntensity * nSignal * PHYSICAL_CONSTANTS.epsilon0 * PHYSICAL_CONSTANTS.c),
    im: 0,
  };
  let A_idler: Complex = { re: 0, im: 0 };

  const z: number[] = [];
  const pumpIntensityOut: number[] = [];
  const signalIntensityOut: number[] = [];
  const idlerIntensityOut: number[] = [];
  const pumpPhaseOut: number[] = [];
  const signalPhaseOut: number[] = [];
  const idlerPhaseOut: number[] = [];

  const polingStructure = generatePolingStructure(params, numSteps);

  const alpha_p = 0.001;
  const alpha_s = 0.001;
  const alpha_i = 0.001;

  const i = { re: 0, im: 1 };

  function derivatives(
    state: [Complex, Complex, Complex],
    currentZ: number,
    idx: number
  ): [Complex, Complex, Complex] {
    const [Ap, As, Ai] = state;
    const polarity = polingStructure.polarity[idx] || 1;

    const kPump = calculateWavevector(params.pumpWavelength, nPump);
    const kSignal = calculateWavevector(signalLambda, nSignal);
    const kIdler = calculateWavevector(idlerLambda, nIdler);
    const deltaK = calculatePhaseMismatch(kPump, kSignal, kIdler, params.polingPeriod);

    const phaseFactor = complexExp(-deltaK * currentZ);

    const nonlinearTerm_p = complexMul(As, complexConj(Ai));
    const nonlinearTerm_s = complexMul(Ap, complexConj(Ai));
    const nonlinearTerm_i = complexMul(Ap, complexConj(As));

    const coeffP = complexMulScalar(i, polarity * (omegaP * deff_si) / (nPump * PHYSICAL_CONSTANTS.c));
    const coeffS = complexMulScalar(i, polarity * (omegaS * deff_si) / (nSignal * PHYSICAL_CONSTANTS.c));
    const coeffI = complexMulScalar(i, polarity * (omegaI * deff_si) / (nIdler * PHYSICAL_CONSTANTS.c));

    const dAp_dz: Complex = complexAdd(
      complexMulScalar(Ap, -alpha_p / 2),
      complexMul(
        complexMul(nonlinearTerm_p, phaseFactor),
        coeffP
      )
    );

    const dAs_dz: Complex = complexAdd(
      complexMulScalar(As, -alpha_s / 2),
      complexMul(
        complexMul(nonlinearTerm_s, phaseFactor),
        coeffS
      )
    );

    const dAi_dz: Complex = complexAdd(
      complexMulScalar(Ai, -alpha_i / 2),
      complexMul(
        complexMul(nonlinearTerm_i, phaseFactor),
        coeffI
      )
    );

    return [dAp_dz, dAs_dz, dAi_dz];
  }

  for (let step = 0; step < numSteps; step++) {
    const currentZ = step * dz;
    z.push(currentZ);

    const intensityP = (complexAbs(A_pump) ** 2) / (2 * nPump * PHYSICAL_CONSTANTS.epsilon0 * PHYSICAL_CONSTANTS.c);
    const intensityS = (complexAbs(A_signal) ** 2) / (2 * nSignal * PHYSICAL_CONSTANTS.epsilon0 * PHYSICAL_CONSTANTS.c);
    const intensityI = (complexAbs(A_idler) ** 2) / (2 * nIdler * PHYSICAL_CONSTANTS.epsilon0 * PHYSICAL_CONSTANTS.c);

    pumpIntensityOut.push(intensityP);
    signalIntensityOut.push(intensityS);
    idlerIntensityOut.push(intensityI);

    pumpPhaseOut.push(Math.atan2(A_pump.im, A_pump.re));
    signalPhaseOut.push(Math.atan2(A_signal.im, A_signal.re));
    idlerPhaseOut.push(Math.atan2(A_idler.im, A_idler.re));

    const k1 = derivatives([A_pump, A_signal, A_idler], currentZ, step);
    const k2 = derivatives(
      [
        complexAdd(A_pump, complexMulScalar(k1[0], dz / 2)),
        complexAdd(A_signal, complexMulScalar(k1[1], dz / 2)),
        complexAdd(A_idler, complexMulScalar(k1[2], dz / 2)),
      ],
      currentZ + dz / 2,
      step
    );
    const k3 = derivatives(
      [
        complexAdd(A_pump, complexMulScalar(k2[0], dz / 2)),
        complexAdd(A_signal, complexMulScalar(k2[1], dz / 2)),
        complexAdd(A_idler, complexMulScalar(k2[2], dz / 2)),
      ],
      currentZ + dz / 2,
      step
    );
    const k4 = derivatives(
      [
        complexAdd(A_pump, complexMulScalar(k3[0], dz)),
        complexAdd(A_signal, complexMulScalar(k3[1], dz)),
        complexAdd(A_idler, complexMulScalar(k3[2], dz)),
      ],
      currentZ + dz,
      step
    );

    A_pump = complexAdd(
      A_pump,
      complexMulScalar(
        complexAdd(
          complexAdd(k1[0], complexMulScalar(k2[0], 2)),
          complexAdd(complexMulScalar(k3[0], 2), k4[0])
        ),
        dz / 6
      )
    );
    A_signal = complexAdd(
      A_signal,
      complexMulScalar(
        complexAdd(
          complexAdd(k1[1], complexMulScalar(k2[1], 2)),
          complexAdd(complexMulScalar(k3[1], 2), k4[1])
        ),
        dz / 6
      )
    );
    A_idler = complexAdd(
      A_idler,
      complexMulScalar(
        complexAdd(
          complexAdd(k1[2], complexMulScalar(k2[2], 2)),
          complexAdd(complexMulScalar(k3[2], 2), k4[2])
        ),
        dz / 6
      )
    );
  }

  const finalPumpIntensity = pumpIntensityOut[pumpIntensityOut.length - 1];
  const finalSignalIntensity = signalIntensityOut[signalIntensityOut.length - 1];
  const conversionEfficiency = (finalSignalIntensity * signalArea / params.pumpPower) * 100;
  const pumpDepletion = (1 - finalPumpIntensity * pumpArea / params.pumpPower) * 100;

  return {
    z,
    pumpIntensity: pumpIntensityOut,
    signalIntensity: signalIntensityOut,
    idlerIntensity: idlerIntensityOut,
    pumpPhase: pumpPhaseOut,
    signalPhase: signalPhaseOut,
    idlerPhase: idlerPhaseOut,
    conversionEfficiency: Math.max(0, conversionEfficiency),
    pumpDepletion: Math.max(0, Math.min(100, pumpDepletion)),
  };
}

export function calculateEfficiencyCurve(
  params: SimulationParams,
  onProgress?: (progress: number) => void
): EfficiencyCurvePoint[] {
  const results: EfficiencyCurvePoint[] = [];
  const numPoints = Math.ceil(
    (params.signalWavelengthMax - params.signalWavelengthMin) / params.signalWavelengthStep
  );

  for (let i = 0; i <= numPoints; i++) {
    const wavelength = params.signalWavelengthMin + i * params.signalWavelengthStep;
    try {
      const cwResult = solveCoupledWaveEquations(params, wavelength);
      results.push({
        wavelength,
        efficiency: cwResult.conversionEfficiency,
      });
    } catch (e) {
      results.push({
        wavelength,
        efficiency: 0,
      });
    }
    if (onProgress) {
      onProgress((i + 1) / (numPoints + 1));
    }
  }

  return results;
}

export function calculateToleranceData(
  params: SimulationParams
): ToleranceData {
  const centerWavelength = (params.signalWavelengthMin + params.signalWavelengthMax) / 2;
  const pmResult = calculatePhaseMatching(params, centerWavelength);

  const crystal = getCrystalById(params.crystalId);
  if (!crystal) {
    return {
      temperatureTolerance: 0,
      angleTolerance: 0,
      wavelengthTolerance: 0,
      bandwidth: 0,
    };
  }

  const bandwidth = calculateBandwidth(
    centerWavelength,
    params.crystalLength,
    pmResult.groupVelocityMismatch
  );

  const dnPump_dT = crystal.thermoOpticCoefficients.dn_e_dT;
  const dnSignal_dT = crystal.thermoOpticCoefficients.dn_o_dT;
  const dnIdler_dT = params.phaseMatchType === 'type1'
    ? crystal.thermoOpticCoefficients.dn_o_dT
    : crystal.thermoOpticCoefficients.dn_e_dT;

  const temperatureTolerance = calculateTemperatureTolerance(
    params.crystalLength,
    dnPump_dT,
    dnSignal_dT,
    dnIdler_dT,
    params.pumpWavelength,
    centerWavelength,
    pmResult.idlerWavelength
  );

  const nO_pump = calculateRefractiveIndexByCrystal(
    params.crystalId,
    params.pumpWavelength,
    'ordinary',
    params.temperature
  );
  const nE_pump = calculateRefractiveIndexByCrystal(
    params.crystalId,
    params.pumpWavelength,
    'extraordinary',
    params.temperature
  );
  const deltaN = Math.abs(nE_pump - nO_pump);

  const angleTolerance = calculateAngleTolerance(
    params.crystalLength,
    deltaN,
    centerWavelength
  );

  const wavelengthTolerance = calculateWavelengthTolerance(
    params.crystalLength,
    pmResult.groupVelocityMismatch
  );

  return {
    temperatureTolerance,
    angleTolerance,
    wavelengthTolerance,
    bandwidth,
  };
}

export function generateFieldDistribution(
  params: SimulationParams,
  cwResult: CoupledWaveResult,
  nx: number = 30,
  ny: number = 30
): FieldDataPoint[] {
  const result: FieldDataPoint[] = [];
  const length = params.crystalLength * PHYSICAL_CONSTANTS.mm_to_m;
  const width = params.pumpWaist * 4 * PHYSICAL_CONSTANTS.um_to_m;

  for (let i = 0; i < nx; i++) {
    const x = (i - nx / 2) * width / nx;
    for (let j = 0; j < ny; j++) {
      const y = (j - ny / 2) * width / ny;
      const r2 = x * x + y * y;
      const w0 = params.pumpWaist * PHYSICAL_CONSTANTS.um_to_m;
      const gaussianProfile = Math.exp(-r2 / (w0 * w0));

      for (let k = 0; k < cwResult.z.length; k += 10) {
        const z = cwResult.z[k];
        const signalAmplitude = Math.sqrt(cwResult.signalIntensity[k]) * gaussianProfile;
        const signalPhase = cwResult.signalPhase[k];

        result.push({
          x,
          y,
          z,
          amplitude: signalAmplitude,
          phase: signalPhase,
        });
      }
    }
  }

  return result;
}

export function scanEfficiencyVsTemperature(
  params: SimulationParams,
  tempMin: number = 0,
  tempMax: number = 100,
  tempStep: number = 2
): { temperature: number; efficiency: number }[] {
  const results: { temperature: number; efficiency: number }[] = [];
  const numSteps = Math.ceil((tempMax - tempMin) / tempStep);

  for (let i = 0; i <= numSteps; i++) {
    const temperature = tempMin + i * tempStep;
    const tempParams = { ...params, temperature };
    try {
      const cwResult = solveCoupledWaveEquations(tempParams);
      results.push({
        temperature,
        efficiency: cwResult.conversionEfficiency,
      });
    } catch (e) {
      results.push({
        temperature,
        efficiency: 0,
      });
    }
  }

  return results;
}

export function scanEfficiencyVsAngle(
  params: SimulationParams,
  angleMin: number = 80,
  angleMax: number = 90,
  angleStep: number = 0.2
): { angle: number; efficiency: number }[] {
  const results: { angle: number; efficiency: number }[] = [];
  const numSteps = Math.ceil((angleMax - angleMin) / angleStep);

  for (let i = 0; i <= numSteps; i++) {
    const angle = angleMin + i * angleStep;
    const angleParams = { ...params, angleTheta: angle };
    try {
      const cwResult = solveCoupledWaveEquations(angleParams);
      results.push({
        angle,
        efficiency: cwResult.conversionEfficiency,
      });
    } catch (e) {
      results.push({
        angle,
        efficiency: 0,
      });
    }
  }

  return results;
}

export function scanEfficiencyVsLength(
  params: SimulationParams,
  lengthMax: number = 50,
  lengthStep: number = 1
): { length: number; efficiency: number }[] {
  const results: { length: number; efficiency: number }[] = [];
  const numSteps = Math.ceil(lengthMax / lengthStep);

  for (let i = 1; i <= numSteps; i++) {
    const length = i * lengthStep;
    const lengthParams = { ...params, crystalLength: length };
    try {
      const cwResult = solveCoupledWaveEquations(lengthParams);
      results.push({
        length,
        efficiency: cwResult.conversionEfficiency,
      });
    } catch (e) {
      results.push({
        length,
        efficiency: 0,
      });
    }
  }

  return results;
}

export function solveCascadeProcesses(
  params: SimulationParams,
  initialCwResult: CoupledWaveResult
): CascadeResult {
  const stages: CascadeStageResult[] = [];
  const intermediateWavelengths: number[] = [];

  const centerWavelength = (params.signalWavelengthMin + params.signalWavelengthMax) / 2;
  const idlerLambda = calculateIdlerWavelength(params.pumpWavelength, centerWavelength);
  intermediateWavelengths.push(centerWavelength, idlerLambda);

  const initialSignalPower = initialCwResult.signalIntensity[initialCwResult.signalIntensity.length - 1] *
    Math.PI * (params.pumpWaist * PHYSICAL_CONSTANTS.um_to_m) ** 2;
  const initialIdlerPower = initialCwResult.idlerIntensity[initialCwResult.idlerIntensity.length - 1] *
    Math.PI * (params.pumpWaist * PHYSICAL_CONSTANTS.um_to_m) ** 2;

  if (params.cascadeProcess === 'opo' || params.cascadeProcess === 'full_cascade') {
    stages.push({
      stage: 1,
      processType: 'opo',
      processName: '光参量振荡 (OPO)',
      inputWavelengths: [params.pumpWavelength],
      inputWavelength: params.pumpWavelength,
      outputWavelength: centerWavelength,
      efficiency: initialCwResult.conversionEfficiency,
      outputPower: initialSignalPower,
      z: initialCwResult.z,
      intensity: initialCwResult.signalIntensity,
    });
  }

  if (params.cascadeProcess === 'shg_signal' || params.cascadeProcess === 'full_cascade') {
    if (initialSignalPower > params.cascadeEfficiencyThreshold * params.pumpPower) {
      const shgSignalResult = solveSHG(
        params,
        centerWavelength,
        initialSignalPower,
        stages.length + 1
      );
      stages.push(shgSignalResult);
      intermediateWavelengths.push(centerWavelength / 2);
    }
  }

  if (params.cascadeProcess === 'shg_idler' || params.cascadeProcess === 'full_cascade') {
    if (initialIdlerPower > params.cascadeEfficiencyThreshold * params.pumpPower) {
      const shgIdlerResult = solveSHG(
        params,
        idlerLambda,
        initialIdlerPower,
        stages.length + 1
      );
      stages.push(shgIdlerResult);
      intermediateWavelengths.push(idlerLambda / 2);
    }
  }

  if (params.cascadeProcess === 'sfg_pump_signal' || params.cascadeProcess === 'full_cascade') {
    if (initialSignalPower > params.cascadeEfficiencyThreshold * params.pumpPower) {
      const sfgResult = solveSFG(
        params,
        params.pumpWavelength,
        centerWavelength,
        params.pumpPower * 0.5,
        initialSignalPower,
        stages.length + 1
      );
      stages.push(sfgResult);
      const sfgWavelength = 1 / (1 / params.pumpWavelength + 1 / centerWavelength);
      intermediateWavelengths.push(sfgWavelength);
    }
  }

  const totalEfficiency = stages.length > 0
    ? stages.reduce((sum, s) => sum + s.efficiency, 0) / stages.length
    : 0;

  return {
    process: params.cascadeProcess,
    stages,
    totalEfficiency,
    intermediateWavelengths,
  };
}

function solveSHG(
  params: SimulationParams,
  fundamentalWavelength: number,
  inputPower: number,
  stageNum: number
): CascadeStageResult {
  const shgWavelength = fundamentalWavelength / 2;
  const crystal = getCrystalById(params.crystalId);

  if (!crystal) {
    return {
      stage: stageNum,
      processType: 'shg',
      processName: '倍频 (SHG)',
      inputWavelengths: [fundamentalWavelength],
      inputWavelength: fundamentalWavelength,
      outputWavelength: shgWavelength,
      efficiency: 0,
      outputPower: 0,
      z: [],
      intensity: [],
    };
  }

  const length_si = params.crystalLength * PHYSICAL_CONSTANTS.mm_to_m;
  const numSteps = Math.max(500, Math.floor(params.crystalLength * 20));
  const dz = length_si / numSteps;

  const nFund = calculateRefractiveIndexByCrystal(
    params.crystalId,
    fundamentalWavelength,
    'ordinary',
    params.temperature
  );
  const nSHG = calculateRefractiveIndexByCrystal(
    params.crystalId,
    shgWavelength,
    'extraordinary',
    params.temperature
  );

  const deff_si = calculateEffectiveNonlinearity(
    params.crystalId,
    params.phaseMatchType,
    params.angleTheta,
    params.anglePhi
  ) * PHYSICAL_CONSTANTS.pm_to_V;

  const omegaFund = (2 * Math.PI * PHYSICAL_CONSTANTS.c) / (fundamentalWavelength * PHYSICAL_CONSTANTS.nm_to_m);
  const omegaSHG = 2 * omegaFund;

  const area = Math.PI * (params.pumpWaist * PHYSICAL_CONSTANTS.um_to_m) ** 2;
  const intensityFund = inputPower / area;

  let A_fund: Complex = {
    re: Math.sqrt(2 * intensityFund * nFund * PHYSICAL_CONSTANTS.epsilon0 * PHYSICAL_CONSTANTS.c),
    im: 0,
  };
  let A_shg: Complex = { re: 0, im: 0 };

  const z: number[] = [];
  const intensitySHG: number[] = [];
  const i = { re: 0, im: 1 };

  const deltaK = 2 * calculateWavevector(fundamentalWavelength, nFund) -
    calculateWavevector(shgWavelength, nSHG);
  const kGrating = (2 * Math.PI) / (params.polingPeriod * 0.5 * PHYSICAL_CONSTANTS.um_to_m);
  const effectiveDeltaK = deltaK - kGrating;

  for (let step = 0; step < numSteps; step++) {
    const currentZ = step * dz;
    z.push(currentZ);

    const currentIntensitySHG = (complexAbs(A_shg) ** 2) / (2 * nSHG * PHYSICAL_CONSTANTS.epsilon0 * PHYSICAL_CONSTANTS.c);
    intensitySHG.push(currentIntensitySHG);

    const phaseFactor = complexExp(-effectiveDeltaK * currentZ);
    const polarity = Math.floor(currentZ / (params.polingPeriod * 0.5 * PHYSICAL_CONSTANTS.um_to_m)) % 2 === 0 ? 1 : -1;

    const coeffSHG = complexMulScalar(i, polarity * (omegaSHG * deff_si) / (nSHG * PHYSICAL_CONSTANTS.c));
    const nonlinearTerm = complexMul(A_fund, complexMul(A_fund, phaseFactor));

    const dFund_dz = complexMulScalar(A_fund, -0.0005);
    const dSHG_dz = complexAdd(
      complexMulScalar(A_shg, -0.0005),
      complexMul(nonlinearTerm, coeffSHG)
    );

    A_fund = complexAdd(A_fund, complexMulScalar(dFund_dz, dz));
    A_shg = complexAdd(A_shg, complexMulScalar(dSHG_dz, dz));
  }

  const finalIntensitySHG = (complexAbs(A_shg) ** 2) / (2 * nSHG * PHYSICAL_CONSTANTS.epsilon0 * PHYSICAL_CONSTANTS.c);
  const outputPower = finalIntensitySHG * area;
  const efficiency = (outputPower / Math.max(inputPower, 1e-12)) * 100;

  return {
    stage: stageNum,
    processType: 'shg',
    processName: '倍频 (SHG)',
    inputWavelengths: [fundamentalWavelength],
    inputWavelength: fundamentalWavelength,
    outputWavelength: shgWavelength,
    efficiency: Math.max(0, efficiency),
    outputPower,
    z,
    intensity: intensitySHG,
  };
}

function solveSFG(
  params: SimulationParams,
  lambda1: number,
  lambda2: number,
  power1: number,
  power2: number,
  stageNum: number
): CascadeStageResult {
  const sfgWavelength = 1 / (1 / lambda1 + 1 / lambda2);
  const crystal = getCrystalById(params.crystalId);

  if (!crystal) {
    return {
      stage: stageNum,
      processType: 'sfg',
      processName: '和频 (SFG)',
      inputWavelengths: [lambda1, lambda2],
      inputWavelength: lambda1,
      outputWavelength: sfgWavelength,
      efficiency: 0,
      outputPower: 0,
      z: [],
      intensity: [],
    };
  }

  const length_si = params.crystalLength * PHYSICAL_CONSTANTS.mm_to_m;
  const numSteps = Math.max(500, Math.floor(params.crystalLength * 20));
  const dz = length_si / numSteps;

  const n1 = calculateRefractiveIndexByCrystal(params.crystalId, lambda1, 'ordinary', params.temperature);
  const n2 = calculateRefractiveIndexByCrystal(params.crystalId, lambda2, 'ordinary', params.temperature);
  const n3 = calculateRefractiveIndexByCrystal(params.crystalId, sfgWavelength, 'extraordinary', params.temperature);

  const deff_si = calculateEffectiveNonlinearity(
    params.crystalId,
    params.phaseMatchType,
    params.angleTheta,
    params.anglePhi
  ) * PHYSICAL_CONSTANTS.pm_to_V;

  const omegaSFG = (2 * Math.PI * PHYSICAL_CONSTANTS.c) / (sfgWavelength * PHYSICAL_CONSTANTS.nm_to_m);

  const area = Math.PI * (params.pumpWaist * PHYSICAL_CONSTANTS.um_to_m) ** 2;
  const intensity1 = power1 / area;
  const intensity2 = power2 / area;

  let A1: Complex = {
    re: Math.sqrt(2 * intensity1 * n1 * PHYSICAL_CONSTANTS.epsilon0 * PHYSICAL_CONSTANTS.c),
    im: 0,
  };
  let A2: Complex = {
    re: Math.sqrt(2 * intensity2 * n2 * PHYSICAL_CONSTANTS.epsilon0 * PHYSICAL_CONSTANTS.c),
    im: 0,
  };
  let A3: Complex = { re: 0, im: 0 };

  const z: number[] = [];
  const intensity3: number[] = [];
  const i = { re: 0, im: 1 };

  const k1 = calculateWavevector(lambda1, n1);
  const k2 = calculateWavevector(lambda2, n2);
  const k3 = calculateWavevector(sfgWavelength, n3);
  const deltaK = k1 + k2 - k3;
  const polingPeriodSFG = Math.abs(deltaK) > 1e-12
    ? (2 * Math.PI) / deltaK / PHYSICAL_CONSTANTS.um_to_m
    : params.polingPeriod;
  const kGrating = (2 * Math.PI) / (polingPeriodSFG * PHYSICAL_CONSTANTS.um_to_m);
  const effectiveDeltaK = deltaK - kGrating;

  for (let step = 0; step < numSteps; step++) {
    const currentZ = step * dz;
    z.push(currentZ);

    const currentIntensity3 = (complexAbs(A3) ** 2) / (2 * n3 * PHYSICAL_CONSTANTS.epsilon0 * PHYSICAL_CONSTANTS.c);
    intensity3.push(currentIntensity3);

    const phaseFactor = complexExp(-effectiveDeltaK * currentZ);
    const polarity = Math.floor(currentZ / (polingPeriodSFG * PHYSICAL_CONSTANTS.um_to_m)) % 2 === 0 ? 1 : -1;

    const coeff3 = complexMulScalar(i, polarity * (omegaSFG * deff_si) / (n3 * PHYSICAL_CONSTANTS.c));
    const nonlinearTerm = complexMul(A1, complexMul(A2, phaseFactor));

    const dA1_dz = complexMulScalar(A1, -0.0005);
    const dA2_dz = complexMulScalar(A2, -0.0005);
    const dA3_dz = complexAdd(
      complexMulScalar(A3, -0.0005),
      complexMul(nonlinearTerm, coeff3)
    );

    A1 = complexAdd(A1, complexMulScalar(dA1_dz, dz));
    A2 = complexAdd(A2, complexMulScalar(dA2_dz, dz));
    A3 = complexAdd(A3, complexMulScalar(dA3_dz, dz));
  }

  const finalIntensity3 = (complexAbs(A3) ** 2) / (2 * n3 * PHYSICAL_CONSTANTS.epsilon0 * PHYSICAL_CONSTANTS.c);
  const outputPower = finalIntensity3 * area;
  const totalInputPower = Math.max(power1 + power2, 1e-12);
  const efficiency = (outputPower / totalInputPower) * 100;

  return {
    stage: stageNum,
    processType: 'sfg',
    processName: '和频 (SFG)',
    inputWavelengths: [lambda1, lambda2],
    inputWavelength: lambda1,
    outputWavelength: sfgWavelength,
    efficiency: Math.max(0, efficiency),
    outputPower,
    z,
    intensity: intensity3,
  };
}
