function separateVoices(parsedData) {
  const events = parsedData.events;
  const notes = events.filter(e => e.type === 'note' || e.type === 'rest');

  if (notes.length === 0) {
    return [{
      name: 'Voice 1',
      events: notes,
      clef: 'treble',
      midiChannel: 0,
      midiProgram: 0,
    }];
  }

  const sortedNotes = [...notes].sort((a, b) => {
    if (a.measure !== b.measure) return a.measure - b.measure;
    return 0;
  });

  const trebleNotes = [];
  const bassNotes = [];
  const middleC = 60;
  let hasTreble = false;
  let hasBass = false;

  sortedNotes.forEach((note, idx) => {
    if (note.type === 'rest') {
      trebleNotes.push({ ...note, originalIndex: idx });
      bassNotes.push({ ...note, originalIndex: idx, isSharedRest: true });
    } else {
      if (note.midiNote >= middleC) {
        trebleNotes.push({ ...note, originalIndex: idx });
        hasTreble = true;
      }
      if (note.midiNote <= middleC) {
        bassNotes.push({ ...note, originalIndex: idx });
        hasBass = true;
      }
    }
  });

  if (!hasTreble || !hasBass) {
    return [{
      name: 'Voice 1',
      events: sortedNotes,
      clef: hasTreble ? 'treble' : 'bass',
      midiChannel: 0,
      midiProgram: 0,
    }];
  }

  const trebleFilled = fillMissingRests(trebleNotes, sortedNotes);
  const bassFilled = fillMissingRests(bassNotes, sortedNotes);

  return [
    {
      name: 'Treble Voice',
      events: trebleFilled,
      clef: 'treble',
      midiChannel: 0,
      midiProgram: 0,
    },
    {
      name: 'Bass Voice',
      events: bassFilled,
      clef: 'bass',
      midiChannel: 1,
      midiProgram: 0,
    },
  ];
}

function fillMissingRests(voiceNotes, allNotes) {
  const result = [];
  let voiceIdx = 0;

  allNotes.forEach((note, originalIdx) => {
    if (voiceIdx < voiceNotes.length && voiceNotes[voiceIdx].originalIndex === originalIdx) {
      result.push(voiceNotes[voiceIdx]);
      voiceIdx++;
    } else {
      result.push({
        type: 'rest',
        rest: 'Quarter rest',
        duration: note.duration || 1.0,
        measure: note.measure,
        rawPattern: 'rest',
        originalIndex: originalIdx,
      });
    }
  });

  return result;
}

function separateVoicesByPattern(parsedData) {
  const events = parsedData.events;
  const notes = events.filter(e => e.type === 'note' || e.type === 'rest');

  if (notes.length === 0) {
    return [{ name: 'Voice 1', events: notes, clef: 'treble', midiChannel: 0, midiProgram: 0 }];
  }

  const voices = {
    right: { name: 'Right Hand', events: [], clef: 'treble', midiChannel: 0, midiProgram: 0 },
    left: { name: 'Left Hand', events: [], clef: 'bass', midiChannel: 1, midiProgram: 0 },
  };

  let currentHand = 'right';

  notes.forEach((note, idx) => {
    if (note.type === 'rest') {
      voices.right.events.push({ ...note, originalIndex: idx });
      voices.left.events.push({ ...note, originalIndex: idx, isSharedRest: true });
    } else {
      const pattern = note.rawPattern || '';

      if (pattern.includes('6') && !pattern.includes('3')) {
        currentHand = 'right';
      } else if (pattern.includes('3') && !pattern.includes('6')) {
        currentHand = 'left';
      }

      if (currentHand === 'right') {
        voices.right.events.push({ ...note, originalIndex: idx });
        voices.left.events.push({
          type: 'rest',
          rest: 'Quarter rest',
          duration: note.duration,
          measure: note.measure,
          rawPattern: 'rest',
          originalIndex: idx,
        });
      } else {
        voices.left.events.push({ ...note, originalIndex: idx });
        voices.right.events.push({
          type: 'rest',
          rest: 'Quarter rest',
          duration: note.duration,
          measure: note.measure,
          rawPattern: 'rest',
          originalIndex: idx,
        });
      }
    }
  });

  return Object.values(voices).filter(v => v.events.some(e => e.type === 'note'));
}

function detectSimultaneousNotes(events) {
  const grouped = {};
  const result = [];

  events.forEach((event, idx) => {
    if (event.type !== 'note') {
      result.push([event]);
      return;
    }

    const key = `${event.measure}_${idx}`;

    if (grouped[event.measure]) {
      grouped[event.measure].push(event);
    } else {
      grouped[event.measure] = [event];
    }
  });

  return result;
}

function getVoiceByRange(midiNote) {
  if (midiNote >= 60) return 'treble';
  return 'bass';
}

module.exports = {
  separateVoices,
  separateVoicesByPattern,
  detectSimultaneousNotes,
  getVoiceByRange,
};
