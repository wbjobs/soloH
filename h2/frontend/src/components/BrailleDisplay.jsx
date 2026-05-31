import React from 'react';

function BrailleCell({ pattern, highlight = false }) {
  const dots = pattern ? pattern.split(',').map(d => parseInt(d.trim())) : [];

  return (
    <div className="braille-cell" style={highlight ? { borderColor: '#667eea', background: '#ebf8ff' } : {}}>
      <div className="dot-row">
        <div className={`dot ${dots.includes(1) ? 'active' : ''}`} />
        <div className={`dot ${dots.includes(4) ? 'active' : ''}`} />
      </div>
      <div className="dot-row">
        <div className={`dot ${dots.includes(2) ? 'active' : ''}`} />
        <div className={`dot ${dots.includes(5) ? 'active' : ''}`} />
      </div>
      <div className="dot-row">
        <div className={`dot ${dots.includes(3) ? 'active' : ''}`} />
        <div className={`dot ${dots.includes(6) ? 'active' : ''}`} />
      </div>
    </div>
  );
}

function BrailleDisplay({ tokens, events }) {
  const getEventForToken = (index) => {
    return events && events[index] ? events[index] : null;
  };

  return (
    <div className="braille-display">
      {tokens && tokens.length > 0 ? (
        tokens.map((token, idx) => {
          const event = getEventForToken(idx);
          const isNote = event?.type === 'note';
          return (
            <div key={idx} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <BrailleCell pattern={token.normalized} highlight={isNote} />
              {event?.type === 'note' && (
                <span style={{ fontSize: '0.7rem', color: '#667eea', fontWeight: 600, marginTop: 2 }}>
                  {event.pitch}
                </span>
              )}
              {event?.type === 'dynamic' && (
                <span style={{ fontSize: '0.7rem', color: '#38a169', fontWeight: 600, marginTop: 2 }}>
                  {event.dynamic}
                </span>
              )}
            </div>
          );
        })
      ) : (
        <div style={{ width: '100%', textAlign: 'center', color: '#718096', padding: 20 }}>
          上传文件后将显示盲文点阵预览
        </div>
      )}
    </div>
  );
}

export default BrailleDisplay;
export { BrailleCell };
