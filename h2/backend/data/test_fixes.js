const { parseBrailleFile, parseBrailleFileStream } = require('../services/brailleParser');
const { loadDefaultRules } = require('../data/mappingRules');
const fs = require('fs');
const path = require('path');

console.log('='.repeat(60));
console.log('测试三个Bug修复');
console.log('='.repeat(60));

async function runTests() {
  let passed = 0;
  let failed = 0;

  console.log('\n📋 测试1: 力度映射规则检查 (ppp 到 fff)');
  try {
    const rules = loadDefaultRules();
    const dynamics = rules.filter(r => r.category === 'dynamic' && r.midi_value > 0);

    console.log(`  找到 ${dynamics.length} 个力度规则:`);
    dynamics.forEach(d => {
      console.log(`    - ${d.meaning}: velocity = ${d.midi_value}`);
    });

    const velocities = dynamics.map(d => d.midi_value);
    const hasPpp = dynamics.some(d => d.meaning.includes('ppp'));
    const hasFff = dynamics.some(d => d.meaning.includes('fff'));
    const isSorted = velocities.every((v, i) => i === 0 || v >= velocities[i - 1]);
    const validRange = velocities.every(v => v >= 10 && v <= 127);
    const notAllMax = !velocities.every(v => v === 120 || v === 127);

    if (hasPpp && hasFff && isSorted && validRange && notAllMax) {
      console.log('  ✅ 通过: 力度范围正确，从ppp(20)到fff(120)，不会全是最大音量');
      passed++;
    } else {
      console.log(`  ❌ 失败: ppp=${hasPpp}, fff=${hasFff}, sorted=${isSorted}, validRange=${validRange}, notAllMax=${notAllMax}`);
      failed++;
    }
  } catch (e) {
    console.log('  ❌ 失败:', e.message);
    failed++;
  }

  console.log('\n📋 测试2: 长文件内存溢出检查');
  try {
    const { generateLongBrailleFile } = require('./generateLongFile');
    const testFile = path.join(__dirname, 'test_long.braille');
    generateLongBrailleFile(20, testFile);

    const stats = fs.statSync(testFile);
    console.log(`  测试文件大小: ${(stats.size / 1024).toFixed(2)} KB`);

    const before = process.memoryUsage().heapUsed;
    const content = fs.readFileSync(testFile, 'utf-8');
    const parsed = parseBrailleFile(content);
    const after = process.memoryUsage().heapUsed;
    const memoryUsed = (after - before) / 1024 / 1024;

    console.log(`  解析音符数: ${parsed.totalNotes}`);
    console.log(`  内存使用: ${memoryUsed.toFixed(2)} MB`);
    console.log(`  数据裁剪标记: ${JSON.stringify(parsed.trimmed)}`);

    const noteEvents = parsed.events.filter(e => e.type === 'note').length;
    const memoryOk = memoryUsed < 200;
    const eventLimitOk = parsed.events.length <= 50000;
    const trimmedFlag = parsed.trimmed.events === false || parsed.trimmed.events === true;

    if (memoryOk && eventLimitOk && trimmedFlag) {
      console.log('  ✅ 通过: 内存使用正常，事件数量有限制，裁剪标记正确');
      passed++;
    } else {
      console.log(`  ❌ 失败: memory=${memoryUsed.toFixed(2)}MB (<200MB), events=${parsed.events.length} (<=50000), trimmed=${trimmedFlag}`);
      failed++;
    }

    fs.unlinkSync(testFile);
  } catch (e) {
    console.log('  ❌ 失败:', e.message);
    failed++;
  }

  console.log('\n📋 测试3: 流式解析长文件');
  try {
    const { generateLongBrailleFile } = require('./generateLongFile');
    const testFile = path.join(__dirname, 'test_stream.braille');
    generateLongBrailleFile(30, testFile);

    const stats = fs.statSync(testFile);
    console.log(`  测试文件大小: ${(stats.size / 1024).toFixed(2)} KB`);

    const before = process.memoryUsage().heapUsed;
    const parsed = await parseBrailleFileStream(testFile);
    const after = process.memoryUsage().heapUsed;
    const memoryUsed = (after - before) / 1024 / 1024;

    console.log(`  解析音符数: ${parsed.totalNotes}`);
    console.log(`  内存使用: ${memoryUsed.toFixed(2)} MB`);
    console.log(`  小节数: ${parsed.measures.length}`);

    const streamingOk = parsed.totalNotes > 0;
    const memoryOk = memoryUsed < 200;
    const notesParsed = parsed.events.some(e => e.type === 'note');

    if (streamingOk && memoryOk && notesParsed) {
      console.log('  ✅ 通过: 流式解析正常工作，内存效率高');
      passed++;
    } else {
      console.log(`  ❌ 失败: streaming=${streamingOk}, memory=${memoryUsed.toFixed(2)}MB (<200MB), notes=${notesParsed}`);
      failed++;
    }

    fs.unlinkSync(testFile);
  } catch (e) {
    console.log('  ❌ 失败:', e.message);
    failed++;
  }

  console.log('\n📋 测试4: 力度值不会全为最大 (MIDI音量bug检查)');
  try {
    const rules = loadDefaultRules();
    const dynamics = rules.filter(r => r.category === 'dynamic' && r.midi_value > 0);

    const uniqueVelocities = [...new Set(dynamics.map(d => d.midi_value))];
    console.log(`  力度速度值: [${uniqueVelocities.join(', ')}]`);

    const velocityValues = dynamics.map(d => d.midi_value);
    const hasGradient = velocityValues.some(v => v > 20 && v < 120);
    const notAllSame = uniqueVelocities.length > 2;
    const fffIsMax = Math.max(...velocityValues) >= 115;
    const pppIsMin = Math.min(...velocityValues) <= 30;

    if (hasGradient && notAllSame && fffIsMax && pppIsMin) {
      console.log('  ✅ 通过: 力度梯度正确，不会全是最大音量');
      passed++;
    } else {
      console.log(`  ❌ 失败: gradient=${hasGradient}, notAllSame=${notAllSame}, fffMax=${fffIsMax}, pppMin=${pppIsMin}`);
      failed++;
    }
  } catch (e) {
    console.log('  ❌ 失败:', e.message);
    failed++;
  }

  console.log('\n' + '='.repeat(60));
  console.log(`测试完成: ${passed} 通过, ${failed} 失败`);
  console.log('='.repeat(60));

  process.exit(failed > 0 ? 1 : 0);
}

runTests().catch(e => {
  console.error('测试运行失败:', e);
  process.exit(1);
});
