import React, { useEffect, useRef } from 'react';
import Vex from 'vexflow';

const { Factory, StaveNote, Barline } = Vex.Flow;

function durationToVex(duration) {
  if (duration >= 4) return 'w';
  if (duration >= 2) return 'h';
  if (duration >= 1) return 'q';
  if (duration >= 0.5) return '8';
  if (duration >= 0.25) return '16';
  return '32';
}

function midiToNoteName(midiNote) {
  const notes = ['c', 'c#', 'd', 'd#', 'e', 'f', 'f#', 'g', 'g#', 'a', 'a#', 'b'];
  const octave = Math.floor(midiNote / 12) - 1;
  const noteIndex = midiNote % 12;
  return notes[noteIndex] + '/' + octave;
}

function getDominantClef(notes) {
  let trebleCount = 0;
  let bassCount = 0;
  notes.forEach(note => {
    if (note.midiNote >= 60) trebleCount++;
    else bassCount++;
  });
  return trebleCount >= bassCount ? 'treble' : 'bass';
}

function StaffNotation({ parsedData }) {
  const containerRef = useRef(null);

  useEffect(() => {
    if (!parsedData || !parsedData.events) {
      return;
    }

    if (containerRef.current) {
      containerRef.current.innerHTML = '';
    }

    const notes = parsedData.events.filter(e => e.type === 'note');
    if (notes.length === 0) return;

    const beatsPerMeasure = parsedData.meta.timeSignature?.beats || 4;

    const measures = [];
    let currentMeasureNotes = [];
    let currentMeasureIndex = notes[0]?.measure || 0;

    notes.forEach((note) => {
      if (note.measure !== currentMeasureIndex) {
        if (currentMeasureNotes.length > 0) {
          measures.push([...currentMeasureNotes]);
        }
        currentMeasureNotes = [];
        currentMeasureIndex = note.measure;
      }
      currentMeasureNotes.push(note);
    });
    if (currentMeasureNotes.length > 0) {
      measures.push(currentMeasureNotes);
    }

    if (measures.length === 0) {
      measures.push(notes);
    }

    const systemWidth = 900;
    const measuresPerSystem = 4;
    const padding = 60;
    const totalSystems = Math.ceil(measures.length / measuresPerSystem);
    const totalHeight = 150 + totalSystems * 160;

    const vf = new Factory({
      renderer: {
        elementId: containerRef.current,
        width: systemWidth + padding * 2,
        height: totalHeight + 40,
      },
    });

    const score = vf.EasyScore();

    for (let systemIdx = 0; systemIdx < totalSystems; systemIdx++) {
      const startMeasure = systemIdx * measuresPerSystem;
      const endMeasure = Math.min(startMeasure + measuresPerSystem, measures.length);
      const systemMeasures = measures.slice(startMeasure, endMeasure);

      if (systemMeasures.length === 0) continue;

      const allNotesInSystem = systemMeasures.flat();
      const dominantClef = getDominantClef(allNotesInSystem);

      const system = vf.System({
        x: padding,
        y: 80 + systemIdx * 160,
        width: systemWidth,
        spaceBetweenStaves: 12,
      });

      let currentX = 0;
      const measureWidth = systemWidth / measuresPerSystem;

      systemMeasures.forEach((measureNotes, measureIdx) => {
        const isFirstInSystem = measureIdx === 0;
        const isLastMeasure = (startMeasure + measureIdx) === measures.length - 1;

        const staveNotes = measureNotes.map(note => {
          const noteName = midiToNoteName(note.midiNote);
          const dur = durationToVex(note.duration);
          return score.note(noteName + '[' + dur + ']');
        });

        const stave = system.addStave({
          x: currentX,
          voices: [score.voice(staveNotes)],
          noJustification: !isFirstInSystem,
        });

        if (isFirstInSystem) {
          stave.addClef(dominantClef);
          stave.addTimeSignature(beatsPerMeasure + '/4');
        }

        if (isLastMeasure) {
          stave.setEndBarType(Barline.type.END);
        } else {
          stave.setEndBarType(Barline.type.SINGLE);
        }

        currentX += measureWidth;
      });
    }

    vf.draw();
  }, [parsedData]);

  return (
    <div className="staff-container">
      <div ref={containerRef} id="staff-output" className="staff-svg" />
    </div>
  );
}

export default StaffNotation;
