const { Complex, FFT, Beamforming, generateScanAngles, findPeaks } = require('../src/signal-processing');
const ArrayGeometry = require('../src/array-geometry');
const { SourceSimulator } = require('../src/source-simulation');

console.log('========================================');
console.log('  麦克风阵列信号处理 - 性能测试');
console.log('========================================\n');

function runFFTTest(size, iterations = 100) {
  console.log(`\n[FFT 测试] 大小: ${size}, 迭代: ${iterations}次`);
  
  const fft = new FFT(size);
  const input = new Array(size);
  
  for (let i = 0; i < size; i++) {
    input[i] = new Complex(Math.sin(2 * Math.PI * i / size), 0);
  }

  const start = Date.now();
  for (let i = 0; i < iterations; i++) {
    fft.transform(input);
  }
  const elapsed = Date.now() - start;
  const avgTime = elapsed / iterations;
  
  console.log(`  总耗时: ${elapsed}ms, 平均: ${avgTime.toFixed(3)}ms/次`);
  console.log(`  性能: ${(1000 / avgTime).toFixed(1)} FFT/秒`);
  
  return avgTime;
}

function runBeamformingTest(numChannels, fftSize, algorithm, iterations = 20) {
  console.log(`\n[波束形成测试] ${algorithm.toUpperCase()}, 通道: ${numChannels}, FFT: ${fftSize}, 迭代: ${iterations}次`);
  
  const arrayGeom = new ArrayGeometry({
    numElements: numChannels,
    topology: 'circular',
    spacing: 0.08
  });
  const positions = arrayGeom.generate();
  
  const beamforming = new Beamforming(positions, {
    fftSize: fftSize,
    sampleRate: 48000
  });
  
  const sourceSim = new SourceSimulator({ sampleRate: 48000 });
  
  const sources = [{
    type: 'sine',
    position: { x: 3, y: 2, z: 0 },
    options: { frequency: 2000, amplitude: 1 }
  }];
  
  const signals = sourceSim.generateMultiSourceSignals(sources, positions, fftSize * 4);
  
  const scanAngles = generateScanAngles(5, false);
  console.log(`  扫描角度数: ${scanAngles.length}`);
  
  const frame = signals.map(s => s.slice(0, fftSize));
  
  const start = Date.now();
  let powerMap;
  
  for (let i = 0; i < iterations; i++) {
    switch (algorithm) {
      case 'das':
        powerMap = beamforming.das(frame, scanAngles);
        break;
      case 'mvdr':
        powerMap = beamforming.mvdr(frame, scanAngles);
        break;
      case 'music':
        powerMap = beamforming.music(frame, scanAngles, 1);
        break;
    }
  }
  
  const elapsed = Date.now() - start;
  const avgTime = elapsed / iterations;
  
  const peaks = findPeaks(powerMap, 1, 0.1, 5);
  
  console.log(`  总耗时: ${elapsed}ms, 平均: ${avgTime.toFixed(2)}ms/次`);
  console.log(`  性能: ${(1000 / avgTime).toFixed(1)} 帧/秒`);
  console.log(`  检测到 ${peaks.length} 个峰值`);
  
  if (peaks.length > 0) {
    const peak = peaks[0];
    const expectedAz = Math.atan2(2, 3);
    const error = Math.abs(peak.azimuth - expectedAz) * 180 / Math.PI;
    console.log(`  峰值方位角: ${(peak.azimuth * 180 / Math.PI).toFixed(1)}°, 期望: ${(expectedAz * 180 / Math.PI).toFixed(1)}°, 误差: ${error.toFixed(2)}°`);
  }
  
  return avgTime;
}

function runDistanceEstimationTest() {
  console.log(`\n[距离估计测试]`);
  
  const arrayGeom = new ArrayGeometry({
    numElements: 32,
    topology: 'circular',
    spacing: 0.08
  });
  const positions = arrayGeom.generate();
  
  const beamforming = new Beamforming(positions, {
    fftSize: 1024,
    sampleRate: 48000
  });
  
  const sourceSim = new SourceSimulator({ sampleRate: 48000, noiseLevel: 0.01 });
  
  const testDistances = [1, 2, 3, 5, 8];
  
  for (const trueDistance of testDistances) {
    const azimuth = 45 * Math.PI / 180;
    const elevation = 10 * Math.PI / 180;
    
    const sources = [{
      type: 'sine',
      position: {
        x: trueDistance * Math.cos(elevation) * Math.cos(azimuth),
        y: trueDistance * Math.cos(elevation) * Math.sin(azimuth),
        z: trueDistance * Math.sin(elevation)
      },
      options: { frequency: 2000, amplitude: 1 }
    }];
    
    const signals = sourceSim.generateMultiSourceSignals(sources, positions, 4096);
    const frame = signals.map(s => s.slice(0, 1024));
    
    const distance = beamforming.estimateDistance(frame, azimuth, elevation, 2000);
    
    console.log(`  真实距离: ${trueDistance}m, 估计: ${distance.combined.toFixed(2)}m, 误差: ${Math.abs(distance.combined - trueDistance).toFixed(2)}m`);
  }
}

function runMultiSourceTest() {
  console.log(`\n[多声源定位测试] MUSIC算法, 32通道, 2个声源`);
  
  const arrayGeom = new ArrayGeometry({
    numElements: 32,
    topology: 'circular',
    spacing: 0.08
  });
  const positions = arrayGeom.generate();
  
  const beamforming = new Beamforming(positions, {
    fftSize: 1024,
    sampleRate: 48000
  });
  
  const sourceSim = new SourceSimulator({ sampleRate: 48000, noiseLevel: 0.02 });
  
  const sources = [
    {
      type: 'sine',
      position: { x: 3, y: 0, z: 0 },
      options: { frequency: 2000, amplitude: 1 }
    },
    {
      type: 'sine',
      position: { x: 0, y: -3, z: 0 },
      options: { frequency: 3000, amplitude: 0.8 }
    }
  ];
  
  const signals = sourceSim.generateMultiSourceSignals(sources, positions, 4096);
  const frame = signals.map(s => s.slice(0, 1024));
  
  const scanAngles = generateScanAngles(5, false);
  
  const start = Date.now();
  const powerMap = beamforming.music(frame, scanAngles, 2);
  const elapsed = Date.now() - start;
  
  const peaks = findPeaks(powerMap, 2, 0.1, 5);
  
  console.log(`  处理时间: ${elapsed}ms`);
  console.log(`  检测到 ${peaks.length} 个峰值:`);
  
  peaks.forEach((peak, idx) => {
    console.log(`    源${idx + 1}: 方位角 ${(peak.azimuth * 180 / Math.PI).toFixed(1)}°, 功率 ${(peak.normalizedPower * 100).toFixed(1)}%`);
  });
}

function runPerformanceBenchmark() {
  console.log('\n========================================');
  console.log('  性能基准测试 - 64通道 1024点FFT');
  console.log('========================================');
  
  const target = 50;
  console.log(`\n目标: 单帧处理 < ${target}ms`);
  
  const dasTime = runBeamformingTest(64, 1024, 'das', 10);
  const mvdrTime = runBeamformingTest(64, 1024, 'mvdr', 5);
  const musicTime = runBeamformingTest(64, 1024, 'music', 5);
  
  console.log('\n========================================');
  console.log('  测试结果汇总');
  console.log('========================================\n');
  
  console.log(`DAS:    ${dasTime.toFixed(2)}ms ${dasTime < target ? '✓ PASS' : '✗ FAIL'}`);
  console.log(`MVDR:   ${mvdrTime.toFixed(2)}ms ${mvdrTime < target ? '✓ PASS' : '✗ FAIL'}`);
  console.log(`MUSIC:  ${musicTime.toFixed(2)}ms ${musicTime < target ? '✓ PASS' : '✗ FAIL'}`);
  
  const allPass = dasTime < target && mvdrTime < target && musicTime < target;
  console.log(`\n总体: ${allPass ? '✓ 所有算法满足性能要求' : '✗ 部分算法不满足性能要求'}`);
  
  return allPass;
}

function runTopologyTest() {
  console.log(`\n[阵列拓扑测试]`);
  
  const topologies = ['linear', 'circular', 'spiral', 'planar'];
  const numElements = 16;
  
  for (const topology of topologies) {
    const arrayGeom = new ArrayGeometry({
      numElements,
      topology,
      spacing: 0.08
    });
    
    const positions = arrayGeom.generate();
    const baseline = arrayGeom.getBaseline();
    const maxFreq = arrayGeom.getMaxFrequency();
    const resolution = arrayGeom.getDOAResolution(2000);
    
    const topologyNames = {
      linear: '线性',
      circular: '圆形',
      spiral: '螺旋',
      planar: '平面'
    };
    
    console.log(`  ${topologyNames[topology]}阵列:`);
    console.log(`    基线: ${baseline.toFixed(3)}m, 最大频率: ${(maxFreq / 1000).toFixed(1)}kHz, 分辨率: ${resolution.toFixed(2)}°`);
  }
}

async function runAllTests() {
  console.log('开始执行信号处理测试...\n');
  
  runFFTTest(1024, 1000);
  runFFTTest(2048, 500);
  runFFTTest(4096, 200);
  
  runTopologyTest();
  
  runBeamformingTest(16, 1024, 'das', 50);
  runBeamformingTest(16, 1024, 'mvdr', 20);
  runBeamformingTest(16, 1024, 'music', 20);
  
  runBeamformingTest(32, 1024, 'das', 30);
  runBeamformingTest(64, 1024, 'das', 20);
  
  runDistanceEstimationTest();
  runMultiSourceTest();
  
  const performanceOK = runPerformanceBenchmark();
  
  console.log('\n========================================');
  console.log('  测试完成');
  console.log('========================================\n');
  
  process.exit(performanceOK ? 0 : 1);
}

runAllTests().catch(err => {
  console.error('测试失败:', err);
  process.exit(1);
});
