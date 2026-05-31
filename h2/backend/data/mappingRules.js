function loadDefaultRules() {
  const rules = [];

  const notes = [
    { pattern: '1', meaning: 'C', midi: 0, category: 'note' },
    { pattern: '1,4', meaning: 'D', midi: 2, category: 'note' },
    { pattern: '1,2', meaning: 'E', midi: 4, category: 'note' },
    { pattern: '1,2,4', meaning: 'F', midi: 5, category: 'note' },
    { pattern: '1,2,4,5', meaning: 'G', midi: 7, category: 'note' },
    { pattern: '1,2,5', meaning: 'A', midi: 9, category: 'note' },
    { pattern: '2,4,5', meaning: 'B', midi: 11, category: 'note' },
  ];

  notes.forEach(n => {
    rules.push({
      category: n.category,
      braille_pattern: n.pattern,
      meaning: n.meaning,
      midi_value: n.midi,
      duration: null,
      description: `Note ${n.meaning} (semitone offset from C: ${n.midi})`
    });
  });

  const durations = [
    { pattern: '1,2,5,6', meaning: 'Whole note', duration: 4.0, category: 'duration' },
    { pattern: '1,2,5', meaning: 'Half note', duration: 2.0, category: 'duration' },
    { pattern: '1,2,6', meaning: 'Quarter note', duration: 1.0, category: 'duration' },
    { pattern: '1,6', meaning: 'Eighth note', duration: 0.5, category: 'duration' },
    { pattern: '1,3', meaning: 'Sixteenth note', duration: 0.25, category: 'duration' },
    { pattern: '1,2,3,6', meaning: 'Thirty-second note', duration: 0.125, category: 'duration' },
  ];

  durations.forEach(d => {
    rules.push({
      category: d.category,
      braille_pattern: d.pattern,
      meaning: d.meaning,
      midi_value: null,
      duration: d.duration,
      description: `${d.meaning} (${d.duration} beats in 4/4 time)`
    });
  });

  const octaves = [
    { pattern: '3,4,5,6', meaning: 'Octave 1', midiOffset: -24, category: 'octave' },
    { pattern: '3,4,5', meaning: 'Octave 2', midiOffset: -12, category: 'octave' },
    { pattern: '3,4', meaning: 'Octave 3', midiOffset: 0, category: 'octave' },
    { pattern: '4,5', meaning: 'Octave 4', midiOffset: 12, category: 'octave' },
    { pattern: '4,5,6', meaning: 'Octave 5', midiOffset: 24, category: 'octave' },
    { pattern: '5,6', meaning: 'Octave 6', midiOffset: 36, category: 'octave' },
    { pattern: '6', meaning: 'Octave 7', midiOffset: 48, category: 'octave' },
  ];

  octaves.forEach(o => {
    rules.push({
      category: o.category,
      braille_pattern: o.pattern,
      meaning: o.meaning,
      midi_value: o.midiOffset,
      duration: null,
      description: `${o.meaning} (MIDI offset: ${o.midiOffset > 0 ? '+' : ''}${o.midiOffset})`
    });
  });

  const dynamics = [
    { pattern: '2,3,5', meaning: 'Pianississimo (ppp)', midiVelocity: 20, category: 'dynamic' },
    { pattern: '5,6', meaning: 'Pianissimo (pp)', midiVelocity: 35, category: 'dynamic' },
    { pattern: '5', meaning: 'Piano (p)', midiVelocity: 55, category: 'dynamic' },
    { pattern: '4,5,6', meaning: 'Mezzo-piano (mp)', midiVelocity: 70, category: 'dynamic' },
    { pattern: '4', meaning: 'Mezzo-forte (mf)', midiVelocity: 78, category: 'dynamic' },
    { pattern: '4,5', meaning: 'Forte (f)', midiVelocity: 90, category: 'dynamic' },
    { pattern: '4,6', meaning: 'Fortissimo (ff)', midiVelocity: 105, category: 'dynamic' },
    { pattern: '3,4,6', meaning: 'Fortississimo (fff)', midiVelocity: 120, category: 'dynamic' },
    { pattern: '1,4,5', meaning: 'Crescendo', midiVelocity: 0, category: 'dynamic' },
    { pattern: '1,5,6', meaning: 'Decrescendo', midiVelocity: 0, category: 'dynamic' },
  ];

  dynamics.forEach(d => {
    rules.push({
      category: d.category,
      braille_pattern: d.pattern,
      meaning: d.meaning,
      midi_value: d.midiVelocity,
      duration: null,
      description: `Dynamic: ${d.meaning}`
    });
  });

  const ornaments = [
    { pattern: '3,5', meaning: 'Trill', category: 'ornament' },
    { pattern: '3,4,5', meaning: 'Mordent', category: 'ornament' },
    { pattern: '2,5,6', meaning: 'Turn', category: 'ornament' },
    { pattern: '2,3,5,6', meaning: 'Appoggiatura', category: 'ornament' },
    { pattern: '3,6', meaning: 'Staccato', category: 'ornament' },
    { pattern: '2,6', meaning: 'Accent', category: 'ornament' },
    { pattern: '3,4,6', meaning: 'Fermata', category: 'ornament' },
    { pattern: '2,3,4,5,6', meaning: 'Tremolo', category: 'ornament' },
  ];

  ornaments.forEach(o => {
    rules.push({
      category: o.category,
      braille_pattern: o.pattern,
      meaning: o.meaning,
      midi_value: null,
      duration: null,
      description: `Ornament: ${o.meaning}`
    });
  });

  const accidentals = [
    { pattern: '1,4,5', meaning: 'Sharp', midiOffset: 1, category: 'accidental' },
    { pattern: '1,2,3,4,5', meaning: 'Natural', midiOffset: 0, category: 'accidental' },
    { pattern: '1,2,3,4', meaning: 'Flat', midiOffset: -1, category: 'accidental' },
    { pattern: '3,5', meaning: 'Double sharp', midiOffset: 2, category: 'accidental' },
    { pattern: '3,4', meaning: 'Double flat', midiOffset: -2, category: 'accidental' },
  ];

  accidentals.forEach(a => {
    rules.push({
      category: a.category,
      braille_pattern: a.pattern,
      meaning: a.meaning,
      midi_value: a.midiOffset,
      duration: null,
      description: `Accidental: ${a.meaning}`
    });
  });

  const timeSignatures = [
    { pattern: '3,4', meaning: '3/4 time', beatsPerMeasure: 3, beatUnit: 4, category: 'time_signature' },
    { pattern: '2,4', meaning: '2/4 time', beatsPerMeasure: 2, beatUnit: 4, category: 'time_signature' },
    { pattern: '4,4', meaning: '4/4 time', beatsPerMeasure: 4, beatUnit: 4, category: 'time_signature' },
    { pattern: '6,8', meaning: '6/8 time', beatsPerMeasure: 6, beatUnit: 8, category: 'time_signature' },
    { pattern: '3,8', meaning: '3/8 time', beatsPerMeasure: 3, beatUnit: 8, category: 'time_signature' },
  ];

  timeSignatures.forEach(t => {
    rules.push({
      category: t.category,
      braille_pattern: t.pattern,
      meaning: t.meaning,
      midi_value: null,
      duration: null,
      description: `Time signature: ${t.meaning}`
    });
  });

  const restPatterns = [
    { pattern: '1,2,5,6', meaning: 'Whole rest', duration: 4.0, category: 'rest' },
    { pattern: '1,2,5', meaning: 'Half rest', duration: 2.0, category: 'rest' },
    { pattern: '1,2,6', meaning: 'Quarter rest', duration: 1.0, category: 'rest' },
    { pattern: '1,6', meaning: 'Eighth rest', duration: 0.5, category: 'rest' },
    { pattern: '1,3', meaning: 'Sixteenth rest', duration: 0.25, category: 'rest' },
  ];

  restPatterns.forEach(r => {
    rules.push({
      category: r.category,
      braille_pattern: r.pattern,
      meaning: r.meaning,
      midi_value: null,
      duration: r.duration,
      description: `Rest: ${r.meaning}`
    });
  });

  const barlines = [
    { pattern: '3,5,6', meaning: 'Single barline', category: 'barline' },
    { pattern: '2,3,5,6', meaning: 'Double barline', category: 'barline' },
    { pattern: '2,3,5', meaning: 'Final barline', category: 'barline' },
    { pattern: '1,2,3', meaning: 'Repeat start', category: 'barline' },
    { pattern: '4,5,6', meaning: 'Repeat end', category: 'barline' },
  ];

  barlines.forEach(b => {
    rules.push({
      category: b.category,
      braille_pattern: b.pattern,
      meaning: b.meaning,
      midi_value: null,
      duration: null,
      description: b.meaning
    });
  });

  return rules;
}

module.exports = { loadDefaultRules };
