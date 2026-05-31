import React, { useState, useRef, useEffect } from 'react';
import * as Tone from 'tone';
import { Midi } from '@tonejs/midi';

function MidiPlayer({ midiUrl, parsedData }) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [duration, setDuration] = useState(0);
  const synthRef = useRef(null);
  const partRef = useRef(null);
  const startTimeRef = useRef(0);

  useEffect(() => {
    return () => {
      if (partRef.current) {
        partRef.current.stop();
        partRef.current.dispose();
      }
      if (synthRef.current) {
        synthRef.current.dispose();
      }
    };
  }, []);

  const loadAndPlay = async () => {
    if (!parsedData || !parsedData.events) return;

    if (isPlaying) {
      if (partRef.current) {
        partRef.current.stop();
      }
      setIsPlaying(false);
      setProgress(0);
      return;
    }

    setIsLoading(true);
    setProgress(0);

    await Tone.start();

    if (synthRef.current) {
      synthRef.current.dispose();
    }

    synthRef.current = new Tone.PolySynth(Tone.Synth, {
      envelope: {
        attack: 0.02,
        decay: 0.1,
        sustain: 0.3,
        release: 1,
      },
    }).toDestination();

    const notes = parsedData.events.filter(e => e.type === 'note');
    const tempo = parsedData.meta?.tempo || 120;
    Tone.Transport.bpm.value = tempo;

    let currentTime = 0;
    const totalDuration = notes.reduce((acc, n) => acc + n.duration * (60 / tempo), 0);
    setDuration(totalDuration);

    const noteEvents = notes.map(note => {
      const noteDuration = note.duration * (60 / tempo);
      const event = {
        time: currentTime,
        note: Tone.Midi(note.midiNote).toNote(),
        duration: noteDuration,
        velocity: (note.velocity || 80) / 127,
      };
      currentTime += noteDuration;
      return event;
    });

    if (partRef.current) {
      partRef.current.stop();
      partRef.current.dispose();
    }

    partRef.current = new Tone.Part((time, value) => {
      synthRef.current.triggerAttackRelease(value.note, value.duration, time, value.velocity);
    }, noteEvents).start(0);

    partRef.current.callback = (time, value) => {
      synthRef.current.triggerAttackRelease(value.note, value.duration, time, value.velocity);
    };

    Tone.Transport.start();
    startTimeRef.current = Tone.now();
    setIsPlaying(true);
    setIsLoading(false);

    const updateProgress = () => {
      if (isPlaying && startTimeRef.current) {
        const elapsed = Tone.now() - startTimeRef.current;
        setProgress(Math.min(100, (elapsed / totalDuration) * 100));
        if (elapsed < totalDuration) {
          requestAnimationFrame(updateProgress);
        } else {
          setIsPlaying(false);
          setProgress(100);
        }
      }
    };
    requestAnimationFrame(updateProgress);

    partRef.current.onstop = () => {
      setIsPlaying(false);
    };
  };

  const stop = () => {
    if (partRef.current) {
      partRef.current.stop();
    }
    Tone.Transport.stop();
    setIsPlaying(false);
    setProgress(0);
  };

  const downloadMidi = () => {
    if (midiUrl) {
      window.open(midiUrl, '_blank');
    }
  };

  return (
    <div>
      <div className="controls">
        <button
          className="control-btn primary"
          onClick={loadAndPlay}
          disabled={isLoading || !parsedData}
        >
          {isLoading ? (
            <><div className="spinner" style={{ width: 16, height: 16 }} /> 加载中...</>
          ) : isPlaying ? (
            <>⏹ 停止播放</>
          ) : (
            <>▶ 播放MIDI</>
          )}
        </button>
        <button
          className="control-btn secondary"
          onClick={stop}
          disabled={!isPlaying}
        >
          ⏹ 停止
        </button>
        <button
          className="control-btn secondary"
          onClick={downloadMidi}
          disabled={!midiUrl}
        >
          ⬇ 下载MIDI
        </button>
      </div>
      {(progress > 0 || isPlaying) && (
        <div style={{ marginTop: 15 }}>
          <div style={{
            width: '100%',
            height: 8,
            background: '#e2e8f0',
            borderRadius: 4,
            overflow: 'hidden',
          }}>
            <div style={{
              width: `${progress}%`,
              height: '100%',
              background: 'linear-gradient(90deg, #667eea 0%, #764ba2 100%)',
              transition: 'width 0.1s linear',
            }} />
          </div>
          <div style={{ marginTop: 8, fontSize: '0.9rem', color: '#718096' }}>
            {progress.toFixed(0)}% 播放完成
          </div>
        </div>
      )}
    </div>
  );
}

export default MidiPlayer;
