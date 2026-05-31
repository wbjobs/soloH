const fs = require('fs');
const path = require('path');

function midiNoteToName(midiNote) {
  const notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
  const octave = Math.floor(midiNote / 12) - 1;
  const noteIndex = midiNote % 12;
  return {
    name: notes[noteIndex].replace('#', '#'),
    octave: octave,
    hasSharp: notes[noteIndex].includes('#'),
    hasFlat: false,
  };
}

function getAlter(midiNote) {
  const noteNames = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
  const noteName = noteNames[midiNote % 12];
  if (noteName.includes('#')) return 1;
  return 0;
}

function durationToType(duration) {
  if (duration >= 4) return 'whole';
  if (duration >= 2) return 'half';
  if (duration >= 1) return 'quarter';
  if (duration >= 0.5) return 'eighth';
  if (duration >= 0.25) return '16th';
  if (duration >= 0.125) return '32nd';
  return '64th';
}

function durationToDivisions(duration, divisions = 4) {
  return Math.round(duration * divisions * 4);
}

function generateMusicXML(parsedData, options = {}) {
  const { title = 'Untitled', composer = 'Unknown' } = options;
  const events = parsedData.events;
  const notes = events.filter(e => e.type === 'note');
  const rests = events.filter(e => e.type === 'rest');
  const allEvents = [...notes, ...rests].sort((a, b) => {
    if (a.measure !== b.measure) return a.measure - b.measure;
    return 0;
  });

  const tempo = parsedData.meta?.tempo || 120;
  const beats = parsedData.meta?.timeSignature?.beats || 4;
  const beatUnit = parsedData.meta?.timeSignature?.unit || 4;
  const key = parsedData.meta?.keySignature || 'C';
  const divisions = 4;

  const voices = separateVoices(parsedData);

  let xml = `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">
<score-partwise version="3.1">
  <work>
    <work-title>${escapeXml(title)}</work-title>
  </work>
  <identification>
    <creator type="composer">${escapeXml(composer)}</creator>
    <encoding-date>${new Date().toISOString().split('T')[0]}</encoding-date>
    <software>Braille to MIDI Converter</software>
  </identification>
  <part-list>
    ${generatePartList(voices)}
  </part-list>
`;

  voices.forEach((voice, voiceIndex) => {
    xml += generatePart(voice, voiceIndex, tempo, beats, beatUnit, key, divisions, title);
  });

  xml += `</score-partwise>`;
  return xml;
}

function generatePartList(voices) {
  return voices.map((voice, idx) => `
    <score-part id="P${idx + 1}">
      <part-name>${escapeXml(voice.name || `Voice ${idx + 1}`)}</part-name>
      <score-instrument id="P${idx + 1}-I${idx + 1}">
        <instrument-name>${getInstrumentName(idx)}</instrument-name>
      </score-instrument>
      <midi-instrument id="P${idx + 1}-I${idx + 1}">
        <midi-channel>${idx + 1}</midi-channel>
        <midi-program>${getMidiProgram(idx)}</midi-program>
      </midi-instrument>
    </score-part>
  `).join('');
}

function generatePart(voice, voiceIndex, tempo, beats, beatUnit, key, divisions, title) {
  const measures = groupIntoMeasures(voice.events, beats);
  let part = `  <part id="P${voiceIndex + 1}">
`;

  measures.forEach((measure, measureIdx) => {
    part += `    <measure number="${measureIdx + 1}">
`;

    if (measureIdx === 0) {
      part += `      <attributes>
        <divisions>${divisions}</divisions>
        <key>
          <fifths>${getKeyFifths(key)}</fifths>
        </key>
        <time>
          <beats>${beats}</beats>
          <beat-type>${beatUnit}</beat-type>
        </time>
        <staves>1</staves>
        <clef number="1">
          <sign>${getClefForEvents(voice.events)}</sign>
          <line>${getClefLine(voice.events)}</line>
        </clef>
      </attributes>
      <sound tempo="${tempo}"/>
`;
    }

    const allMeasureEvents = measure.events;
    let position = 0;

    allMeasureEvents.forEach(event => {
      if (event.type === 'rest') {
        const durType = durationToType(event.duration);
        const durDiv = durationToDivisions(event.duration, divisions);
        part += `      <note>
        <rest/>
        <duration>${durDiv}</duration>
        <voice>1</voice>
        <type>${durType}</type>
      </note>
`;
      } else if (event.type === 'note') {
        const noteInfo = midiNoteToName(event.midiNote);
        const durType = durationToType(event.duration);
        const durDiv = durationToDivisions(event.duration, divisions);
        const alter = getAlter(event.midiNote);

        part += `      <note>
        <pitch>
          <step>${noteInfo.name.replace('#', '')}</step>
          ${alter !== 0 ? `<alter>${alter}</alter>` : ''}
          <octave>${noteInfo.octave}</octave>
        </pitch>
        <duration>${durDiv}</duration>
        <voice>1</voice>
        <type>${durType}</type>
        <staff>1</staff>
        <notations>
          <technical>
            <string>1</string>
            <fret>0</fret>
          </technical>
        </notations>
      </note>
`;
      }
    });

    if (measure.isLast) {
      part += `      <barline location="right">
        <bar-style>light-heavy</bar-style>
      </barline>
`;
    } else if (measure.hasRepeatEnd) {
      part += `      <barline location="right">
        <bar-style>heavy-light</bar-style>
        <repeat direction="backward"/>
      </barline>
`;
    }

    part += `    </measure>
`;
  });

  part += `  </part>
`;
  return part;
}

function separateVoices(parsedData) {
  const events = parsedData.events;
  const notes = events.filter(e => e.type === 'note' || e.type === 'rest');

  if (notes.length === 0) {
    return [{ name: 'Voice 1', events: notes }];
  }

  const sortedNotes = [...notes].sort((a, b) => {
    if (a.measure !== b.measure) return a.measure - b.measure;
    return 0;
  });

  const trebleNotes = [];
  const bassNotes = [];
  const middleC = 60;

  sortedNotes.forEach(note => {
    if (note.type === 'rest') {
      trebleNotes.push(note);
      bassNotes.push({ ...note, isSharedRest: true });
    } else {
      if (note.midiNote >= middleC) {
        trebleNotes.push(note);
      }
      if (note.midiNote <= middleC) {
        bassNotes.push(note);
      }
    }
  });

  const trebleHasNotes = trebleNotes.some(n => n.type === 'note');
  const bassHasNotes = bassNotes.some(n => n.type === 'note' && n.midiNote < middleC);

  if (!trebleHasNotes || !bassHasNotes) {
    return [{ name: 'Voice 1', events: sortedNotes }];
  }

  const trebleRests = fillRestsForMissing(trebleNotes, sortedNotes);
  const bassRests = fillRestsForMissing(bassNotes, sortedNotes);

  return [
    { name: 'Treble Voice', events: trebleRests, clef: 'treble' },
    { name: 'Bass Voice', events: bassRests, clef: 'bass' },
  ];
}

function fillRestsForMissing(voiceNotes, allNotes) {
  const result = [];
  let noteIdx = 0;

  allNotes.forEach(note => {
    if (note.type === 'rest') {
      result.push(note);
    } else if (noteIdx < voiceNotes.length && voiceNotes[noteIdx] === note) {
      result.push(note);
      noteIdx++;
    } else if (voiceNotes.includes(note)) {
      result.push(note);
    } else {
      result.push({
        type: 'rest',
        rest: 'Quarter rest',
        duration: note.duration,
        measure: note.measure,
        rawPattern: 'rest',
      });
    }
  });

  return result;
}

function groupIntoMeasures(events, beatsPerMeasure) {
  const measures = [];
  let currentMeasure = { events: [], totalDuration: 0 };
  let currentMeasureIndex = 0;

  events.forEach(event => {
    if (event.measure !== currentMeasureIndex) {
      if (currentMeasure.events.length > 0) {
        measures.push({
          events: currentMeasure.events,
          isLast: false,
          hasRepeatEnd: false,
        });
      }
      currentMeasure = { events: [], totalDuration: 0 };
      currentMeasureIndex = event.measure;
    }
    currentMeasure.events.push(event);
  });

  if (currentMeasure.events.length > 0) {
    measures.push({
      events: currentMeasure.events,
      isLast: true,
      hasRepeatEnd: false,
    });
  }

  if (measures.length === 0 && events.length > 0) {
    measures.push({ events, isLast: true, hasRepeatEnd: false });
  }

  return measures;
}

function getKeyFifths(key) {
  const keyMap = {
    'C': 0, 'G': 1, 'D': 2, 'A': 3, 'E': 4, 'B': 5, 'F#': 6,
    'F': -1, 'Bb': -2, 'Eb': -3, 'Ab': -4, 'Db': -5, 'Gb': -6,
    'Am': 0, 'Em': 1, 'Bm': 2, 'F#m': 3, 'C#m': 4,
    'Dm': -1, 'Gm': -2, 'Cm': -3, 'Fm': -4,
  };
  return keyMap[key] || 0;
}

function getClefForEvents(events) {
  const notes = events.filter(e => e.type === 'note');
  if (notes.length === 0) return 'G';
  const avgMidi = notes.reduce((sum, n) => sum + n.midiNote, 0) / notes.length;
  return avgMidi >= 60 ? 'G' : 'F';
}

function getClefLine(events) {
  const notes = events.filter(e => e.type === 'note');
  if (notes.length === 0) return 2;
  const avgMidi = notes.reduce((sum, n) => sum + n.midiNote, 0) / notes.length;
  return avgMidi >= 60 ? 2 : 4;
}

function getInstrumentName(idx) {
  const instruments = ['Piano', 'Violin', 'Viola', 'Cello', 'Flute', 'Clarinet'];
  return instruments[idx % instruments.length];
}

function getMidiProgram(idx) {
  const programs = [0, 40, 41, 42, 73, 71];
  return programs[idx % programs.length];
}

function escapeXml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

module.exports = { generateMusicXML };
