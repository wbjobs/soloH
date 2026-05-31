const fs = require('fs');
const path = require('path');

function generateLongBrailleFile(pages = 15, outputPath) {
  const lines = [];

  lines.push('#title: 长测试乐谱');
  lines.push('#composer: 测试生成');
  lines.push('#tempo: 100');
  lines.push('#key: C');
  lines.push('#time: 4/4');
  lines.push('');

  const patterns = [
    ['3,4', '5', '1,2,6'],
    ['1', '1', '2,4,5', '2,4,5'],
    ['1,2,4,5', '1,2,4,5', '2,4,5', '1,2,5'],
    ['1,2,6', '1,2,5', '1,2,4,5', '2,4,5'],
    ['1', '1', '2,4,5', '2,4,5'],
    ['1,2,4,5', '1,2,4,5', '2,4,5', '1,2,5'],
    ['1,2,6', '1,2,5', '1,2,4,5', '2,4,5'],
    ['3,5,6'],
  ];

  const dynamics = [
    { pattern: '2,3,5', label: 'ppp' },
    { pattern: '5,6', label: 'pp' },
    { pattern: '5', label: 'p' },
    { pattern: '4,5,6', label: 'mp' },
    { pattern: '4', label: 'mf' },
    { pattern: '4,5', label: 'f' },
    { pattern: '4,6', label: 'ff' },
    { pattern: '3,4,6', label: 'fff' },
  ];

  for (let page = 0; page < pages; page++) {
    lines.push(`% 第 ${page + 1} 页`);

    const dynamic = dynamics[page % dynamics.length];
    lines.push(`${dynamic.pattern} % ${dynamic.label}`);

    for (let i = 0; i < patterns.length; i++) {
      const measure = patterns[i].join(' ');
      lines.push(measure);
    }

    if (page % 2 === 0) {
      lines.push('% 添加装饰音');
      lines.push('3,5 1 1,2,6 % 带颤音的C');
      lines.push('3,4,5 2,4,5 1,2,6 % 带波音的D');
    }

    if (page === Math.floor(pages / 2)) {
      lines.push('% 变奏');
      lines.push('1,6 1 1,6 2,4,5 % 八分音符');
      lines.push('1,3 1 1,3 2,4,5 % 十六分音符');
    }

    lines.push('');
  }

  lines.push('2,3,5 % 结束');

  const content = lines.join('\n');
  fs.writeFileSync(outputPath, content, 'utf-8');
  console.log(`生成 ${pages} 页盲文乐谱，共 ${lines.length} 行，${content.length} 字节`);
  return content.length;
}

if (require.main === module) {
  const pages = process.argv[2] ? parseInt(process.argv[2]) : 15;
  const output = process.argv[3] || path.join(__dirname, 'long_test.braille');
  generateLongBrailleFile(pages, output);
}

module.exports = { generateLongBrailleFile };
