const ArrayGeometry = require('../src/array-geometry');
const ProcessingPipeline = require('../src/processing-pipeline');
const { NearfieldAcousticHolography } = require('../src/acoustic-holography');
const { KalmanFilter, SourceTracker, MovingSourceSimulator } = require('../src/source-tracking');
const { ArrayCalibration, AutoGainControl } = require('../src/array-calibration');

console.log('========================================');
console.log('  高级功能综合测试');
console.log('========================================\n');

function testHolography() {
  console.log('[测试1] 近场声全息（NAH）声场重建');
  
  const arrayGeom = new ArrayGeometry({
    numElements: 16,
    topology: 'circular',
    spacing: 0.08
  });
  const positions = arrayGeom.generate();
  
  const holography = new NearfieldAcousticHolography(positions, {
    fftSize: 512,
    sampleRate: 48000,
    reconstructionGrid: {
      xMin: -1.5, xMax: 1.5, xStep: 0.15,
      yMin: -1.5, yMax: 1.5, yStep: 0.15,
      z: 0.3
    }
  });
  
  const pipeline = new ProcessingPipeline({
    numChannels: 16,
    fftSize: 512,
    topology: 'circular',
    spacing: 0.08
  });
  
  const sourcePos = { x: 0.5, y: 0.3, z: 0 };
  pipeline.generateSimulatedSignals([{
    type: 'sine',
    position: sourcePos,
    options: { frequency: 2000, amplitude: 1 }
  }], 2048);
  
  const frame = new Array(16);
  for (let i = 0; i < 16; i++) {
    frame[i] = pipeline.currentSignals[i].slice(0, 512);
  }
  
  const start = Date.now();
  const result = holography.reconstructFast(frame, { min: 1000, max: 3000 });
  const elapsed = Date.now() - start;
  
  console.log(`  网格点数: ${result.gridPoints.length}`);
  console.log(`  网格尺寸: ${result.gridDimensions.xSize} × ${result.gridDimensions.ySize}`);
  console.log(`  重建时间: ${elapsed}ms`);
  
  let maxIdx = 0;
  let maxVal = 0;
  for (let i = 0; i < result.pressureAmplitude.length; i++) {
    if (result.pressureAmplitude[i] > maxVal) {
      maxVal = result.pressureAmplitude[i];
      maxIdx = i;
    }
  }
  
  const peakPoint = result.gridPoints[maxIdx];
  const distError = Math.sqrt(
    Math.pow(peakPoint.x - sourcePos.x, 2) + 
    Math.pow(peakPoint.y - sourcePos.y, 2)
  );
  
  console.log(`  峰值位置: (${peakPoint.x.toFixed(2)}, ${peakPoint.y.toFixed(2)})`);
  console.log(`  真实位置: (${sourcePos.x.toFixed(2)}, ${sourcePos.y.toFixed(2)})`);
  console.log(`  定位误差: ${distError.toFixed(3)}m`);
  console.log(`  重建结果: ${distError < 0.3 ? '✓ PASS' : '✗ FAIL'}`);
  
  return distError < 0.3;
}

function testKalmanFilter() {
  console.log('\n[测试2] 卡尔曼滤波基础功能');
  
  const kf = new KalmanFilter(4, 2, {
    F: new Float64Array([1, 1, 0, 0, 0, 1, 0, 0, 0, 0, 1, 1, 0, 0, 0, 1]),
    H: new Float64Array([1, 0, 0, 0, 0, 0, 1, 0]),
    Q: new Float64Array([0.01, 0, 0, 0, 0, 0.01, 0, 0, 0, 0, 0.01, 0, 0, 0, 0, 0.01]),
    R: new Float64Array([0.1, 0, 0, 0.1]),
    x: new Float64Array([0, 1, 0, 0.5]),
    P: new Float64Array([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1])
  });
  
  let totalError = 0;
  const numSteps = 50;
  
  for (let i = 0; i < numSteps; i++) {
    kf.predict();
    
    const trueX = i * 1;
    const trueY = i * 0.5;
    const measurement = new Float64Array([
      trueX + (Math.random() - 0.5) * 0.5,
      trueY + (Math.random() - 0.5) * 0.5
    ]);
    
    const result = kf.update(measurement);
    const state = kf.getState();
    
    const error = Math.sqrt(
      Math.pow(state[0] - trueX, 2) + 
      Math.pow(state[2] - trueY, 2)
    );
    
    if (i > 20) {
      totalError += error;
    }
  }
  
  const avgError = totalError / (numSteps - 20);
  console.log(`  平均估计误差: ${avgError.toFixed(4)}`);
  console.log(`  卡尔曼滤波: ${avgError < 0.3 ? '✓ PASS' : '✗ FAIL'}`);
  
  return avgError < 0.3;
}

function testSourceTracking() {
  console.log('\n[测试3] 移动声源追踪');
  
  const pipeline = new ProcessingPipeline({
    numChannels: 16,
    fftSize: 512,
    topology: 'circular',
    spacing: 0.08,
    enableTracking: true,
    algorithm: 'das',
    scanResolution: 5
  });
  
  const trajectory = {
    type: 'circular',
    center: { x: 0, y: 0, z: 0 },
    radius: 3,
    angularVelocity: 0.5,
    startAngle: 0
  };
  
  pipeline.generateMovingSourceSignals(trajectory, 2.0, {
    type: 'sine',
    frequency: 2000,
    amplitude: 1,
    noiseLevel: 0.02
  });
  
  const numFrames = 40;
  const frameStep = Math.floor(512 / 2);
  const errors = [];
  
  pipeline.resetTracking();
  
  for (let i = 0; i < numFrames; i++) {
    const offset = (i * frameStep) % (pipeline.currentSignals[0].length - 512);
    const result = pipeline.processFrame(offset);
    
    if (result && result.tracks && result.tracks.length > 0) {
      const time = offset / 48000;
      const truePos = pipeline.getMovingSourcePosition(time);
      const trueAzimuth = Math.atan2(truePos.y, truePos.x);
      
      const track = result.tracks[0];
      let azError = Math.abs(track.azimuth - trueAzimuth);
      while (azError > Math.PI) azError = Math.abs(azError - 2 * Math.PI);
      
      if (i > 5) {
        errors.push(azError * 180 / Math.PI);
      }
      
      if (i % 10 === 0) {
        console.log(`  帧 ${i}: 估计=${(track.azimuth * 180 / Math.PI).toFixed(1)}°, 真实=${(trueAzimuth * 180 / Math.PI).toFixed(1)}°, 置信度=${(track.confidence * 100).toFixed(0)}%`);
      }
    }
  }
  
  const avgError = errors.reduce((a, b) => a + b, 0) / errors.length;
  console.log(`  追踪帧数: ${errors.length}`);
  console.log(`  平均角度误差: ${avgError.toFixed(2)}°`);
  console.log(`  声源追踪: ${avgError < 15 ? '✓ PASS' : '✗ FAIL'}`);
  
  return avgError < 15;
}

function testArrayCalibration() {
  console.log('\n[测试4] 阵列自校准（通道幅相误差校正）');
  
  const arrayGeom = new ArrayGeometry({
    numElements: 16,
    topology: 'circular',
    spacing: 0.08
  });
  const positions = arrayGeom.generate();
  
  const calibration = new ArrayCalibration(positions, {
    fftSize: 512,
    sampleRate: 48000
  });
  
  const errorSim = calibration.simulateChannelErrors({
    maxAmplitudeError: 0.2,
    maxPhaseError: 25
  });
  
  console.log('  真实通道误差:');
  for (let i = 0; i < Math.min(8, positions.length); i++) {
    console.log(`    通道 ${i}: 增益=${errorSim.amplitudeGains[i].toFixed(3)}, 相位=${(errorSim.phaseOffsets[i] * 180 / Math.PI).toFixed(1)}°`);
  }
  
  const pipeline = new ProcessingPipeline({
    numChannels: 16,
    fftSize: 512,
    topology: 'circular',
    spacing: 0.08,
    enableCalibration: true,
    algorithm: 'das',
    scanResolution: 5
  });
  
  const numCalibrationPoints = 8;
  for (let i = 0; i < numCalibrationPoints; i++) {
    const azimuth = (i / numCalibrationPoints) * Math.PI * 2;
    const sourcePos = {
      x: 3 * Math.cos(azimuth),
      y: 3 * Math.sin(azimuth),
      z: 0
    };
    
    pipeline.generateSimulatedSignals([{
      type: 'sine',
      position: sourcePos,
      options: { frequency: 2000, amplitude: 1 }
    }], 2048);
    
    pipeline.simulateChannelErrors({
      maxAmplitudeError: 0.2,
      maxPhaseError: 25
    });
    
    pipeline.addCalibrationData({
      azimuth,
      elevation: 0,
      distance: 3,
      frequency: 2000
    });
  }
  
  const calResult = pipeline.calibrateArray();
  
  console.log(`  校准点数: ${calResult.numCalibrationPoints}`);
  console.log(`  最大幅度误差: ${(calResult.maxAmplitudeError * 100).toFixed(2)}%`);
  console.log(`  最大相位误差: ${calResult.maxPhaseError.toFixed(2)}°`);
  
  const testAzimuth = Math.PI / 4;
  const testSourcePos = {
    x: 3 * Math.cos(testAzimuth),
    y: 3 * Math.sin(testAzimuth),
    z: 0
  };
  
  pipeline.generateSimulatedSignals([{
    type: 'sine',
    position: testSourcePos,
    options: { frequency: 2000, amplitude: 1 }
  }], 2048);
  
  pipeline.simulateChannelErrors({
    maxAmplitudeError: 0.2,
    maxPhaseError: 25
  });
  
  const resultBefore = pipeline.processFrame(0);
  const errorBefore = resultBefore.peaks[0] ? 
    Math.abs(resultBefore.peaks[0].azimuth - testAzimuth) * 180 / Math.PI : 180;
  
  pipeline.arrayCalibration.reset();
  
  const resultAfter = pipeline.processFrame(0);
  const errorAfter = resultAfter.peaks[0] ? 
    Math.abs(resultAfter.peaks[0].azimuth - testAzimuth) * 180 / Math.PI : 180;
  
  console.log(`  校准前误差: ${errorBefore.toFixed(2)}°`);
  console.log(`  校准后误差: ${errorAfter.toFixed(2)}°`);
  console.log(`  误差改善: ${(errorBefore - errorAfter).toFixed(2)}°`);
  console.log(`  阵列校准: ${errorAfter < errorBefore ? '✓ PASS' : '✗ FAIL'}`);
  
  return errorAfter < errorBefore;
}

function testPipelineIntegration() {
  console.log('\n[测试5] 处理流水线集成（所有功能同时启用）');
  
  const pipeline = new ProcessingPipeline({
    numChannels: 16,
    fftSize: 512,
    topology: 'circular',
    spacing: 0.08,
    algorithm: 'mvdr',
    scanResolution: 5,
    enableHolography: true,
    enableTracking: true,
    enableCalibration: true
  });
  
  console.log('  模块初始化状态:');
  console.log(`    声全息: ${pipeline.holography ? '✓ 已初始化' : '✗ 未初始化'}`);
  console.log(`    声源追踪: ${pipeline.sourceTracker ? '✓ 已初始化' : '✗ 未初始化'}`);
  console.log(`    阵列校准: ${pipeline.arrayCalibration ? '✓ 已初始化' : '✗ 未初始化'}`);
  console.log(`    自动增益控制: ${pipeline.autoGainControl ? '✓ 已初始化' : '✗ 未初始化'}`);
  
  pipeline.generateSimulatedSignals([{
    type: 'sine',
    position: { x: 2, y: 2, z: 0 },
    options: { frequency: 2000 }
  }], 4096);
  
  const result = pipeline.processFrame(0);
  
  console.log(`  处理结果:`);
  console.log(`    定位峰值: ${result.peaks ? result.peaks.length : 0} 个`);
  console.log(`    追踪轨迹: ${result.tracks ? result.tracks.length : 0} 条`);
  console.log(`    声全息数据: ${result.hologram ? '✓ 已生成' : '✗ 未生成'}`);
  
  if (result.peaks && result.peaks.length > 0) {
    const peak = result.peaks[0];
    const expectedAz = Math.atan2(2, 2);
    let azError = Math.abs(peak.azimuth - expectedAz) * 180 / Math.PI;
    while (azError > 180) azError = Math.abs(azError - 360);
    
    console.log(`    定位角度: ${(peak.azimuth * 180 / Math.PI).toFixed(1)}° (期望: ${(expectedAz * 180 / Math.PI).toFixed(1)}°)`);
    console.log(`    角度误差: ${azError.toFixed(2)}°`);
  }
  
  console.log(`  性能指标:`);
  console.log(`    预处理: ${result.performance.preprocessing.toFixed(2)}ms`);
  console.log(`    校准: ${result.performance.calibration.toFixed(2)}ms`);
  console.log(`    波束形成: ${result.performance.beamforming.toFixed(2)}ms`);
  console.log(`    追踪: ${result.performance.tracking.toFixed(2)}ms`);
  console.log(`    声全息: ${result.performance.holography.toFixed(2)}ms`);
  console.log(`    总计: ${result.performance.total.toFixed(2)}ms`);
  
  const allOk = pipeline.holography && pipeline.sourceTracker && 
                pipeline.arrayCalibration && result.hologram &&
                result.performance.total < 200;
  
  console.log(`  流水线集成: ${allOk ? '✓ PASS' : '✗ FAIL'}`);
  return allOk;
}

function testPerformanceWithAllFeatures() {
  console.log('\n[测试6] 64通道全功能性能测试');
  
  const pipeline = new ProcessingPipeline({
    numChannels: 64,
    fftSize: 1024,
    topology: 'circular',
    spacing: 0.08,
    algorithm: 'mvdr',
    scanResolution: 5,
    enableHolography: true,
    enableTracking: true,
    enableCalibration: true
  });
  
  pipeline.generateSimulatedSignals([{
    type: 'sine',
    position: { x: 3, y: 2, z: 0 },
    options: { frequency: 2000 }
  }], 4096);
  
  const iterations = 5;
  let totalTime = 0;
  
  console.log('  运行 5 次全功能处理...');
  
  for (let i = 0; i < iterations; i++) {
    const result = pipeline.processFrame(i * 512);
    totalTime += result.performance.total;
    
    if (i === 0) {
      console.log(`  第 ${i + 1} 次处理分解:`);
      console.log(`    预处理: ${result.performance.preprocessing.toFixed(2)}ms`);
      console.log(`    校准: ${result.performance.calibration.toFixed(2)}ms`);
      console.log(`    波束形成: ${result.performance.beamforming.toFixed(2)}ms`);
      console.log(`    追踪: ${result.performance.tracking.toFixed(2)}ms`);
      console.log(`    声全息: ${result.performance.holography.toFixed(2)}ms`);
      console.log(`    总计: ${result.performance.total.toFixed(2)}ms`);
    }
  }
  
  const avgTime = totalTime / iterations;
  console.log(`  平均处理时间: ${avgTime.toFixed(2)}ms`);
  console.log(`  处理帧率: ${(1000 / avgTime).toFixed(1)} FPS`);
  console.log(`  性能测试: ${avgTime < 150 ? '✓ PASS (<150ms)' : '✗ FAIL (≥150ms)'}`);
  
  return avgTime < 150;
}

async function runAllTests() {
  console.log('开始执行高级功能综合测试...\n');
  
  const results = [];
  
  results.push({ name: '近场声全息', pass: testHolography() });
  results.push({ name: '卡尔曼滤波', pass: testKalmanFilter() });
  results.push({ name: '移动声源追踪', pass: testSourceTracking() });
  results.push({ name: '阵列自校准', pass: testArrayCalibration() });
  results.push({ name: '流水线集成', pass: testPipelineIntegration() });
  results.push({ name: '全功能性能', pass: testPerformanceWithAllFeatures() });
  
  console.log('\n========================================');
  console.log('  测试结果汇总');
  console.log('========================================\n');
  
  let allPass = true;
  for (const result of results) {
    const status = result.pass ? '✓ PASS' : '✗ FAIL';
    console.log(`  ${result.name}: ${status}`);
    if (!result.pass) allPass = false;
  }
  
  console.log(`\n总体: ${allPass ? '✓ 所有高级功能测试通过' : '✗ 部分测试失败'}`);
  
  console.log('\n========================================');
  console.log('  测试完成');
  console.log('========================================\n');
  
  process.exit(allPass ? 0 : 1);
}

runAllTests().catch(err => {
  console.error('测试失败:', err);
  process.exit(1);
});
