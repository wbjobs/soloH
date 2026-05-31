const midiFile = require('midi-file');
const { separateVoices } = require('./voiceSeparator');

function generateMidi(parsedData, options = {}) {
  const { tempo = 120, timeSignature = { beats: 4, unit: 4 }, multiVoice = false } = options;
  const events = parsedData.events;
  const ticksPerBeat = 480;

  const voices = multiVoice ? separateVoices(parsedData) : [{
    name: 'Voice 1',
    events: events,
    midiChannel: 0,
    midiProgram: 0,
  }];

  const numTracks = 1 + voices.length;

  const header = {
    format: 1,
    numTracks: numTracks,
    ticksPerBeat,
  };

  const tempoTrack = [];
  tempoTrack.push({
    type: 'setTempo',
    microsecondsPerBeat: Math.floor(60000000 / tempo),
    deltaTime: 0,
  });
  tempoTrack.push({
    type: 'timeSignature',
    deltaTime: 0,
    numerator: timeSignature.beats,
    denominator: Math.log2(timeSignature.unit),
    metronome: 24,
    thirtyseconds: 8,
  });
  tempoTrack.push({
    type: 'keySignature',
    deltaTime: 0,
    key: 'C',
    scale: 'major',
  });
  tempoTrack.push({
    type: 'endOfTrack',
    deltaTime: 0,
  });

  const tracks = [tempoTrack];

  voices.forEach((voice, voiceIdx) => {
    const channel = voice.midiChannel || voiceIdx;
    const program = voice.midiProgram || 0;
    const noteTrack = generateNoteTrack(voice.events, channel, program, ticksPerBeat);
    tracks.push(noteTrack);
  });

  const midiData = {
    header,
    tracks,
  };

  return midiFile.writeMidi(midiData);
}

function generateNoteTrack(events, channel, program, ticksPerBeat) {
  const track = [];

  track.push({
    type: 'programChange',
    deltaTime: 0,
    channel: channel,
    programNumber: program,
  });

  let currentTime = 0;

  for (let i = 0; i < events.length; i++) {
    const event = events[i];

    if (event.type === 'note') {
      const durationInTicks = Math.round(event.duration * ticksPerBeat);
      const midiNote = clampMidi(event.midiNote);

      track.push({
        type: 'noteOn',
        deltaTime: 0,
        channel: channel,
        noteNumber: midiNote,
        velocity: event.velocity || 80,
      });

      const ornamentEffects = applyOrnaments(event.ornaments, midiNote, event.velocity, durationInTicks, channel);
      track.push(...ornamentEffects);

      track.push({
        type: 'noteOff',
        deltaTime: durationInTicks,
        channel: channel,
        noteNumber: midiNote,
        velocity: 0,
      });

      currentTime = 0;
    } else if (event.type === 'rest') {
      const restTicks = Math.round(event.duration * ticksPerBeat);
      if (track.length > 0 && track[track.length - 1].type !== 'noteOn') {
        track[track.length - 1].deltaTime += restTicks;
      } else {
        track.push({
          type: 'noteOff',
          deltaTime: restTicks,
          channel: channel,
          noteNumber: 0,
          velocity: 0,
        });
      }
      currentTime = 0;
    }
  }

  track.push({
    type: 'endOfTrack',
    deltaTime: 0,
  });

  return track;
}

function applyOrnaments(ornaments, baseNote, velocity, baseDuration, channel = 0) {
  const effects = [];

  for (const ornament of ornaments) {
    switch (ornament) {
      case 'Trill':
        const trillNote = Math.min(127, baseNote + 2);
        const trillSegment = Math.round(baseDuration / 8);
        for (let i = 0; i < 4; i++) {
          effects.push({
            type: 'noteOn',
            deltaTime: 0,
            channel: channel,
            noteNumber: trillNote,
            velocity: velocity,
          });
          effects.push({
            type: 'noteOff',
            deltaTime: trillSegment,
            channel: channel,
            noteNumber: trillNote,
            velocity: 0,
          });
        }
        break;

      case 'Mordent':
        const mordentNote = Math.min(127, baseNote + 1);
        const mordentSeg = Math.round(baseDuration / 4);
        effects.push({
          type: 'noteOn',
          deltaTime: 0,
          channel: channel,
          noteNumber: mordentNote,
          velocity: velocity,
        });
        effects.push({
          type: 'noteOff',
          deltaTime: mordentSeg,
          channel: channel,
          noteNumber: mordentNote,
          velocity: 0,
        });
        break;

      case 'Turn':
        const upperNote = Math.min(127, baseNote + 2);
        const lowerNote = Math.max(0, baseNote - 2);
        const turnSeg = Math.round(baseDuration / 6);
        [upperNote, baseNote, lowerNote].forEach(n => {
          effects.push({
            type: 'noteOn',
            deltaTime: 0,
            channel: channel,
            noteNumber: n,
            velocity: velocity,
          });
          effects.push({
            type: 'noteOff',
            deltaTime: turnSeg,
            channel: channel,
            noteNumber: n,
            velocity: 0,
          });
        });
        break;

      case 'Staccato':
        effects.push({
          type: 'noteOff',
          deltaTime: Math.round(baseDuration / 2),
          channel: channel,
          noteNumber: baseNote,
          velocity: 0,
        });
        break;

      case 'Accent':
        effects.push({
          type: 'noteOn',
          deltaTime: 0,
          channel: channel,
          noteNumber: baseNote,
          velocity: Math.min(127, velocity + 20),
        });
        break;
    }
  }

  return effects;
}

function clampMidi(note) {
  return Math.max(0, Math.min(127, note));
}

module.exports = { generateMidi };
