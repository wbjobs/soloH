const fs = require('fs');
const readline = require('readline');
const { getRuleByPattern, getAllRules } = require('../db/database');

const MAX_EVENTS_IN_MEMORY = 50000;
const MAX_MEASURES_IN_MEMORY = 10000;
const MAX_TOKENS_IN_MEMORY = 100000;

function normalizePattern(cell) {
  return cell.split(',').map(d => d.trim()).sort((a, b) => parseInt(a) - parseInt(b)).join(',');
}

function createRuleMap() {
  const rules = getAllRules();
  const ruleMap = {};
  rules.forEach(r => {
    if (!ruleMap[r.category]) ruleMap[r.category] = {};
    ruleMap[r.category][r.braille_pattern] = r;
  });
  return ruleMap;
}

function lookupPattern(ruleMap, pattern, category) {
  if (category && ruleMap[category]) {
    return ruleMap[category][pattern] || null;
  }
  for (const cat of Object.keys(ruleMap)) {
    if (ruleMap[cat][pattern]) {
      return ruleMap[cat][pattern];
    }
  }
  return null;
}

function parseBrailleFile(fileContent) {
  const ruleMap = createRuleMap();

  const tokens = [];
  const events = [];
  const measures = [];
  let noteCount = 0;

  let meta = {
    title: '',
    composer: '',
    tempo: 120,
    timeSignature: { beats: 4, unit: 4 },
    keySignature: 'C',
  };

  let currentMeasure = { index: 0, notes: [] };
  let currentContext = {
    octaveOffset: 0,
    duration: 1.0,
    velocity: 80,
    accidental: 0,
    ornaments: [],
    tie: false,
  };

  const lines = fileContent.split('\n');
  let lineCount = 0;

  for (let line of lines) {
    lineCount++;
    line = line.trim();
    if (!line) continue;

    if (line.startsWith('#')) {
      const metaLine = line.substring(1).trim();
      if (metaLine.toLowerCase().startsWith('title:')) {
        meta.title = metaLine.substring(6).trim();
      } else if (metaLine.toLowerCase().startsWith('composer:')) {
        meta.composer = metaLine.substring(9).trim();
      } else if (metaLine.toLowerCase().startsWith('tempo:')) {
        const t = parseInt(metaLine.substring(6).trim());
        if (!isNaN(t)) meta.tempo = t;
      } else if (metaLine.toLowerCase().startsWith('key:')) {
        meta.keySignature = metaLine.substring(4).trim();
      } else if (metaLine.toLowerCase().startsWith('time:')) {
        const timeMatch = metaLine.substring(5).trim().match(/(\d+)\/(\d+)/);
        if (timeMatch) {
          meta.timeSignature = { beats: parseInt(timeMatch[1]), unit: parseInt(timeMatch[2]) };
        }
      }
      continue;
    }

    if (line.startsWith('%')) continue;

    const cells = line.split(/\s+/);

    for (const cell of cells) {
      if (!cell) continue;

      const normalizedPattern = normalizePattern(cell);

      if (tokens.length < MAX_TOKENS_IN_MEMORY) {
        tokens.push({ pattern: cell, normalized: normalizedPattern });
      }

      const noteRule = lookupPattern(ruleMap, normalizedPattern, 'note');
      const durationRule = lookupPattern(ruleMap, normalizedPattern, 'duration');
      const octaveRule = lookupPattern(ruleMap, normalizedPattern, 'octave');
      const dynamicRule = lookupPattern(ruleMap, normalizedPattern, 'dynamic');
      const ornamentRule = lookupPattern(ruleMap, normalizedPattern, 'ornament');
      const accidentalRule = lookupPattern(ruleMap, normalizedPattern, 'accidental');
      const restRule = lookupPattern(ruleMap, normalizedPattern, 'rest');
      const barlineRule = lookupPattern(ruleMap, normalizedPattern, 'barline');
      const timeSigRule = lookupPattern(ruleMap, normalizedPattern, 'time_signature');

      if (noteRule) {
        const midiNote = 60 + currentContext.octaveOffset + noteRule.midi_value + currentContext.accidental;
        const noteEvent = {
          type: 'note',
          pitch: noteRule.meaning,
          midiNote: midiNote,
          duration: currentContext.duration,
          velocity: currentContext.velocity,
          ornaments: [...currentContext.ornaments],
          measure: currentMeasure.index,
          rawPattern: cell,
        };

        if (events.length < MAX_EVENTS_IN_MEMORY) {
          events.push(noteEvent);
        }
        currentMeasure.notes.push(noteEvent);
        noteCount++;
        currentContext.accidental = 0;
        currentContext.ornaments = [];
        continue;
      }

      if (octaveRule) {
        currentContext.octaveOffset = octaveRule.midi_value;
        if (events.length < MAX_EVENTS_IN_MEMORY) {
          events.push({
            type: 'octave',
            octave: octaveRule.meaning,
            offset: octaveRule.midi_value,
            measure: currentMeasure.index,
            rawPattern: cell,
          });
        }
        continue;
      }

      if (durationRule) {
        currentContext.duration = durationRule.duration;
        if (events.length < MAX_EVENTS_IN_MEMORY) {
          events.push({
            type: 'duration',
            duration: durationRule.meaning,
            value: durationRule.duration,
            measure: currentMeasure.index,
            rawPattern: cell,
          });
        }
        continue;
      }

      if (dynamicRule) {
        if (dynamicRule.midi_value > 0) {
          currentContext.velocity = dynamicRule.midi_value;
        }
        if (events.length < MAX_EVENTS_IN_MEMORY) {
          events.push({
            type: 'dynamic',
            dynamic: dynamicRule.meaning,
            measure: currentMeasure.index,
            rawPattern: cell,
          });
        }
        continue;
      }

      if (ornamentRule) {
        currentContext.ornaments.push(ornamentRule.meaning);
        if (events.length < MAX_EVENTS_IN_MEMORY) {
          events.push({
            type: 'ornament',
            ornament: ornamentRule.meaning,
            measure: currentMeasure.index,
            rawPattern: cell,
          });
        }
        continue;
      }

      if (accidentalRule) {
        currentContext.accidental = accidentalRule.midi_value;
        if (events.length < MAX_EVENTS_IN_MEMORY) {
          events.push({
            type: 'accidental',
            accidental: accidentalRule.meaning,
            offset: accidentalRule.midi_value,
            measure: currentMeasure.index,
            rawPattern: cell,
          });
        }
        continue;
      }

      if (restRule) {
        if (events.length < MAX_EVENTS_IN_MEMORY) {
          events.push({
            type: 'rest',
            rest: restRule.meaning,
            duration: restRule.duration,
            measure: currentMeasure.index,
            rawPattern: cell,
          });
        }
        continue;
      }

      if (barlineRule) {
        if (events.length < MAX_EVENTS_IN_MEMORY) {
          events.push({
            type: 'barline',
            barline: barlineRule.meaning,
            measure: currentMeasure.index,
            rawPattern: cell,
          });
        }
        if (barlineRule.meaning !== 'Repeat start') {
          if (currentMeasure.notes.length > 0) {
            if (measures.length < MAX_MEASURES_IN_MEMORY) {
              measures.push(currentMeasure);
            }
            currentMeasure = { index: currentMeasure.index + 1, notes: [] };
          }
        }
        continue;
      }

      if (timeSigRule) {
        const tsMatch = timeSigRule.meaning.match(/(\d+)\/(\d+)/);
        if (tsMatch) {
          meta.timeSignature = { beats: parseInt(tsMatch[1]), unit: parseInt(tsMatch[2]) };
        }
        if (events.length < MAX_EVENTS_IN_MEMORY) {
          events.push({
            type: 'time_signature',
            timeSignature: timeSigRule.meaning,
            measure: currentMeasure.index,
            rawPattern: cell,
          });
        }
        continue;
      }

      if (events.length < MAX_EVENTS_IN_MEMORY) {
        events.push({
          type: 'unknown',
          rawPattern: cell,
          measure: currentMeasure.index,
        });
      }
    }

    if (lineCount % 500 === 0) {
      if (global.gc) {
        global.gc();
      }
    }
  }

  if (currentMeasure.notes.length > 0 && measures.length < MAX_MEASURES_IN_MEMORY) {
    measures.push(currentMeasure);
  }

  return {
    meta,
    tokens,
    events,
    measures,
    totalNotes: noteCount,
    trimmed: {
      events: events.length >= MAX_EVENTS_IN_MEMORY,
      tokens: tokens.length >= MAX_TOKENS_IN_MEMORY,
      measures: measures.length >= MAX_MEASURES_IN_MEMORY,
    },
  };
}

async function parseBrailleFileStream(filePath) {
  const ruleMap = createRuleMap();

  const tokens = [];
  const events = [];
  const measures = [];
  let noteCount = 0;
  let lineCount = 0;

  let meta = {
    title: '',
    composer: '',
    tempo: 120,
    timeSignature: { beats: 4, unit: 4 },
    keySignature: 'C',
  };

  let currentMeasure = { index: 0, notes: [] };
  let currentContext = {
    octaveOffset: 0,
    duration: 1.0,
    velocity: 80,
    accidental: 0,
    ornaments: [],
    tie: false,
  };

  const rl = readline.createInterface({
    input: fs.createReadStream(filePath, { encoding: 'utf-8', highWaterMark: 64 * 1024 }),
    crlfDelay: Infinity,
  });

  for await (const line of rl) {
    lineCount++;
    const trimmedLine = line.trim();
    if (!trimmedLine) continue;

    if (trimmedLine.startsWith('#')) {
      const metaLine = trimmedLine.substring(1).trim();
      if (metaLine.toLowerCase().startsWith('title:')) {
        meta.title = metaLine.substring(6).trim();
      } else if (metaLine.toLowerCase().startsWith('composer:')) {
        meta.composer = metaLine.substring(9).trim();
      } else if (metaLine.toLowerCase().startsWith('tempo:')) {
        const t = parseInt(metaLine.substring(6).trim());
        if (!isNaN(t)) meta.tempo = t;
      } else if (metaLine.toLowerCase().startsWith('key:')) {
        meta.keySignature = metaLine.substring(4).trim();
      } else if (metaLine.toLowerCase().startsWith('time:')) {
        const timeMatch = metaLine.substring(5).trim().match(/(\d+)\/(\d+)/);
        if (timeMatch) {
          meta.timeSignature = { beats: parseInt(timeMatch[1]), unit: parseInt(timeMatch[2]) };
        }
      }
      continue;
    }

    if (trimmedLine.startsWith('%')) continue;

    const cells = trimmedLine.split(/\s+/);

    for (const cell of cells) {
      if (!cell) continue;

      const normalizedPattern = normalizePattern(cell);

      if (tokens.length < MAX_TOKENS_IN_MEMORY) {
        tokens.push({ pattern: cell, normalized: normalizedPattern });
      }

      const noteRule = lookupPattern(ruleMap, normalizedPattern, 'note');
      const durationRule = lookupPattern(ruleMap, normalizedPattern, 'duration');
      const octaveRule = lookupPattern(ruleMap, normalizedPattern, 'octave');
      const dynamicRule = lookupPattern(ruleMap, normalizedPattern, 'dynamic');
      const ornamentRule = lookupPattern(ruleMap, normalizedPattern, 'ornament');
      const accidentalRule = lookupPattern(ruleMap, normalizedPattern, 'accidental');
      const restRule = lookupPattern(ruleMap, normalizedPattern, 'rest');
      const barlineRule = lookupPattern(ruleMap, normalizedPattern, 'barline');
      const timeSigRule = lookupPattern(ruleMap, normalizedPattern, 'time_signature');

      if (noteRule) {
        const midiNote = 60 + currentContext.octaveOffset + noteRule.midi_value + currentContext.accidental;
        const noteEvent = {
          type: 'note',
          pitch: noteRule.meaning,
          midiNote: midiNote,
          duration: currentContext.duration,
          velocity: currentContext.velocity,
          ornaments: [...currentContext.ornaments],
          measure: currentMeasure.index,
          rawPattern: cell,
        };

        if (events.length < MAX_EVENTS_IN_MEMORY) {
          events.push(noteEvent);
        }
        currentMeasure.notes.push(noteEvent);
        noteCount++;
        currentContext.accidental = 0;
        currentContext.ornaments = [];
        continue;
      }

      if (octaveRule) {
        currentContext.octaveOffset = octaveRule.midi_value;
        if (events.length < MAX_EVENTS_IN_MEMORY) {
          events.push({
            type: 'octave',
            octave: octaveRule.meaning,
            offset: octaveRule.midi_value,
            measure: currentMeasure.index,
            rawPattern: cell,
          });
        }
        continue;
      }

      if (durationRule) {
        currentContext.duration = durationRule.duration;
        if (events.length < MAX_EVENTS_IN_MEMORY) {
          events.push({
            type: 'duration',
            duration: durationRule.meaning,
            value: durationRule.duration,
            measure: currentMeasure.index,
            rawPattern: cell,
          });
        }
        continue;
      }

      if (dynamicRule) {
        if (dynamicRule.midi_value > 0) {
          currentContext.velocity = dynamicRule.midi_value;
        }
        if (events.length < MAX_EVENTS_IN_MEMORY) {
          events.push({
            type: 'dynamic',
            dynamic: dynamicRule.meaning,
            measure: currentMeasure.index,
            rawPattern: cell,
          });
        }
        continue;
      }

      if (ornamentRule) {
        currentContext.ornaments.push(ornamentRule.meaning);
        if (events.length < MAX_EVENTS_IN_MEMORY) {
          events.push({
            type: 'ornament',
            ornament: ornamentRule.meaning,
            measure: currentMeasure.index,
            rawPattern: cell,
          });
        }
        continue;
      }

      if (accidentalRule) {
        currentContext.accidental = accidentalRule.midi_value;
        if (events.length < MAX_EVENTS_IN_MEMORY) {
          events.push({
            type: 'accidental',
            accidental: accidentalRule.meaning,
            offset: accidentalRule.midi_value,
            measure: currentMeasure.index,
            rawPattern: cell,
          });
        }
        continue;
      }

      if (restRule) {
        if (events.length < MAX_EVENTS_IN_MEMORY) {
          events.push({
            type: 'rest',
            rest: restRule.meaning,
            duration: restRule.duration,
            measure: currentMeasure.index,
            rawPattern: cell,
          });
        }
        continue;
      }

      if (barlineRule) {
        if (events.length < MAX_EVENTS_IN_MEMORY) {
          events.push({
            type: 'barline',
            barline: barlineRule.meaning,
            measure: currentMeasure.index,
            rawPattern: cell,
          });
        }
        if (barlineRule.meaning !== 'Repeat start') {
          if (currentMeasure.notes.length > 0) {
            if (measures.length < MAX_MEASURES_IN_MEMORY) {
              measures.push(currentMeasure);
            }
            currentMeasure = { index: currentMeasure.index + 1, notes: [] };
          }
        }
        continue;
      }

      if (timeSigRule) {
        const tsMatch = timeSigRule.meaning.match(/(\d+)\/(\d+)/);
        if (tsMatch) {
          meta.timeSignature = { beats: parseInt(tsMatch[1]), unit: parseInt(tsMatch[2]) };
        }
        if (events.length < MAX_EVENTS_IN_MEMORY) {
          events.push({
            type: 'time_signature',
            timeSignature: timeSigRule.meaning,
            measure: currentMeasure.index,
            rawPattern: cell,
          });
        }
        continue;
      }

      if (events.length < MAX_EVENTS_IN_MEMORY) {
        events.push({
          type: 'unknown',
          rawPattern: cell,
          measure: currentMeasure.index,
        });
      }
    }

    if (lineCount % 500 === 0) {
      if (global.gc) {
        global.gc();
      }
      await new Promise(resolve => setImmediate(resolve));
    }
  }

  if (currentMeasure.notes.length > 0 && measures.length < MAX_MEASURES_IN_MEMORY) {
    measures.push(currentMeasure);
  }

  return {
    meta,
    tokens,
    events,
    measures,
    totalNotes: noteCount,
    trimmed: {
      events: events.length >= MAX_EVENTS_IN_MEMORY,
      tokens: tokens.length >= MAX_TOKENS_IN_MEMORY,
      measures: measures.length >= MAX_MEASURES_IN_MEMORY,
    },
  };
}

module.exports = { parseBrailleFile, parseBrailleFileStream };
