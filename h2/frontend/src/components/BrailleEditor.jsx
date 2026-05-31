import React, { useState, useCallback } from 'react';

const DOT_POSITIONS = [
  { dot: 1, row: 0, col: 0 },
  { dot: 2, row: 1, col: 0 },
  { dot: 3, row: 2, col: 0 },
  { dot: 4, row: 0, col: 1 },
  { dot: 5, row: 1, col: 1 },
  { dot: 6, row: 2, col: 1 },
];

function InteractiveBrailleCell({ pattern, onChange, highlight = false, index }) {
  const [isDragging, setIsDragging] = useState(false);
  const [dragMode, setDragMode] = useState(null);

  const dots = pattern ? pattern.split(',').map(d => parseInt(d.trim())) : [];

  const hasDot = (dotNum) => dots.includes(dotNum);

  const toggleDot = (dotNum) => {
    let newDots;
    if (hasDot(dotNum)) {
      newDots = dots.filter(d => d !== dotNum);
    } else {
      newDots = [...dots, dotNum].sort((a, b) => a - b);
    }
    onChange?.(index, newDots.join(','));
  };

  const setDot = (dotNum, active) => {
    if (active && !hasDot(dotNum)) {
      const newDots = [...dots, dotNum].sort((a, b) => a - b);
      onChange?.(index, newDots.join(','));
    } else if (!active && hasDot(dotNum)) {
      const newDots = dots.filter(d => d !== dotNum);
      onChange?.(index, newDots.join(','));
    }
  };

  const handleMouseDown = (dotNum, e) => {
    e.preventDefault();
    const willActivate = !hasDot(dotNum);
    setIsDragging(true);
    setDragMode(willActivate ? 'activate' : 'deactivate');
    setDot(dotNum, willActivate);
  };

  const handleMouseEnter = (dotNum) => {
    if (isDragging && dragMode) {
      setDot(dotNum, dragMode === 'activate');
    }
  };

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
    setDragMode(null);
  }, []);

  React.useEffect(() => {
    if (isDragging) {
      document.addEventListener('mouseup', handleMouseUp);
      return () => document.removeEventListener('mouseup', handleMouseUp);
    }
  }, [isDragging, handleMouseUp]);

  return (
    <div
      className="braille-cell interactive"
      style={{
        ...(highlight ? { borderColor: '#667eea', background: '#ebf8ff', cursor: 'pointer' } : { cursor: 'pointer' }),
        userSelect: 'none',
      }}
      onMouseLeave={() => { if (isDragging) { setIsDragging(false); setDragMode(null); } }}
    >
      {[0, 1, 2].map(row => (
        <div key={row} className="dot-row">
          {[0, 1].map(col => {
            const dotInfo = DOT_POSITIONS.find(d => d.row === row && d.col === col);
            const dotNum = dotInfo?.dot || 0;
            const isActive = hasDot(dotNum);
            return (
              <div
                key={col}
                className={`dot ${isActive ? 'active' : ''}`}
                style={{
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
                onMouseDown={(e) => handleMouseDown(dotNum, e)}
                onMouseEnter={() => handleMouseEnter(dotNum)}
              />
            );
          })}
        </div>
      ))}
    </div>
  );
}

function BrailleEditor({ tokens, events, onCellChange, onApplyChanges, onReset }) {
  const [localTokens, setLocalTokens] = useState(tokens || []);
  const [isEditing, setIsEditing] = useState(false);

  React.useEffect(() => {
    setLocalTokens(tokens || []);
  }, [tokens]);

  const handleCellChange = (index, newPattern) => {
    const newTokens = [...localTokens];
    if (newTokens[index]) {
      newTokens[index] = {
        ...newTokens[index],
        pattern: newPattern,
        normalized: newPattern,
      };
      setLocalTokens(newTokens);
      setIsEditing(true);
    }
  };

  const getEventForToken = (idx) => {
    return events && events[idx] ? events[idx] : null;
  };

  const exportToText = () => {
    return localTokens.map(t => t.normalized).join('\n');
  };

  return (
    <div className="braille-editor">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 15 }}>
        <h3 style={{ margin: 0, fontSize: '1.1rem', color: '#4a5568' }}>
          ✏️ 盲文点阵编辑器
          {isEditing && <span style={{ color: '#ed8936', marginLeft: 10, fontSize: '0.9rem' }}>(已修改)</span>}
        </h3>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            className="control-btn secondary"
            onClick={onReset}
            disabled={!isEditing}
            style={{ padding: '6px 12px', fontSize: '0.85rem' }}
          >
            🔄 重置
          </button>
          <button
            className="control-btn primary"
            onClick={() => onApplyChanges?.(localTokens)}
            disabled={!isEditing}
            style={{ padding: '6px 12px', fontSize: '0.85rem' }}
          >
            ✓ 应用修改
          </button>
        </div>
      </div>

      <div style={{ marginBottom: 10, fontSize: '0.85rem', color: '#718096' }}>
        💡 提示：点击或拖拽圆点来编辑盲文点位。修改后点击"应用修改"重新解析。
      </div>

      <div className="braille-display">
        {localTokens.length > 0 ? (
          localTokens.map((token, idx) => {
            const event = getEventForToken(idx);
            const isNote = event?.type === 'note';
            return (
              <div
                key={idx}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  padding: '4px',
                  borderRadius: 4,
                  border: isEditing ? '2px dashed #cbd5e0' : 'none',
                }}
              >
                <InteractiveBrailleCell
                  pattern={token.normalized}
                  onChange={handleCellChange}
                  highlight={isNote}
                  index={idx}
                />
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
                {event?.type === 'unknown' && (
                  <span style={{ fontSize: '0.7rem', color: '#e53e3e', fontWeight: 600, marginTop: 2 }}>
                    ?
                  </span>
                )}
              </div>
            );
          })
        ) : (
          <div style={{ width: '100%', textAlign: 'center', color: '#718096', padding: 20 }}>
            上传文件后可在此编辑盲文点阵
          </div>
        )}
      </div>
    </div>
  );
}

export default BrailleEditor;
export { InteractiveBrailleCell };
