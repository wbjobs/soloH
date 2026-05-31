const { Beamforming, generateScanAngles, findPeaks, angularDistance } = require('../src/signal-processing');
const ArrayGeometry = require('../src/array-geometry');
const { SourceSimulator } = require('../src/source-simulation');

console.log('========================================');
console.log('  Bug修复验证测试');
console.log('========================================\n');

function testCircularArraySymmetry() {
  console.log('[测试1] 圆形阵列对称性破缺验证');
  
  const arrayGeom = new ArrayGeometry({
    numElements: 16,
    topology: 'circular',
    spacing: 0.08
  });
  const positions = arrayGeom.generate();
  
  let hasZVariation = false;
  let hasXYVariation = false;
  
  for (let i = 0; i < positions.length; i++) {
    if (Math.abs(positions[i].z) > 1e-10) {
      hasZVariation = true;
    }
    const expectedAngle = (2 * Math.PI * i) / positions.length;
    const expectedRadius = 0.08 * positions.length / (2 * Math.PI);
    const expectedX = expectedRadius * Math.cos(expectedAngle);
    const expectedY = expectedRadius * Math.sin(expectedAngle);
    if (Math.abs(positions[i].x - expectedX) > 1e-10 || 
        Math.abs(positions[i].y - expectedY) > 1e-10) {
      hasXYVariation = true;
    }
  }
  
  console.log(`  Z轴扰动: ${hasZVariation ? '✓ 已添加' : '✗ 缺失'}`);
  console.log(`  XY平面扰动: ${hasXYVariation ? '✓ 已添加' : '✗ 缺失'}`);
  
  const beamforming = new Beamforming(positions, {
    fftSize: 1024,
    sampleRate: 48000
  });
  
  const sourceSim = new SourceSimulator({ sampleRate: 48000, noiseLevel: 0.01 });
  
  const sources = [{
    type: 'sine',
    position: { x: 3, y: 2, z: 0 },
    options: { frequency: 2000, amplitude: 1 }
  }];
  
  const signals = sourceSim.generateMultiSourceSignals(sources, positions, 4096);
  const frame = signals.map(s => s.slice(0, 1024));
  const scanAngles = generateScanAngles(5, false);
  
  const expectedAz = Math.atan2(2, 3);
  const oppositeAz = expectedAz + Math.PI;
  
  const powerMap = beamforming.das(frame, scanAngles);
  const peaks = findPeaks(powerMap, 2, 0.1, 5);
  
  let mainPeak = peaks[0];
  let oppositePeak = null;
  
  for (const peak of peaks) {
    const distToExpected = Math.abs(angularDistance(peak.azimuth, peak.elevation, expectedAz, 0));
    const distToOpposite = Math.abs(angularDistance(peak.azimuth, peak.elevation, oppositeAz, 0));
    if (distToOpposite < 0.2) {
      oppositePeak = peak;
    }
  }
  
  const mainOppositeRatio = oppositePeak ? (mainPeak.power / oppositePeak.power) : Infinity;
  
  console.log(`  主峰方位角: ${(mainPeak.azimuth * 180 / Math.PI).toFixed(1)}°`);
  console.log(`  期望方位角: ${(expectedAz * 180 / Math.PI).toFixed(1)}°`);
  console.log(`  主峰/对峰功率比: ${mainOppositeRatio.toFixed(2)}`);
  console.log(`  对称性破缺效果: ${mainOppositeRatio > 2 ? '✓ 良好 (>2:1)' : '✗ 不足 (<2:1)'}`);
  
  return mainOppositeRatio > 2;
}

function testDiagonalLoading() {
  console.log('\n[测试2] MVDR对角加载因子自动选择验证');
  
  const arrayGeom = new ArrayGeometry({
    numElements: 32,
    topology: 'circular',
    spacing: 0.08
  });
  const positions = arrayGeom.generate();
  
  const sourceSim = new SourceSimulator({ sampleRate: 48000 });
  
  const testCases = [
    { amplitude: 1.0, desc: '强信号' },
    { amplitude: 0.1, desc: '弱信号' },
    { amplitude: 0.01, desc: '极弱信号' }
  ];
  
  let allPass = true;
  
  for (const testCase of testCases) {
    const beamforming = new Beamforming(positions, {
      fftSize: 1024,
      sampleRate: 48000,
      diagonalLoading: null
    });
    
    const sources = [{
      type: 'sine',
      position: { x: 3, y: 2, z: 0 },
      options: { frequency: 2000, amplitude: testCase.amplitude }
    }];
    
    const signals = sourceSim.generateMultiSourceSignals(sources, positions, 4096);
    const frame = signals.map(s => s.slice(0, 1024));
    const scanAngles = generateScanAngles(5, false);
    
    beamforming.computeSpectraFast(frame);
    const covResult = beamforming.computeCovarianceMatrixFast();
    
    const loading = covResult.loading;
    const avgDiag = covResult.avgDiag;
    const ratio = loading / avgDiag;
    
    console.log(`  ${testCase.desc} (幅度=${testCase.amplitude}):`);
    console.log(`    平均对角值: ${avgDiag.toExponential(2)}`);
    console.log(`    加载因子: ${loading.toExponential(2)}`);
    console.log(`    加载比例: ${(ratio * 1000).toFixed(2)}‰`);
    
    const loadingInRange = ratio > 1e-4 && ratio < 1e-2;
    console.log(`    自动选择: ${loadingInRange ? '✓ 合理' : '✗ 不合理'}`);
    
    if (!loadingInRange) allPass = false;
    
    const powerMap = beamforming.mvdr(frame, scanAngles);
    const peaks = findPeaks(powerMap, 1, 0.1, 5);
    
    if (peaks.length > 0) {
      const expectedAz = Math.atan2(2, 3);
      const error = Math.abs(angularDistance(peaks[0].azimuth, peaks[0].elevation, expectedAz, 0)) * 180 / Math.PI;
      console.log(`    定位误差: ${error.toFixed(2)}°`);
    }
  }
  
  return allPass;
}

function testMultiSourceClustering() {
  console.log('\n[测试3] 多声源聚类阈值验证');
  
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
  
  const testCases = [
    { 
      desc: '两源分离90°', 
      sources: [
        { type: 'sine', position: { x: 3, y: 0, z: 0 }, options: { frequency: 2000, amplitude: 1 } },
        { type: 'sine', position: { x: 0, y: -3, z: 0 }, options: { frequency: 3000, amplitude: 0.8 } }
      ],
      expectedAngles: [0, -Math.PI / 2]
    },
    { 
      desc: '两源接近30°', 
      sources: [
        { type: 'sine', position: { x: 3, y: 0, z: 0 }, options: { frequency: 2000, amplitude: 1 } },
        { type: 'sine', position: { x: 3 * Math.cos(Math.PI/6), y: 3 * Math.sin(Math.PI/6), z: 0 }, options: { frequency: 3000, amplitude: 0.8 } }
      ],
      expectedAngles: [0, Math.PI / 6]
    },
    { 
      desc: '两源接近边界350°和10°', 
      sources: [
        { type: 'sine', position: { x: 3 * Math.cos(-Math.PI/18), y: 3 * Math.sin(-Math.PI/18), z: 0 }, options: { frequency: 2000, amplitude: 1 } },
        { type: 'sine', position: { x: 3 * Math.cos(Math.PI/18), y: 3 * Math.sin(Math.PI/18), z: 0 }, options: { frequency: 3000, amplitude: 0.8 } }
      ],
      expectedAngles: [-Math.PI/18, Math.PI/18]
    }
  ];
  
  let allPass = true;
  
  for (const testCase of testCases) {
    const signals = sourceSim.generateMultiSourceSignals(testCase.sources, positions, 4096);
    const frame = signals.map(s => s.slice(0, 1024));
    const scanAngles = generateScanAngles(5, false);
    
    const powerMap = beamforming.music(frame, scanAngles, 2);
    const peaks = findPeaks(powerMap, 2, 0.1, 5);
    
    console.log(`  ${testCase.desc}:`);
    console.log(`    检测到 ${peaks.length} 个声源`);
    
    if (peaks.length !== 2) {
      console.log(`    ✗ 期望检测到2个声源`);
      allPass = false;
      continue;
    }
    
    let matched = 0;
    for (const peak of peaks) {
      let minDist = Infinity;
      for (const expected of testCase.expectedAngles) {
        const dist = Math.abs(angularDistance(peak.azimuth, peak.elevation, expected, 0));
        minDist = Math.min(minDist, dist);
      }
      const errorDeg = minDist * 180 / Math.PI;
      console.log(`    检测角度: ${(peak.azimuth * 180 / Math.PI).toFixed(1)}°, 误差: ${errorDeg.toFixed(2)}°`);
      
      if (errorDeg < 15) {
        matched++;
      }
    }
    
    if (matched === 2) {
      console.log(`    ✓ 两个声源都正确匹配`);
    } else {
      console.log(`    ✗ 仅匹配 ${matched}/2 个声源`);
      allPass = false;
    }
  }
  
  return allPass;
}

async function runAllTests() {
  console.log('开始执行Bug修复验证测试...\n');
  
  const result1 = testCircularArraySymmetry();
  const result2 = testDiagonalLoading();
  const result3 = testMultiSourceClustering();
  
  console.log('\n========================================');
  console.log('  测试结果汇总');
  console.log('========================================\n');
  
  console.log(`圆形阵列对称性破缺: ${result1 ? '✓ PASS' : '✗ FAIL'}`);
  console.log(`MVDR对角加载自动选择: ${result2 ? '✓ PASS' : '✗ FAIL'}`);
  console.log(`多声源聚类阈值: ${result3 ? '✓ PASS' : '✗ FAIL'}`);
  
  const allPass = result1 && result2 && result3;
  console.log(`\n总体: ${allPass ? '✓ 所有修复验证通过' : '✗ 部分修复验证失败'}`);
  
  console.log('\n========================================');
  console.log('  测试完成');
  console.log('========================================\n');
  
  process.exit(allPass ? 0 : 1);
}

runAllTests().catch(err => {
  console.error('测试失败:', err);
  process.exit(1);
});
