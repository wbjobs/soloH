const { parseBrailleFile } = require('../services/brailleParser');
const { generateMidi } = require('../services/midiGenerator');
const { generateMusicXML } = require('../services/musicxmlGenerator');
const { separateVoices, separateVoicesByPattern } = require('../services/voiceSeparator');
const fs = require('fs');
const path = require('path');

console.log('='.repeat(70));
console.log('测试新功能: 编辑器、MusicXML、多声部分离');
console.log('='.repeat(70));

async function runTests() {
  let passed = 0;
  let failed = 0;

  const exampleFile = path.join(__dirname, 'example.braille');
  let parsedData;

  console.log('\n📋 测试1: 加载并解析示例文件');
  try {
    if (fs.existsSync(exampleFile)) {
      const content = fs.readFileSync(exampleFile, 'utf-8');
      parsedData = parseBrailleFile(content);
      console.log(`  解析成功: ${parsedData.totalNotes} 个音符, ${parsedData.measures.length} 个小节`);
      passed++;
    } else {
      console.log('  ⚠️ 示例文件不存在，创建测试数据');
      parsedData = {
        meta: {
          title: 'Test',
          composer: 'Test',
          tempo: 120,
          timeSignature: { beats: 4, unit: 4 },
          keySignature: 'C',
        },
        events: [
          { type: 'note', pitch: 'C', midiNote: 60, duration: 1.0, velocity: 80, measure: 0, ornaments: [] },
          { type: 'note', pitch: 'D', midiNote: 62, duration: 1.0, velocity: 80, measure: 0, ornaments: [] },
          { type: 'note', pitch: 'E', midiNote: 64, duration: 1.0, velocity: 80, measure: 0, ornaments: [] },
          { type: 'note', pitch: 'F', midiNote: 65, duration: 1.0, velocity: 80, measure: 0, ornaments: [] },
          { type: 'note', pitch: 'G', midiNote: 55, duration: 1.0, velocity: 80, measure: 1, ornaments: [] },
          { type: 'note', pitch: 'A', midiNote: 57, duration: 1.0, velocity: 80, measure: 1, ornaments: [] },
          { type: 'note', pitch: 'B', midiNote: 59, duration: 1.0, velocity: 80, measure: 1, ornaments: [] },
          { type: 'note', pitch: 'C', midiNote: 60, duration: 1.0, velocity: 80, measure: 1, ornaments: [] },
        ],
        measures: [{ index: 0, notes: [] }, { index: 1, notes: [] }],
        totalNotes: 8,
      };
      passed++;
    }
  } catch (e) {
    console.log('  ❌ 失败:', e.message);
    failed++;
  }

  console.log('\n📋 测试2: 多声部分离功能');
  try {
    const voices = separateVoices(parsedData);
    console.log(`  分离出 ${voices.length} 个声部:`);
    voices.forEach((v, idx) => {
      const noteCount = v.events.filter(e => e.type === 'note').length;
      console.log(`    - ${v.name}: ${noteCount} 个音符, 谱号: ${v.clef || 'N/A'}`);
    });

    if (voices.length >= 1 && voices.length <= 2) {
      console.log('  ✅ 通过: 声部分离功能正常');
      passed++;
    } else {
      console.log('  ❌ 失败: 声部数量异常');
      failed++;
    }
  } catch (e) {
    console.log('  ❌ 失败:', e.message);
    failed++;
  }

  console.log('\n📋 测试3: 多声部MIDI生成');
  try {
    const midiBuffer = generateMidi(parsedData, {
      tempo: 120,
      timeSignature: { beats: 4, unit: 4 },
      multiVoice: true,
    });

    const testFile = path.join(__dirname, 'test_multivoice.mid');
    fs.writeFileSync(testFile, Buffer.from(midiBuffer));
    const stats = fs.statSync(testFile);
    console.log(`  多声部MIDI生成成功: ${stats.size} 字节`);

    if (stats.size > 0) {
      console.log('  ✅ 通过: 多声部MIDI生成正常');
      passed++;
    } else {
      console.log('  ❌ 失败: MIDI文件为空');
      failed++;
    }

    fs.unlinkSync(testFile);
  } catch (e) {
    console.log('  ❌ 失败:', e.message);
    failed++;
  }

  console.log('\n📋 测试4: MusicXML导出功能');
  try {
    const musicxml = generateMusicXML(parsedData, {
      title: 'Test Song',
      composer: 'Test Composer',
    });

    const testFile = path.join(__dirname, 'test_musicxml.xml');
    fs.writeFileSync(testFile, musicxml, 'utf-8');
    const stats = fs.statSync(testFile);
    console.log(`  MusicXML生成成功: ${stats.size} 字节`);

    const hasScore = musicxml.includes('score-partwise');
    const hasPart = musicxml.includes('<part ');
    const hasNote = musicxml.includes('<note>');
    const hasClef = musicxml.includes('<clef');

    console.log(`  XML结构检查: score=${hasScore}, part=${hasPart}, note=${hasNote}, clef=${hasClef}`);

    if (hasScore && hasPart && hasNote && hasClef) {
      console.log('  ✅ 通过: MusicXML格式正确');
      passed++;
    } else {
      console.log('  ❌ 失败: MusicXML格式不完整');
      failed++;
    }

    fs.unlinkSync(testFile);
  } catch (e) {
    console.log('  ❌ 失败:', e.message);
    failed++;
  }

  console.log('\n📋 测试5: 基于模式的声部分离');
  try {
    const testData = {
      ...parsedData,
      events: parsedData.events.map((e, idx) => ({
        ...e,
        rawPattern: idx % 2 === 0 ? '1' : '3,4',
      })),
    };

    const voices = separateVoicesByPattern(testData);
    console.log(`  基于模式分离出 ${voices.length} 个声部:`);
    voices.forEach((v, idx) => {
      const noteCount = v.events.filter(e => e.type === 'note').length;
      console.log(`    - ${v.name}: ${noteCount} 个音符`);
    });

    if (voices.length >= 1) {
      console.log('  ✅ 通过: 基于模式的声部分离正常');
      passed++;
    } else {
      console.log('  ❌ 失败: 声部分离失败');
      failed++;
    }
  } catch (e) {
    console.log('  ❌ 失败:', e.message);
    failed++;
  }

  console.log('\n📋 测试6: 重新解析功能（编辑器支持）');
  try {
    const tokens = [
      { pattern: '1', normalized: '1' },
      { pattern: '1,2,6', normalized: '1,2,6' },
      { pattern: '2,4,5', normalized: '2,4,5' },
      { pattern: '1,2,4,5', normalized: '1,2,4,5' },
    ];

    const fileContent = tokens.map(t => t.normalized).join('\n');
    const reparsed = parseBrailleFile(fileContent);

    console.log(`  重新解析: ${reparsed.totalNotes} 个音符`);

    if (reparsed.totalNotes > 0) {
      console.log('  ✅ 通过: 重新解析功能正常');
      passed++;
    } else {
      console.log('  ❌ 失败: 重新解析未识别到音符');
      failed++;
    }
  } catch (e) {
    console.log('  ❌ 失败:', e.message);
    failed++;
  }

  console.log('\n' + '='.repeat(70));
  console.log(`测试完成: ${passed} 通过, ${failed} 失败`);
  console.log('='.repeat(70));

  process.exit(failed > 0 ? 1 : 0);
}

runTests().catch(e => {
  console.error('测试运行失败:', e);
  process.exit(1);
});
