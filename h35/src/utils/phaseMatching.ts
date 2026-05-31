import type { SimulationParams, PhaseMatchingResult, Polarization, NoncollinearResult } from '../types';
import { getCrystalById } from '../data/crystals';
import {
  calculateRefractiveIndexByCrystal,
  calculateExtraordinaryIndex,
  calculateIdlerWavelength,
  calculateWavevector,
  calculatePhaseMismatch,
  calculateCoherenceLength,
  calculateWalkoffAngle,
  calculateEffectiveNonlinearity,
  calculateGroupVelocity,
  calculateGroupVelocityMismatch,
  degToRad,
  PHYSICAL_CONSTANTS,
} from './physics';

export function calculatePhaseMatching(
  params: SimulationParams,
  signalWavelength?: number
): PhaseMatchingResult {
  const signalLambda = signalWavelength ?? (params.signalWavelengthMin + params.signalWavelengthMax) / 2;
  const idlerLambda = calculateIdlerWavelength(params.pumpWavelength, signalLambda);
  const crystal = getCrystalById(params.crystalId);

  if (!crystal) {
    throw new Error(`Crystal not found: ${params.crystalId}`);
  }

  let pumpPol: Polarization, signalPol: Polarization, idlerPol: Polarization;
  if (params.phaseMatchType === 'type1') {
    pumpPol = 'extraordinary';
    signalPol = 'ordinary';
    idlerPol = 'ordinary';
  } else {
    pumpPol = 'extraordinary';
    signalPol = 'ordinary';
    idlerPol = 'extraordinary';
  }

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
  const nPump = calculateExtraordinaryIndex(nO_pump, nE_pump, params.angleTheta);

  const nO_signal = calculateRefractiveIndexByCrystal(
    params.crystalId,
    signalLambda,
    'ordinary',
    params.temperature
  );
  const nE_signal = calculateRefractiveIndexByCrystal(
    params.crystalId,
    signalLambda,
    'extraordinary',
    params.temperature
  );
  const nSignal = signalPol === 'ordinary'
    ? nO_signal
    : calculateExtraordinaryIndex(nO_signal, nE_signal, params.angleTheta);

  const nO_idler = calculateRefractiveIndexByCrystal(
    params.crystalId,
    idlerLambda,
    'ordinary',
    params.temperature
  );
  const nE_idler = calculateRefractiveIndexByCrystal(
    params.crystalId,
    idlerLambda,
    'extraordinary',
    params.temperature
  );
  const nIdler = idlerPol === 'ordinary'
    ? nO_idler
    : calculateExtraordinaryIndex(nO_idler, nE_idler, params.angleTheta);

  const kPump = calculateWavevector(params.pumpWavelength, nPump);
  const kSignal = calculateWavevector(signalLambda, nSignal);
  const kIdler = calculateWavevector(idlerLambda, nIdler);
  const deltaK = calculatePhaseMismatch(kPump, kSignal, kIdler, params.polingPeriod);

  const coherenceLength = calculateCoherenceLength(deltaK);
  const walkoffAngle = calculateWalkoffAngle(nO_pump, nE_pump, params.angleTheta);
  const effectiveNonlinearity = calculateEffectiveNonlinearity(
    params.crystalId,
    params.phaseMatchType,
    params.angleTheta,
    params.anglePhi
  );

  const dn_pump = numericalDerivative(
    (lambda: number) => calculateRefractiveIndexByCrystal(params.crystalId, lambda, pumpPol, params.temperature),
    params.pumpWavelength
  );
  const dn_signal = numericalDerivative(
    (lambda: number) => calculateRefractiveIndexByCrystal(params.crystalId, lambda, signalPol, params.temperature),
    signalLambda
  );
  const dn_idler = numericalDerivative(
    (lambda: number) => calculateRefractiveIndexByCrystal(params.crystalId, lambda, idlerPol, params.temperature),
    idlerLambda
  );

  const vgPump = calculateGroupVelocity(params.pumpWavelength, nPump, dn_pump);
  const vgSignal = calculateGroupVelocity(signalLambda, nSignal, dn_signal);
  const vgIdler = calculateGroupVelocity(idlerLambda, nIdler, dn_idler);
  const gvm = calculateGroupVelocityMismatch(vgPump, vgSignal, vgIdler);

  let matchAngle = params.angleTheta;
  if (Math.abs(deltaK) > 1) {
    matchAngle = findPhaseMatchingAngle(params, signalLambda);
  }

  return {
    phaseMatchAngle: matchAngle,
    walkoffAngle,
    effectiveNonlinearity,
    coherenceLength: coherenceLength === Infinity ? -1 : coherenceLength / PHYSICAL_CONSTANTS.um_to_m,
    groupVelocityMismatch: gvm,
    nPump,
    nSignal,
    nIdler,
    idlerWavelength: idlerLambda,
    deltaK,
  };
}

function numericalDerivative(
  func: (x: number) => number,
  x: number,
  h: number = 0.1
): number {
  return (func(x + h) - func(x - h)) / (2 * h);
}

export function findPhaseMatchingAngle(
  params: SimulationParams,
  signalWavelength: number
): number {
  const idlerLambda = calculateIdlerWavelength(params.pumpWavelength, signalWavelength);

  function deltaK(theta: number): number {
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
    const nPump = calculateExtraordinaryIndex(nO_pump, nE_pump, theta);

    const nO_signal = calculateRefractiveIndexByCrystal(
      params.crystalId,
      signalWavelength,
      'ordinary',
      params.temperature
    );
    const nE_signal = calculateRefractiveIndexByCrystal(
      params.crystalId,
      signalWavelength,
      'extraordinary',
      params.temperature
    );
    const nSignal = params.phaseMatchType === 'type1'
      ? nO_signal
      : calculateExtraordinaryIndex(nO_signal, nE_signal, theta);

    const nO_idler = calculateRefractiveIndexByCrystal(
      params.crystalId,
      idlerLambda,
      'ordinary',
      params.temperature
    );
    const nE_idler = calculateRefractiveIndexByCrystal(
      params.crystalId,
      idlerLambda,
      'extraordinary',
      params.temperature
    );
    const nIdler = params.phaseMatchType === 'type1'
      ? nO_idler
      : calculateExtraordinaryIndex(nO_idler, nE_idler, theta);

    const kPump = calculateWavevector(params.pumpWavelength, nPump);
    const kSignal = calculateWavevector(signalWavelength, nSignal);
    const kIdler = calculateWavevector(idlerLambda, nIdler);

    return calculatePhaseMismatch(kPump, kSignal, kIdler, params.polingPeriod);
  }

  let thetaLow = 0;
  let thetaHigh = 90;
  let deltaKLow = deltaK(thetaLow);
  let deltaKHigh = deltaK(thetaHigh);

  if (deltaKLow * deltaKHigh > 0) {
    let minDeltaK = Infinity;
    let bestTheta = 90;
    for (let theta = 0; theta <= 90; theta += 0.5) {
      const dk = Math.abs(deltaK(theta));
      if (dk < minDeltaK) {
        minDeltaK = dk;
        bestTheta = theta;
      }
    }
    return bestTheta;
  }

  for (let i = 0; i < 100; i++) {
    const thetaMid = (thetaLow + thetaHigh) / 2;
    const deltaKMid = deltaK(thetaMid);

    if (Math.abs(deltaKMid) < 1e-6) {
      return thetaMid;
    }

    if (deltaKLow * deltaKMid < 0) {
      thetaHigh = thetaMid;
      deltaKHigh = deltaKMid;
    } else {
      thetaLow = thetaMid;
      deltaKLow = deltaKMid;
    }
  }

  return (thetaLow + thetaHigh) / 2;
}

export function calculatePhaseMatchingCurve(
  params: SimulationParams
): { wavelength: number; phaseMatchAngle: number; deltaK: number }[] {
  const results: { wavelength: number; phaseMatchAngle: number; deltaK: number }[] = [];
  const numPoints = Math.ceil(
    (params.signalWavelengthMax - params.signalWavelengthMin) / params.signalWavelengthStep
  );

  for (let i = 0; i <= numPoints; i++) {
    const wavelength = params.signalWavelengthMin + i * params.signalWavelengthStep;
    const pmResult = calculatePhaseMatching(params, wavelength);
    results.push({
      wavelength,
      phaseMatchAngle: pmResult.phaseMatchAngle,
      deltaK: pmResult.deltaK,
    });
  }

  return results;
}

export function calculateNoncollinearPhaseMatching(
  params: SimulationParams,
  signalWavelength?: number
): NoncollinearResult {
  const signalLambda = signalWavelength ?? (params.signalWavelengthMin + params.signalWavelengthMax) / 2;
  const idlerLambda = calculateIdlerWavelength(params.pumpWavelength, signalLambda);
  const crystal = getCrystalById(params.crystalId);

  if (!crystal) {
    throw new Error(`Crystal not found: ${params.crystalId}`);
  }

  const thetaRad = degToRad(params.angleTheta);

  const alphaSignal = params.noncollinearConfig === 'noncollinear_signal' || params.noncollinearConfig === 'noncollinear_both'
    ? degToRad(params.noncollinearAngleSignal)
    : 0;

  const alphaIdler = params.noncollinearConfig === 'noncollinear_idler' || params.noncollinearConfig === 'noncollinear_both'
    ? degToRad(params.noncollinearAngleIdler)
    : 0;

  let pumpPol: Polarization, signalPol: Polarization, idlerPol: Polarization;
  if (params.phaseMatchType === 'type1') {
    pumpPol = 'extraordinary';
    signalPol = 'ordinary';
    idlerPol = 'ordinary';
  } else {
    pumpPol = 'extraordinary';
    signalPol = 'ordinary';
    idlerPol = 'extraordinary';
  }

  const nO_pump = calculateRefractiveIndexByCrystal(params.crystalId, params.pumpWavelength, 'ordinary', params.temperature);
  const nE_pump = calculateRefractiveIndexByCrystal(params.crystalId, params.pumpWavelength, 'extraordinary', params.temperature);
  const nPump = calculateExtraordinaryIndex(nO_pump, nE_pump, params.angleTheta);

  const nO_signal = calculateRefractiveIndexByCrystal(params.crystalId, signalLambda, 'ordinary', params.temperature);
  const nE_signal = calculateRefractiveIndexByCrystal(params.crystalId, signalLambda, 'extraordinary', params.temperature);
  const nSignal = params.phaseMatchType === 'type1'
    ? nO_signal
    : calculateExtraordinaryIndex(nO_signal, nE_signal, params.angleTheta);

  const nO_idler = calculateRefractiveIndexByCrystal(params.crystalId, idlerLambda, 'ordinary', params.temperature);
  const nE_idler = calculateRefractiveIndexByCrystal(params.crystalId, idlerLambda, 'extraordinary', params.temperature);
  const nIdler = params.phaseMatchType === 'type1'
    ? nO_idler
    : calculateExtraordinaryIndex(nO_idler, nE_idler, params.angleTheta);

  const kPump = calculateWavevector(params.pumpWavelength, nPump);
  const kSignal = calculateWavevector(signalLambda, nSignal);
  const kIdler = calculateWavevector(idlerLambda, nIdler);
  const kGrating = (2 * Math.PI) / (params.polingPeriod * PHYSICAL_CONSTANTS.um_to_m);

  const kPumpVec = { x: 0, z: kPump };
  const kSignalVec = { x: kSignal * Math.sin(alphaSignal), z: kSignal * Math.cos(alphaSignal) };
  const kIdlerVec = { x: kIdler * Math.sin(alphaIdler), z: kIdler * Math.cos(alphaIdler) };

  const deltaKx = kPumpVec.x - kSignalVec.x - kIdlerVec.x;
  const deltaKz = kPumpVec.z - kSignalVec.z - kIdlerVec.z - kGrating;
  const deltaKTotal = Math.sqrt(deltaKx * deltaKx + deltaKz * deltaKz);

  function findMatchAngleForNoncollinear(alpha: number, wavelength: number, pol: Polarization): number {
    const nO = calculateRefractiveIndexByCrystal(params.crystalId, wavelength, 'ordinary', params.temperature);
    const nE = calculateRefractiveIndexByCrystal(params.crystalId, wavelength, 'extraordinary', params.temperature);

    function deltaKForAngle(theta: number): number {
      const n = calculateExtraordinaryIndex(nO, nE, theta);
      const k = calculateWavevector(wavelength, n);
      const kVec = { x: k * Math.sin(alpha), z: k * Math.cos(alpha) };
      const kPumpN = calculateWavevector(params.pumpWavelength, calculateExtraordinaryIndex(nO_pump, nE_pump, theta));
      return kPumpN - kVec.z - kGrating;
    }

    let thetaLow = 0, thetaHigh = 90;
    for (let i = 0; i < 100; i++) {
      const thetaMid = (thetaLow + thetaHigh) / 2;
      const dk = deltaKForAngle(thetaMid);
      if (Math.abs(dk) < 1e-6) return thetaMid;
      if (deltaKForAngle(thetaLow) * dk < 0) thetaHigh = thetaMid;
      else thetaLow = thetaMid;
    }
    return (thetaLow + thetaHigh) / 2;
  }

  const phaseMatchAngle = findMatchAngleForNoncollinear(alphaSignal, signalLambda, signalPol);

  const walkoffSignal = calculateWalkoffAngle(nO_signal, nE_signal, params.angleTheta);
  const walkoffIdler = calculateWalkoffAngle(nO_idler, nE_idler, params.angleTheta);

  const deff = calculateEffectiveNonlinearity(params.crystalId, params.phaseMatchType, params.angleTheta, params.anglePhi);

  const acceptanceAngleSignal = calculateNoncollinearAcceptance(params, signalLambda, alphaSignal);
  const acceptanceAngleIdler = calculateNoncollinearAcceptance(params, idlerLambda, alphaIdler);

  return {
    config: params.noncollinearConfig,
    signalAngle: params.noncollinearAngleSignal,
    idlerAngle: params.noncollinearAngleIdler,
    walkoffAngleSignal: walkoffSignal,
    walkoffAngleIdler: walkoffIdler,
    acceptanceAngleSignal: acceptanceAngleSignal,
    acceptanceAngleIdler: acceptanceAngleIdler,
    phaseMatchAngle: phaseMatchAngle,
    effectiveNonlinearity: deff,
    kPump,
    kSignal,
    kIdler,
    kGrating,
    kPumpX: kPumpVec.x,
    kPumpZ: kPumpVec.z,
    kSignalX: kSignalVec.x,
    kSignalZ: kSignalVec.z,
    kIdlerX: kIdlerVec.x,
    kIdlerZ: kIdlerVec.z,
    deltaKx,
    deltaKz,
    deltaK: deltaKTotal,
  };
}

function calculateNoncollinearAcceptance(
  params: SimulationParams,
  wavelength: number,
  alpha: number
): number {
  const crystal = getCrystalById(params.crystalId);
  if (!crystal) return 0;

  const length_si = params.crystalLength * PHYSICAL_CONSTANTS.mm_to_m;
  const wavelength_si = wavelength * PHYSICAL_CONSTANTS.nm_to_m;

  const nO = calculateRefractiveIndexByCrystal(params.crystalId, wavelength, 'ordinary', params.temperature);
  const nE = calculateRefractiveIndexByCrystal(params.crystalId, wavelength, 'extraordinary', params.temperature);
  const n = calculateExtraordinaryIndex(nO, nE, params.angleTheta);

  const k = (2 * Math.PI * n) / wavelength_si;
  const alphaRad = degToRad(alpha);

  const dk_dalpha = k * Math.cos(alphaRad) * length_si;
  const acceptance = 0.886 * Math.PI / Math.abs(dk_dalpha);

  return acceptance * (180 / Math.PI) * 1000;
}
